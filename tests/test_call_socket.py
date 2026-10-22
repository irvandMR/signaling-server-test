import uuid
import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import configs
from services.call_repo import get_call_log_by_id
from sockets.server_socket import sio
from sockets.fake_pool import fake_pool, FakePool
from sockets.handler_socket import (
    handle_call_make,
    handle_call_hangup,
    active_calls,
    extension_calls,
    cleanup_active_call,
)

# Peta session terotentikasi untuk unit testing
SESSION_MAP = {
    "sid_test_val": {"user_id": 1, "ext": "11099"},
    "sid_test_concurrency": {"user_id": 1, "ext": "11099"},
    "sid_test_fakepool": {"user_id": 1, "ext": "11099"},
    "sid_owner": {"user_id": 1, "ext": "11099"},
    "sid_intruder": {"user_id": 2, "ext": "99999"},
}


async def mock_get_authenticated_user(sid: str):
    return SESSION_MAP.get(sid)


@pytest.fixture(autouse=True)
async def setup_test_db_and_clean_state():
    """
    Fixture database async per-test menggunakan NullPool
    agar koneksi tidak bocor atau menempel pada event-loop yang sudah ditutup.
    """
    active_calls.clear()
    extension_calls.clear()

    test_engine = create_async_engine(configs.DATABASE, poolclass=NullPool)
    test_sessionmaker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    with patch("sockets.handler_socket.AsyncSessionLocal", test_sessionmaker), \
         patch("sockets.fake_pool.AsyncSessionLocal", test_sessionmaker):
        yield test_sessionmaker

    active_calls.clear()
    extension_calls.clear()
    await test_engine.dispose()


# ---------------------------------------------------------------------------
# Test 1: Validasi Nomor Tujuan (Hanya Angka)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_number_validation_only_digits():
    sid = "sid_test_val"

    with patch("sockets.handler_socket.get_authenticated_user", side_effect=mock_get_authenticated_user):
        with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
            # 1. Nomor mengandung huruf -> harus ditolak
            await handle_call_make(sid, {"to": "11100abc"})
            mock_emit.assert_called_once()
            args = mock_emit.call_args[0]
            assert args[0] == "call:error"
            assert args[1]["code"] == "INVALID_NUMBER"

            mock_emit.reset_mock()

            # 2. Nomor mengandung simbol (+62) -> harus ditolak karena hanya angka
            await handle_call_make(sid, {"to": "+628123456"})
            mock_emit.assert_called_once()
            args = mock_emit.call_args[0]
            assert args[0] == "call:error"
            assert args[1]["code"] == "INVALID_NUMBER"

            mock_emit.reset_mock()

            # 3. Nomor kosong -> harus ditolak
            await handle_call_make(sid, {"to": ""})
            mock_emit.assert_called_once()
            args = mock_emit.call_args[0]
            assert args[0] == "call:error"
            assert args[1]["code"] == "INVALID_NUMBER"

            # Pastikan tidak ada panggilan yang terdaftar di active_calls
            assert len(active_calls) == 0
            assert len(extension_calls) == 0


# ---------------------------------------------------------------------------
# Test 2: Batas 1 Call per Extension
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_limit_one_call_per_extension():
    sid = "sid_test_concurrency"
    ext = "11099"

    # Konfigurasi fake_pool dengan delay cukup lama agar panggilan tetap aktif
    fake_pool.ringing_delay = 5.0
    fake_pool.answer_delay = 5.0
    fake_pool.talk_duration = 5.0

    with patch("sockets.handler_socket.get_authenticated_user", side_effect=mock_get_authenticated_user):
        with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
            # Panggilan pertama: harus berhasil di-initiate
            await handle_call_make(sid, {"to": "11100"})
            assert ext in extension_calls
            call_id_1 = extension_calls[ext]
            assert call_id_1 in active_calls

            mock_emit.reset_mock()

            # Panggilan kedua saat panggilan pertama masih aktif: harus ditolak
            await handle_call_make(sid, {"to": "11102"})
            mock_emit.assert_called_once()
            event_name, payload = mock_emit.call_args[0]
            assert event_name == "call:error"
            assert payload["code"] == "CALL_ALREADY_ACTIVE"
            assert payload["active_call_id"] == call_id_1

            # Batalkan panggilan pertama untuk membersihkan
            fake_pool.cancel_call(call_id_1)
            cleanup_active_call(call_id_1, ext)


# ---------------------------------------------------------------------------
# Test 3: FakePool Terjadwal (call:ringing, call:answer, call:ended) & Call Log Lengkap
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fakepool_scheduled_events_and_db_row(setup_test_db_and_clean_state):
    test_sessionmaker = setup_test_db_and_clean_state
    sid = "sid_test_fakepool"
    ext = "11099"
    to_number = "11100"

    # Atur delay cepat untuk testing (total ~0.35 detik)
    fake_pool.ringing_delay = 0.1
    fake_pool.answer_delay = 0.1
    fake_pool.talk_duration = 0.15

    emitted_events = []

    async def fake_emit(event, data=None, **kwargs):
        emitted_events.append((event, data))

    with patch("sockets.handler_socket.get_authenticated_user", side_effect=mock_get_authenticated_user):
        with patch.object(sio, "emit", side_effect=fake_emit):
            await handle_call_make(sid, {"to": to_number})
            call_id = extension_calls[ext]

            # Tunggu sampai siklus FakePool selesai secara dinamis (maksimal 3 detik)
            for _ in range(30):
                if any(ev[0] == "call:ended" for ev in emitted_events):
                    break
                await asyncio.sleep(0.1)

            # 1. Verifikasi Urutan Event yang Diterima Client:
            # call:invited -> call:ringing -> call:answer -> call:ended
            event_names = [ev[0] for ev in emitted_events]
            assert "call:invited" in event_names
            assert "call:ringing" in event_names
            assert "call:answer" in event_names
            assert "call:ended" in event_names

            # Cek detail payload event call:ended
            ended_payload = next(data for ev, data in emitted_events if ev == "call:ended")
            assert ended_payload["call_id"] == call_id
            assert ended_payload["state"] == "ended"
            assert ended_payload["reason"] == "normal_clearing"
            assert ended_payload["ended_by"] == "callee"
            assert "billsec" in ended_payload

            # 2. Verifikasi Baris Database call_logs Lengkap
            async with test_sessionmaker() as db:
                call_log = await get_call_log_by_id(db, call_id)
                assert call_log is not None
                assert call_log.call_id == call_id
                assert call_log.from_ext == ext
                assert call_log.to_number == to_number
                assert call_log.state == "ended"
                assert call_log.direction == "outbound"
                assert call_log.invited_at is not None
                assert call_log.ringing_at is not None
                assert call_log.answered_at is not None
                assert call_log.ended_at is not None
                assert call_log.end_reason == "normal_clearing"
                assert call_log.ended_by == "callee"
                assert call_log.sip_code == 200

            # In-memory tracking harus sudah bersih
            assert call_id not in active_calls
            assert ext not in extension_calls


# ---------------------------------------------------------------------------
# Test 4: Hangup Hanya Boleh oleh Pemilik Call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hangup_authorized_only_by_owner(setup_test_db_and_clean_state):
    test_sessionmaker = setup_test_db_and_clean_state
    sid_owner = "sid_owner"
    sid_intruder = "sid_intruder"

    ext_owner = "11099"
    ext_intruder = "99999"

    # Set delay cukup lama agar panggilan tetap aktif
    fake_pool.ringing_delay = 5.0
    fake_pool.answer_delay = 5.0
    fake_pool.talk_duration = 5.0

    with patch("sockets.handler_socket.get_authenticated_user", side_effect=mock_get_authenticated_user):
        with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
            # 1. Owner memulai panggilan
            await handle_call_make(sid_owner, {"to": "11100"})
            call_id = extension_calls[ext_owner]
            assert call_id is not None

            mock_emit.reset_mock()

            # 2. Pengguna lain (intruder) mencoba hangup panggilan milik owner
            await handle_call_hangup(sid_intruder, {"call_id": call_id})

            # Harus ditolak dengan kode FORBIDDEN
            mock_emit.assert_called_once()
            event_name, payload = mock_emit.call_args[0]
            assert event_name == "call:error"
            assert payload["code"] == "FORBIDDEN"
            assert "bukan pemilik" in payload["error"]

            # Panggilan harus masih tetap aktif!
            assert call_id in active_calls
            assert extension_calls[ext_owner] == call_id

            mock_emit.reset_mock()

            # 3. Sekarang owner sah melakukan hangup
            await handle_call_hangup(sid_owner, {"call_id": call_id})

            # Harus berhasil emit call:ended
            mock_emit.assert_called_once()
            event_name, payload = mock_emit.call_args[0]
            assert event_name == "call:ended"
            assert payload["call_id"] == call_id
            assert payload["reason"] == "caller_hangup"
            assert payload["ended_by"] == "caller"

            # Panggilan dibersihkan dari in-memory
            assert call_id not in active_calls
            assert ext_owner not in extension_calls

            # Cek database
            async with test_sessionmaker() as db:
                call_log = await get_call_log_by_id(db, call_id)
                assert call_log.state == "ended"
                assert call_log.end_reason == "caller_hangup"
                assert call_log.ended_by == "caller"
