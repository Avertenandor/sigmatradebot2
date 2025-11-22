"""Final test execution script."""
import subprocess
import sys
from pathlib import Path

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

out = Path("TEST_RESULTS.txt")

with open(out, "w", encoding="utf-8") as f:
    f.write("TEST EXECUTION\n" + "="*80 + "\n\n")
    
    p = 0
    fl = 0
    
    for i, t in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {t}")
        f.write(f"\n[{i}/{len(tests)}] {t}\n{'='*80}\n")
        f.flush()
        
        r = subprocess.run(
            [sys.executable, "-m", "pytest", t, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        f.write(r.stdout)
        if r.stderr:
            f.write(f"\nSTDERR:\n{r.stderr}")
        
        if r.returncode == 0:
            p += 1
            f.write("\n✅ PASSED\n")
        else:
            fl += 1
            f.write(f"\n❌ FAILED ({r.returncode})\n")
        
        f.flush()
    
    f.write(f"\n{'='*80}\nSUMMARY: {p} passed, {fl} failed\n{'='*80}\n")

print(f"\nResults: {p} passed, {fl} failed")
print(f"Saved to: {out}")

