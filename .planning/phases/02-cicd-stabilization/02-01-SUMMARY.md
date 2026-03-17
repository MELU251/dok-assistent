---
phase: 02-cicd-stabilization
plan: 01
subsystem: infra
tags: [github-actions, docker, tailscale, ci-cd, pytest, health-check]

# Dependency graph
requires:
  - phase: 01-tech-debt-foundation
    provides: passing pytest suite used in test job
provides:
  - Three-job GitHub Actions pipeline (test, build, deploy)
  - Failing pytest blocks build and deploy (CICD-01)
  - Visible job dependency chain in GitHub Actions UI (CICD-02)
  - Post-deploy container health check with 120s timeout (CICD-03)
  - Tailscale SSH retry via Wandalen/wretry.action
affects: [03-rag-pipeline, 04-chainlit-ui]

# Tech tracking
tech-stack:
  added:
    - tailscale/github-action@v4 (upgraded from v2, adds ping: support)
    - Wandalen/wretry.action@master (Tailscale SSH retry)
    - actions/setup-python@v5 (Python 3.11 in test job)
  patterns:
    - Three-job CI/CD: test gates build, build gates deploy
    - Health-check loop: poll docker inspect every 10s up to MAX_WAIT=120
    - Separate permissions per job (packages:write only on build)

key-files:
  created: []
  modified:
    - .github/workflows/deploy.yml

key-decisions:
  - "tailscale/github-action@v4 used (not v2) — v4 adds ping: pre-flight that confirms VPS is reachable before SSH steps begin"
  - "Wandalen/wretry.action@master wraps nc reachability check with attempt_limit=3 and attempt_delay=10000ms — replaces bare nc with no retry"
  - "MAX_WAIT=120s chosen because Docker healthcheck window is 20s start_period + 3*30s interval = 110s maximum"
  - "packages:write permission only on build job — deploy job uses contents:read only, reducing attack surface"
  - "test job has no secrets — all tests use mocks, no live credentials needed in test environment"
  - "System deps (libmagic1, poppler-utils, tesseract-ocr) installed in test job — required by unstructured.io at import time"
  - "tailscale/github-action@v4 sets --accept-routes/--accept-dns internally — passing them in args: causes duplicate-flag failure; args removed after CI failure"
  - "Integration tests excluded in CI via pytest -m 'not integration' — live Ollama/Supabase not available in CI environment"
  - "get_settings mock added to test_ingest.py alongside _get_embedder/_get_supabase_client — embed_and_store() calls get_settings() directly for log message, not via singleton getter"

patterns-established:
  - "Pattern 1: Job isolation — test/build/deploy each have only the permissions they need"
  - "Pattern 2: Gate pattern — needs: [test] on build, needs: [build] on deploy creates hard dependency chain"
  - "Pattern 3: Health polling — bash while loop with elapsed counter, exit 0 on healthy, exit 1 on timeout"

requirements-completed: [CICD-01, CICD-02, CICD-03]

# Metrics
duration: ~45min (including live CI iteration)
completed: 2026-03-17
---

# Phase 2 Plan 01: CI/CD Three-Job Pipeline Summary

**Single-job build-and-deploy workflow split into three explicitly ordered jobs (test, build, deploy) with Tailscale v4 ping pre-flight, Wandalen retry on SSH reachability, and a 120s container health-check loop — verified green end-to-end in GitHub Actions**

## Performance

- **Duration:** ~45 min (including live CI iteration over multiple pushes)
- **Started:** 2026-03-17T12:28:19Z
- **Completed:** 2026-03-17
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint, all complete)
- **Files modified:** 2 (.github/workflows/deploy.yml, tests/test_ingest.py)

## Accomplishments
- Rewrote `.github/workflows/deploy.yml` from a monolithic single job into three dependent jobs — verified green in GitHub Actions UI with all three job cards visible
- `test` job runs pytest with Python 3.11 and system deps — no secrets, blocks build on failure (CICD-01)
- `build` job has `needs: [test]` with packages:write for ghcr.io push and actions:write for GHA cache (CICD-02)
- `deploy` job has `needs: [build]`, Tailscale v4 with ping:, Wandalen/wretry retry, and 120s health-check bash loop — VPS container confirmed healthy (CICD-03)
- Fixed two CI issues during live verification: integration test exclusion and Tailscale v4 duplicate-args failure

## Task Commits

Each task was committed atomically:

1. **Tasks 1+2: Split workflow + add deploy job** - `ac06bc1` (feat)
2. **Fix: skip integration tests in CI, fix missing get_settings mock** - `66af3af` (fix)
3. **Fix: remove duplicate tailscale args for v4** - `09f2c80` (fix)

_Note: Task 1 (test+build jobs) and Task 2 (deploy job) were written atomically since they modify the same file. Fix commits 2 and 3 were applied during live CI verification (Task 3 checkpoint)._

**Plan metadata:** `490bd8a` (docs: complete three-job CI/CD pipeline plan — checkpoint reached)

## Files Created/Modified
- `.github/workflows/deploy.yml` - Complete three-job CI/CD pipeline replacing single monolithic job; two fix iterations during live CI verification
- `tests/test_ingest.py` - Added get_settings mock to embed_and_store test; added integration marker to live-connection tests

## Decisions Made
- tailscale/github-action@v4 (not v2) — v4 adds `ping:` support that confirms VPS reachability before any SSH step
- Wandalen/wretry.action@master for the nc SSH reachability check — replaces bare `nc` with no retry
- MAX_WAIT=120s — Docker's full healthcheck window: 20s start_period + 3*30s interval = 110s max, 120s gives 10s margin
- `packages: write` permission only on the build job — deploy job needs only `contents: read`
- No secrets in the test job — all tests use mocks, clean isolation
- Integration tests excluded in CI via `pytest -m "not integration"` — live Ollama/Supabase unavailable in GitHub-hosted runners

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed duplicate Tailscale v4 args causing CI failure**
- **Found during:** Task 3 (live CI verification)
- **Issue:** `tailscale/github-action@v4` sets `--accept-routes` and `--accept-dns` internally; passing them again in `args:` caused a duplicate-flag error and the deploy job failed
- **Fix:** Removed `args: --accept-routes --accept-dns` from the Tailscale step
- **Files modified:** `.github/workflows/deploy.yml`
- **Verification:** Deploy job passed green after removal
- **Committed in:** `09f2c80`

**2. [Rule 1 - Bug] Fixed test job failure: integration tests + missing get_settings mock**
- **Found during:** Task 3 (live CI verification)
- **Issue:** (a) Test job ran integration tests that require live Ollama/Supabase — unavailable in CI. (b) `embed_and_store()` calls `get_settings()` directly for a log message; test mocked only `_get_embedder` and `_get_supabase_client`, leaving `get_settings()` unmocked and causing a test error
- **Fix:** Added `-m "not integration"` to pytest command in workflow; added `@patch("src.ingest.get_settings")` to the relevant test
- **Files modified:** `.github/workflows/deploy.yml`, `tests/test_ingest.py`
- **Verification:** Test job passed green after fix
- **Committed in:** `66af3af`

---

**Total deviations:** 2 auto-fixed (both bugs discovered during live CI verification)
**Impact on plan:** Both fixes were direct consequences of running in the actual CI environment. No scope creep — the plan's intent was fully achieved.

## Issues Encountered
- Tailscale v4 sets certain flags internally — passing them explicitly in `args:` is a breaking change vs v2. Discovered via CI failure logs, fixed immediately.
- Integration tests were not separated from unit tests before this phase. The fix (marker exclusion) is a minor test-infrastructure improvement that also satisfies the CI requirement.

## User Setup Required
None - no external service configuration required. All secrets already exist in the repository.

## Next Phase Readiness
- Phase 2 is fully complete: every push to master now runs tests, builds only on green tests, and verifies the VPS container is healthy
- Phase 3 (Chat History and Multi-Turn Context) can begin — Phase 1 and Phase 2 prerequisites are both satisfied
- Before planning Phase 3, run the two prerequisite checks documented in STATE.md blockers: verify Chainlit 2.x `BaseDataLayer` API surface and `RunnableWithMessageHistory` import path in installed langchain-core version

---
*Phase: 02-cicd-stabilization*
*Completed: 2026-03-17*
