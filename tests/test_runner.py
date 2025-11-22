"""Test runner utility."""
import subprocess
import sys
from pathlib import Path

def run_tests(test_path: str) -> int:
    """Run tests at given path."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-v"],
        cwd=Path(__file__).parent.parent
    ).returncode

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(run_tests(sys.argv[1]))
    else:
        sys.exit(run_tests("tests/unit/"))

