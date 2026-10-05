"""
run_tests.py
------------
Single-command automated test runner for the Live ETA Technician System.
Executes all unit tests and smoke tests:
- eta_engine unit tests
- Four edge case unit tests
- Automatic event trigger tests
- Customer notification tests
- Flask route smoke tests
"""

import sys
import unittest

if __name__ == "__main__":
    print("=" * 70)
    print("  LIVE ETA TECHNICIAN SYSTEM — AUTOMATED TEST SUITE")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print(f"  Tests run: {result.testsRun}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Failures: {len(result.failures)}")
    print("=" * 70)

    if result.wasSuccessful():
        print(">> ALL TESTS PASSED SUCCESSFULLY (100% SUCCESS)")
        sys.exit(0)
    else:
        print(">> SOME TESTS FAILED")
        sys.exit(1)
