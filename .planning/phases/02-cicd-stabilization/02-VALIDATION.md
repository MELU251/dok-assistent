---
phase: 2
slug: cicd-stabilization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ with pytest-asyncio 0.23+ |
| **Config file** | `pytest.ini` (exists, `asyncio_mode = auto`) |
| **Quick run command** | `pytest tests/ -v` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -v`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green AND one successful end-to-end GitHub Actions workflow run
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | CICD-01, CICD-02 | manual | `pytest tests/ -v` (smoke: existing tests stay green) | ✅ existing | ⬜ pending |
| 2-01-02 | 01 | 1 | CICD-03 | manual | `pytest tests/ -v` (smoke) | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

*No new test files needed — this phase modifies GitHub Actions YAML only. Existing pytest suite acts as smoke test to confirm no regressions.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Failing pytest blocks build and deploy | CICD-01 | Cannot be unit-tested; requires live CI run | Push a commit with `assert False` in a test, observe red `test` job + skipped `build`/`deploy` jobs, then revert |
| Three separate jobs visible in Actions UI | CICD-02 | Structural verification of YAML `needs:` syntax — only observable in GitHub Actions UI | After push, open GitHub → Actions → observe three separate job cards: `test`, `build`, `deploy` |
| Tailscale retry + container health check | CICD-03 | Requires live VPS and Tailscale connection | After successful push, inspect deploy job logs for "Container ist healthy." message |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
