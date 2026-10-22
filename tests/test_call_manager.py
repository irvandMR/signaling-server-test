import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import configs
from services.call_manager import CallManager
from services.call_repo import update_call_log


@pytest.fixture
async def db_session():
    """
    Fixture database session async per-test menggunakan NullPool
    agar koneksi tidak bocor antar event-loop asyncio pytest.
    """
    test_engine = create_async_engine(configs.DATABASE, poolclass=NullPool)
    test_sessionmaker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with test_sessionmaker() as session:
        yield session
    await test_engine.dispose()


# -------------------------------------------------------------
# Test 1: Start dan Ringing dengan Timestamp UTC Server
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_call_start_and_ringing(db_session):
    call_id = f"test_start_{uuid.uuid4().hex[:8]}"
    from_ext = "11099"
    to_number = "11100"

    before_utc = datetime.utcnow() - timedelta(seconds=2)

    # 1. Start call
    call = await CallManager.start(
        db=db_session,
        call_id=call_id,
        from_ext=from_ext,
        to_number=to_number,
        direction="outbound"
    )

    after_start_utc = datetime.utcnow() + timedelta(seconds=2)

    assert call.id is not None
    assert call.call_id == call_id
    assert call.state == "invited"
    assert call.from_ext == from_ext
    assert call.to_number == to_number
    # Timestamp harus dari jam server UTC
    assert before_utc <= call.invited_at <= after_start_utc

    # 2. Ringing
    ringing_call = await CallManager.ringing(db=db_session, call_id=call_id)
    after_ringing_utc = datetime.utcnow() + timedelta(seconds=2)

    assert ringing_call.state == "ringing"
    assert ringing_call.ringing_at is not None
    assert call.invited_at <= ringing_call.ringing_at <= after_ringing_utc


# -------------------------------------------------------------
# Test 2: Answered, End, dan Perhitungan Billsec (Durasi Bicara)
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_call_answered_and_billsec_calculation(db_session):
    call_id = f"test_ans_{uuid.uuid4().hex[:8]}"

    # 1. Start & Answer
    await CallManager.start(db=db_session, call_id=call_id, from_ext="11099", to_number="11100")
    await CallManager.ringing(db=db_session, call_id=call_id)
    ans_call = await CallManager.answered(db=db_session, call_id=call_id)

    assert ans_call.state == "answered"
    assert ans_call.answered_at is not None

    # Simulasikan durasi bicara 15 detik yang lalu
    simulated_answered_at = datetime.utcnow() - timedelta(seconds=15)
    await update_call_log(db=db_session, call_id=call_id, answered_at=simulated_answered_at)

    # 2. End Call
    ended_call = await CallManager.end(
        db=db_session,
        call_id=call_id,
        reason="normal_hangup",
        ended_by="caller",
        sip_code=200
    )

    assert ended_call.state == "ended"
    assert ended_call.ended_at is not None
    assert ended_call.end_reason == "normal_hangup"
    assert ended_call.ended_by == "caller"
    # billsec harus sekitar 15 detik (toleransi 14 - 16 detik)
    assert 14 <= ended_call.billsec <= 16


# -------------------------------------------------------------
# Test 3: end() Bersifat Idempotent (Multiple Calls Aman)
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_call_end_idempotent(db_session):
    call_id = f"test_idem_{uuid.uuid4().hex[:8]}"

    await CallManager.start(db=db_session, call_id=call_id, from_ext="11099", to_number="11100")
    await CallManager.answered(db=db_session, call_id=call_id)

    # Panggilan end() pertama kali
    first_end = await CallManager.end(
        db=db_session,
        call_id=call_id,
        reason="caller_hangup",
        ended_by="caller"
    )
    first_ended_at = first_end.ended_at
    first_billsec = first_end.billsec
    first_reason = first_end.end_reason

    assert first_end.state == "ended"
    assert first_ended_at is not None

    # Panggilan end() kedua kali dengan parameter berbeda
    second_end = await CallManager.end(
        db=db_session,
        call_id=call_id,
        reason="callee_hangup_different",
        ended_by="callee"
    )

    # Panggilan end() ketiga kali
    third_end = await CallManager.end(db=db_session, call_id=call_id)

    # Nilai ended_at, billsec, dan reason TIDAK BOLEH BERUBAH (Idempotent)
    assert second_end.ended_at == first_ended_at
    assert second_end.billsec == first_billsec
    assert second_end.end_reason == first_reason
    assert third_end.ended_at == first_ended_at
    assert third_end.billsec == first_billsec


# -------------------------------------------------------------
# Test 4: Ringing Timeout 60 Detik (Auto Terminate)
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_ringing_timeout_60_seconds(db_session):
    call_id = f"test_timeout_{uuid.uuid4().hex[:8]}"

    # 1. Panggilan dimulai dan berdering
    await CallManager.start(db=db_session, call_id=call_id, from_ext="11099", to_number="11100")
    await CallManager.ringing(db=db_session, call_id=call_id)

    # A. Jika baru berdering (belum 60 detik) -> TIDAK boleh timeout
    still_ringing = await CallManager.check_ringing_timeout(
        db=db_session,
        call_id=call_id,
        timeout_seconds=60
    )
    assert still_ringing.state == "ringing"

    # B. Simulasikan panggilan berdering 65 detik yang lalu
    stale_ringing_time = datetime.utcnow() - timedelta(seconds=65)
    await update_call_log(db=db_session, call_id=call_id, ringing_at=stale_ringing_time)

    # C. Cek timeout kembali -> Harus otomatis berakhir
    timed_out_call = await CallManager.check_ringing_timeout(
        db=db_session,
        call_id=call_id,
        timeout_seconds=60
    )

    assert timed_out_call.state == "ended"
    assert timed_out_call.end_reason == "no_answer_timeout"
    assert timed_out_call.ended_by == "system"
    assert timed_out_call.sip_code == 408  # 408 Request Timeout
    assert timed_out_call.billsec == 0      # Tidak dijawab -> durasi bicara 0
