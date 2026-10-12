from pydantic import Field
from pydantic import BaseModel
from datetime import datetime

class PBXReceiverReq(BaseModel): 
    task_id : str
    receive_date : datetime
    from_phone_number : str
    to_extension : str
    callback_ip : str



class PBXReceiverResp(BaseModel):
    call_to_agent :str
    call_from :str
    