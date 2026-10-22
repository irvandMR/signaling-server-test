from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from service.auth_service import login_user, register_new_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Schema request login
class LoginRequest(BaseModel):
    extension: str = Field(..., description="Nomor ekstensi SIP akun", example="11099")
    password: str = Field(..., description="Password akun", example="Pass1234")


# Schema request register user baru
class RegisterRequest(BaseModel):
    name: str = Field(..., description="Nama lengkap user/agent", example="Agent John")
    extension: str = Field(..., description="Nomor ekstensi SIP akun", example="11099")
    password: str = Field(..., description="Password akun SIP", example="Pass1234")


# Endpoint POST /auth/register
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint Tambah User Baru:
    - Membuat akun di tabel users_account.
    - Otomatis menghitung sip_ha1 = md5(ext:realm:password).
    """
    try:
        user = await register_new_user(
            db=db,
            name=req.name,
            extension=req.extension,
            password=req.password
        )
        return {
            "status": "success",
            "message": "User baru berhasil dibuat",
            "data": user
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Endpoint POST /auth/login
@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint Login Akun:
    - Memverifikasi extension & password.
    - Menghasilkan token aktif baru.
    - Otomatis mencabut (menimpa) token lama di database.
    """
    result = await login_user(
        db=db,
        extension=req.extension,
        password=req.password
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nomor ekstensi atau password salah",
        )

    return {
        "status": "success",
        "message": "Login berhasil",
        "data": result
    }
