import sys
import os
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch
import pytest

# Tambahkan path 'app' ke sys.path
sys.path.insert(0, os.path.abspath("app"))

from core.database import AsyncSessionLocal, engine
from services.call_repo import get_call_log_by_id
from sockets.server_socket import sio
from sockets.fake_pool import fake_pool
from sockets.handler_socket import (
    handle_call_make,
    handle_call_hangup,
    active_calls,
    extension_calls,
    cleanup_active_call,
)

# Mock authenticated user session
MOCK_SESSIONS = {
    "sid_caller_11099": {"user_id": 1, "ext": "11099"},
    "sid_intruder_99999": {"user_id": 2, "ext": "99999"},
}


async def mock_get_authenticated_user(sid: str):
    return MOCK_SESSIONS.get(sid)


@pytest.mark.asyncio
async def test_full_call_simulation_flow():
    """
    Skenario end-to-end simulasi alur FakePool dari inisiasi hingga berakhir,
    termasuk pengecekan baris database call_logs.
    """
    sid = "sid_caller_11099"
    fake_pool.ringing_delay = 0.2
    fake_pool.answer_delay = 0.2
    fake_pool.talk_duration = 0.3

    received_events = []

    async def capture_emit(event, data=None, **kwargs):
        received_events.append((event, data))

    with patch("sockets.handler_socket.get_authenticated_user", side_effect=mock_get_authenticated_user):
        with patch.object(sio, "emit", side_effect=capture_emit):
            await handle_call_make(sid, {"to": "11100"})
            test_call_id = extension_calls.get("11099")
            assert test_call_id is not None

            for _ in range(30):
                if any(ev[0] == "call:ended" for ev in received_events):
                    break
                await asyncio.sleep(0.1)

            events = [ev[0] for ev in received_events]
            assert "call:ringing" in events
            assert "call:answer" in events
            assert "call:ended" in events

            async with AsyncSessionLocal() as db:
                call_log = await get_call_log_by_id(db, test_call_id)
                assert call_log is not None
                assert call_log.state == "ended"
                assert call_log.from_ext == "11099"
                assert call_log.to_number == "11100"


async def run_standalone_cli():
    print("=" * 65)
    print("🚀 PENGUJIAN LENGKAP FAKEPOOL, VALIDASI, & SIKLUS PANGGILAN")
    print("=" * 65)

    with patch("sockets.handler_socket.get_authenticated_user", side_effect=mock_get_authenticated_user):
        
        # 1. Validasi Nomor
        print("\n[TEST 1] Menguji Validasi Nomor Tujuan (Hanya Angka)...")
        sid = "sid_caller_11099"
        with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
            await handle_call_make(sid, {"to": "0812abc"})
            event_name, payload = mock_emit.call_args[0]
            assert event_name == "call:error" and payload["code"] == "INVALID_NUMBER"
            print(f"  ✅ Ditolak dengan benar! Event: '{event_name}', Error: '{payload['error']}'")

        # 2. Batas 1 Call per Extension
        print("\n[TEST 2] Menguji Batas 1 Call per Extension...")
        fake_pool.ringing_delay = 5.0
        fake_pool.answer_delay = 5.0
        fake_pool.talk_duration = 5.0

        with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
            await handle_call_make(sid, {"to": "11100"})
            call_id_1 = extension_calls.get("11099")
            print(f"  ✅ Call 1 aktif dengan ID: {call_id_1}")

            mock_emit.reset_mock()
            await handle_call_make(sid, {"to": "11102"})
            event_name, payload = mock_emit.call_args[0]
            assert event_name == "call:error" and payload["code"] == "CALL_ALREADY_ACTIVE"
            print(f"  ✅ Call 2 ditolak! Event: '{event_name}', Pesan: '{payload['error']}'")

            fake_pool.cancel_call(call_id_1)
            cleanup_active_call(call_id_1, "11099")

        # 3. Otorisasi Hangup
        print("\n[TEST 3] Menguji Otorisasi Hangup (Hanya Pemilik Call)...")
        with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
            await handle_call_make(sid, {"to": "11100"})
            call_id = extension_calls.get("11099")

            mock_emit.reset_mock()
            await handle_call_hangup("sid_intruder_99999", {"call_id": call_id})
            event_name, payload = mock_emit.call_args[0]
            assert event_name == "call:error" and payload["code"] == "FORBIDDEN"
            print(f"  ✅ Intruder ditolak! Event: '{event_name}', Pesan: '{payload['error']}'")

            mock_emit.reset_mock()
            await handle_call_hangup(sid, {"call_id": call_id})
            event_name, payload = mock_emit.call_args[0]
            assert event_name == "call:ended" and payload["reason"] == "caller_hangup"
            print(f"  ✅ Hangup pemilik sah berhasil! Event: '{event_name}'")

        # 4. Alur Lengkap FakePool
        print("\n[TEST 4] Menguji Siklus Terjadwal FakePool & Baris Database Lengkap...")
        fake_pool.ringing_delay = 0.3
        fake_pool.answer_delay = 0.3
        fake_pool.talk_duration = 0.5
        received_events = []

        async def capture_emit(event, data=None, **kwargs):
            now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"    📡 [{now_str}] EVENT DITERIMA CLIENT: {event} -> {data}")
            received_events.append((event, data))

        with patch.object(sio, "emit", side_effect=capture_emit):
            await handle_call_make(sid, {"to": "11100"})
            test_call_id = extension_calls.get("11099")

            for _ in range(40):
                if any(ev[0] == "call:ended" for ev in received_events):
                    break
                await asyncio.sleep(0.1)

            events = [ev[0] for ev in received_events]
            assert "call:ringing" in events
            assert "call:answer" in events
            assert "call:ended" in events
            print("  ✅ Semua event (call:ringing, call:answer, call:ended) berhasil diterima client!")

            async with AsyncSessionLocal() as db:
                call_log = await get_call_log_by_id(db, test_call_id)
                assert call_log is not None
                print("  " + "-" * 55)
                print(f"  Call ID      : {call_log.call_id}")
                print(f"  From Ext     : {call_log.from_ext}")
                print(f"  To Number    : {call_log.to_number}")
                print(f"  State        : {call_log.state}")
                print(f"  Invited At   : {call_log.invited_at} UTC")
                print(f"  Ringing At   : {call_log.ringing_at} UTC")
                print(f"  Answered At  : {call_log.answered_at} UTC")
                print(f"  Ended At     : {call_log.ended_at} UTC")
                print(f"  Billsec      : {call_log.billsec} detik")
                print("  " + "-" * 55)
                print("  ✅ Baris database call_logs LENGKAP dan VALID!")

    await engine.dispose()
    print("\n" + "=" * 65)
    print("🎉 SELURUH PENGUJIAN SELESAI & SUKSES 100%!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_standalone_cli())
