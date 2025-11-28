import sys
import os
import inspect

sys.path.append('/app')

try:
    from app.services.finpass_recovery_service import FinpassRecoveryService
    print(f"File: {inspect.getfile(FinpassRecoveryService)}")
    has_method = hasattr(FinpassRecoveryService, 'get_request_by_id')
    print(f"Has get_request_by_id: {has_method}")
except Exception as e:
    print(f"Error: {e}")

