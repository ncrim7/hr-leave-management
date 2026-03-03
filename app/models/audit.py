from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=False)
    action_type = Column(String, nullable=False) # e.g., "created", "approved", "rejected", "cancelled"
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False) # The user who performed the action
    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    leave_request = relationship("LeaveRequest", back_populates="audit_logs")
    actor = relationship("User", foreign_keys=[actor_user_id])
