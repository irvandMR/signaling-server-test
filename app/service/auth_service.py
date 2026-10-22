import hashlib
import secrets
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from repository.users_account_repository import (
    get_user_by_token,
    get_user_by_extension,
    update_user_token,
    create_user_account,
)
from core.config import configs


# 1. Membuat token statis/acak (bukan JWT)
def create_token(prefix: str = "tok_") -> str:
    """
    Menghasilkan token acak sederhana tanpa JWT.
    Bisa juga disesuaikan jika ingin mengembalikan token statis tertentu.
    """
    random_hex = secrets.token_hex(20)
    return f"{prefix}{random_hex}"


# Helper untuk menghitung digest SIP HA1: md5(ext:realm:password)
def generate_sip_ha1(ext: str, realm: str, password: str) -> str:
    """
    Menghitung hash MD5 untuk Asterisk SIP Digest Auth:
    sip_ha1 = md5(extension:realm:password)
    """
    raw = f"{ext}:{realm}:{password}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# 2. Verifikasi Password
def verify_password(
    plain_password: str,
    user_password: Optional[str] = None,
    ext: Optional[str] = None,
    sip_ha1: Optional[str] = None,
    realm: Optional[str] = None
) -> bool:
    """
    Memverifikasi kecocokan password:
    1. Cek langsung kecocokan plain_password dengan user_password jika ada.
    2. Atau verifikasi kecocokan via digest sip_ha1 = md5(ext:realm:plain_password).
    """
    # Verifikasi langsung jika ada kolom password
    if user_password and plain_password == user_password:
        return True

    # Verifikasi berbasis digest sip_ha1 jika tersedia
    if sip_ha1 and ext:
        target_realm = realm or configs.SIP_DOMAIN or "asterisk"
        computed_ha1 = generate_sip_ha1(ext, target_realm, plain_password)
        if computed_ha1.lower() == sip_ha1.lower():
            return True

    return False


# 3. Verifikasi Token Socket (+ Cocokkan dengan kolom token di DB)
async def verify_socket_token(db: AsyncSession, token: str) -> Optional[Dict[str, Any]]:
    """
    Mencocokkan token dengan kolom 'token' di tabel users_account.
    Hasil jika valid:
        {
            "user_id": ...,
            "ext": ...,
            "sip_ha1": ...
        }
    Jika tidak valid / tidak ditemukan:
        None
    """
    if not token or not token.strip():
        return None

    # Cari user di database berdasarkan token
    user = await get_user_by_token(db, token.strip())
    if not user:
        return None

    # Mengembalikan hasil sesuai ekspektasi: user_id, ext, sip_ha1
    return {
        "user_id": user.account_id,
        "ext": user.account_extension,
        "sip_ha1": user.sip_ha1
    }


# 4. Login User (Satu Token Aktif: Login Baru Mencabut Token Lama)
async def login_user(
    db: AsyncSession, 
    extension: str, 
    password: str
) -> Optional[Dict[str, Any]]:
    """
    Alur Login:
    1. Cari akun berdasarkan nomor extension (ekstensi SIP).
    2. Verifikasi password (plain text atau cocok dengan digest sip_ha1).
    3. Buat token baru jika kredensial cocok.
    4. Simpan token baru ke database (otomatis menimpa & MENCABUT token lama).
    5. Mengembalikan data user_id, ext, sip_ha1, dan token aktif baru.
    """
    if not extension or not password:
        return None

    # 1. Cari user berdasarkan nomor extension
    user = await get_user_by_extension(db, extension.strip())
    if not user:
        return None

    # 2. Verifikasi kecocokan password
    is_valid = verify_password(
        plain_password=password,
        user_password=user.password,
        ext=user.account_extension,
        sip_ha1=user.sip_ha1
    )
    if not is_valid:
        return None

    # 3. Generate token aktif baru
    new_token = create_token()

    # 4. Simpan ke database (menimpa token lama di kolom 'token')
    success = await update_user_token(db, user.account_id, new_token)
    if not success:
        return None

    # 5. Return hasil login
    return {
        "user_id": user.account_id, 
        "name": user.account_name,
        "ext": user.account_extension,
        "sip_ha1": user.sip_ha1,
        "token": new_token
    }


# 5. Pendaftaran / Insert User Baru Lewat Kode
async def register_new_user(
    db: AsyncSession,
    name: str,
    extension: str,
    password: str
) -> Dict[str, Any]:
    """
    Membuat user baru:
    1. Mengecek apakah extension sudah terdaftar.
    2. Menghitung sip_ha1 otomatis: md5(ext:realm:password).
    3. Menyimpan data ke tabel users_account.
    """
    # Cek duplikasi nomor extension
    existing_user = await get_user_by_extension(db, extension.strip())
    if existing_user:
        raise ValueError(f"Ekstensi {extension} sudah terdaftar.")

    # Hitung sip_ha1
    realm = configs.SIP_DOMAIN or "asterisk"
    sip_ha1 = generate_sip_ha1(extension.strip(), realm, password)

    # Simpan ke tabel users_account
    user = await create_user_account(
        db=db,
        account_name=name.strip(),
        extension=extension.strip(),
        password=password,
        sip_ha1=sip_ha1
    )

    return {
        "user_id": user.account_id,
        "name": user.account_name,
        "ext": user.account_extension,
        "sip_ha1": user.sip_ha1
    }
