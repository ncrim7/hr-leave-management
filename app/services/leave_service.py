from datetime import date, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, update
from sqlalchemy.orm import selectinload

from app.models.leave import LeaveRequest, LeaveStatus, LeaveType
from app.models.user import User
from app.models.audit import AuditLog

def calculate_business_days(start_date: date, end_date: date) -> int:
    """Calculate business days between two dates, inclusive, excluding weekends."""
    business_days = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # 0-4 are Monday to Friday
            business_days += 1
        current_date += timedelta(days=1)
    return business_days

async def check_leave_conflict(db: AsyncSession, user_id: int, start_date: date, end_date: date) -> bool:
    """Return True if there is a conflict (overlapping leave that is not rejected/cancelled)."""
    stmt = select(LeaveRequest).where(
        LeaveRequest.user_id == user_id,
        LeaveRequest.status.notin_([LeaveStatus.rejected, LeaveStatus.cancelled]),
        or_(
            and_(LeaveRequest.start_date <= end_date, LeaveRequest.end_date >= start_date)
        )
    )
    result = await db.execute(stmt)
    conflicting_leave = result.scalars().first()
    return conflicting_leave is not None

async def create_leave_request(
    db: AsyncSession,
    user_id: int,
    leave_type_id: int,
    start_date: date,
    end_date: date,
    reason: Optional[str] = None
) -> LeaveRequest:
    
    # Check conflicts
    if await check_leave_conflict(db, user_id, start_date, end_date):
        raise ValueError("Overlapping leave request exists.")

    leave_request = LeaveRequest(
        user_id=user_id,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status=LeaveStatus.pending
    )
    
    db.add(leave_request)
    await db.flush() # flush to get the id

    audit_log = AuditLog(
        leave_request_id=leave_request.id,
        action_type="created",
        actor_user_id=user_id,
        old_status=None,
        new_status=LeaveStatus.pending.value
    )
    db.add(audit_log)
    await db.commit()
    await db.refresh(leave_request)
    return leave_request

async def get_leave_request(db: AsyncSession, request_id: int) -> Optional[LeaveRequest]:
    stmt = select(LeaveRequest).options(
        selectinload(LeaveRequest.user),
        selectinload(LeaveRequest.leave_type)
    ).where(LeaveRequest.id == request_id)
    result = await db.execute(stmt)
    return result.scalars().first()

async def process_leave_approval(
    db: AsyncSession,
    request_id: int,
    actor_id: int,
    approve: bool
) -> LeaveRequest:
    leave_request = await get_leave_request(db, request_id)
    if not leave_request:
        raise ValueError("Leave request not found.")
    
    if leave_request.status != LeaveStatus.pending:
        raise ValueError(f"Leave request is already {leave_request.status.value}.")

    old_status = leave_request.status.value
    new_status = LeaveStatus.approved if approve else LeaveStatus.rejected

    # Deduct balance if approved and deducts_from_balance is True
    if approve and leave_request.leave_type.deducts_from_balance:
        days_to_deduct = calculate_business_days(leave_request.start_date, leave_request.end_date)
        
        user = leave_request.user
        if user.annual_leave_balance < days_to_deduct:
            raise ValueError("Insufficient leave balance.")
            
        user.annual_leave_balance -= days_to_deduct
        db.add(user)

    leave_request.status = new_status
    db.add(leave_request)

    audit_log = AuditLog(
        leave_request_id=leave_request.id,
        action_type="approved" if approve else "rejected",
        actor_user_id=actor_id,
        old_status=old_status,
        new_status=new_status.value
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(leave_request)
    return leave_request

async def get_leave_types(db: AsyncSession) -> List[LeaveType]:
    result = await db.execute(select(LeaveType))
    return list(result.scalars().all())

