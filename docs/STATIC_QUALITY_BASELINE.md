# Static Quality Baseline

**Generated**: 2026-01-24
**Gate**: 4 (Static Quality)

## Overview

This document establishes the static quality baseline for quant_industry_v1 and defines improvement targets.

## Current State

### Ruff Analysis

```
Total Issues: 1246
Auto-fixable: 244 (with --fix)
Unsafe-fixable: 580 (with --unsafe-fixes)

Top Issues by Category:
- UP006 (non-pep585-annotation): 490
- F401 (unused-import): 165
- I001 (unsorted-imports): 83
- PLC0415 (import-outside-top-level): 77
- UP035 (deprecated-import): 76
- PTH120 (os-path-dirname): 41
- RUF013 (implicit-optional): 41
- PLW0603 (global-statement): 36
- B904 (raise-without-from-inside-except): 27
- F841 (unused-variable): 19
```

### Mypy Analysis

```
Total Errors: 315
Files with Errors: 26 of 42
Primary Issues:
- implicit-optional: Multiple
- attr-defined: Missing attributes on ML classes
- call-arg: Wrong arguments to ML methods
- assignment: Type mismatches
- operator: Unsupported operand types
```

## Quality Targets

### Phase 1: Critical Fixes (Week 1)
- [ ] Fix all auto-fixable issues with `ruff check --fix`
- [ ] Fix implicit Optional type hints
- [ ] Fix unused imports and variables
- Target: < 500 ruff issues, < 200 mypy errors

### Phase 2: Type Safety (Week 2)
- [ ] Add type hints to all public APIs
- [ ] Fix attribute-defined errors
- [ ] Fix call-arg mismatches
- Target: < 200 ruff issues, < 100 mypy errors

### Phase 3: Clean Code (Week 3)
- [ ] Modernize imports (pathlib, typing)
- [ ] Remove global statements where possible
- [ ] Fix exception handling (raise from)
- Target: < 100 ruff issues, < 50 mypy errors

### Phase 4: Maintenance (Ongoing)
- [ ] All new code must pass ruff and mypy
- [ ] CI blocks PRs with new violations
- Target: Zero new violations

## Rule Configuration

### Ruff Rules Enabled
```toml
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "ERA",    # eradicate
    "PL",     # Pylint
    "RUF",    # Ruff-specific
]
```

### Rules Intentionally Ignored
```toml
ignore = [
    "E501",    # line too long (formatter handles)
    "PLR0913", # too many arguments (trading functions need them)
    "PLR0912", # too many branches (complex logic acceptable)
    "PLR0915", # too many statements
    "PLR2004", # magic values (common in trading)
    "B008",    # function call in default argument
    "ARG001",  # unused function argument (callbacks)
    "ARG002",  # unused method argument
    "SIM108",  # ternary operator (readability preference)
    "ERA001",  # commented code (too aggressive)
]
```

## Commands

### Run Ruff Check
```bash
cd quant_industry_v1
ruff check backend/ --exclude "backend/venv"
```

### Run Ruff with Auto-fix
```bash
ruff check backend/ --exclude "backend/venv" --fix
```

### Run Mypy
```bash
mypy backend/ --exclude "backend/venv" --ignore-missing-imports
```

### Run Both (CI)
```bash
ruff check backend/ --exclude "backend/venv" && mypy backend/ --exclude "backend/venv" --ignore-missing-imports
```

## CI Integration

Static quality is enforced via `.github/workflows/ci.yml`:
- Ruff runs on every PR
- Mypy runs on every PR
- New violations block merge
- Baseline allows existing issues (temporary)

## Improvement Tracking

| Date | Ruff Issues | Mypy Errors | Notes |
|------|-------------|-------------|-------|
| 2026-01-24 | 1246 | 315 | Baseline established |
| TBD | < 500 | < 200 | Phase 1 target |
| TBD | < 200 | < 100 | Phase 2 target |
| TBD | < 100 | < 50 | Phase 3 target |
