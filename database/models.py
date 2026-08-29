from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
from database.connection import Base
import enum


class PlatformType(str, enum.Enum):
    GOSPLIT = "gosplit"
    SHARESUB = "sharesub"
    STREAMING = "streaming"


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class Credential(Base):
    __tablename__ = 'credentials'
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(SQLEnum(PlatformType), nullable=False, index=True)
    username = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    encrypted_api_key = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Credential(id={self.id}, platform={self.platform}, username={self.username})>"


class Account(Base):
    __tablename__ = 'accounts'
    
    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(Integer, nullable=False, index=True)
    platform_account_id = Column(String(255), nullable=False)
    account_name = Column(String(255), nullable=False)
    status = Column(SQLEnum(AccountStatus), default=AccountStatus.ACTIVE)
    subscription_end_date = Column(DateTime(timezone=True), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Account(id={self.id}, platform_account_id={self.platform_account_id}, status={self.status})>"


class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    plan_name = Column(String(255), nullable=False)
    price = Column(Integer, nullable=False)
    currency = Column(String(3), default='USD')
    renewal_date = Column(DateTime(timezone=True), nullable=True)
    is_auto_renew = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, plan_name={self.plan_name}, renewal_date={self.renewal_date})>"
