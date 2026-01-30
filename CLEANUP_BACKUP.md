# Cleanup Backup - Files Removed/Changed

**Date:** Auto-generated during debloat

## Results
| Metric | Before | After | Saved |
|--------|--------|-------|-------|
| Python files | 448 | 437 | 11 files |
| Total size | ~7.0 MB | 6.65 MB | ~350 KB |
| Root modules | 38 | 33 | 5 modules |

## Summary
- **Unused root modules removed:** 5 folders, ~145 KB of code
- **Empty directories removed:** 3 folders
- **.db files:** Already in .gitignore (not tracked)
- **Empty test files:** None found (all have tests)
- **Core imports verified:** ✅ Working

## Removed Directories

### 1. explainability/ (23.6 KB, 0 imports)
- `explainability/__init__.py` (24 lines)
- `explainability/model_explainer.py` (686 lines)
**Reason:** Zero imports anywhere in codebase. Note: `brain/explainability.py` is different and IS used.

### 2. marketplace/ (25 KB, 0 imports)
- `marketplace/__init__.py` (32 lines)
- `marketplace/signal_marketplace.py` (753 lines)
**Reason:** Zero imports anywhere in codebase.

### 3. orchestration/ (25.7 KB, 0 imports)
- `orchestration/__init__.py` (30 lines)
- `orchestration/strategy_orchestrator.py` (742 lines)
**Reason:** Zero imports anywhere in codebase. Note: `backend/trading/orchestrator.py` is different and IS used.

### 4. reports/ (20.3 KB, 0 imports)
- `reports/__init__.py` (22 lines)
- `reports/automated_reports.py` (612 lines)
**Reason:** Zero imports anywhere in codebase. Note: backend/main.py has inline `/api/reports/*` endpoints.

### 5. validation/ (51 KB, 0 imports)
- `validation/__init__.py` (46 lines)
- `validation/anti_overfit.py` (771 lines)
- `validation/capacity.py` (604 lines)
**Reason:** Zero imports anywhere in codebase. Note: `utils/validation.py` is different and IS used.

### 6. Empty directories removed
- `memory/` (0 files)
- `models/` (0 files)
- `docs/` (0 files)

## Files NOT Changed (Preserved)

### Already in .gitignore (not tracked)
- `*.db` files (~5.9 MB total in backend/data/, backend/cache/, data/, decision_intelligence/)
- These are runtime-generated databases, correctly not in version control

### Large files that need refactoring (future task, not deleted)
- `backend/main.py` (319 KB, 8211 lines, 192 endpoints) - Should be split into route modules
- `backend/brain/propfirm_brain_v6.py` (92 KB, 2587 lines) - Complex trading logic, don't touch

### Modules with low import count but ARE used
- `bots/` (1 import) - Keep
- `crypto/` (1 import) - Keep
- `accounting/` (2 imports) - Keep
- `monitoring/` (2 imports) - Keep
- `reconciliation/` (2 imports) - Keep

## How to Restore
If any removed code is needed later, check git history:
```bash
git log --all --full-history -- explainability/
git checkout <commit-hash> -- explainability/
```
