import os
import threading
import uvicorn
import logging
from fastapi import FastAPI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Import your handlers from your separate files
from claims import claims_conv_handler
from attendance import attendance_conv_handler

# 1. Setup Dummy Web Server for Hugging Face (Solves Port 7860 Issue)
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Thrive Bot is Alive!"}

def run_fastapi():
    """Runs FastAPI on port 7860 to keep Hugging Face happy."""
    uvicorn.run(app, host="0.0.0.0", port=7860)

# 2. Setup Telegram Bot Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hi! Use /claims to submit a receipt, or /attendance to upload Wooclap files.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('in_attendance_flow'):
        await update.message.reply_text("📎 To process an attendance file, please use the /attendance command first[cite: 25].")

def main():
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    
    # Start the dummy server in the background
    threading.Thread(target=run_fastapi, daemon=True).start()

    # Start the Telegram Bot
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        raise ValueError("TELEGRAM_TOKEN is missing!")

    bot_app = Application.builder().token(TOKEN).build()
    
    bot_app.add_handler(CommandHandler('start', start_command))
    bot_app.add_handler(claims_conv_handler)
    bot_app.add_handler(attendance_conv_handler)
    bot_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Starting bot polling...")
    bot_app.run_polling(poll_interval=2)

if __name__ == '__main__':
    main()
