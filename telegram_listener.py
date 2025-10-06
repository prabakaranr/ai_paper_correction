#!/usr/bin/env python3
"""
Telegram Chat Listener
A Python script to listen to Telegram chats and receive messages using the Bot API.
"""

import os
import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from ollama_integration import get_ollama_processor, initialize_ollama

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('telegram_messages.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramListener:
    def __init__(self, bot_token: str):
        """Initialize the Telegram listener with bot token."""
        self.bot_token = bot_token
        self.application = None
        self.ollama_processor = get_ollama_processor()
        self.ollama_enabled = False
    
    def escape_markdown_v2(self, text: str) -> str:
        """Escape special characters for Telegram MarkdownV2."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
        
    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages."""
        if update.message:
            message = update.message
            chat = message.chat
            user = message.from_user
            
            # Extract message information
            message_info = {
                'timestamp': datetime.now().isoformat(),
                'message_id': message.message_id,
                'chat_id': chat.id,
                'chat_title': chat.title if chat.title else f"{user.first_name} {user.last_name or ''}".strip(),
                'chat_type': chat.type,
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'text': message.text,
                'message_type': 'text'
            }
            
            # Handle different message types
            if message.photo:
                message_info['message_type'] = 'photo'
                message_info['text'] = message.caption or '[Photo]'
                # Process image with Ollama if enabled
                if self.ollama_enabled:
                    await self.process_image_with_ollama(message, update, context)
            elif message.document:
                message_info['message_type'] = 'document'
                message_info['text'] = f"[Document: {message.document.file_name}]"
                # Check if document is an image and process with Ollama if enabled
                if (self.ollama_enabled and message.document.mime_type and 
                    message.document.mime_type.startswith('image/')):
                    await self.process_document_image_with_ollama(message, update, context)
            elif message.audio:
                message_info['message_type'] = 'audio'
                message_info['text'] = '[Audio]'
            elif message.video:
                message_info['message_type'] = 'video'
                message_info['text'] = '[Video]'
            elif message.voice:
                message_info['message_type'] = 'voice'
                message_info['text'] = '[Voice Message]'
            elif message.location:
                message_info['message_type'] = 'location'
                message_info['text'] = f"[Location: {message.location.latitude}, {message.location.longitude}]"
            elif message.sticker:
                message_info['message_type'] = 'sticker'
                message_info['text'] = f"[Sticker: {message.sticker.emoji}]"
            
            # Log the message
            self.log_message(message_info)
            
            # Process the message (you can customize this)
            await self.process_message(message_info, update, context)
    
    def log_message(self, message_info: dict) -> None:
        """Log message information."""
        log_text = (
            f"[{message_info['timestamp']}] "
            f"Chat: {message_info['chat_title']} ({message_info['chat_type']}) "
            f"| User: {message_info['first_name']} {message_info['last_name'] or ''} "
            f"(@{message_info['username']}) "
            f"| Type: {message_info['message_type']} "
            f"| Message: {message_info['text']}"
        )
        logger.info(log_text)
        
        # Also save to a structured log file
        self.save_to_file(message_info)
    
    def save_to_file(self, message_info: dict) -> None:
        """Save message to a JSON-like file for further processing."""
        try:
            import json
            with open('messages_data.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps(message_info, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Error saving message to file: {e}")
    
    async def process_image_with_ollama(self, message, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process image with Ollama LLaVA model to extract text."""
        try:
            if not message.photo:
                return
                
            # Get the largest photo size
            largest_photo = max(message.photo, key=lambda x: x.file_size or 0)
            
            # Send "typing" action to show bot is processing
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            logger.info(f"Processing image with Ollama LLaVA model (file_id: {largest_photo.file_id})...")
            
            # Process image with Ollama
            extracted_text = await self.ollama_processor.process_telegram_image(
                context.bot, 
                largest_photo.file_id
            )
            
            if extracted_text and extracted_text.strip():
                # Evaluate the answer if it's substantial enough
                if len(extracted_text.strip()) > 20:  # Only evaluate substantial answers
                    logger.info("Starting answer evaluation...")
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                    
                    evaluation_result = await self.ollama_processor.evaluate_answer(extracted_text)
                    
                    if evaluation_result:
                        score = evaluation_result.get('score', 0)
                        reason = evaluation_result.get('reason', 'No reason provided')
                        
                        # Format evaluation response
                        evaluation_text = f"📝 ANSWER EVALUATION:\n\n🎯 Score: {score}/5\n💭 Feedback: {reason}"
                        
                        await update.message.reply_text(
                            evaluation_text,
                            reply_to_message_id=message.message_id
                        )
                        
                        logger.info(f"Successfully sent evaluation - Score: {score}/5")
                    else:
                        logger.warning("Evaluation failed, no result returned")
                        await update.message.reply_text(
                            "❌ Unable to evaluate this answer. Please try again.",
                            reply_to_message_id=message.message_id
                        )
                else:
                    # Answer too short to evaluate
                    await update.message.reply_text(
                        "📝 Answer too short to evaluate. Please provide a more detailed response.",
                        reply_to_message_id=message.message_id
                    )
                    logger.info("Answer too short for evaluation")
            else:
                await update.message.reply_text(
                    "❌ No readable text found in this image. The image may not contain text, or the text may be too blurry/small to read.",
                    reply_to_message_id=message.message_id
                )
                
        except Exception as e:
            logger.error(f"Error processing image with Ollama: {e}")
            await update.message.reply_text(
                f"❌ Error processing image: {str(e)[:100]}...\nPlease check if Ollama is running.",
                reply_to_message_id=message.message_id
            )

    async def process_document_image_with_ollama(self, message, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process document image with Ollama LLaVA model to extract text."""
        try:
            if not message.document or not message.document.mime_type.startswith('image/'):
                return
                
            # Send "typing" action to show bot is processing
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            
            logger.info(f"Processing document image with Ollama LLaVA model (file: {message.document.file_name}, file_id: {message.document.file_id})...")
            
            # Process document image with Ollama
            extracted_text = await self.ollama_processor.process_telegram_image(
                context.bot, 
                message.document.file_id
            )
            
            if extracted_text and extracted_text.strip():
                # Evaluate the answer if it's substantial enough
                if len(extracted_text.strip()) > 20:  # Only evaluate substantial answers
                    logger.info("Starting answer evaluation for document...")
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
                    
                    evaluation_result = await self.ollama_processor.evaluate_answer(extracted_text)
                    
                    if evaluation_result:
                        score = evaluation_result.get('score', 0)
                        reason = evaluation_result.get('reason', 'No reason provided')
                        
                        # Format evaluation response
                        evaluation_text = f"📝 ANSWER EVALUATION:\n\n🎯 Score: {score}/5\n💭 Feedback: {reason}"
                        
                        await update.message.reply_text(
                            evaluation_text,
                            reply_to_message_id=message.message_id
                        )
                        
                        logger.info(f"Successfully sent evaluation for document - Score: {score}/5")
                    else:
                        logger.warning("Document evaluation failed, no result returned")
                        await update.message.reply_text(
                            "❌ Unable to evaluate this answer. Please try again.",
                            reply_to_message_id=message.message_id
                        )
                else:
                    # Answer too short to evaluate
                    await update.message.reply_text(
                        "📝 Answer too short to evaluate. Please provide a more detailed response.",
                        reply_to_message_id=message.message_id
                    )
                    logger.info("Document answer too short for evaluation")
            else:
                await update.message.reply_text(
                    "❌ No readable text found in this document. The image may not contain text, or the text may be too blurry/small to read.",
                    reply_to_message_id=message.message_id
                )
                
        except Exception as e:
            logger.error(f"Error processing document image with Ollama: {e}")
            await update.message.reply_text(
                f"❌ Error processing document image: {str(e)[:100]}...\nPlease check if Ollama is running.",
                reply_to_message_id=message.message_id
            )

    async def process_message(self, message_info: dict, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process the received message. Customize this method for your needs."""
        # Example: Respond to specific commands or keywords
        text = message_info.get('text', '').lower()
        
        # You can add custom processing logic here
        if text.startswith('/hello'):
            await update.message.reply_text("Hello! I'm listening to this chat.")
        elif text.startswith('/ollama'):
            # Toggle Ollama processing
            if 'on' in text or 'enable' in text:
                self.ollama_enabled = True
                await update.message.reply_text("✅ Ollama image processing enabled! Send images to extract text.")
            elif 'off' in text or 'disable' in text:
                self.ollama_enabled = False
                await update.message.reply_text("❌ Ollama image processing disabled.")
            else:
                status = "enabled" if self.ollama_enabled else "disabled"
                await update.message.reply_text(f"🤖 Ollama image processing is currently {status}.\nUse /ollama on or /ollama off to toggle.")
        elif 'important' in text:
            logger.warning(f"IMPORTANT MESSAGE DETECTED: {message_info['text']}")
        
        # Example: Save messages from specific users or chats
        if message_info['chat_type'] in ['group', 'supergroup']:
            logger.info(f"Group message from {message_info['chat_title']}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        logger.error(f"Update {update} caused error {context.error}")
    
    async def startup(self, application) -> None:
        """Initialize services on startup."""
        # Check Ollama connection
        logger.info("Checking Ollama connection...")
        ollama_available = await initialize_ollama()
        
        if ollama_available:
            self.ollama_enabled = True
            logger.info("✅ Ollama LLaVA model is available! Image processing enabled.")
        else:
            self.ollama_enabled = False
            logger.warning("⚠️  Ollama not available. Image processing disabled.")
            logger.info("To enable image processing:")
            logger.info("1. Install Ollama: https://ollama.ai/")
            logger.info("2. Run: ollama pull llava")
            logger.info("3. Start Ollama service")

    def run(self) -> None:
        """Start the bot and begin listening."""
        if not self.bot_token:
            raise ValueError("Bot token is required. Please set TELEGRAM_BOT_TOKEN in your .env file.")
        
        # Create application
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add startup callback
        self.application.post_init = self.startup
        
        # Add handlers
        self.application.add_handler(MessageHandler(filters.ALL, self.message_handler))
        self.application.add_error_handler(self.error_handler)
        
        # Start the bot
        logger.info("Starting Telegram listener...")
        logger.info("Bot is now listening for messages. Press Ctrl+C to stop.")
        
        try:
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            # Clean up temporary files
            if hasattr(self, 'ollama_processor'):
                self.ollama_processor.cleanup_temp_files()
        except Exception as e:
            logger.error(f"Error running bot: {e}")

def main():
    """Main function to run the Telegram listener."""
    # Get bot token from environment variable
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        print("Please create a .env file with your bot token:")
        print("TELEGRAM_BOT_TOKEN=your_bot_token_here")
        return
    
    # Create and run the listener
    listener = TelegramListener(bot_token)
    listener.run()

if __name__ == '__main__':
    main()