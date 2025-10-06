#!/usr/bin/env python3
"""
Enhanced Message Handler for Telegram Listener
Additional utilities for processing and analyzing Telegram messages.
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class MessageData:
    """Data class for structured message storage."""
    timestamp: str
    message_id: int
    chat_id: int
    chat_title: str
    chat_type: str
    user_id: int
    username: Optional[str]
    first_name: str
    last_name: Optional[str]
    text: str
    message_type: str
    has_media: bool = False
    media_type: Optional[str] = None
    is_forwarded: bool = False
    reply_to_message: Optional[int] = None

class MessageProcessor:
    """Enhanced message processing with filtering and analysis."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.keywords = self.config.get('HIGHLIGHT_KEYWORDS', '').split(',')
        self.keywords = [k.strip().lower() for k in self.keywords if k.strip()]
        
    def extract_message_data(self, update) -> MessageData:
        """Extract structured data from Telegram update."""
        message = update.message
        chat = message.chat
        user = message.from_user
        
        # Determine message type and content
        text = message.text or ''
        message_type = 'text'
        has_media = False
        media_type = None
        
        if message.photo:
            message_type = 'photo'
            text = message.caption or '[Photo]'
            has_media = True
            media_type = 'photo'
        elif message.document:
            message_type = 'document'
            text = f"[Document: {message.document.file_name}]"
            has_media = True
            media_type = 'document'
        elif message.audio:
            message_type = 'audio'
            text = '[Audio]'
            has_media = True
            media_type = 'audio'
        elif message.video:
            message_type = 'video'
            text = '[Video]'
            has_media = True
            media_type = 'video'
        elif message.voice:
            message_type = 'voice'
            text = '[Voice Message]'
            has_media = True
            media_type = 'voice'
        elif message.location:
            message_type = 'location'
            text = f"[Location: {message.location.latitude}, {message.location.longitude}]"
        elif message.sticker:
            message_type = 'sticker'
            text = f"[Sticker: {message.sticker.emoji}]"
            has_media = True
            media_type = 'sticker'
        
        return MessageData(
            timestamp=datetime.now().isoformat(),
            message_id=message.message_id,
            chat_id=chat.id,
            chat_title=chat.title if chat.title else f"{user.first_name} {user.last_name or ''}".strip(),
            chat_type=chat.type,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name or '',
            last_name=user.last_name,
            text=text,
            message_type=message_type,
            has_media=has_media,
            media_type=media_type,
            is_forwarded=bool(message.forward_date),
            reply_to_message=message.reply_to_message.message_id if message.reply_to_message else None
        )
    
    def is_highlighted_message(self, text: str) -> bool:
        """Check if message contains highlighted keywords."""
        if not self.keywords:
            return False
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.keywords)
    
    def extract_mentions(self, text: str) -> List[str]:
        """Extract @mentions from message text."""
        return re.findall(r'@(\w+)', text)
    
    def extract_hashtags(self, text: str) -> List[str]:
        """Extract #hashtags from message text."""
        return re.findall(r'#(\w+)', text)
    
    def extract_urls(self, text: str) -> List[str]:
        """Extract URLs from message text."""
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(url_pattern, text)
    
    def analyze_message(self, message_data: MessageData) -> Dict:
        """Perform comprehensive message analysis."""
        analysis = {
            'is_highlighted': self.is_highlighted_message(message_data.text),
            'mentions': self.extract_mentions(message_data.text),
            'hashtags': self.extract_hashtags(message_data.text),
            'urls': self.extract_urls(message_data.text),
            'word_count': len(message_data.text.split()) if message_data.text else 0,
            'char_count': len(message_data.text) if message_data.text else 0,
            'has_special_content': bool(
                self.extract_mentions(message_data.text) or 
                self.extract_hashtags(message_data.text) or 
                self.extract_urls(message_data.text)
            )
        }
        return analysis

class MessageStorage:
    """Handle message storage and retrieval."""
    
    def __init__(self, filename: str = 'messages_data.jsonl'):
        self.filename = filename
    
    def save_message(self, message_data: MessageData, analysis: Dict = None) -> None:
        """Save message data to file."""
        try:
            data = asdict(message_data)
            if analysis:
                data['analysis'] = analysis
            
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Error saving message: {e}")
    
    def load_messages(self, limit: Optional[int] = None) -> List[Dict]:
        """Load messages from file."""
        messages = []
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f):
                    if limit and line_num >= limit:
                        break
                    try:
                        messages.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return messages
    
    def get_messages_by_chat(self, chat_id: int) -> List[Dict]:
        """Get all messages from a specific chat."""
        all_messages = self.load_messages()
        return [msg for msg in all_messages if msg.get('chat_id') == chat_id]
    
    def get_messages_by_user(self, user_id: int) -> List[Dict]:
        """Get all messages from a specific user."""
        all_messages = self.load_messages()
        return [msg for msg in all_messages if msg.get('user_id') == user_id]

def create_message_report(storage: MessageStorage) -> str:
    """Create a summary report of collected messages."""
    messages = storage.load_messages()
    if not messages:
        return "No messages found."
    
    # Basic statistics
    total_messages = len(messages)
    unique_chats = len(set(msg.get('chat_id') for msg in messages))
    unique_users = len(set(msg.get('user_id') for msg in messages))
    
    # Message types
    message_types = {}
    for msg in messages:
        msg_type = msg.get('message_type', 'unknown')
        message_types[msg_type] = message_types.get(msg_type, 0) + 1
    
    # Most active chats
    chat_counts = {}
    for msg in messages:
        chat_title = msg.get('chat_title', 'Unknown')
        chat_counts[chat_title] = chat_counts.get(chat_title, 0) + 1
    
    top_chats = sorted(chat_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    report = f"""
MESSAGE SUMMARY REPORT
=====================
Total Messages: {total_messages}
Unique Chats: {unique_chats}
Unique Users: {unique_users}

Message Types:
{chr(10).join(f"  {type_name}: {count}" for type_name, count in message_types.items())}

Most Active Chats:
{chr(10).join(f"  {chat}: {count} messages" for chat, count in top_chats)}
"""
    
    return report

if __name__ == '__main__':
    # Example usage
    storage = MessageStorage()
    print(create_message_report(storage))