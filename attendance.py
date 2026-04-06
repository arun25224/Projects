import pandas as pd
import os
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from sheets_helper import update_attendance

# Simplified states (removed the confirmation steps for a faster user experience)
WAITING_FOR_FILE, WAITING_FOR_EVENT_NAME, WAITING_FOR_EVENT_ID = range(3)

async def attendance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['in_attendance_flow'] = True
    await update.message.reply_text(
        "📋 *Attendance Tracking*\n\nPlease upload your CSV or Excel (.xlsx) file.\nUse /cancel to exit at any time.", 
        parse_mode='Markdown'
    )
    return WAITING_FOR_FILE

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.endswith((".csv", ".xlsx")):
        await update.message.reply_text("❌ Please upload a CSV or Excel (.xlsx) file only.")
        return WAITING_FOR_FILE
    
    await update.message.reply_text("⏳ Processing your file...")
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_path = f"./{doc.file_name}"
        await tg_file.download_to_drive(file_path)
        
        df = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path)
        
        email_col = next((c for c in df.columns if 'email' in c.lower()), None)
        if email_col is None:
            await update.message.reply_text("❌ This file doesn't have an *Email* column.", parse_mode='Markdown')
            os.remove(file_path)
            return WAITING_FOR_FILE
            
        context.user_data.update({'file_path': file_path, 'dataframe': df, 'file_name': doc.file_name})
        await update.message.reply_text("✅ File received.\n\nPlease enter the *Event Name* (e.g., General Meeting 1):", parse_mode='Markdown')
        return WAITING_FOR_EVENT_NAME
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error reading file: {e}")
        return WAITING_FOR_FILE

async def handle_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['event_name'] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Event Name saved as *{context.user_data['event_name']}*.\n\nPlease enter the *Event ID* (e.g., EVT001):", 
        parse_mode='Markdown'
    )
    return WAITING_FOR_EVENT_ID

async def handle_event_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['event_id'] = update.message.text.strip()
    await update.message.reply_text(f"⏳ Matching attendance against the master sheet...", parse_mode='Markdown')
    
    try:
        # Pushes data to Google Sheets via sheets_helper.py
        result = update_attendance(context.user_data['dataframe'], context.user_data['event_id'], context.user_data['event_name'])
        
        await update.message.reply_text(
            f"✅ *Attendance Updated Successfully!*\n\n"
            f"✅ Attended: {result['matched']}/{result['total']}\n"
            f"📊 Column added: `{result['column_name']}`", 
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")
    finally:
        # Always clean up the downloaded file
        if os.path.exists(context.user_data.get('file_path', '')): 
            os.remove(context.user_data['file_path'])
        context.user_data.clear()
        
    return ConversationHandler.END

async def cancel_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(context.user_data.get('file_path', '')): 
        os.remove(context.user_data['file_path'])
    context.user_data.clear()
    await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END

attendance_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('attendance', attendance_command)],
    states={
        WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, handle_file_upload)],
        WAITING_FOR_EVENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_name)],
        WAITING_FOR_EVENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_id)],
    },
    fallbacks=[CommandHandler('cancel', cancel_attendance)],
)
