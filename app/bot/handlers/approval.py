from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from app.db.session import AsyncSessionLocal
from app.services.leave_service import process_leave_approval, get_leave_request
from app.services.user_service import get_user_by_telegram_id
import logging

logger = logging.getLogger(__name__)

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Format: approve:{leave_id} or reject:{leave_id}
    data = query.data
    action, leave_id_str = data.split(":")
    leave_id = int(leave_id_str)
    approve = (action == "approve")

    manager_telegram_id = update.effective_user.id

    async with AsyncSessionLocal() as db:
        manager = await get_user_by_telegram_id(db, manager_telegram_id)
        if not manager or manager.role.value not in ["manager", "hr_admin"]:
            await query.edit_message_text(text="You are not authorized to approve leave requests.")
            return

        try:
            # Check leave request exists and hasn't been modified yet
            leave_request = await get_leave_request(db, leave_id)
            if not leave_request:
                 await query.edit_message_text(text="Leave request not found.")
                 return

            # Authorization: only employee's manager or hr_admin can approve/reject
            if manager.role.value != "hr_admin" and leave_request.user.manager_id != manager.id:
                await query.edit_message_text(text="You can only process requests from your own subordinates.")
                return
                 
            if leave_request.status.value != "pending":
                await query.edit_message_text(text=f"Leave request is already {leave_request.status.value}.")
                return

            processed_request = await process_leave_approval(
                db=db,
                request_id=leave_id,
                actor_id=manager.id,
                approve=approve
            )
            
            # Notify manager
            status_str = "APPROVED" if approve else "REJECTED"
            await query.edit_message_text(
                text=f"Request #{leave_id} has been {status_str}."
            )

            # Notify employee
            employee = processed_request.user
            await context.bot.send_message(
                chat_id=employee.telegram_id,
                text=f"Your leave request from {processed_request.start_date} to {processed_request.end_date} has been {status_str} by your manager."
            )

        except ValueError as e:
            await query.edit_message_text(text=f"Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing approval: {e}")
            await query.edit_message_text(text="An unexpected error occurred.")

approval_handler = CallbackQueryHandler(handle_approval_callback, pattern="^(approve|reject):[0-9]+$")
