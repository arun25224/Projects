import os
import io
import re
import uuid
import logging
import datetime
from PIL import Image
import numpy as np
import cv2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

from sheets_helper import append_claim
from paddleocr import PaddleOCR

logging.getLogger('ppocr').setLevel(logging.ERROR)
ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)

(WAITING_FOR_MATRIC_NUM, WAITING_FOR_RECEIPT, WAITING_FOR_EVENT_CHOICE, WAITING_FOR_EVENT_OTHER,
 WAITING_FOR_PURPOSE_CHOICE, WAITING_FOR_PURPOSE_OTHER, CONFIRM_CLAIM, WAITING_FOR_MANUAL_AMOUNT) = range(8)

async def claims_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧾 *Submit a Claim*\n\nPlease enter your full matriculation number (e.g. U1234567S).\nUse /cancel to exit.", parse_mode='Markdown')
    return WAITING_FOR_MATRIC_NUM

async def handle_matric_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['matric_num'] = update.message.text.strip().upper()
    await update.message.reply_text("✅ Thank you. Now, please upload a photo of your receipt.")
    return WAITING_FOR_RECEIPT

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    status_message = await update.message.reply_text("⏳ Scanning receipt...")
    try:
        tg_file = await context.bot.get_file(photo.file_id)
        file_byte_array = await tg_file.download_as_bytearray()
        context.user_data['image_url'] = tg_file.file_path # Keep TG URL
        context.user_data['chat_id'] = update.message.chat_id

        pil_image = Image.open(io.BytesIO(file_byte_array)).convert('RGB')
        img_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        result = ocr_engine.ocr(img_bgr, cls=True)

        extracted_text = " ".join([line[1][0] for line in result[0]]) if result and result[0] else ""

        amounts = re.findall(r'\b\d{1,3}(?:,\d{3})*\.\d{2}\b', extracted_text)
        context.user_data['amount'] = f"{max([float(a.replace(',', '')) for a in amounts]):.2f}" if amounts else "0.00"

        dates_found = re.findall(r'\b(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}[/.-]\d{1,2}[/.-]\d{1,2})\b', extracted_text)
        context.user_data['event_date'] = dates_found[0] if dates_found else "Not Found"
        context.user_data['description'] = extracted_text[:100] if extracted_text else "No text found"

    except Exception as e:
        context.user_data.update({'amount': "0.00", 'event_date': "Error", 'description': "Scanning Failed"})

    keyboard = [[InlineKeyboardButton("Event 1", callback_data="event_Event 1")], [InlineKeyboardButton("Others", callback_data="event_others")]]
    await status_message.edit_text("✅ *Scan Complete!*\n\nWhich event are you claiming for?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return WAITING_FOR_EVENT_CHOICE

async def handle_event_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "event_others":
        await query.edit_message_text("Please type the name of the Event:")
        return WAITING_FOR_EVENT_OTHER
    context.user_data['event'] = query.data.replace("event_", "")
    return await prompt_for_purpose(query, context)

async def handle_event_other_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['event'] = update.message.text.strip()
    return await prompt_for_purpose(update, context, is_message=True)

async def prompt_for_purpose(update_or_query, context, is_message=False):
    keyboard = [[InlineKeyboardButton("Food", callback_data="purpose_Food")], [InlineKeyboardButton("Others", callback_data="purpose_others")]]
    text = "What is the *Type of Claim*?"
    if is_message: await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return WAITING_FOR_PURPOSE_CHOICE

async def handle_purpose_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "purpose_others":
        await query.edit_message_text("Please type the type of the claim:")
        return WAITING_FOR_PURPOSE_OTHER
    context.user_data['purpose'] = query.data.replace("purpose_", "")
    return await display_claim_summary(query, context)

async def handle_purpose_other_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['purpose'] = update.message.text.strip()
    return await display_claim_summary(update, context, is_message=True)

async def display_claim_summary(update_or_query, context, is_message=False):
    keyboard = [[InlineKeyboardButton("✅ Confirm & Submit", callback_data="confirm_claim_yes")], [InlineKeyboardButton("✏️ Edit Amount", callback_data="edit_amount")], [InlineKeyboardButton("❌ Cancel", callback_data="confirm_claim_no")]]
    text = f"🧾 *Claim Summary:*\nAmount: ${context.user_data.get('amount')}\nEvent: {context.user_data.get('event')}\nIs this correct?"
    if is_message: await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CONFIRM_CLAIM

async def handle_manual_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['amount'] = update.message.text.strip()
    return await display_claim_summary(update, context, is_message=True)

async def confirm_claim_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_claim_yes":
        claim_id = f"CLM-{str(uuid.uuid4())[:6].upper()}"
        try:
            claim_data = {
                "Claim ID": claim_id, "Chat ID": context.user_data.get('chat_id'),
                "Matriculation Number": context.user_data.get('matric_num'),
                "Date of Upload": datetime.datetime.now().strftime("%Y-%m-%d"),
                "Date of Event": context.user_data.get('event_date'), "Event Name": context.user_data.get('event'),
                "Type of Claim": context.user_data.get('purpose'), "Amount": context.user_data.get('amount'),
                "Image URL": context.user_data.get('image_url'), "Description": context.user_data.get('description'),
                "Status": "Pending"
            }
            append_claim(claim_data)
            await query.edit_message_text(f"✅ Thank you! Claim {claim_id} has been submitted.", parse_mode='Markdown')
        except Exception as e:
            await query.edit_message_text(f"⚠️ Failed to save. Error: {e}")
        finally:
            context.user_data.clear()
        return ConversationHandler.END
    elif query.data == "edit_amount":
        await query.edit_message_text("Please type the correct amount (e.g., 10.10):")
        return WAITING_FOR_MANUAL_AMOUNT
    else:
        await query.edit_message_text("❌ Claim cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

async def cancel_claims(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END

claims_conv_handler = ConversationHandler(
    entry_points=[CommandHandler('claims', claims_command)],
    states={
        WAITING_FOR_MATRIC_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_matric_num)],
        WAITING_FOR_RECEIPT: [MessageHandler(filters.PHOTO, handle_receipt_photo)],
        WAITING_FOR_EVENT_CHOICE: [CallbackQueryHandler(handle_event_choice, pattern='^event_')],
        WAITING_FOR_EVENT_OTHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_other_text)],
        WAITING_FOR_PURPOSE_CHOICE: [CallbackQueryHandler(handle_purpose_choice, pattern='^purpose_')],
        WAITING_FOR_PURPOSE_OTHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_purpose_other_text)],
        CONFIRM_CLAIM: [CallbackQueryHandler(confirm_claim_callback, pattern='^(confirm_claim_yes|confirm_claim_no|edit_amount)$')],
        WAITING_FOR_MANUAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_amount)],
    },
    fallbacks=[CommandHandler('cancel', cancel_claims)],
)
