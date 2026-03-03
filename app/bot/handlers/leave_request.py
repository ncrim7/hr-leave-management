import re
from datetime import datetime, date
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
from app.db.session import AsyncSessionLocal
from app.services.leave_service import get_leave_types, create_leave_request
from app.services.user_service import get_user_by_telegram_id
from app.bot.state_manager import StateManager
from app.models.user import User

DATE_FORMAT = "%Y-%m-%d"

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels and ends the conversation."""
    user = update.message.from_user
    await StateManager.clear_state(user.id)
    await update.message.reply_text(
        "Operation cancelled. Use /leave to start again.",
        reply_markup=ReplyKeyboardRemove()
    )

async def start_leave_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg = update.message.from_user
    
    async with AsyncSessionLocal() as db:
        user = await get_user_by_telegram_id(db, user_tg.id)
        if not user:
            await update.message.reply_text("You are not registered in the system. Please contact HR.")
            return

        leave_types = await get_leave_types(db)
        if not leave_types:
            await update.message.reply_text("No leave types configured in the system. Please contact HR.")
            return
            
        leave_types_dict = {str(lt.name): lt.id for lt in leave_types}
        
        keyboard = [[lt.name] for lt in leave_types]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await StateManager.set_state(user_tg.id, "AWAITING_LEAVE_TYPE", leave_types=leave_types_dict)
        await update.message.reply_text(
            f"Hello {user.full_name}, your current annual leave balance is {user.annual_leave_balance} days.\n"
            "Please select the type of leave you want to request:",
            reply_markup=reply_markup
        )

async def receive_leave_type(update: Update, context: ContextTypes.DEFAULT_TYPE, state_data: dict):
    text = update.message.text
    user_tg = update.message.from_user

    leave_types = state_data.get('leave_types', {})
    if text not in leave_types:
        await update.message.reply_text("Please select a valid option from the keyboard.")
        return
        
    await StateManager.set_state(
        user_tg.id, 
        "AWAITING_START_DATE", 
        selected_leave_type_id=leave_types[text],
        selected_leave_type_name=text
    )
    
    # Show calendar for start date
    calendar, step = DetailedTelegramCalendar(min_date=date.today()).build()
    await update.message.reply_text(
        "Great. Now select the start date of your leave:",
        reply_markup=calendar
    )

async def calendar_start_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle calendar selection for start date"""
    query = update.callback_query
    user_tg = update.effective_user
    
    state_data = await StateManager.get_state_data(user_tg.id)
    if state_data.get('state') != 'AWAITING_START_DATE':
        return
    
    result, key, step = DetailedTelegramCalendar(min_date=date.today()).process(query.data)
    
    if not result and key:
        await query.edit_message_text(
            f"Select the start date of your leave:",
            reply_markup=key
        )
    elif result:
        start_date = result
        await query.edit_message_text(
            f"Start date selected: {start_date.strftime('%Y-%m-%d')}"
        )
        
        # Save start date and move to next step
        state_data['start_date'] = start_date.isoformat()
        kwargs = {k: v for k, v in state_data.items() if k != 'state'}
        await StateManager.set_state(user_tg.id, "AWAITING_END_DATE", **kwargs)
        
        # Show calendar for end date
        calendar, step = DetailedTelegramCalendar(min_date=start_date).build()
        await context.bot.send_message(
            chat_id=user_tg.id,
            text="Now select the end date of your leave:",
            reply_markup=calendar
        )

async def receive_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE, state_data: dict):
    """Fallback for manual date entry (backward compatibility)"""
    text = update.message.text
    user_tg = update.message.from_user
    
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        await update.message.reply_text("Invalid format. Please use the calendar or YYYY-MM-DD format:")
        return
        
    try:
        start_date = datetime.strptime(text, DATE_FORMAT).date()
        if start_date < date.today():
             await update.message.reply_text("Start date cannot be in the past. Try again:")
             return
             
        state_data['start_date'] = start_date.isoformat()
        state_data['state'] = "AWAITING_END_DATE"
        
        kwargs = {k: v for k, v in state_data.items() if k != 'state'}
        await StateManager.set_state(user_tg.id, "AWAITING_END_DATE", **kwargs)
        
        # Show calendar for end date
        calendar, step = DetailedTelegramCalendar(min_date=start_date).build()
        await update.message.reply_text("Got it. Now select the end date:", reply_markup=calendar)
    except ValueError:
        await update.message.reply_text("Invalid date value. Please use the calendar or YYYY-MM-DD:")

async def calendar_end_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle calendar selection for end date"""
    query = update.callback_query
    user_tg = update.effective_user
    
    state_data = await StateManager.get_state_data(user_tg.id)
    if state_data.get('state') != 'AWAITING_END_DATE':
        return
    
    start_date = datetime.strptime(state_data['start_date'], DATE_FORMAT).date()
    result, key, step = DetailedTelegramCalendar(min_date=start_date).process(query.data)
    
    if not result and key:
        await query.edit_message_text(
            f"Select the end date of your leave:",
            reply_markup=key
        )
    elif result:
        end_date = result
        await query.edit_message_text(
            f"End date selected: {end_date.strftime('%Y-%m-%d')}"
        )
        
        # Save end date and move to next step
        state_data['end_date'] = end_date.isoformat()
        kwargs = {k: v for k, v in state_data.items() if k != 'state'}
        await StateManager.set_state(user_tg.id, "AWAITING_REASON", **kwargs)
        
        await context.bot.send_message(
            chat_id=user_tg.id,
            text="Got it. Optional: Enter a reason for your leave, or reply with 'none':"
        )

async def receive_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE, state_data: dict):
    """Fallback for manual date entry (backward compatibility)"""
    text = update.message.text
    user_tg = update.message.from_user
    
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        await update.message.reply_text("Invalid format. Please use the calendar or YYYY-MM-DD format:")
        return
        
    try:
        end_date = datetime.strptime(text, DATE_FORMAT).date()
        start_date = datetime.strptime(state_data['start_date'], DATE_FORMAT).date()
        
        if end_date < start_date:
            await update.message.reply_text("End date cannot be before the start date. Try again:")
            return
            
        state_data['end_date'] = end_date.isoformat()
        
        kwargs = {k: v for k, v in state_data.items() if k != 'state'}
        await StateManager.set_state(user_tg.id, "AWAITING_REASON", **kwargs)
        
        await update.message.reply_text("Got it. Optional: Enter a reason for your leave, or reply with 'none':")
    except ValueError:
        await update.message.reply_text("Invalid date value. Please use the calendar or YYYY-MM-DD:")

async def receive_reason(update: Update, context: ContextTypes.DEFAULT_TYPE, state_data: dict):
    text = update.message.text
    user_tg = update.message.from_user
    
    reason = text if text.lower() != 'none' else None
    state_data['reason'] = reason
    
    kwargs = {k: v for k, v in state_data.items() if k != 'state'}
    await StateManager.set_state(user_tg.id, "AWAITING_CONFIRMATION", **kwargs)
    
    summary = (
        f"Please confirm your request:\n\n"
        f"Type: {state_data.get('selected_leave_type_name')}\n"
        f"Start Date: {state_data.get('start_date')}\n"
        f"End Date: {state_data.get('end_date')}\n"
        f"Reason: {reason or 'No reason provided'}"
    )
    
    keyboard = [["Confirm", "Cancel"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(summary, reply_markup=reply_markup)

async def confirm_request(update: Update, context: ContextTypes.DEFAULT_TYPE, state_data: dict):
    text = update.message.text
    user_tg = update.message.from_user
    
    if text.lower() == 'cancel':
        await cancel(update, context)
        return
        
    if text.lower() != 'confirm':
        await update.message.reply_text("Please select Confirm or Cancel from the keyboard.")
        return
        
    # Process request
    async with AsyncSessionLocal() as db:
        user = await get_user_by_telegram_id(db, user_tg.id)
        
        start_date = datetime.strptime(state_data['start_date'], DATE_FORMAT).date()
        end_date = datetime.strptime(state_data['end_date'], DATE_FORMAT).date()
        
        try:
            leave_request = await create_leave_request(
                db=db,
                user_id=user.id,
                leave_type_id=state_data['selected_leave_type_id'],
                start_date=start_date,
                end_date=end_date,
                reason=state_data.get('reason')
            )
            
            await update.message.reply_text(
                "Your request has been submitted successfully and is awaiting approval.",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Send notification to manager if exists
            if user.manager_id:
                manager = await db.get(User, user.manager_id)
                if manager:
                     keyboard = [
                         [
                             InlineKeyboardButton("Approve", callback_data=f"approve:{leave_request.id}"),
                             InlineKeyboardButton("Reject", callback_data=f"reject:{leave_request.id}")
                         ]
                     ]
                     reply_markup = InlineKeyboardMarkup(keyboard)
                     
                     msg = (
                         f"New Leave Request from {user.full_name}:\n"
                         f"Type: {state_data.get('selected_leave_type_name')}\n"
                         f"Dates: {start_date} to {end_date}\n"
                         f"Reason: {state_data.get('reason') or 'No reason provided'}"
                     )
                     
                     await context.bot.send_message(
                         chat_id=manager.telegram_id,
                         text=msg,
                         reply_markup=reply_markup
                     )
                     
        except ValueError as e:
            await update.message.reply_text(
                f"Failed to submit request: {str(e)}",
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error submitting request: {e}", exc_info=True)
            await update.message.reply_text(
                "An unexpected error occurred while processing your request.",
                reply_markup=ReplyKeyboardRemove()
            )

    await StateManager.clear_state(user_tg.id)

# Dispatcher function to route text messages based on state
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    state_data = await StateManager.get_state_data(user_id)
    state = state_data.get("state")

    if state == "AWAITING_LEAVE_TYPE":
        await receive_leave_type(update, context, state_data)
    elif state == "AWAITING_START_DATE":
        await receive_start_date(update, context, state_data)
    elif state == "AWAITING_END_DATE":
        await receive_end_date(update, context, state_data)
    elif state == "AWAITING_REASON":
        await receive_reason(update, context, state_data)
    elif state == "AWAITING_CONFIRMATION":
        await confirm_request(update, context, state_data)
    else:
        # Ignore messages if not in flow
        pass
