"""Execute all tests."""
import subprocess
import sys

tests = [
    "tests/unit/test_settings.py",
    "tests/unit/test_main_menu_keyboard.py",
    "tests/unit/test_deposit_validation_service.py",
    "tests/unit/test_withdrawal_service.py",
    "tests/unit/test_referral_service.py",
    "tests/unit/models/test_user.py",
    "tests/unit/models/test_deposit.py",
    "tests/unit/models/test_transaction.py",
    "tests/unit/models/test_referral.py",
    "tests/unit/models/test_referral_earning.py",
    "tests/unit/repositories/test_user_repository.py",
    "tests/unit/repositories/test_deposit_repository.py",
    "tests/unit/repositories/test_transaction_repository.py",
    "tests/unit/services/test_user_service.py",
    "tests/unit/services/test_transaction_service.py",
    "tests/unit/services/test_reward_service.py",
    "tests/unit/services/test_deposit_service.py",
]

if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "pytest"] + tests + ["-v"])

