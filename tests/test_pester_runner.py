"""Run PowerShell Pester tests alongside Python tests."""

import subprocess
import sys
from pathlib import Path


def run_pester_tests() -> int:
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

        # Load Pester module (try from system path first, then common locations)
        command = f"""
        Remove-Module Pester -Force -ErrorAction SilentlyContinue;

        # Try to import Pester from system modules path first
        if (Get-Module -ListAvailable -Name Pester) {{
            Import-Module Pester -MinimumVersion 5.0 -Force -ErrorAction SilentlyContinue
        }}

        # If not found, try common installation locations
        if (-not (Get-Module Pester)) {{
            $pesterPaths = @(
                "$env:USERPROFILE\\scoop\\modules\\Pester",
                "$env:ProgramFiles\\WindowsPowerShell\\Modules\\Pester",
                "$env:ProgramFiles\\PowerShell\\Modules\\Pester"
            )
            foreach ($path in $pesterPaths) {{
                if (Test-Path $path) {{
                    Import-Module $path -Force -ErrorAction SilentlyContinue
                    break
                }}
            }}
        }}

        Invoke-Pester '{test_file}'
        """

        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=False, text=True)  # noqa: S603, S607

        if result.returncode != 0:
            all_passed = False
            print(f"FAILED: {test_file.name}")
        else:
            print(f"PASSED: {test_file.name}")
        print()

    return 0 if all_passed else 1


def test_pester_create_portable() -> None:
    """Run Pester tests for create-portable.ps1 script.

    This test will fail if Pester tests fail for ANY reason,
    including missing virtual environment or actual test failures.
    """
    result = run_pester_tests()
    assert result == 0, "Pester tests failed"


if __name__ == "__main__":
    sys.exit(run_pester_tests())
