import sys
import os

# Add /app to sys.path to ensure imports work
sys.path.append('/app')

try:
    from app.services.finpass_recovery_service import FinpassRecoveryService
    has_method = hasattr(FinpassRecoveryService, 'get_request_by_id')
    print(f"Has get_request_by_id: {has_method}")
    
    if has_method:
        print("Method detected successfully.")
    else:
        print("Method NOT detected.")
        print("Dir:", dir(FinpassRecoveryService))
except Exception as e:
    print(f"Error importing: {e}")

