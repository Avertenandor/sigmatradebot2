#!/usr/bin/env python3
"""Run all unit tests."""
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

print("=" * 80)
print("RUNNING ALL TESTS")
print("=" * 80)

passed = 0
failed = 0

for i, test_file in enumerate(tests, 1):
    print(f"\n[{i}/{len(tests)}] {test_file}")
    print("-" * 80)
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
        capture_output=False
    )
    
    if result.returncode == 0:
        passed += 1
        print(f"✅ PASSED")
    else:
        failed += 1
        print(f"❌ FAILED")

print("\n" + "=" * 80)
print(f"SUMMARY: {passed} passed, {failed} failed out of {len(tests)}")
print("=" * 80)

sys.exit(0 if failed == 0 else 1)

