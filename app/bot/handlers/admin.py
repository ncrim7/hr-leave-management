from telegram import Update
from telegram.ext import ContextTypes

from app.db.session import AsyncSessionLocal
from app.services.user_service import (
    get_user_by_telegram_id,
    create_or_update_employee_under_manager,
    list_employees_under_manager,
    set_employee_manager_by_telegram_id,
)


def _admin_usage_text() -> str:
    return (
        "Admin commands:\n"
        "/add_employee <telegram_id> <full_name>\n"
        "/list_employees\n"
        "/set_manager <employee_telegram_id> <manager_telegram_id>\n\n"
        "Examples:\n"
        "/add_employee 5201413028 Ali Veli\n"
        "/set_manager 5201413028 1093618339"
    )


async def _ensure_hr_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg = update.effective_user
    async with AsyncSessionLocal() as db:
        requester = await get_user_by_telegram_id(db, user_tg.id)
        if not requester or requester.role.value != "hr_admin":
            await update.message.reply_text("Only hr_admin can use this command.")
            return None
        return requester


async def add_employee_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requester = await _ensure_hr_admin(update, context)
    if requester is None:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /add_employee <telegram_id> <full_name>\n"
            "Example: /add_employee 5201413028 Ali Veli"
        )
        return

    try:
        employee_telegram_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid telegram_id. Please provide a numeric telegram id.")
        return

    full_name = " ".join(context.args[1:]).strip()
    if not full_name:
        await update.message.reply_text("Employee full name is required.")
        return

    async with AsyncSessionLocal() as db:
        employee, created = await create_or_update_employee_under_manager(
            db=db,
            telegram_id=employee_telegram_id,
            full_name=full_name,
            manager_id=requester.id,
            annual_leave_balance=14,
        )

        if created:
            await update.message.reply_text(
                f"Employee added successfully.\n"
                f"Name: {employee.full_name}\n"
                f"Telegram ID: {employee.telegram_id}\n"
                f"Role: {employee.role.value}\n"
                f"Manager ID: {employee.manager_id}"
            )
        else:
            await update.message.reply_text(
                f"Employee updated successfully.\n"
                f"Name: {employee.full_name}\n"
                f"Telegram ID: {employee.telegram_id}\n"
                f"Role: {employee.role.value}\n"
                f"Manager ID: {employee.manager_id}"
            )


async def list_employees_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requester = await _ensure_hr_admin(update, context)
    if requester is None:
        return

    async with AsyncSessionLocal() as db:
        employees = await list_employees_under_manager(db, requester.id)

    if not employees:
        await update.message.reply_text("You have no employees assigned yet.")
        return

    lines = ["Employees under you:"]
    for employee in employees:
        lines.append(
            f"- {employee.full_name} | tg_id: {employee.telegram_id} | balance: {employee.annual_leave_balance}"
        )
    await update.message.reply_text("\n".join(lines))


async def set_manager_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requester = await _ensure_hr_admin(update, context)
    if requester is None:
        return

    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "Usage: /set_manager <employee_telegram_id> <manager_telegram_id>\n"
            "Example: /set_manager 5201413028 1093618339"
        )
        return

    try:
        employee_tg_id = int(context.args[0])
        manager_tg_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Both telegram IDs must be numeric.")
        return

    async with AsyncSessionLocal() as db:
        manager_user = await get_user_by_telegram_id(db, manager_tg_id)
        if not manager_user or manager_user.role.value not in ["manager", "hr_admin"]:
            await update.message.reply_text("Target manager must exist and have role manager/hr_admin.")
            return

        employee = await set_employee_manager_by_telegram_id(
            db=db,
            employee_telegram_id=employee_tg_id,
            manager_telegram_id=manager_tg_id,
        )

    if employee is None:
        await update.message.reply_text("Employee or manager not found.")
        return

    await update.message.reply_text(
        f"Manager updated successfully.\n"
        f"Employee: {employee.full_name} ({employee.telegram_id})\n"
        f"New manager telegram_id: {manager_tg_id}"
    )


async def admin_help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requester = await _ensure_hr_admin(update, context)
    if requester is None:
        return
    await update.message.reply_text(_admin_usage_text())
