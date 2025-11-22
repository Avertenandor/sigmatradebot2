"""Execute all tests and generate comprehensive report."""
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

test_files = [
    ("1", "tests/unit/test_settings.py"),
    ("2", "tests/unit/test_main_menu_keyboard.py"),
    ("3", "tests/unit/test_deposit_validation_service.py"),
    ("4", "tests/unit/test_withdrawal_service.py"),
    ("5", "tests/unit/test_referral_service.py"),
    ("6", "tests/unit/models/test_user.py"),
    ("7", "tests/unit/models/test_deposit.py"),
    ("8", "tests/unit/models/test_transaction.py"),
    ("9", "tests/unit/models/test_referral.py"),
    ("10", "tests/unit/models/test_referral_earning.py"),
    ("11", "tests/unit/repositories/test_user_repository.py"),
    ("12", "tests/unit/repositories/test_deposit_repository.py"),
    ("13", "tests/unit/repositories/test_transaction_repository.py"),
    ("14", "tests/unit/services/test_user_service.py"),
    ("15", "tests/unit/services/test_transaction_service.py"),
    ("16", "tests/unit/services/test_reward_service.py"),
    ("17", "tests/unit/services/test_deposit_service.py"),
]

results_file = Path("test_execution_report.txt")
json_file = Path("test_execution_report.json")

print("Starting test execution...")
print(f"Total test files: {len(test_files)}\n")

results = {
    "started_at": datetime.now().isoformat(),
    "total_files": len(test_files),
    "passed": 0,
    "failed": 0,
    "test_results": []
}

with open(results_file, "w", encoding="utf-8") as f:
    f.write("=" * 80 + "\n")
    f.write(f"TEST EXECUTION REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write("=" * 80 + "\n\n")
    
    for num, test_file in test_files:
        print(f"[{num}/{len(test_files)}] {test_file}")
        f.write(f"\n{'='*80}\n")
        f.write(f"[{num}/{len(test_files)}] {test_file}\n")
        f.write('='*80 + "\n\n")
        f.flush()
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600
            )
            
            f.write(result.stdout)
            if result.stderr:
                f.write("\n\nSTDERR:\n" + result.stderr)
            
            # Extract test count from output
            test_count = 0
            passed_count = 0
            failed_count = 0
            
            if result.stdout:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'passed' in line.lower() and 'failed' in line.lower():
                        # Try to extract numbers
                        import re
                        nums = re.findall(r'\d+', line)
                        if len(nums) >= 2:
                            passed_count = int(nums[0])
                            failed_count = int(nums[1])
                            test_count = passed_count + failed_count
            
            test_result = {
                "num": num,
                "file": test_file,
                "passed": result.returncode == 0,
                "returncode": result.returncode,
                "test_count": test_count,
                "passed_tests": passed_count,
                "failed_tests": failed_count,
                "output_preview": result.stdout[-500:] if result.stdout else ""
            }
            results["test_results"].append(test_result)
            
            if result.returncode == 0:
                results["passed"] += 1
                status = f"✅ PASSED ({passed_count} tests)"
                print(f"  ✅ PASSED ({passed_count} tests)")
            else:
                results["failed"] += 1
                status = f"❌ FAILED (exit code: {result.returncode}, {failed_count} failed)"
                print(f"  ❌ FAILED ({failed_count} failed)")
            
            f.write(f"\n{status}\n")
            f.flush()
            
        except subprocess.TimeoutExpired:
            results["failed"] += 1
            status = "❌ TIMEOUT (exceeded 10 minutes)"
            f.write(f"\n{status}\n")
            print(f"  ❌ TIMEOUT")
            results["test_results"].append({
                "num": num,
                "file": test_file,
                "passed": False,
                "returncode": "TIMEOUT",
                "test_count": 0,
                "passed_tests": 0,
                "failed_tests": 0
            })
            f.flush()
        except Exception as e:
            results["failed"] += 1
            status = f"❌ ERROR: {str(e)}"
            f.write(f"\n{status}\n")
            print(f"  ❌ ERROR: {e}")
            results["test_results"].append({
                "num": num,
                "file": test_file,
                "passed": False,
                "returncode": "ERROR",
                "error": str(e)
            })
            f.flush()
    
    # Summary
    total_tests = sum(r.get("test_count", 0) for r in results["test_results"])
    total_passed_tests = sum(r.get("passed_tests", 0) for r in results["test_results"])
    total_failed_tests = sum(r.get("failed_tests", 0) for r in results["test_results"])
    
    f.write("\n" + "=" * 80 + "\n")
    f.write("SUMMARY\n")
    f.write("=" * 80 + "\n")
    f.write(f"Test files: {len(test_files)}\n")
    f.write(f"  Passed: {results['passed']}\n")
    f.write(f"  Failed: {results['failed']}\n\n")
    f.write(f"Total tests executed: {total_tests}\n")
    f.write(f"  Passed: {total_passed_tests}\n")
    f.write(f"  Failed: {total_failed_tests}\n")
    f.write("=" * 80 + "\n")

results["completed_at"] = datetime.now().isoformat()
results["total_tests"] = sum(r.get("test_count", 0) for r in results["test_results"])
results["total_passed_tests"] = sum(r.get("passed_tests", 0) for r in results["test_results"])
results["total_failed_tests"] = sum(r.get("failed_tests", 0) for r in results["test_results"])

with open(json_file, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\n" + "=" * 80)
print("EXECUTION COMPLETED")
print("=" * 80)
print(f"Test files: {results['passed']} passed, {results['failed']} failed")
print(f"Total tests: {results['total_tests']} ({results['total_passed_tests']} passed, {results['total_failed_tests']} failed)")
print(f"\nDetailed report: {results_file}")
print(f"JSON report: {json_file}")

