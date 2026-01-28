#!/usr/bin/env python
"""
QUANT_INDUSTRY_V1 Test Runner

Run all tests with coverage reporting.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --quick      # Run quick tests only
    python run_tests.py --coverage   # Run with coverage
    python run_tests.py --module brain  # Run specific module tests
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(args):
    """Run tests with specified options."""
    base_cmd = [sys.executable, '-m', 'pytest']

    # Add verbosity
    base_cmd.extend(['-v', '--tb=short'])

    # Add timeout
    base_cmd.extend(['--timeout=120'])

    # Coverage options
    if args.coverage:
        base_cmd.extend([
            '--cov=brain',
            '--cov=data',
            '--cov=execution',
            '--cov=risk',
            '--cov=strategies',
            '--cov=services',
            '--cov=security',
            '--cov-report=term-missing',
            '--cov-report=html:coverage_html',
        ])

    # Quick mode - skip slow tests
    if args.quick:
        base_cmd.extend(['-m', 'not slow and not integration'])

    # Specific module
    if args.module:
        test_file = Path('tests') / f'test_{args.module}.py'
        if test_file.exists():
            base_cmd.append(str(test_file))
        else:
            print(f"Test file not found: {test_file}")
            return 1
    else:
        base_cmd.append('tests/')

    # Stop on first failure
    if args.failfast:
        base_cmd.append('-x')

    # Parallel execution
    if args.parallel:
        base_cmd.extend(['-n', 'auto'])

    print(f"Running: {' '.join(base_cmd)}")
    print("-" * 60)

    result = subprocess.run(base_cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='Run QUANT_INDUSTRY_V1 tests')

    parser.add_argument(
        '--quick', '-q',
        action='store_true',
        help='Run quick tests only (skip slow and integration)'
    )
    parser.add_argument(
        '--coverage', '-c',
        action='store_true',
        help='Run with coverage reporting'
    )
    parser.add_argument(
        '--module', '-m',
        type=str,
        help='Run tests for specific module (brain, execution, risk, etc.)'
    )
    parser.add_argument(
        '--failfast', '-x',
        action='store_true',
        help='Stop on first failure'
    )
    parser.add_argument(
        '--parallel', '-p',
        action='store_true',
        help='Run tests in parallel (requires pytest-xdist)'
    )

    args = parser.parse_args()

    sys.exit(run_tests(args))


if __name__ == '__main__':
    main()
