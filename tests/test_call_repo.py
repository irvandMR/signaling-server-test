import uuid
from datetime import datetime, timedelta
import pytest
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import configs
from services.call_repo import (
    insert_call_log,
    update_call_log,
    close_stale,
    get_call_log_by_id,
)


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
        expire_on_commit=False,
    )
    async with test_sessionmaker() as session:
        yield session
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_insert_call_log(db_session):
    test_call_id = f"test_insert_{uuid.uuid4().hex[:8]}"
    call = await insert_call_log(
        db=db_session,
        call_id=test_call_id,
        from_ext="11099",
        to_number="11100",
        direction="outbound",
        state="invited",
    )
    assert call.id is not None
    assert call.call_id == test_call_id
    assert call.state == "invited"
    assert call.from_ext == "11099"
    assert call.to_number == "11100"


@pytest.mark.asyncio
async def test_update_call_log_and_billsec(db_session):
    test_call_id = f"test_update_{uuid.uuid4().hex[:8]}"
    await insert_call_log(
        db=db_session,
        call_id=test_call_id,
        from_ext="11099",
        to_number="11100",
        direction="outbound",
        state="invited",
    )

    now = datetime.utcnow()
    answered = now + timedelta(seconds=2)
    ended = now + timedelta(seconds=12)

    updated = await update_call_log(
        db=db_session,
        call_id=test_call_id,
        state="ended",
        answered_at=answered,
        ended_at=ended,
        end_reason="caller_hangup",
        ended_by="caller",
        sip_code=200,
    )
    assert updated is not None
    assert updated.state == "ended"
    assert updated.billsec == 10  # 12 detik - 2 detik
    assert updated.end_reason == "caller_hangup"
    assert updated.ended_by == "caller"


@pytest.mark.asyncio
async def test_close_stale_calls(db_session):
    stale_call_id = f"stale_{uuid.uuid4().hex[:8]}"
    await insert_call_log(
        db=db_session,
        call_id=stale_call_id,
        from_ext="11099",
        to_number="11102",
        state="ringing",
    )
    closed_count = await close_stale(db_session, stale_reason="cleanup_stale_test")
    assert closed_count >= 1

    check_stale = await get_call_log_by_id(db_session, stale_call_id)
    assert check_stale is not None
    assert check_stale.state == "ended"
    assert check_stale.end_reason == "cleanup_stale_test"
