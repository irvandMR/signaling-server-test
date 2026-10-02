import logging
import asyncio
import types

# Patch untuk library aiosip (karena menggunakan fitur lama dari Python < 3.11)
if not hasattr(asyncio, "coroutine"):
    def coroutine(func):
        return func
    asyncio.coroutine = coroutine
    asyncio.iscoroutine = asyncio.iscoroutinefunction

import aiosip

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
        # local_addr port menggunakan 5061 (atau 0 untuk random) agar tidak menabrak port 5060 milik Asterisk di server yang sama
        dialog = await app.start_dialog(
            local_addr=('0.0.0.0', 5061),
            remote_addr=(PBX_IP, PBX_PORT),
            from_uri=my_contact,
            to_uri=target_contact
            # Catatan: Jika Asterisk Anda meminta otentikasi password, kita harus menambahkan parameter password di sini.
        )
        
        log.info(f"Mengirim SIP INVITE ke Asterisk...")
        
        # 3. Tembak SIP INVITE dengan menyisipkan SDP mentah dari klien Socket.IO
        response = await dialog.invite(payload=sdp_offer, content_type="application/sdp")
        
        # 4. Tangkap balasan dari Asterisk
        if response.status_code == 200:
            log.info("Menerima SIP 200 OK dari Asterisk!")
            # Ambil SDP Answer dari badan pesan (payload) SIP
            sdp_answer = response.payload
            
            # Simpan dialog agar kita bisa memutus telepon (mengirim SIP BYE) nantinya
            active_sip_calls[caller_extension] = dialog
            
            return {"status": "success", "sdp": sdp_answer}
        else:
            log.error(f"Asterisk menolak: {response.status_code}")
            return {"status": "error", "message": f"Ditolak Asterisk: {response.status_code}"}
            
    except Exception as e:
        log.error(f"Gagal melakukan SIP INVITE: {e}")
        return {"status": "error", "message": str(e)}
