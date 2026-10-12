from app.core.config import Settings
from app.dto.pbx_receiver_dto import PBXReceiverResp, PBXReceiverReq
from app.dto.base_response import SuccessResponse
from app.handler.custome_exception import AppException
from fastapi import APIRouter

client_router = APIRouter(prefix="/external", tags=["client"])
internal_ip = Settings.PBX_IP


@client_router.post("/pbx/receiver", response_model=SuccessResponse[PBXReceiverResp])
async def receive_call_from_external(request: PBXReceiverReq):
    try:
        from app.socket.sockets import sio, connected
        print("Received payload:", request.model_dump())
        call_to = f"sip:{request.to_extension}@{internal_ip}"
        call_from = f"sip:{request.from_phone_number}@{request.callback_ip}"
        resp_data = PBXReceiverResp(call_to_agent=call_to, call_from=call_from)
        
        # Mengecek apakah agen (extension) sedang terhubung ke websocket
        target_sid = connected.get(request.to_extension)
        if target_sid:
            print(f"Mengirim notifikasi panggilan ke extension {request.to_extension} (SID: {target_sid})")
            # Emit event "incoming_call" khusus ke agent tersebut (room=target_sid)
            await sio.emit("incoming_call", {
                "task_id": request.task_id,
                "call_from": call_from,
                "call_to": call_to,
                "receive_date": request.receive_date.isoformat()
            }, room=target_sid)
        else:
            print(f"Extension {request.to_extension} sedang offline.")

        return SuccessResponse(is_success=True, code=200, message="Success", data=resp_data)
        
    except Exception as e:
        print("Error:", e)
        raise AppException(status_code=500, message="Error processing request", errors=str(e))