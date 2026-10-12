from app.dto.base_response import SuccessResponse
from app.model.user_model import UserCreateRequest
from fastapi import APIRouter, HTTPException
from app.service.user_service import register_new_user

user_router = APIRouter(prefix="/user", tags=["user"])


@user_router.post("/new")
async def add_new_user(req: UserCreateRequest):
    try:
        # Panggil service registrasi (koneksi DB otomatis ter-handle oleh @with_db di service)
        new_user = await register_new_user(
            account_name=req.account_name,
            plain_password=req.password,
            account_extension=req.account_extension
        )
        
        return SuccessResponse(
            message="User berhasil dibuat",
            data={
                "account_id": new_user.account_id,
                "account_name": new_user.account_name,
                "account_extension": new_user.account_extension
            }
        ).to_response()
    except Exception as e:
        # Tangkap error (misalnya kalau account_id sudah ada di DB / duplikat)
        raise HTTPException(status_code=400, detail=f"Gagal membuat user: {str(e)}")
