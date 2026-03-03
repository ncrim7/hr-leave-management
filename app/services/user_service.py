from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User, UserRole

async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[User]:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def list_employees_under_manager(db: AsyncSession, manager_id: int) -> list[User]:
    stmt = select(User).where(
        User.role == UserRole.employee,
        User.manager_id == manager_id,
    ).order_by(User.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def set_employee_manager_by_telegram_id(
    db: AsyncSession,
    employee_telegram_id: int,
    manager_telegram_id: int,
) -> Optional[User]:
    employee = await get_user_by_telegram_id(db, employee_telegram_id)
    manager = await get_user_by_telegram_id(db, manager_telegram_id)

    if not employee or not manager:
        return None

    employee.role = "employee"
    employee.manager_id = manager.id
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee

async def create_user(
    db: AsyncSession,
    telegram_id: int,
    full_name: str,
    role: str = "employee",
    manager_id: Optional[int] = None,
    annual_leave_balance: int = 14
) -> User:
    new_user = User(
        telegram_id=telegram_id,
        full_name=full_name,
        role=role,
        manager_id=manager_id,
        annual_leave_balance=annual_leave_balance
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def create_or_update_employee_under_manager(
    db: AsyncSession,
    telegram_id: int,
    full_name: str,
    manager_id: int,
    annual_leave_balance: int = 14,
) -> tuple[User, bool]:
    existing = await get_user_by_telegram_id(db, telegram_id)

    if existing:
        existing.full_name = full_name
        existing.role = "employee"
        existing.manager_id = manager_id
        existing.annual_leave_balance = annual_leave_balance
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing, False

    created = User(
        telegram_id=telegram_id,
        full_name=full_name,
        role="employee",
        manager_id=manager_id,
        annual_leave_balance=annual_leave_balance,
    )
    db.add(created)
    await db.commit()
    await db.refresh(created)
    return created, True
