from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Enum as SQLEnum, orm
from sqlalchemy.sql import func
from database.connection import Base
import enum
from sqlalchemy import orm

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
    
    id = Column('id', Integer, primary_key=True, index=True)
    platform = Column('platform', SQLEnum(PlatformType), nullable=False, index=True)
    username = Column('username', String(255), nullable=False)
    encrypted_password = Column('encrypted_password', Text, nullable=False)
    encrypted_api_key = Column('encrypted_api_key', Text, nullable=True)
    email = Column('email', String(255), nullable=True)
    phone = Column('phone', String(50), nullable=True)
    is_active = Column('is_active', Boolean, default=True)
    created_at = Column('created_at', DateTime(timezone=True), server_default=func.now())
    updated_at = Column('updated_at', DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Credential(id={self.id}, platform={self.platform}, username={self.username})>"

class Account(Base):
    __tablename__ = 'accounts'
    
    id = Column('id', Integer, primary_key=True, index=True)
    credential_id = Column('platform_id', Integer, nullable=False, index=True)
    
    # Definimos la columna física principal apuntando a 'email'
    email = Column('email', String(255), nullable=False)
    
    # Creamos sinónimos para que los atributos que el motor busca funcionen sin duplicar columnas físicas
    platform_account_id = orm.synonym('email')
    account_name = orm.synonym('email')
    
    status = Column('status', SQLEnum(AccountStatus), default=AccountStatus.ACTIVE)
    subscription_end_date = Column('expiration_date', DateTime(timezone=True), nullable=True)
    created_at = Column('created_at', DateTime(timezone=True), server_default=func.now())
    updated_at = Column('updated_at', DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Account(id={self.id}, email={self.email}, status={self.status})>"
class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column('id', Integer, primary_key=True, index=True)
    account_id = Column('account_id', Integer, nullable=False, index=True)
    plan_name = Column('plan_name', String(255), nullable=False)
    price = Column('price', Integer, nullable=False)
    currency = Column('currency', String(3), default='USD')
    renewal_date = Column('renewal_date', DateTime(timezone=True), nullable=True)
    is_auto_renew = Column('is_auto_renew', Boolean, default=True)
    created_at = Column('created_at', DateTime(timezone=True), server_default=func.now())
    updated_at = Column('updated_at', DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, plan_name={self.plan_name}, renewal_date={self.renewal_date})>"