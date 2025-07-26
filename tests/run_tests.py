#!/usr/bin/env python3
"""
Test runner for the Weirding Host Utility.

This script runs all unit and integration tests and provides a comprehensive
test report for developers.
"""

import unittest
import sys
import os
from pathlib import Path
import subprocess
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "modules"))


class ColoredTextTestResult(unittest.TextTestResult):
    """Custom test result class with colored output."""
    
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.success_count = 0
        self.verbosity = verbosity  # Store verbosity for later use
    
    def addSuccess(self, test):
        super().addSuccess(test)
        self.success_count += 1
        if self.verbosity > 1:
            self.stream.write("✅ ")
            self.stream.writeln(self.getDescription(test))
    
    def addError(self, test, err):
        super().addError(test, err)
        if self.verbosity > 1:
            self.stream.write("❌ ")
            self.stream.writeln(self.getDescription(test))
    
    def addFailure(self, test, err):
        super().addFailure(test, err)
        if self.verbosity > 1:
            self.stream.write("❌ ")
            self.stream.writeln(self.getDescription(test))
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.verbosity > 1:
            self.stream.write("⏭️  ")
            self.stream.writeln(f"{self.getDescription(test)} (skipped: {reason})")


class ColoredTextTestRunner(unittest.TextTestRunner):
    """Custom test runner with colored output."""
    
    resultclass = ColoredTextTestResult
    
    def run(self, test):
        result = super().run(test)
        
        # Print summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        total_tests = result.testsRun
        failures = len(result.failures)
        errors = len(result.errors)
        skipped = len(result.skipped)
        successes = result.success_count
        
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {successes}")
        print(f"❌ Failed: {failures}")
        print(f"💥 Errors: {errors}")
        print(f"⏭️  Skipped: {skipped}")
        
        if failures == 0 and errors == 0:
            print("\n🎉 All tests passed!")
            return result
        else:
            print(f"\n⚠️  {failures + errors} test(s) failed")
            return result


def check_dependencies():
    """Check if all required dependencies are available."""
    print("Checking dependencies...")
    
    required_packages = ['typer', 'rich', 'questionary']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (missing)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Install them with: pip install " + " ".join(missing_packages))
        return False
    
    print("✅ All dependencies available\n")
    return True


def check_project_structure():
    """Check if the project structure is correct."""
    print("Checking project structure...")
    
    required_files = [
        "main.py",
        "weirding-setup",
        "Makefile",
        "requirements.txt",
        "modules/device_setup.py",
        "modules/interactive_ui.py",
        "modules/logger.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} (missing)")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️  Missing files: {', '.join(missing_files)}")
        return False
    
    print("✅ Project structure is correct\n")
    return True


def run_unit_tests():
    """Run unit tests."""
    print("Running Unit Tests...")
    print("-" * 50)
    
    # Discover and run unit tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Load specific test modules
    test_modules = [
        'test_device_setup',
    ]
    
    for module_name in test_modules:
        try:
            module = __import__(module_name)
            suite.addTests(loader.loadTestsFromModule(module))
        except ImportError as e:
            print(f"⚠️  Could not load {module_name}: {e}")
    
    # Run the tests
    runner = ColoredTextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_integration_tests():
    """Run integration tests."""
    print("\nRunning Integration Tests...")
    print("-" * 50)
    
    # Discover and run integration tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Load integration test modules
    test_modules = [
        'test_cli_integration',
    ]
    
    for module_name in test_modules:
        try:
            module = __import__(module_name)
            suite.addTests(loader.loadTestsFromModule(module))
        except ImportError as e:
            print(f"⚠️  Could not load {module_name}: {e}")
    
    # Run the tests
    runner = ColoredTextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_functional_tests():
    """Run functional tests using actual commands."""
    print("\nRunning Functional Tests...")
    print("-" * 50)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Version command
    tests_total += 1
    try:
        result = subprocess.run([
            sys.executable, str(project_root / "main.py"), "version"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "Weirding Host Utility" in result.stdout:
            print("✅ Version command works")
            tests_passed += 1
        else:
            print("❌ Version command failed")
    except Exception as e:
        print(f"❌ Version command error: {e}")
    
    # Test 2: List drives command
    tests_total += 1
    try:
        result = subprocess.run([
            sys.executable, str(project_root / "main.py"), "list-drives"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and "Scanning storage devices" in result.stdout:
            print("✅ List drives command works")
            tests_passed += 1
        else:
            print("❌ List drives command failed")
    except Exception as e:
        print(f"❌ List drives command error: {e}")
    
    # Test 3: Standalone script version
    tests_total += 1
    try:
        result = subprocess.run([
            str(project_root / "weirding-setup"), "version"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "Weirding Module Setup Utility" in result.stdout:
            print("✅ Standalone script version works")
            tests_passed += 1
        else:
            print("❌ Standalone script version failed")
    except Exception as e:
        print(f"❌ Standalone script version error: {e}")
    
    # Test 4: Makefile test command
    tests_total += 1
    try:
        result = subprocess.run([
            "make", "test"
        ], cwd=project_root, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and "Standalone script works" in result.stdout:
            print("✅ Makefile test command works")
            tests_passed += 1
        else:
            print("❌ Makefile test command failed")
    except Exception as e:
        print(f"❌ Makefile test command error: {e}")
    
    print(f"\nFunctional Tests: {tests_passed}/{tests_total} passed")
    return tests_passed == tests_total


def main():
    """Main test runner function."""
    print("🧪 Weirding Host Utility - Test Suite")
    print("=" * 70)
    
    start_time = time.time()
    
    # Pre-flight checks
    if not check_dependencies():
        sys.exit(1)
    
    if not check_project_structure():
        sys.exit(1)
    
    # Run all test suites
    all_passed = True
    
    # Unit tests
    unit_tests_passed = run_unit_tests()
    all_passed = all_passed and unit_tests_passed
    
    # Integration tests
    integration_tests_passed = run_integration_tests()
    all_passed = all_passed and integration_tests_passed
    
    # Functional tests
    functional_tests_passed = run_functional_tests()
    all_passed = all_passed and functional_tests_passed
    
    # Final summary
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"Test Duration: {duration:.2f} seconds")
    print(f"Unit Tests: {'✅ PASSED' if unit_tests_passed else '❌ FAILED'}")
    print(f"Integration Tests: {'✅ PASSED' if integration_tests_passed else '❌ FAILED'}")
    print(f"Functional Tests: {'✅ PASSED' if functional_tests_passed else '❌ FAILED'}")
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! The Weirding Host Utility is working correctly.")
        sys.exit(0)
    else:
        print("\n⚠️  SOME TESTS FAILED. Please review the output above.")
        sys.exit(1)


if __name__ == '__main__':
    main()