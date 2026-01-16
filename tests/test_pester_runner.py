"""Run PowerShell Pester tests alongside Python tests."""

import subprocess
import sys
from pathlib import Path
import pytest


def run_pester_tests():
    """Run all Pester tests in the tests directory."""
    tests_dir = Path(__file__).parent
    pester_tests = list(tests_dir.glob("*.Tests.ps1"))

    if not pester_tests:
        print("No Pester tests found")
        return 0

    print(f"\n{'='*70}")
    print("Running PowerShell Pester Tests")
    print(f"{'='*70}\n")

    all_passed = True
    for test_file in pester_tests:
        print(f"Running: {test_file.name}")

        # Force load Pester 5.x from Scoop
        command = f"""
        Remove-Module Pester -Force -ErrorAction SilentlyContinue;
        Import-Module "$env:USERPROFILE\\scoop\\modules\\Pester" -Force;
        Invoke-Pester '{test_file}'
        """

        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=False, text=True)

        if result.returncode != 0:
            all_passed = False
            print(f"✗ {test_file.name} failed")
        else:
            print(f"✓ {test_file.name} passed")
        print()

    return 0 if all_passed else 1


def test_pester_create_portable():
    """Run Pester tests for create-portable.ps1 script."""
    result = run_pester_tests()
    assert result == 0, "Pester tests failed"


if __name__ == "__main__":
    sys.exit(run_pester_tests())
