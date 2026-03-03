import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from app.core.config import settings
from app.bot.handlers.leave_request import (
    start_leave_request, 
    cancel, 
    handle_message,
    calendar_start_date_handler,
    calendar_end_date_handler
)
from app.bot.handlers.approval import approval_handler
from app.bot.handlers.admin import add_employee_cmd, list_employees_cmd, set_manager_cmd, admin_help_cmd
from app.db.session import AsyncSessionLocal
from app.services.user_service import get_user_by_telegram_id
from app.bot.state_manager import StateManager

logger = logging.getLogger(__name__)

async def calendar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route calendar callbacks to appropriate handler based on state"""
    user_id = update.effective_user.id
    state_data = await StateManager.get_state_data(user_id)
    state = state_data.get("state")
    
    if state == "AWAITING_START_DATE":
        await calendar_start_date_handler(update, context)
    elif state == "AWAITING_END_DATE":
        await calendar_end_date_handler(update, context)
    else:
        # Ignore if not in a date-selection state
        await update.callback_query.answer("Please start a leave request first with /leave")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg = update.effective_user
    async with AsyncSessionLocal() as db:
        user = await get_user_by_telegram_id(db, user_tg.id)
        if user:
            await update.message.reply_text(f"Welcome back, {user.full_name}! Use /leave to request time off.")
        else:
            await update.message.reply_text("Welcome to the HR Bot! It seems you are not registered yet. Please contact HR.")

async def run_bot():
    """Start the bot in polling mode (for dev/local testing)"""
    application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("leave", start_leave_request))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("add_employee", add_employee_cmd))
    application.add_handler(CommandHandler("list_employees", list_employees_cmd))
    application.add_handler(CommandHandler("set_manager", set_manager_cmd))
    application.add_handler(CommandHandler("admin_help", admin_help_cmd))
    
    # Approval handler must be first (specific pattern)
    application.add_handler(approval_handler)
    
    # Calendar handlers for date selection (more general pattern)
    application.add_handler(CallbackQueryHandler(calendar_handler, pattern="^cbcal"))
    
    # Global message handler for our manual FSM
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    return application

async def stop_bot(application):
    logger.info("Bot is stopping...")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
