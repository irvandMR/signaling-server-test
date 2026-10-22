# Services package
from services.call_repo import insert_call_log, update_call_log, close_stale, get_call_log_by_id

__all__ = ["insert_call_log", "update_call_log", "close_stale", "get_call_log_by_id"]
