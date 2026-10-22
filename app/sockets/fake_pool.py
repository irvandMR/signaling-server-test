import asyncio
import logging
from typing import Dict, Optional, Callable
from datetime import datetime

try:
    from core.database import AsyncSessionLocal
    from services.call_manager import CallManager
except ImportError:
    from app.core.database import AsyncSessionLocal
    from app.services.call_manager import CallManager

logger = logging.getLogger("FakePool")


class FakePool:
    """
    FakePool menggantikan SipPool untuk simulasi panggilan SIP secara terjadwal.
    
    Alur panggilan terjadwal:
    1. Setelah jeda ringing_delay detik:
       - Update status DB menjadi 'ringing' (jam server UTC)
       - Emit event 'call:ringing' ke socket pemanggil
    2. Setelah jeda answer_delay detik:
       - Update status DB menjadi 'answered' (jam server UTC)
       - Emit event 'call:answer' ke socket pemanggil
    3. Setelah jeda talk_duration detik:
       - Update status DB menjadi 'ended' (hitung billsec presisi dari jam server UTC)
       - Emit event 'call:ended' ke socket pemanggil
       - Bersihkan data panggilan aktif
    """

    def __init__(
        self,
        ringing_delay: float = 1.0,
        answer_delay: float = 2.0,
        talk_duration: float = 3.0,
    ):
        self.ringing_delay = ringing_delay
        self.answer_delay = answer_delay
        self.talk_duration = talk_duration
        self._tasks: Dict[str, asyncio.Task] = {}

    async def schedule_call(
        self,
        call_id: str,
        from_ext: str,
        to_number: str,
        sid: str,
        sio_server,
        on_cleanup: Optional[Callable[[str, str], None]] = None,
    ) -> asyncio.Task:
        """
        Menjadwalkan siklus panggilan simulasi secara background task (asyncio.Task).
        """
        task = asyncio.create_task(
            self._run_scheduled_call(
                call_id=call_id,
                from_ext=from_ext,
                to_number=to_number,
                sid=sid,
                sio_server=sio_server,
                on_cleanup=on_cleanup,
            )
        )
        self._tasks[call_id] = task
        return task

    async def _run_scheduled_call(
        self,
        call_id: str,
        from_ext: str,
        to_number: str,
        sid: str,
        sio_server,
        on_cleanup: Optional[Callable[[str, str], None]] = None,
    ):
        try:
            # -------------------------------------------------------------
            # Tahap 1: Ringing (Berdering)
            # -------------------------------------------------------------
            await asyncio.sleep(self.ringing_delay)
            async with AsyncSessionLocal() as db:
                await CallManager.ringing(db=db, call_id=call_id)

            await sio_server.emit(
                "call:ringing",
                {
                    "call_id": call_id,
                    "from_ext": from_ext,
                    "to": to_number,
                    "to_number": to_number,
                    "state": "ringing",
                },
                to=sid,
            )

            # -------------------------------------------------------------
            # Tahap 2: Answer (Diangkat / Dijawab)
            # -------------------------------------------------------------
            await asyncio.sleep(self.answer_delay)
            async with AsyncSessionLocal() as db:
                await CallManager.answered(db=db, call_id=call_id)

            await sio_server.emit(
                "call:answer",
                {
                    "call_id": call_id,
                    "from_ext": from_ext,
                    "to": to_number,
                    "to_number": to_number,
                    "state": "answered",
                },
                to=sid,
            )

            # -------------------------------------------------------------
            # Tahap 3: Ended (Panggilan Selesai Normal)
            # -------------------------------------------------------------
            await asyncio.sleep(self.talk_duration)
            async with AsyncSessionLocal() as db:
                ended_log = await CallManager.end(
                    db=db,
                    call_id=call_id,
                    reason="normal_clearing",
                    ended_by="callee",
                    sip_code=200,
                )

            billsec = ended_log.billsec if ended_log else int(self.talk_duration)
            await sio_server.emit(
                "call:ended",
                {
                    "call_id": call_id,
                    "from_ext": from_ext,
                    "to_number": to_number,
                    "state": "ended",
                    "billsec": billsec,
                    "reason": "normal_clearing",
                    "ended_by": "callee",
                },
                to=sid,
            )

        except asyncio.CancelledError:
            # Panggilan dibatalkan sebelum simulasi selesai (misalnya caller hangup)
            pass
        except Exception as e:
            logger.error(f"Error in FakePool scheduled call {call_id}: {e}", exc_info=True)
        finally:
            self._tasks.pop(call_id, None)
            if on_cleanup:
                try:
                    on_cleanup(call_id, from_ext)
                except Exception as e:
                    logger.error(f"Error executing on_cleanup for {call_id}: {e}")

    def cancel_call(self, call_id: str) -> bool:
        """
        Membatalkan background task simulasi panggilan jika panggilan di-hangup sebelum selesai.
        """
        task = self._tasks.pop(call_id, None)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_call_running(self, call_id: str) -> bool:
        """
        Mengecek apakah task panggilan tertentu sedang aktif berjalan.
        """
        task = self._tasks.get(call_id)
        return bool(task and not task.done())


# Default singleton instance FakePool
fake_pool = FakePool(
    ringing_delay=1.0,
    answer_delay=2.0,
    talk_duration=3.0,
)
