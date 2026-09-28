import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.user_model import User

async def get_user_by_id(db: AsyncSession, account_id: str) -> User | None:
    """Mengambil satu data user berdasarkan ID menggunakan ORM"""
    query = sa.select(User).where(User.account_id == account_id)
    result = await db.execute(query)
    return result.scalars().first()

async def get_user_by_name(db: AsyncSession, account_name: str) -> str | None:
    """Mengambil token berdasarkan account_name"""
    query = sa.select(User.token).where(User.account_name == account_name)
    result = await db.execute(query)
    return result.scalars().first()

async def get_user_by_extension(db: AsyncSession, account_extension: str) -> User | None:
    """Mengambil satu data user berdasarkan extension menggunakan ORM"""
    query = sa.select(User).where(User.account_extension == account_extension)
    result = await db.execute(query)
    return result.scalars().first()

async def create_user(db: AsyncSession, account_name: str, password: str, account_extension: str = None) -> User:
    """Menambahkan user baru ke database (password sudah di-hash dari service)"""
    new_user = User(
        account_name=account_name,
        password=password,
        account_extension=account_extension
    )
    
    # Masukkan ke dalam sesi, simpan, dan muat ulang datanya dari DB
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

async def update_user_token_connected(db: AsyncSession, account_id: str, new_token: str) -> User | None:
    """Memperbarui token user. new_token digenerate dari service."""
    # 1. Cari dulu usernya
    user = await get_user_by_id(db, account_id)
    
    if user:
        # 2. Ubah nilainya secara langsung lewat objek (ORM)
        user.token = new_token
        user.last_update_token = sa.func.now()
        
        # 3. Simpan perubahannya
        await db.commit()
        await db.refresh(user)
        
    return user
