from sqlalchemy import Column, Integer, String, BigInteger, Enum, ForeignKey
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base

class UserRole(str, enum.Enum):
    employee = "employee"
    manager = "manager"
    hr_admin = "hr_admin"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.employee, nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    annual_leave_balance = Column(Integer, default=14, nullable=False)

    # Relationships
    manager = relationship("User", remote_side=[id], backref="subordinates")
    leave_requests = relationship("LeaveRequest", back_populates="user", foreign_keys="[LeaveRequest.user_id]")
