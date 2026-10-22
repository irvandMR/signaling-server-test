from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

# Menggunakan call_repo sebagai satu-satunya perantara ke database tabel call_logs
try:
    from services.call_repo import (
        insert_call_log,
        update_call_log,
        get_call_log_by_id,
        TERMINAL_STATES,
    )
    from model.call_log_model import CallLog
except ImportError:
    from app.services.call_repo import (
        insert_call_log,
        update_call_log,
        get_call_log_by_id,
        TERMINAL_STATES,
    )
    from app.model.call_log_model import CallLog


class CallManager:
    """
    Mengelola siklus hidup panggilan (Call Lifecycle) & logging durasi secara presisi:
    - start: Memulai panggilan (invited_at dari jam server UTC).
    - ringing: Sinyal berdering (ringing_at dari jam server UTC).
    - answered: Panggilan diangkat (answered_at dari jam server UTC).
    - end: Mengakhiri panggilan (idempotent, menghitung billsec dari jam server UTC).
    - timeout_ringing: Menutup panggilan otomatis jika berdering > 60 detik tanpa jawaban.
    """

    RINGING_TIMEOUT: int = 60  # Default batas timeout berdering (detik)

    @classmethod
    async def start(
        cls,
        db: AsyncSession,
        call_id: str,
        from_ext: str,
        to_number: str,
        direction: str = "outbound",
        sip_call_id: Optional[str] = None,
    ) -> CallLog:
        """
        Memulai panggilan baru dengan state 'invited' dan timestamp UTC server.
        """
        now = datetime.utcnow()
        return await insert_call_log(
            db=db,
            call_id=call_id,
            from_ext=from_ext,
            to_number=to_number,
            direction=direction,
            state="invited",
            sip_call_id=sip_call_id,
            invited_at=now,
        )

    @classmethod
    async def ringing(
        cls,
        db: AsyncSession,
        call_id: str,
        sip_call_id: Optional[str] = None,
    ) -> Optional[CallLog]:
        """
        Mencatat bahwa perangkat tujuan sedang berdering (ringing_at UTC server).
        """
        now = datetime.utcnow()
        return await update_call_log(
            db=db,
            call_id=call_id,
            state="ringing",
            ringing_at=now,
            sip_call_id=sip_call_id,
        )

    @classmethod
    async def answered(
        cls,
        db: AsyncSession,
        call_id: str,
        sip_call_id: Optional[str] = None,
    ) -> Optional[CallLog]:
        """
        Mencatat saat panggilan dijawab/diangkat (answered_at UTC server).
        """
        now = datetime.utcnow()
        return await update_call_log(
            db=db,
            call_id=call_id,
            state="answered",
            answered_at=now,
            sip_call_id=sip_call_id,
        )

    @classmethod
    async def end(
        cls,
        db: AsyncSession,
        call_id: str,
        reason: str = "normal",
        ended_by: str = "caller",
        sip_code: Optional[int] = 200,
    ) -> Optional[CallLog]:
        """
        Mengakhiri panggilan:
        1. IDEMPOTENT: Jika panggilan sudah ended sebelumnya, kembalikan record tanpa mengubah
           ended_at atau menghitung ulang billsec.
        2. HITUNG BILLSEC: Jika panggilan sempat dijawab (answered_at), hitung durasi bicara
           = int((ended_at - answered_at).total_seconds()). Jika belum dijawab, billsec = 0.
        """
        call = await get_call_log_by_id(db, call_id)
        if not call:
            return None

        # 1. Idempotency Check: Jika sudah berakhir, jangan ubah nilai yang sudah ada!
        if call.state in TERMINAL_STATES or call.ended_at is not None:
            return call

        # 2. Timestamp berakhir selalu dari jam server UTC saat ini
        ended_at = datetime.utcnow()

        # 3. Hitung billsec secara presisi
        if call.answered_at:
            duration = int((ended_at - call.answered_at).total_seconds())
            billsec = max(0, duration)
        else:
            billsec = 0

        # 4. Simpan perubahan ke database via call_repo
        return await update_call_log(
            db=db,
            call_id=call_id,
            state="ended",
            ended_at=ended_at,
            billsec=billsec,
            end_reason=reason,
            ended_by=ended_by,
            sip_code=sip_code,
        )

    @classmethod
    async def check_ringing_timeout(
        cls,
        db: AsyncSession,
        call_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> Optional[CallLog]:
        """
        Mengecek apakah panggilan berdering melebihi batas (default 60 detik).
        Jika melebihi batas, akhiri panggilan dengan alasan 'no_answer_timeout'.
        """
        timeout = timeout_seconds or cls.RINGING_TIMEOUT
        call = await get_call_log_by_id(db, call_id)
        if not call:
            return None

        # Hanya cek panggilan yang belum berakhir (masih ringing atau invited)
        if call.state in ("ringing", "invited"):
            ref_time = call.ringing_at or call.invited_at
            if ref_time:
                elapsed = (datetime.utcnow() - ref_time).total_seconds()
                if elapsed >= timeout:
                    return await cls.end(
                        db=db,
                        call_id=call_id,
                        reason="no_answer_timeout",
                        ended_by="system",
                        sip_code=408,  # 408 Request Timeout (standar SIP)
                    )

        return call


# Module-level aliases agar bisa dipanggil secara fungsional maupun class
start = CallManager.start
ringing = CallManager.ringing
answered = CallManager.answered
end = CallManager.end
check_ringing_timeout = CallManager.check_ringing_timeout
