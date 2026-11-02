"""
run_tests.py
------------
Single-command automated test runner for the Live ETA Technician System.

Executes all 6 test suites (63 tests) verifying end-to-end functionality,
mathematical invariants, and defensive error boundaries:
1. `tests/test_eta_engine.py`: Haversine orthodromic distance, traffic multipliers, lower clamp invariants.
2. `tests/test_edge_cases.py`: The 4 required demo scenarios (traffic, unavailable, overrun, mismatch).
3. `tests/test_event_triggers.py`: Autonomous status listeners (availability changes, traffic surges).
4. `tests/test_notifications.py`: Multi-channel alerts (SMS, Push, Email) and persistence integrity.
5. `tests/test_routes.py`: Flask route smoke tests covering all 27 HTTP endpoints and actions.
6. `tests/test_error_boundaries.py`: 5-layer failure containment, 404/500 handlers, FK constraints, phone fallback.

Usage:
    python3 run_tests.py
"""

import sys
import unittest

if __name__ == "__main__":
    print("=" * 75)
    print("  LIVE ETA TECHNICIAN SYSTEM — AUTOMATED QUALITY ASSURANCE SUITE")
    print("  Evaluating Invariants, Edge Cases, Event Triggers & Error Boundaries")
    print("=" * 75)

    # Automatically discover all test modules matching test_*.py in tests/
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    # Execute with verbose test output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 75)
    print(f"  Test Suites Discovered : {suite.countTestCases()} tests across 6 modules")
    print(f"  Tests Successfully Run : {result.testsRun}")
    print(f"  Execution Failures     : {len(result.failures)}")
    print(f"  Unhandled Errors       : {len(result.errors)}")
    print("=" * 75)

    if result.wasSuccessful():
        print(">> ALL TESTS PASSED SUCCESSFULLY (100% SUCCESS RATE)")
        sys.exit(0)
    else:
        print(">> SOME TESTS ENCOUNTERED FAILURES OR ERRORS")
        sys.exit(1)
