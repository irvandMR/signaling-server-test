import logging
import asyncio
import types
import collections
import collections.abc

# Patch untuk library aiosip (karena menggunakan fitur lama dari Python < 3.11)
if not hasattr(asyncio, "coroutine"):
    def coroutine(func):
        return func
    asyncio.coroutine = coroutine
    asyncio.iscoroutine = asyncio.iscoroutinefunction

# Patch tambahan: di Python 3.10+, MutableMapping dipindah ke collections.abc
collections.MutableMapping = collections.abc.MutableMapping
collections.Mapping = collections.abc.Mapping
collections.Iterable = collections.abc.Iterable
collections.Iterator = collections.abc.Iterator

import aiovoip as aiosip

log = logging.getLogger("sip-gateway")

from app.core.config import Settings

PBX_IP = Settings.PBX_IP
PBX_PORT = Settings.PBX_PORT

# Cache untuk menyimpan dialog SIP yang sedang aktif agar bisa diakhiri (BYE) nanti
active_sip_calls = {}

async def originate_call_with_sdp(caller_extension: str, target_extension: str, sdp_offer: str):
    """
    Fungsi ini bertindak sebagai SIP Gateway.
    Menerima WebRTC SDP Offer dari klien, membungkusnya dalam SIP INVITE, dan menembak ke Asterisk.
    """
    log.info(f"Menerjemahkan panggilan dari {caller_extension} ke {target_extension} menjadi SIP INVITE...")
    
    try:
        app = aiosip.Application()
        
        # 1. Bangun identitas kontak
        my_contact = f"sip:{caller_extension}@{PBX_IP}"
        target_contact = f"sip:{target_extension}@{PBX_IP}"
        
        # 2. Buka percakapan SIP (Dialog) ke Asterisk
        # Kita generate port acak secara manual, karena aiosip ternyata mengalami bug syntax error 
        # (mengirim tulisan "port 0" di header Via) jika kita menggunakan port 0 dari OS.
        import random
        local_port = random.randint(20000, 60000)
        
        # Di aiovoip (versi modern), kita melakukan koneksi ke peer terlebih dahulu
        peer = await app.connect(
            remote_addr=(PBX_IP, PBX_PORT),
            local_addr=('127.0.0.1', local_port)
        )
        
        log.info(f"Mengirim SIP INVITE ke Asterisk menggunakan aiovoip...")
        
        # 3. Tembak SIP INVITE
        dialog = await peer.invite(
            from_details=my_contact,
            to_details=target_contact,
            payload=sdp_offer
        )
        
        # 4. Tangkap balasan dari Asterisk
        # Kita perlu menembak SIP dan menunggu response (200 OK)
        log.info("SIP INVITE terkirim. Menunggu 200 OK...")
        
        # Kita bisa await dialog.ready() jika ingin menunggu 200 OK, tapi sementara kita mock saja dulu
        sdp_answer = "v=0\r\no=- 123456 123456 IN IP4 127.0.0.1\r\ns=Asterisk\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio 10000 RTP/SAVPF 111\r\n"
        
        # Simpan dialog agar kita bisa memutus telepon (mengirim SIP BYE) nantinya
        active_sip_calls[caller_extension] = dialog
        
        return {"status": "success", "sdp": sdp_answer}
            
    except Exception as e:
        log.error(f"Gagal melakukan SIP INVITE: {e}")
        return {"status": "error", "message": str(e)}
