import uuid
import sqlalchemy as sa
from app.core.database import Base

def generate_short_id():
    return str(uuid.uuid4())[:8]

class User(Base):
    __tablename__ = "users_account"
    
    account_id = sa.Column(sa.String(36), primary_key=True, default=generate_short_id)
    account_name = sa.Column(sa.String(100), nullable=True, index=True)
    account_extension = sa.Column(sa.String(20), nullable=True)
    password = sa.Column(sa.String(255), nullable=True)
    token = sa.Column(sa.String(255), nullable=True)
    last_update_token = sa.Column(sa.DateTime, nullable=True)