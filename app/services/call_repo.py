from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from model.call_log_model import CallLog

# Daftar status panggilan yang sudah selesai / terminal
TERMINAL_STATES = ("ended", "cancelled", "rejected", "failed", "busy", "missed")


# 1. INSERT: Menambahkan record panggilan baru saat pertama kali dimulai
async def insert_call_log(
    db: AsyncSession,
    call_id: str,
    from_ext: str,
    to_number: str,
    direction: str = "outbound",
    state: str = "invited",
    sip_call_id: Optional[str] = None,
    invited_at: Optional[datetime] = None,
) -> CallLog:
    """
    Menyimpan record panggilan baru ke tabel call_logs.
    """
    now = datetime.utcnow()
    call_log = CallLog(
        call_id=call_id,
        sip_call_id=sip_call_id,
        direction=direction,
        from_ext=from_ext,
        to_number=to_number,
        state=state,
        invited_at=invited_at or now,
        billsec=0,
    )
    db.add(call_log)
    await db.commit()
    await db.refresh(call_log)
    return call_log


# 2. UPDATE: Memperbarui status, timestamp, durasi, dan detail akhir panggilan
async def update_call_log(
    db: AsyncSession,
    call_id: str,
    state: Optional[str] = None,
    sip_call_id: Optional[str] = None,
    ringing_at: Optional[datetime] = None,
    answered_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    billsec: Optional[int] = None,
    end_reason: Optional[str] = None,
    ended_by: Optional[str] = None,
    sip_code: Optional[int] = None,
) -> Optional[CallLog]:
    """
    Memperbarui kolom panggilan yang cocok berdasarkan call_id.
    Otomatis menghitung billsec jika answered_at dan ended_at tersedia.
    """
    # 1. Ambil data call log saat ini
    stmt = select(CallLog).where(CallLog.call_id == call_id)
    result = await db.execute(stmt)
    call_log = result.scalars().first()

    if not call_log:
        return None

    # 2. Update kolom jika nilainya diberikan
    if state is not None:
        call_log.state = state
    if sip_call_id is not None:
        call_log.sip_call_id = sip_call_id
    if ringing_at is not None:
        call_log.ringing_at = ringing_at
    if answered_at is not None:
        call_log.answered_at = answered_at
    if ended_at is not None:
        call_log.ended_at = ended_at
    if end_reason is not None:
        call_log.end_reason = end_reason
    if ended_by is not None:
        call_log.ended_by = ended_by
    if sip_code is not None:
        call_log.sip_code = sip_code

    # 3. Hitung billsec otomatis jika panggilan sudah selesai dijawab
    if billsec is not None:
        call_log.billsec = billsec
    elif call_log.answered_at and call_log.ended_at and call_log.billsec == 0:
        duration = int((call_log.ended_at - call_log.answered_at).total_seconds())
        call_log.billsec = max(0, duration)

    await db.commit()
    await db.refresh(call_log)
    return call_log


# 3. CLOSE_STALE: Menutup panggilan yang 'menggantung' karena disconnect/crash/timeout
async def close_stale(
    db: AsyncSession,
    stale_reason: str = "stale_timeout",
    ended_by: str = "system",
    older_than_seconds: Optional[int] = None,
) -> int:
    """
    Menutup semua panggilan yang statusnya belum selesai (bukan ended/cancelled/rejected)
    dan menggantung.

    - older_than_seconds: Jika diberikan, hanya menutup panggilan yang di-invite lebih dari X detik lalu.
    - Mengembalikan jumlah panggilan menggantung yang berhasil ditutup.
    """
    now = datetime.utcnow()

    # Query kondisi panggilan yang belum selesai
    conditions = [CallLog.state.notin_(TERMINAL_STATES)]

    if older_than_seconds is not None:
        cutoff_time = datetime.fromtimestamp(now.timestamp() - older_than_seconds)
        conditions.append(CallLog.invited_at <= cutoff_time)

    # Eksekusi batch update
    stmt = (
        update(CallLog)
        .where(*conditions)
        .values(
            state="ended",
            ended_at=now,
            end_reason=stale_reason,
            ended_by=ended_by,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


# Helper: Mengambil satu record panggilan berdasarkan call_id
async def get_call_log_by_id(db: AsyncSession, call_id: str) -> Optional[CallLog]:
    stmt = select(CallLog).where(CallLog.call_id == call_id)
    result = await db.execute(stmt)
    return result.scalars().first()
