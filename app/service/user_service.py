import hashlib
import secrets
from sqlalchemy.ext.asyncio import AsyncSession
from app.query.user_query import (
    create_user,
    update_user_token_connected,
    get_user_by_extension,
    get_user_by_name
)
from app.model.user_model import User
from app.decorator.db_decorator import with_db

@with_db
async def register_new_user(db: AsyncSession, account_name: str, plain_password: str, account_extension: str = None) -> User:
    """Service untuk memproses registrasi user (mengurus hashing password)"""
    hashed_password = hashlib.sha256(plain_password.encode()).hexdigest()
    return await create_user(
        db=db,
        account_name=account_name,
        password=hashed_password,
        account_extension=account_extension
    )

@with_db
async def authenticate_user_connect(db: AsyncSession, account_extension: str, plain_password: str) -> str | None:
    """Service untuk login dan langsung generate token"""
    # Cari user menggunakan extension
    user = await get_user_by_extension(db, account_extension)
    if not user:
        return None
        
    # Cocokkan password yang di-hash
    hashed_password = hashlib.sha256(plain_password.encode()).hexdigest()
    print("plain password : ", plain_password)
    print("user password : ", user.password)
    print("hash password : ", hashed_password)
    if user.password == hashed_password:
        # Generate token baru
        new_token = secrets.token_hex(16)
        
        # Simpan token ke database (menggunakan account_id dari user yang ditemukan)
        updated_user = await update_user_token_connected(db, user.account_id, new_token)
        if updated_user:
            return new_token
            
    return None
