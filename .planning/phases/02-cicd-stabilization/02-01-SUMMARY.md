---
phase: 02-cicd-stabilization
plan: 01
subsystem: infra
tags: [github-actions, docker, tailscale, ci-cd, pytest]

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

patterns-established:
  - "Pattern 1: Job isolation — test/build/deploy each have only the permissions they need"
  - "Pattern 2: Gate pattern — needs: [test] on build, needs: [build] on deploy creates hard dependency chain"
  - "Pattern 3: Health polling — bash while loop with elapsed counter, exit 0 on healthy, exit 1 on timeout"

requirements-completed: [CICD-01, CICD-02, CICD-03]

# Metrics
duration: 2min
completed: 2026-03-17
---

# Phase 2 Plan 01: CI/CD Three-Job Pipeline Summary

**Single-job build-and-deploy workflow split into three explicitly ordered jobs (test, build, deploy) with Tailscale v4 ping pre-flight, Wandalen retry on SSH reachability, and a 120s container health-check loop**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-17T12:28:19Z
- **Completed:** 2026-03-17T12:29:30Z
- **Tasks:** 2 of 2 auto tasks (Task 3 is checkpoint:human-verify, awaiting verification)
- **Files modified:** 1

## Accomplishments
- Rewrote `.github/workflows/deploy.yml` from a monolithic single job into three dependent jobs
- `test` job runs pytest with Python 3.11 and system deps — no secrets, blocks build on failure (CICD-01)
- `build` job has `needs: [test]` with packages:write for ghcr.io push and actions:write for GHA cache (CICD-02)
- `deploy` job has `needs: [build]`, Tailscale v4 with ping:, Wandalen/wretry retry, and 120s health-check bash loop (CICD-03)

## Task Commits

Each task was committed atomically:

1. **Task 1+2: Split workflow + add deploy job** - `ac06bc1` (feat)

_Note: Task 1 (test+build jobs) and Task 2 (deploy job) were written atomically in one file write and committed together since they are in the same file._

## Files Created/Modified
- `.github/workflows/deploy.yml` - Complete three-job CI/CD pipeline replacing single monolithic job

## Decisions Made
- tailscale/github-action@v4 (not v2) — v4 adds `ping:` support that confirms VPS reachability before any SSH step
- Wandalen/wretry.action@master for the nc SSH reachability check — replaces bare `nc` with no retry
- MAX_WAIT=120s — Docker's full healthcheck window: 20s start_period + 3*30s interval = 110s max, 120s gives 10s margin
- `packages: write` permission only on the build job — deploy job needs only `contents: read`
- No secrets in the test job — all tests use mocks, clean isolation

## Deviations from Plan

None - plan executed exactly as written. Both Task 1 and Task 2 were combined into a single commit since they modify the same file and both needed to be written together for the YAML to be valid.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. All secrets already exist in the repository.

## Next Phase Readiness
- Workflow file is written and committed, ready for push-and-verify
- Task 3 (checkpoint:human-verify) requires pushing to GitHub and observing three green job cards
- After human verification passes, Phase 2 Plan 01 is complete
- Phase 2 Plan 02 (if any) can proceed after checkpoint approval

---
*Phase: 02-cicd-stabilization*
*Completed: 2026-03-17*
