from sqlalchemy import Column, String, Integer, Boolean, DateTime
from core.database import Base

class UserAccount(Base):
    __tablename__ = "users_account"
    
    account_id = Column(String(36), primary_key=True)
    account_name = Column(String(100), nullable=True, index=True)
    account_extension = Column(String(20), nullable=True)
    password = Column(String(255), nullable=True)
    token = Column(String(255), nullable=True)
    last_update_token = Column(DateTime, nullable=True)
    sip_ha1 = Column(String(255), nullable=True)