import pandas as pd
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from sheets_helper import update_attendance

WAITING_FOR_FILE, WAITING_FOR_EVENT_NAME, CONFIRM_EVENT_NAME, WAITING_FOR_EVENT_ID, CONFIRM_EVENT_ID = range(5)

async def attendance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['in_attendance_flow'] = True
    await update.message.reply_text("📋 *Attendance Tracking*\n\nPlease upload your Wooclap CSV or Excel (.xlsx) file[cite: 3, 4].\n\nUse /cancel to exit.", parse_mode='Markdown')
    return WAITING_FOR_FILE

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.endswith((".csv", ".xlsx")):
        await update.message.reply_text("❌ Please upload a CSV or Excel (.xlsx) file only[cite: 4, 5].")
        return WAITING_FOR_FILE
    
    await update.message.reply_text("⏳ Processing your file...")
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_path = f"./{doc.file_name}"
        await tg_file.download_to_drive(file_path)
        
        df = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path) [cite: 5, 6]
        
        email_col = next((c for c in df.columns if 'email' in c.lower()), None)
        if email_col is None:
            await update.message.reply_text("❌ This file doesn't have an *Email* column[cite: 6, 7].", parse_mode='Markdown')
            os.remove(file_path)
            return WAITING_FOR_FILE
            
        context.user_data.update({'file_path': file_path, 'dataframe': df, 'file_name': doc.file_name})
        await update.message.reply_text("✅ File received. Please enter the *Event Name*: [cite: 9]", parse_mode='Markdown')
        return WAITING_FOR_EVENT_NAME
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error reading file: {e}")
        return WAITING_FOR_FILE

async def handle_event_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['event_name'] = update.message.text.strip()
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yes", callback_data="confirm_name_yes"), InlineKeyboardButton("❌ No", callback_data="confirm_name_no")]])
    await update.message.reply_text(f"You entered:\n*Event Name:* {context.user_data['event_name']}\n\nIs this correct?", reply_markup=markup, parse_mode='Markdown')
    return CONFIRM_EVENT_NAME

async def confirm_event_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_name_yes":
        await query.edit_message_text("✅ Event Name confirmed. Please enter the *Event ID*:", parse_mode='Markdown')
        return WAITING_FOR_EVENT_ID
    await query.edit_message_text("Please re-enter the *Event Name*:", parse_mode='Markdown')
    return WAITING_FOR_EVENT_NAME

async def handle_event_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['event_id'] = update.message.text.strip()
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yes", callback_data="confirm_id_yes"), InlineKeyboardButton("❌ No", callback_data="confirm_id_no")]])
    await update.message.reply_text(f"You entered:\n*Event ID:* {context.user_data['event_id']}\n\nIs this correct?", reply_markup=markup, parse_mode='Markdown')
    return CONFIRM_EVENT_ID

async def confirm_event_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_id_yes":
        await query.edit_message_text("⏳ Matching attendance against master sheet... [cite: 14, 15]")
        try:
            result = update_attendance(context.user_data['dataframe'], context.user_data['event_id'], context.user_data['event_name']) [cite: 16]
            await query.message.reply_text(f"✅ *Attendance Updated Successfully!*\n\n✅ Attended: {result['matched']}/{result['total']}\n📊 Column added: `{result['column_name']}` [cite: 16, 17]", parse_mode='Markdown')
        except Exception as e:
            await query.message.reply_text(f"⚠️ Error: {e}")
        finally:
            if os.path.exists(context.user_data.get('file_path', '')): os.remove(context.user_data['file_path'])
            context.user_data.clear()
        return ConversationHandler.END
    await query.edit_message_text("Please re-enter the *Event ID*:", parse_mode='Markdown')
    return WAITING_FOR_EVENT_ID

async def cancel_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(context.user_data.get('file_path', '')): os.remove(context.user_data['file_path'])
    context.user_data.clear()
    await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END

attendance_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('attendance', attendance_command)],
    states={
        WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, handle_file_upload)],
        WAITING_FOR_EVENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_name)],
        CONFIRM_EVENT_NAME: [CallbackQueryHandler(confirm_event_name_callback, pattern='^confirm_name_')],
        WAITING_FOR_EVENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_id)],
        CONFIRM_EVENT_ID: [CallbackQueryHandler(confirm_event_id_callback, pattern='^confirm_id_')],
    },
    fallbacks=[CommandHandler('cancel', cancel_attendance)],
)
