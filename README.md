# AI Paper Correction

A Python application to listen to Telegram chats and receive message content using the Telegram Bot API.

## Features

- 🤖 **Bot-based listening**: Uses Telegram Bot API for reliable message reception
- 📝 **Comprehensive logging**: Logs all messages with timestamps and user information
- 💾 **Data storage**: Saves messages to both log files and structured JSON format
- 🔍 **Message analysis**: Extracts mentions, hashtags, URLs, and other metadata
- 🎯 **Keyword highlighting**: Highlights messages containing specified keywords
- 📊 **Message reporting**: Generate summary reports of collected messages
- 🔒 **Secure configuration**: Uses environment variables for sensitive data

## Prerequisites

- Python 3.8 or higher
- A Telegram account
- A Telegram Bot Token (obtained from @BotFather)

## Setup Instructions

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Start a conversation with BotFather
3. Send `/newbot` command
4. Follow the instructions to choose a name and username for your bot
5. BotFather will provide you with a bot token - **save this token securely**
6. Your bot token looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### 2. Add Bot to Chat/Group

To listen to messages, your bot needs to be added to the chat or group:

1. **For private chats**: Users need to start a conversation with your bot first
2. **For groups**: 
   - Add your bot to the group as a member
   - Make sure the bot has permission to read messages
   - For groups, you might need to disable "Privacy Mode" for your bot via @BotFather

### 3. Install Dependencies

The project is already set up with a virtual environment. The required packages are:
- `python-telegram-bot`: Official Telegram Bot API wrapper
- `python-dotenv`: For loading environment variables

### 4. Configure the Bot

1. Open the `.env` file in the project directory
2. Replace `your_bot_token_here` with your actual bot token:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
3. Optionally configure other settings in `.env`:
   ```
   HIGHLIGHT_KEYWORDS=important,urgent,alert
   LOG_LEVEL=INFO
   ```

## Usage

### Running the Listener

Execute the main script to start listening:

```bash
# Make sure you're in the telegram directory
cd /Users/apple/Documents/telegram

# Run the listener
/Users/apple/Documents/telegram/.venv/bin/python telegram_listener.py
```

The bot will start and display:
```
Starting Telegram listener...
Bot is now listening for messages. Press Ctrl+C to stop.
```

### What the Bot Does

- **Listens to all messages** in chats where the bot is present
- **Logs messages** to both console and `telegram_messages.log`
- **Saves structured data** to `messages_data.jsonl` for analysis
- **Processes different message types**: text, photos, documents, audio, video, etc.
- **Handles errors** gracefully and continues running

### Generated Files

- `telegram_messages.log`: Human-readable log of all messages
- `messages_data.jsonl`: Structured data in JSON Lines format
- Additional log files as configured

### Example Output

Console output will show:
```
2024-09-27 10:30:15 - Chat: My Group (group) | User: John Doe (@johndoe) | Type: text | Message: Hello everyone!
2024-09-27 10:30:20 - Chat: My Group (group) | User: Jane Smith (@janesmith) | Type: photo | Message: [Photo]
```

## Advanced Usage

### Message Analysis

Use the enhanced message handler for detailed analysis:

```python
from message_handler import MessageProcessor, MessageStorage, create_message_report

# Create report of collected messages
storage = MessageStorage()
report = create_message_report(storage)
print(report)
```

### Custom Message Processing

Modify the `process_message` method in `telegram_listener.py` to add custom logic:

```python
async def process_message(self, message_info: dict, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = message_info.get('text', '').lower()
    
    # Custom responses
    if 'hello' in text:
        await update.message.reply_text("Hi there!")
    
    # Save important messages
    if 'urgent' in text:
        # Custom handling for urgent messages
        pass
```

### Filtering Specific Chats

To monitor only specific chats, modify the message handler to check chat IDs:

```python
# Only process messages from specific chat IDs
allowed_chat_ids = [-1001234567890, -1009876543210]  # Replace with actual IDs
if message_info['chat_id'] not in allowed_chat_ids:
    return
```

## Configuration Options

Edit `.env` file to customize behavior:

```bash
# Required: Your bot token
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional: Keywords to highlight (comma-separated)
HIGHLIGHT_KEYWORDS=important,urgent,alert,breaking

# Optional: Specific chat IDs to monitor
MONITORED_CHATS=-1001234567890,-1009876543210

# Logging configuration
LOG_LEVEL=INFO
LOG_FILE=telegram_messages.log

# Data storage
SAVE_MESSAGES_TO_FILE=true
MESSAGES_FILE=messages_data.jsonl
```

## Troubleshooting

### Common Issues

1. **"Bot token is required" error**
   - Make sure you've set `TELEGRAM_BOT_TOKEN` in your `.env` file
   - Verify the token is correct (no extra spaces or characters)

2. **Bot not receiving messages**
   - Ensure the bot is added to the chat/group
   - Check if "Privacy Mode" is disabled for group bots
   - Verify the bot has necessary permissions

3. **Permission errors**
   - Make sure the bot has read message permissions in groups
   - For channels, the bot needs to be an administrator

4. **Network/Connection issues**
   - Check your internet connection
   - Telegram API might be temporarily unavailable

### Getting Chat IDs

To find chat IDs for filtering:

1. Add your bot to the desired chat
2. Run the listener
3. Send a message in the chat
4. Check the logs for the `chat_id` value

### Bot Commands

The bot responds to these commands by default:
- `/hello` - Bot will respond with a greeting
- Any message with "important" - Will be logged as a warning

## Security Notes

- **Never share your bot token** - treat it like a password
- **Use `.env` file** for sensitive configuration
- **Add `.env` to `.gitignore`** if using version control
- **Regularly rotate bot tokens** for security

## Legal and Ethical Considerations

- **Respect privacy**: Only monitor chats you have permission to access
- **Follow Telegram ToS**: Ensure your usage complies with Telegram's terms
- **Data protection**: Handle collected data responsibly
- **Inform users**: Let chat participants know if a bot is monitoring

## File Structure

```
telegram/
├── .env                    # Configuration (your bot token)
├── .env.example           # Configuration template
├── telegram_listener.py   # Main bot script
├── message_handler.py     # Enhanced message processing
├── telegram_messages.log  # Generated: Human-readable logs
├── messages_data.jsonl    # Generated: Structured message data
└── .venv/                 # Python virtual environment
```

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your bot token and permissions
3. Review the log files for error messages
4. Ensure all dependencies are installed correctly

## License

This project is for educational and personal use. Make sure to comply with Telegram's Terms of Service and respect user privacy.
