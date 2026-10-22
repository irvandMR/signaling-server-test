from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from core.database import Base


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    call_id = Column(String(64), nullable=False, unique=True, index=True)
    sip_call_id = Column(String(128), nullable=True, index=True)
    direction = Column(String(30), nullable=False)  # Contoh: 'inbound' / 'outbound'
    from_ext = Column(String(20), nullable=False, index=True)
    to_number = Column(String(30), nullable=False, index=True)
    state = Column(String(30), nullable=False)  # Contoh: 'ringing', 'answered', 'ended', 'busy'
    
    # Timestamp proses panggilan
    invited_at = Column(DateTime, nullable=True)
    ringing_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Durasi & Detail Akhir Panggilan
    billsec = Column(Integer, default=0, nullable=True)  # Durasi bicara dalam detik
    end_reason = Column(String(50), nullable=True)      # Alasan berakhir (misal: 'caller_hangup', 'callee_reject')
    ended_by = Column(String(30), nullable=True)        # Siapa yang mematikan ('caller' / 'callee' / 'system')
    sip_code = Column(Integer, nullable=True)           # SIP Status Code (misal: 200, 486 Busy, 487 Cancelled)

    # Audit timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<CallLog id={self.id} call_id={self.call_id} from={self.from_ext} to={self.to_number} state={self.state}>"

    def to_dict(self):
        return {
            "id": self.id,
            "call_id": self.call_id,
            "sip_call_id": self.sip_call_id,
            "direction": self.direction,
            "from_ext": self.from_ext,
            "to_number": self.to_number,
            "state": self.state,
            "invited_at": self.invited_at.isoformat() if self.invited_at else None,
            "ringing_at": self.ringing_at.isoformat() if self.ringing_at else None,
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "billsec": self.billsec,
            "end_reason": self.end_reason,
            "ended_by": self.ended_by,
            "sip_code": self.sip_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }