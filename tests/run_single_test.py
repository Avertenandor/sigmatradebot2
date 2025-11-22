"""Run a single test file."""
import subprocess
import sys

if len(sys.argv) < 2:
    print("Usage: python run_single_test.py <test_file>")
    sys.exit(1)

test_file = sys.argv[1]
subprocess.run([sys.executable, "-m", "pytest", test_file, "-v"])

