"""Run all tests and generate report - fixed version."""
import subprocess
import sys
from pathlib import Path
from datetime import datetime

test_files = [
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

results_file = Path("FINAL_TEST_REPORT.txt")

print("=" * 80)
print("RUNNING ALL UNIT TESTS")
print("=" * 80)
print()

with open(results_file, "w", encoding="utf-8") as f:
    f.write("=" * 80 + "\n")
    f.write(f"FINAL TEST EXECUTION REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("=" * 80 + "\n\n")
    
    passed_files = 0
    failed_files = 0
    total_tests_passed = 0
    total_tests_failed = 0
    
    for i, test_file in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] {test_file}")
        f.write(f"\n{'='*80}\n")
        f.write(f"[{i}/{len(test_files)}] {test_file}\n")
        f.write('='*80 + "\n\n")
        f.flush()
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300
            )
            
            f.write(result.stdout)
            if result.stderr:
                f.write("\n\nSTDERR:\n" + result.stderr)
            
            # Parse test results
            output_lines = result.stdout.split('\n')
            passed = 0
            failed = 0
            
            for line in output_lines:
                if ' passed' in line.lower() and 'failed' in line.lower():
                    import re
                    nums = re.findall(r'\d+', line)
                    if len(nums) >= 2:
                        passed = int(nums[0])
                        failed = int(nums[1])
                        break
            
            if result.returncode == 0:
                passed_files += 1
                total_tests_passed += passed
                status = f"PASSED ({passed} tests)"
                print(f"  PASSED ({passed} tests)")
            else:
                failed_files += 1
                total_tests_failed += failed
                status = f"FAILED (exit code: {result.returncode}, {failed} failed)"
                print(f"  FAILED ({failed} failed)")
            
            f.write(f"\n{status}\n")
            f.flush()
            
        except subprocess.TimeoutExpired:
            failed_files += 1
            status = "TIMEOUT (exceeded 5 minutes)"
            f.write(f"\n{status}\n")
            print(f"  TIMEOUT")
            f.flush()
        except Exception as e:
            failed_files += 1
            status = f"ERROR: {str(e)}"
            f.write(f"\n{status}\n")
            print(f"  ERROR: {e}")
            f.flush()
    
    # Summary
    f.write("\n" + "=" * 80 + "\n")
    f.write("SUMMARY\n")
    f.write("=" * 80 + "\n")
    f.write(f"Test files: {len(test_files)}\n")
    f.write(f"  Passed: {passed_files}\n")
    f.write(f"  Failed: {failed_files}\n\n")
    f.write(f"Total tests executed: {total_tests_passed + total_tests_failed}\n")
    f.write(f"  Passed: {total_tests_passed}\n")
    f.write(f"  Failed: {total_tests_failed}\n")
    f.write("=" * 80 + "\n")

print("\n" + "=" * 80)
print("EXECUTION COMPLETED")
print("=" * 80)
print(f"Test files: {passed_files} passed, {failed_files} failed")
print(f"Total tests: {total_tests_passed} passed, {total_tests_failed} failed")
print(f"\nDetailed report: {results_file}")

