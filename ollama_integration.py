#!/usr/bin/env python3
"""Ollama Integration for Telegram Bot - Text Extraction"""

import os
import asyncio
import logging
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
import ollama
import requests
import tempfile
import glob

logger = logging.getLogger(__name__)

# Evaluation prompt for grading student answers with guide context
EVALUATION_PROMPT = """
You are an examiner for 12th grade answer sheets. 
The student has written an answer for a 5-mark question. 
Your task is to carefully evaluate the answer text and return ONLY the marks (0 to 5) with brief reasoning.

Rules:
- Be fair and follow a 12th grade standard marking scheme.
- Check grammar, content accuracy, relevance, and completeness.
- Use the provided reference guide to verify correctness of concepts and facts.
- Award marks based on how well the answer aligns with the reference material.
- Do not rewrite or improve the answer.
- Keep the evaluation short and clear.

Reference Guide Content:
{guide_content}

Format your output strictly as JSON:
{{
  "score": <marks out of 5>,
  "reason": "<one short reason why you gave this score>"
}}

Student's answer:
\"\"\"{answer_text}\"\"\"
"""

class OllamaImageProcessor:
    def __init__(self, model_name: str = "minicpm-v:latest", host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.fallback_models = ["llava:latest", "minicpm-v:latest", "llava", "minicpm-v"]
        self.host = host
        self.client = ollama.Client(host=host)
        self.temp_files = []
        self.guide_content = []
        self.guide_loaded = False
        self.temp_dir = Path(tempfile.gettempdir()) / "telegram_images"
        self.temp_dir.mkdir(exist_ok=True)
        
    async def check_ollama_connection(self) -> bool:
        try:
            models = await asyncio.to_thread(self.client.list)
            available_models = []
            if 'models' in models:
                for model in models['models']:
                    if isinstance(model, dict) and 'name' in model:
                        available_models.append(model['name'])
            
            vision_models = [m for m in available_models if any(keyword in m.lower() 
                           for keyword in ['llava', 'vision', 'minicpm', 'visual'])]
            
            if not vision_models:
                for test_model in [self.model_name] + self.fallback_models:
                    try:
                        await asyncio.to_thread(
                            self.client.generate,
                            model=test_model,
                            prompt="test",
                            options={"num_predict": 1}
                        )
                        self.model_name = test_model
                        logger.info(f"✅ Using model: {test_model}")
                        return True
                    except Exception:
                        continue
                return False
            else:
                minicpm_models = [m for m in vision_models if 'minicpm' in m.lower()]
                if minicpm_models:
                    self.model_name = minicpm_models[0]
                else:
                    self.model_name = vision_models[0]
                logger.info(f"✅ Using model: {self.model_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def load_guide_content(self) -> bool:
        """Load and extract text from guide images."""
        if self.guide_loaded:
            return True
            
        try:
            guide_folder = Path("guide_RAG")
            if not guide_folder.exists():
                logger.warning("Guide folder not found, evaluation will proceed without reference material")
                return False
            
            guide_files = list(guide_folder.glob("*.jpeg")) + list(guide_folder.glob("*.jpg")) + list(guide_folder.glob("*.png"))
            
            if not guide_files:
                logger.warning("No guide images found in guide folder")
                return False
            
            logger.info(f"Loading {len(guide_files)} guide files...")
            
            for guide_file in sorted(guide_files):
                try:
                    logger.info(f"Processing guide file: {guide_file}")
                    guide_text = await self.extract_text_from_image(str(guide_file))
                    
                    if guide_text and guide_text.strip():
                        self.guide_content.append({
                            'file': guide_file.name,
                            'content': guide_text.strip()
                        })
                        logger.info(f"Loaded guide content from {guide_file.name}: {len(guide_text)} characters")
                    else:
                        logger.warning(f"No text extracted from {guide_file.name}")
                        
                except Exception as e:
                    logger.error(f"Error processing guide file {guide_file}: {e}")
                    continue
            
            if self.guide_content:
                logger.info(f"Successfully loaded {len(self.guide_content)} guide documents")
                self.guide_loaded = True
                return True
            else:
                logger.warning("No guide content could be extracted")
                return False
                
        except Exception as e:
            logger.error(f"Error loading guide content: {e}")
            return False
    
    def find_relevant_guide_content(self, answer_text: str, max_sections: int = 2) -> str:
        """Find relevant guide content based on answer text using simple keyword matching."""
        if not self.guide_content:
            return "No reference guide available."
        
        try:
            # Extract key terms from the answer (simple approach)
            answer_words = set(answer_text.lower().split())
            # Remove common stop words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
            answer_keywords = answer_words - stop_words
            
            # Score each guide section based on keyword overlap
            scored_sections = []
            for guide_section in self.guide_content:
                guide_words = set(guide_section['content'].lower().split())
                # Calculate simple overlap score
                overlap = len(answer_keywords.intersection(guide_words))
                if overlap > 0:
                    scored_sections.append((overlap, guide_section))
            
            # Sort by relevance score and take top sections
            scored_sections.sort(key=lambda x: x[0], reverse=True)
            
            if not scored_sections:
                # If no keyword overlap, return first guide section as fallback
                return f"Reference Guide ({self.guide_content[0]['file']}):\n{self.guide_content[0]['content'][:1000]}..."
            
            # Combine top relevant sections
            relevant_content = []
            for i, (score, section) in enumerate(scored_sections[:max_sections]):
                content = section['content'][:800]  # Limit length
                relevant_content.append(f"Guide {section['file']} (relevance: {score}):\n{content}")
            
            return "\n\n".join(relevant_content)
            
        except Exception as e:
            logger.error(f"Error finding relevant guide content: {e}")
            return "Error accessing reference guide."
    
    async def download_telegram_image(self, bot, file_id: str) -> Optional[str]:
        try:
            file = await bot.get_file(file_id)
            file_path = file.file_path
            
            if file_path.startswith('https://'):
                file_url = file_path
            else:
                clean_file_path = file_path.lstrip('/')
                file_url = f"https://api.telegram.org/file/bot{bot.token}/{clean_file_path}"
            
            file_extension = file_path.split('.')[-1] if '.' in file_path else 'jpg'
            local_filename = self.temp_dir / f"{file_id}.{file_extension}"
            
            response = requests.get(file_url, timeout=30)
            
            if response.status_code == 404:
                try:
                    file_bytes = await file.download_as_bytearray()
                    with open(local_filename, 'wb') as f:
                        f.write(file_bytes)
                    return str(local_filename)
                except Exception:
                    return None
            
            response.raise_for_status()
            with open(local_filename, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded: {local_filename}")
            return str(local_filename)
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None
    
    async def load_guide_content(self) -> bool:
        """Load and extract text from guide images for RAG."""
        if self.guide_loaded:
            return True
            
        try:
            guide_folder = Path("guide")
            if not guide_folder.exists():
                logger.warning("Guide folder not found, evaluation will proceed without reference material")
                return False
            
            guide_files = list(guide_folder.glob("*.jpeg")) + list(guide_folder.glob("*.jpg")) + list(guide_folder.glob("*.png"))
            
            if not guide_files:
                logger.warning("No guide images found in guide folder")
                return False
            
            logger.info(f"Loading {len(guide_files)} guide files...")
            
            for guide_file in sorted(guide_files):
                try:
                    logger.info(f"Processing guide file: {guide_file}")
                    guide_text = await self.extract_text_from_image(str(guide_file))
                    
                    if guide_text and guide_text.strip():
                        self.guide_content.append({
                            'file': guide_file.name,
                            'content': guide_text.strip()
                        })
                        logger.info(f"Loaded guide content from {guide_file.name}: {len(guide_text)} characters")
                    else:
                        logger.warning(f"No text extracted from {guide_file.name}")
                        
                except Exception as e:
                    logger.error(f"Error processing guide file {guide_file}: {e}")
                    continue
            
            if self.guide_content:
                logger.info(f"Successfully loaded {len(self.guide_content)} guide documents")
                self.guide_loaded = True
                return True
            else:
                logger.warning("No guide content could be extracted")
                return False
                
        except Exception as e:
            logger.error(f"Error loading guide content: {e}")
            return False
    
    def find_relevant_guide_content(self, answer_text: str, max_sections: int = 2) -> str:
        """Find relevant guide content based on answer text using keyword matching."""
        if not self.guide_content:
            return "No reference guide available."
        
        try:
            # Extract key terms from the answer (simple approach)
            answer_words = set(answer_text.lower().split())
            # Remove common stop words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 
                         'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 
                         'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
            answer_keywords = answer_words - stop_words
            
            # Score each guide section based on keyword overlap
            scored_sections = []
            for guide_section in self.guide_content:
                guide_words = set(guide_section['content'].lower().split())
                # Calculate simple overlap score
                overlap = len(answer_keywords.intersection(guide_words))
                if overlap > 0:
                    scored_sections.append((overlap, guide_section))
            
            # Sort by relevance score and take top sections
            scored_sections.sort(key=lambda x: x[0], reverse=True)
            
            if not scored_sections:
                # If no keyword overlap, return first guide section as fallback
                return f"Reference Guide ({self.guide_content[0]['file']}):\n{self.guide_content[0]['content'][:1000]}..."
            
            # Combine top relevant sections
            relevant_content = []
            for i, (score, section) in enumerate(scored_sections[:max_sections]):
                content = section['content'][:800]  # Limit length to avoid token limits
                relevant_content.append(f"Guide {section['file']} (relevance: {score}):\n{content}")
            
            return "\n\n".join(relevant_content)
            
        except Exception as e:
            logger.error(f"Error finding relevant guide content: {e}")
            return "Error accessing reference guide."
    
    async def extract_text_from_image(self, image_path: str, custom_prompt: str = None) -> Optional[str]:
        try:
            if not custom_prompt:
                prompt = """Read ALL text in this image. Extract every word, number, and character visible.

READ EVERYTHING:
- All handwritten text (cursive, print, notes)
- All printed text (documents, books, signs)
- All digital text (screens, apps)
- Numbers, dates, addresses, phone numbers
- Equations, formulas, symbols
- Faded text, partial text, crossed-out text
- Text at any angle or size

RULES:
- Don't skip anything
- Keep exact spelling and punctuation
- Don't interpret or correct
- Transcribe exactly what you see

OUTPUT: Only the actual text content."""
            else:
                prompt = custom_prompt
            
            response = await asyncio.to_thread(
                self.client.generate,
                model=self.model_name,
                prompt=prompt,
                images=[image_path],
                options={
                    "temperature": 0.1,
                    "num_predict": 2048,
                }
            )
            
            extracted_text = response['response'].strip()
            logger.info(f"Extracted {len(extracted_text)} characters")
            return extracted_text
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return None
    
    async def process_telegram_image(self, bot, file_id: str, custom_prompt: str = None) -> Optional[str]:
        try:
            image_path = await self.download_telegram_image(bot, file_id)
            if not image_path:
                return None
            
            extracted_text = await self.extract_text_from_image(image_path, custom_prompt)
            
            try:
                os.remove(image_path)
            except Exception:
                pass
            
            return extracted_text
        except Exception as e:
            logger.error(f"Process failed: {e}")
            return None
    
    async def evaluate_answer(self, answer_text: str) -> Optional[Dict[str, Any]]:
        """Evaluate student answer and return score with reasoning using RAG."""
        try:
            if not answer_text or not answer_text.strip():
                return {"score": 0, "reason": "No answer provided"}
            
            # Load guide content if not already loaded
            if not self.guide_loaded:
                await self.load_guide_content()
            
            # Find relevant guide content for this answer
            guide_content = self.find_relevant_guide_content(answer_text)
            
            # Format the evaluation prompt with guide content and student's answer
            evaluation_prompt = EVALUATION_PROMPT.format(
                guide_content=guide_content,
                answer_text=answer_text.strip()
            )
            
            # Use a more general model for evaluation (prefer text-only models)
            evaluation_models = ["llama3.2:3b", "mistral:7b-instruct", "llama2:latest", self.model_name]
            
            for model in evaluation_models:
                try:
                    response = await asyncio.to_thread(
                        self.client.generate,
                        model=model,
                        prompt=evaluation_prompt,
                        options={
                            "temperature": 0.2,  # Low temperature for consistent evaluation
                            "num_predict": 200,   # Short response for JSON
                        }
                    )
                    
                    evaluation_text = response['response'].strip()
                    logger.info(f"Raw evaluation response: {evaluation_text}")
                    
                    # Try to extract JSON from the response
                    try:
                        # Look for JSON in the response
                        if '{' in evaluation_text and '}' in evaluation_text:
                            json_start = evaluation_text.find('{')
                            json_end = evaluation_text.rfind('}') + 1
                            json_text = evaluation_text[json_start:json_end]
                            evaluation_result = json.loads(json_text)
                            
                            # Validate the response format
                            if 'score' in evaluation_result and 'reason' in evaluation_result:
                                # Ensure score is within valid range
                                score = int(evaluation_result['score'])
                                if 0 <= score <= 5:
                                    logger.info(f"✅ Evaluation successful using model: {model}")
                                    return evaluation_result
                        
                    except (json.JSONDecodeError, ValueError, KeyError) as json_error:
                        logger.warning(f"JSON parsing failed for model {model}: {json_error}")
                        continue
                    
                except Exception as model_error:
                    logger.warning(f"Model {model} failed: {model_error}")
                    continue
            
            # Fallback evaluation if all models fail
            logger.warning("All evaluation models failed, using fallback scoring")
            word_count = len(answer_text.split())
            if word_count < 10:
                return {"score": 1, "reason": "Answer too short for a 5-mark question"}
            elif word_count < 30:
                return {"score": 2, "reason": "Brief answer, may lack detail"}
            elif word_count < 60:
                return {"score": 3, "reason": "Adequate length, content evaluation needed"}
            else:
                return {"score": 4, "reason": "Good length, appears comprehensive"}
                
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {"score": 0, "reason": "Unable to evaluate answer due to technical error"}
    
    def cleanup_temp_files(self) -> None:
        try:
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file():
                    os.remove(file_path)
        except Exception:
            pass

ollama_processor = None

def get_ollama_processor() -> OllamaImageProcessor:
    global ollama_processor
    if ollama_processor is None:
        ollama_processor = OllamaImageProcessor()
    return ollama_processor

async def initialize_ollama() -> bool:
    processor = get_ollama_processor()
    is_connected = await processor.check_ollama_connection()
    
    if is_connected:
        # Load guide content for RAG functionality
        logger.info("Loading reference guide content for RAG...")
        await processor.load_guide_content()
    
    return is_connected
