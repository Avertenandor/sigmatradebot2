import sys
import inspect

print("Sys path:", sys.path)
try:
    import app
    print("App package file:", app.__file__)
    from app.services.finpass_recovery_service import FinpassRecoveryService
    print(f"Service File: {inspect.getfile(FinpassRecoveryService)}")
    print(f"Has method: {hasattr(FinpassRecoveryService, 'get_request_by_id')}")
except Exception as e:
    print(f"Error: {e}")

