import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from model.user_account_model import UserAccount

# 1. Mengambil user berdasarkan account_id
async def get_user_by_id(db: AsyncSession, account_id: str) -> Optional[UserAccount]:
    stmt = select(UserAccount).where(UserAccount.account_id == account_id)
    result = await db.execute(stmt)
    return result.scalars().first()

# 2. Mengambil user berdasarkan account_extension
async def get_user_by_extension(db: AsyncSession, extension: str) -> Optional[UserAccount]:
    stmt = select(UserAccount).where(UserAccount.account_extension == extension)
    result = await db.execute(stmt)
    return result.scalars().first()

# 3. Mengambil user berdasarkan token (untuk verifikasi socket/auth)
async def get_user_by_token(db: AsyncSession, token: str) -> Optional[UserAccount]:
    stmt = select(UserAccount).where(UserAccount.token == token)
    result = await db.execute(stmt)
    return result.scalars().first()

# 4. Update token user
async def update_user_token(db: AsyncSession, account_id: str, new_token: str) -> bool:
    stmt = (
        update(UserAccount)
        .where(UserAccount.account_id == account_id)
        .values(token=new_token, last_update_token=datetime.utcnow())
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

# 5. Insert User Baru ke Database
async def create_user_account(
    db: AsyncSession,
    account_name: str,
    extension: str,
    password: str,
    sip_ha1: Optional[str] = None,
    account_id: Optional[str] = None
) -> UserAccount:
    new_user = UserAccount(
        account_id=account_id or str(uuid.uuid4()),
        account_name=account_name,
        account_extension=extension,
        password=password,
        sip_ha1=sip_ha1,
        token=None,
        last_update_token=None
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

# 6. Mengambil semua user (limit 10) untuk pengujian
async def get_all_users(db: AsyncSession, limit: int = 10) -> List[UserAccount]:
    stmt = select(UserAccount).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
