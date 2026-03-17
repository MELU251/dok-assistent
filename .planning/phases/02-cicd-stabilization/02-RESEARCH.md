# Phase 2: CI/CD Stabilization - Research

**Researched:** 2026-03-17
**Domain:** GitHub Actions workflow restructuring, Tailscale CI integration, Docker health verification
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CICD-01 | pytest-Schritt läuft als eigener GitHub-Actions-Job vor Build und Deploy — fehlgeschlagene Tests blockieren das Deployment | `needs:` keyword creates hard sequential dependency; test job failure prevents dependent jobs from starting |
| CICD-02 | Workflow ist in separate Jobs aufgeteilt: `test → build → deploy` mit expliziten `needs:`-Abhängigkeiten | `needs: [test]` on build, `needs: [build]` on deploy; each job appears as separate card in Actions UI |
| CICD-03 | Tailscale-Verbindung im Deploy-Job hat Retry-Logik; nach `docker compose up -d` wird ein Container-Health-Check ausgeführt | Tailscale action v4 has `ping:` parameter for connection verification; remote bash loop on VPS checks `docker inspect` health status |
</phase_requirements>

---

## Summary

Phase 2 refactors the existing single-job `build-and-deploy` workflow into three explicitly ordered GitHub Actions jobs (`test → build → deploy`) using the `needs:` keyword. The current `deploy.yml` already contains all the necessary steps — the work is reorganization, not invention.

The test job runs pytest on the GitHub runner (no VPS, no real secrets — mock-only). The build job pushes to GHCR only when tests pass. The deploy job connects to the VPS via Tailscale, runs `docker compose up -d`, and then verifies container health via an SSH-executed bash loop checking `docker inspect`. Tailscale connection setup uses the `ping:` parameter for connection verification and `Wandalen/wretry.action` wraps the initial SSH reachability check for retry-on-failure behavior.

**Primary recommendation:** Reorganize existing `deploy.yml` into three jobs with `needs:` chains. Add a bash health-check loop in the deploy step over SSH. Use `Wandalen/wretry.action` for Tailscale connectivity retry. No new libraries or Docker changes needed.

---

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| `tailscale/github-action` | v4 (v4.1.2, 2026-03-11) | Connect GitHub runner to Tailscale network | Official Tailscale action; supports `ping:` for connectivity verification |
| `Wandalen/wretry.action` | `@master` | Retry a shell command or step on failure | GitHub Marketplace standard; explicit `attempt_limit` and `attempt_delay` inputs |
| `docker/build-push-action` | v5 | Build and push Docker image to GHCR | Already in use; standard Buildx-backed action |
| `actions/checkout` | v4 | Checkout code | Already in use |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `docker inspect` (bash) | native Docker | Query container health status after deploy | Run via SSH on VPS to verify `dok-assistent` container health state |
| `nc` (netcat) | system | Test TCP reachability of VPS SSH port | Already used in existing workflow; wrap in retry action |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Bash health-check loop over SSH | `ejhayes/docker-compose-wait-for-healthy` GitHub Action | Marketplace action runs on the GHA runner, not on the VPS — can't reach remote container directly; bash loop over SSH is the correct pattern here |
| `Wandalen/wretry.action` | `nick-invision/retry` | Both work; `Wandalen/wretry.action` is actively maintained and has clearer parameter names |
| authkey `${{ secrets.TAILSCALE_AUTH_KEY }}` | OAuth via `TS_OAUTH_CLIENT_ID`/`TS_OAUTH_SECRET` | OAuth is preferred by Tailscale docs for new setups; existing workflow uses `authkey` which still works — do not change if secret already exists and works |

**Installation:** No new packages. All tools are GitHub Actions marketplace actions or built-in shell utilities.

---

## Architecture Patterns

### Recommended Workflow Structure

```yaml
# .github/workflows/deploy.yml

jobs:
  test:
    runs-on: ubuntu-latest
    # No needs: — this is the entry point
    steps:
      - checkout
      - setup python
      - install test dependencies
      - run pytest

  build:
    needs: [test]           # CICD-01: only runs if test succeeds
    runs-on: ubuntu-latest
    steps:
      - checkout
      - login to ghcr.io
      - build and push image

  deploy:
    needs: [build]          # CICD-02: only runs if build succeeds
    runs-on: ubuntu-latest
    steps:
      - connect tailscale (with retry / ping)
      - setup SSH key
      - verify VPS reachability (with retry)
      - copy docker-compose.yml
      - deploy on VPS (write .env, pull, up -d)
      - health check loop over SSH   # CICD-03
```

### Pattern 1: Three-Job Sequential Pipeline with `needs:`

**What:** Each job declares `needs:` referencing the job ID of its predecessor. GitHub Actions skips all dependent jobs when a prerequisite fails.

**When to use:** Always when test failure must prevent build/deploy.

**Example:**
```yaml
# Source: https://docs.github.com/en/actions/using-jobs/using-jobs-in-a-workflow
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Python einrichten
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Test-Abhängigkeiten installieren
        run: pip install pytest pytest-mock pytest-asyncio
      - name: Tests ausführen
        run: pytest tests/ -v

  build:
    needs: [test]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ghcr.io/melu251/dok-assistent:latest
          cache-from: type=gha
          cache-to: type=gha,mode=min

  deploy:
    needs: [build]
    runs-on: ubuntu-latest
    steps:
      # Tailscale + SSH + deploy steps (see Pattern 2 and 3)
```

### Pattern 2: Tailscale Connection with `ping:` Verification (CICD-03)

**What:** `tailscale/github-action@v4` accepts a `ping:` parameter that waits up to 3 minutes for connectivity confirmation before proceeding. This replaces a separate retry loop for the Tailscale setup itself.

**When to use:** Always when the Tailscale-connected host must be reachable before SSH steps run.

**Example:**
```yaml
# Source: https://github.com/tailscale/github-action (v4.1.2, 2026-03-11)
- name: Mit Tailscale verbinden
  uses: tailscale/github-action@v4
  with:
    authkey: ${{ secrets.TAILSCALE_AUTH_KEY }}
    args: --accept-routes --accept-dns
    ping: ${{ secrets.VPS_HOST }}   # waits up to 3 min for reachability
```

### Pattern 3: SSH Reachability Retry with `wretry.action` (CICD-03)

**What:** Wraps the `nc` reachability check in a retry loop so transient Tailscale propagation delays don't fail the job on the first attempt.

**When to use:** Use when the Tailscale `ping:` parameter is not sufficient (e.g., DNS propagation delay vs TCP port 22 readiness).

**Example:**
```yaml
# Source: https://github.com/marketplace/actions/retry-action (Wandalen/wretry.action)
- name: VPS-Erreichbarkeit prüfen (mit Retry)
  uses: Wandalen/wretry.action@master
  with:
    command: nc -zv -w 10 ${{ secrets.VPS_HOST }} 22
    attempt_limit: 3
    attempt_delay: 10000   # 10 seconds between attempts
```

### Pattern 4: Post-Deploy Container Health Check via SSH (CICD-03)

**What:** After `docker compose up -d`, SSH into the VPS and poll `docker inspect` until the container's health status is `healthy` or a timeout is reached. The script exits non-zero if the timeout expires — this causes the GitHub Actions step to fail, surfacing container startup failures in CI.

**When to use:** Always after remote `docker compose up -d` when the compose file defines a `healthcheck`.

**Key facts about existing setup:**
- `docker-compose.yml` already defines `healthcheck` on the `chainlit` service
- The healthcheck polls `http://localhost:8000/health` with: `interval: 30s`, `timeout: 10s`, `retries: 3`, `start_period: 20s`
- Maximum wait before Docker marks unhealthy: `start_period + (retries * interval)` = 20 + (3 * 30) = **110 seconds**
- The CI health-check loop should wait at least 120 seconds total

**Example (executed remotely via SSH heredoc):**
```bash
# Run via: ssh -i ~/.ssh/deploy_key $USER@$HOST bash << 'ENDSSH'
# Source: standard docker inspect pattern — verified against Docker docs

MAX_WAIT=120
ELAPSED=0
CONTAINER=dok-assistent

echo "Warte auf Container-Health-Check (max ${MAX_WAIT}s)..."
while [ $ELAPSED -lt $MAX_WAIT ]; do
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER 2>/dev/null || echo "not_found")
  echo "  Status nach ${ELAPSED}s: $STATUS"
  if [ "$STATUS" = "healthy" ]; then
    echo "Container ist healthy."
    exit 0
  fi
  sleep 10
  ELAPSED=$((ELAPSED + 10))
done

echo "FEHLER: Container ist nach ${MAX_WAIT}s nicht healthy (Status: $STATUS)"
exit 1
```

### Pattern 5: Test Job — Installing Only Test Dependencies

**What:** The test job does NOT need Docker, Tailscale, or build tools. It only needs Python + test packages. This keeps the test job fast and avoids unnecessary complexity.

**Critical consideration:** The existing tests mock all external services (Ollama, Supabase, Claude). The test job must NOT have real secrets. Pytest should pass using only mocked dependencies.

**What to install in test job:**
```bash
# Only install test subset — not full requirements.txt (avoids unstructured.io build time)
pip install pytest pytest-mock pytest-asyncio \
    langchain langchain-community langchain-ollama langchain-anthropic \
    pydantic pydantic-settings python-dotenv httpx supabase
```

**Alternative:** Install full `requirements.txt` for simplicity — slower but guarantees parity with production environment.

### Anti-Patterns to Avoid

- **Single monolithic job:** The current `build-and-deploy` job — tests and deployment are coupled; a failing test still builds and deploys.
- **Using `if: always()` on build/deploy:** Defeats the purpose of `needs:`. Only use `always()` on cleanup/notification jobs that must run regardless.
- **Checking health from the GHA runner directly:** The VPS is only reachable via Tailscale (Tailscale IP bound to port 8000). Health check must run over SSH on the VPS itself, not via `curl` from the runner.
- **Not setting `set -e` in SSH heredocs:** Without it, individual command failures inside the heredoc are silently swallowed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry Tailscale/SSH step on failure | Custom bash `for i in 1 2 3; do ... done` loop | `Wandalen/wretry.action` | Handles exit codes, delay, logging correctly |
| Tailscale connectivity verification | Polling `tailscale status` in a loop | `ping:` parameter in `tailscale/github-action@v4` | Built-in, waits up to 3 min, handles relay vs direct |
| Job sequencing | Scripting conditional logic in steps | `needs:` keyword | Native GitHub Actions feature; renders correctly in Actions UI as separate cards |

**Key insight:** The existing workflow already has all the correct SSH steps, deploy logic, and docker commands. The refactor is purely structural — split into jobs, add `needs:`, add retry + health check.

---

## Common Pitfalls

### Pitfall 1: Tailscale Action Version Mismatch
**What goes wrong:** The existing workflow uses `tailscale/github-action@v2`. The current version is v4. v2 may not support the `ping:` parameter.
**Why it happens:** The action was added to the project when v2 was current; it hasn't been updated.
**How to avoid:** Update to `tailscale/github-action@v4` as part of this refactor.
**Warning signs:** `ping:` input is silently ignored if not supported by the version.

### Pitfall 2: `permissions:` Scope Needed Only on Build Job
**What goes wrong:** Moving from single job to three jobs means the `packages: write` permission must be declared on the `build` job specifically (or at workflow level). The `deploy` job does not need it.
**Why it happens:** In the current single-job workflow, all permissions are on that one job. When splitting, permissions must be allocated per job.
**How to avoid:** Place `permissions:` block on the `build` job. The `deploy` job needs only `contents: read`.

### Pitfall 3: Health Check Window Too Short
**What goes wrong:** The CI health check loop exits before Docker's own `start_period` (20s) + `retries * interval` (90s) window completes, reporting failure for a container that would have become healthy.
**Why it happens:** The start_period means Docker itself won't mark the container as unhealthy for at least 20 seconds. The full check cycle is up to 110 seconds.
**How to avoid:** Set `MAX_WAIT=120` in the bash loop. Sleep 10 seconds between iterations.

### Pitfall 4: Test Job Fails Due to Missing Optional Dependencies
**What goes wrong:** Running `pytest` with only partial dependency install fails at import time for modules that are installed in `requirements.txt` but not in the lightweight test install.
**Why it happens:** `unstructured[pdf,docx,xlsx]` has heavy system dependencies (libmagic, poppler, tesseract) that take minutes to install and require apt packages.
**How to avoid:** Either install full `requirements.txt` (simplest, most accurate), OR audit all test imports and install only what is used. Given test suite size, full install is recommended.

### Pitfall 5: SSH Heredoc Secret Expansion
**What goes wrong:** The `.env` file written in the deploy SSH heredoc expands secrets on the runner before sending — this is correct behavior but requires careful quoting.
**Why it happens:** The outer heredoc uses `<< 'ENDSSH'` (single quotes = no expansion), but the inner cat heredoc uses `<< EOF` (no quotes = expansion on the runner). This is the correct pattern already in the existing workflow.
**How to avoid:** Keep the existing quoting pattern: outer `'ENDSSH'` prevents expanding runner env vars; inner `EOF` allows secret interpolation.

---

## Code Examples

Verified patterns from official sources:

### Full Three-Job Workflow Skeleton
```yaml
# Source: https://docs.github.com/en/actions/using-jobs/using-jobs-in-a-workflow
name: Test → Build → Deploy

on:
  push:
    branches: [master]
    paths:
      - 'src/**'
      - 'app.py'
      - 'ingest_cli.py'
      - 'requirements.txt'
      - 'Dockerfile'
      - 'docker-compose.yml'
      - '.github/workflows/deploy.yml'

env:
  IMAGE: ghcr.io/melu251/dok-assistent:latest

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: System-Abhängigkeiten installieren
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y --no-install-recommends libmagic1 poppler-utils tesseract-ocr
      - name: Python-Abhängigkeiten installieren
        run: pip install -r requirements.txt
      - name: Tests ausführen
        run: pytest tests/ -v

  build:
    needs: [test]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      actions: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ env.IMAGE }}
          cache-from: type=gha
          cache-to: type=gha,mode=min

  deploy:
    needs: [build]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Mit Tailscale verbinden
        uses: tailscale/github-action@v4
        with:
          authkey: ${{ secrets.TAILSCALE_AUTH_KEY }}
          args: --accept-routes --accept-dns
          ping: ${{ secrets.VPS_HOST }}

      - name: SSH-Key einrichten
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.VPS_SSH_KEY }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          ssh-keyscan -H ${{ secrets.VPS_HOST }} >> ~/.ssh/known_hosts

      - name: VPS-Erreichbarkeit prüfen (mit Retry)
        uses: Wandalen/wretry.action@master
        with:
          command: nc -zv -w 10 ${{ secrets.VPS_HOST }} 22
          attempt_limit: 3
          attempt_delay: 10000

      - name: Dateien auf VPS kopieren
        run: |
          ssh -i ~/.ssh/deploy_key ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} \
            "mkdir -p /opt/dok-assistent"
          scp -i ~/.ssh/deploy_key \
            docker-compose.yml \
            ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }}:/opt/dok-assistent/

      - name: Auf VPS deployen
        run: |
          ssh -i ~/.ssh/deploy_key ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} bash << 'ENDSSH'
            set -e
            cd /opt/dok-assistent
            cat > .env << EOF
          ANTHROPIC_API_KEY=${{ secrets.ANTHROPIC_API_KEY }}
          OLLAMA_BASE_URL=${{ secrets.OLLAMA_BASE_URL }}
          OLLAMA_EMBED_MODEL=${{ secrets.OLLAMA_EMBED_MODEL }}
          SUPABASE_URL=${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY=${{ secrets.SUPABASE_SERVICE_KEY }}
          CHUNK_SIZE=${{ secrets.CHUNK_SIZE }}
          CHUNK_OVERLAP=${{ secrets.CHUNK_OVERLAP }}
          TOP_K_RESULTS=${{ secrets.TOP_K_RESULTS }}
          LOG_LEVEL=${{ secrets.LOG_LEVEL }}
          CHAINLIT_AUTH_SECRET=${{ secrets.CHAINLIT_AUTH_SECRET }}
          CHAINLIT_USER=${{ secrets.CHAINLIT_USER }}
          CHAINLIT_PASSWORD=${{ secrets.CHAINLIT_PASSWORD }}
          EOF
            echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u melu251 --password-stdin
            docker compose pull
            docker compose up -d --remove-orphans
          ENDSSH

      - name: Container-Health-Check
        run: |
          ssh -i ~/.ssh/deploy_key ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} bash << 'ENDSSH'
            set -e
            MAX_WAIT=120
            ELAPSED=0
            CONTAINER=dok-assistent
            echo "Warte auf Container-Health-Check (max ${MAX_WAIT}s)..."
            while [ $ELAPSED -lt $MAX_WAIT ]; do
              STATUS=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER 2>/dev/null || echo "not_found")
              echo "  Status nach ${ELAPSED}s: $STATUS"
              if [ "$STATUS" = "healthy" ]; then
                echo "Container ist healthy."
                exit 0
              fi
              sleep 10
              ELAPSED=$((ELAPSED + 10))
            done
            echo "FEHLER: Container ist nach ${MAX_WAIT}s nicht healthy (Status: $STATUS)"
            exit 1
          ENDSSH
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailscale/github-action@v2` | `tailscale/github-action@v4` | 2025 (v3→v4 in early 2025) | v4 adds `ping:` parameter for connectivity verification; old authkey format still works |
| Single monolithic CI job | Three separate jobs with `needs:` | Standard GitHub Actions pattern | Each job shows as separate card in Actions UI; failure is isolated and visible |
| No post-deploy verification | `docker inspect` health loop via SSH | This phase | Deployment failures surface in CI rather than silently passing |

**Deprecated/outdated:**
- `tailscale/github-action@v2`: Still works but does not support `ping:` parameter for connectivity verification. Update to v4.

---

## Open Questions

1. **Tailscale authkey type**
   - What we know: The existing secret `TAILSCALE_AUTH_KEY` exists and was working with v2. The current project uses `authkey:` input.
   - What's unclear: Whether the existing key is ephemeral+reusable (required for CI) or a single-use key that may have expired.
   - Recommendation: Verify in Tailscale admin console that the key is tagged as "Reusable" and "Ephemeral". Regenerate if needed before running the new workflow.

2. **GitHub Actions cache scope across split jobs**
   - What we know: `cache-from: type=gha` / `cache-to: type=gha,mode=min` is in the current build step. When split into a separate `build` job, the GHA cache should still be available between jobs in the same workflow run.
   - What's unclear: Whether the `actions: write` permission (needed for GHA cache) is still needed on the build job after split.
   - Recommendation: Keep `actions: write` on the `build` job. GHA cache is scoped to the repo and branch, not individual jobs.

3. **System apt dependencies for test job**
   - What we know: `unstructured[pdf,docx,xlsx]` requires `libmagic1`, `poppler-utils`, `tesseract-ocr` to import without errors.
   - What's unclear: Whether test mocks prevent these imports from being exercised, or whether the import itself fails without system libs.
   - Recommendation: Add a brief apt-get install step in the test job for these three packages before `pip install -r requirements.txt`. This mirrors the Dockerfile and ensures import parity.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.23+ |
| Config file | `pytest.ini` (exists, `asyncio_mode = auto`) |
| Quick run command | `pytest tests/ -v` |
| Full suite command | `pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map

This phase's requirements are workflow-level (GitHub Actions YAML), not Python code. The test strategy is **smoke/manual verification** after the workflow is committed.

| Req ID | Behavior | Test Type | Automated Command | Notes |
|--------|----------|-----------|-------------------|-------|
| CICD-01 | Failing pytest blocks build and deploy | manual-only | Trigger via a deliberately broken test commit | Cannot be unit-tested; verified by observing red CI status |
| CICD-02 | Three separate jobs visible in Actions UI | manual-only | Observe GitHub Actions run after push | Structural verification — correct `needs:` syntax guarantees this |
| CICD-03 | Tailscale retry + container health check | manual-only | Observe deploy job logs after successful push | Health check bash script is self-verifying via exit code |

**Note on CICD-01 manual verification:** The cleanest approach is: (1) commit the new workflow, (2) temporarily introduce a `assert False` in a test, (3) push, (4) observe red `test` job + skipped `build`/`deploy` jobs, (5) revert the broken test.

### Sampling Rate
- **Per task commit:** `pytest tests/ -v` (existing tests must remain green)
- **Per wave merge:** `pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work` AND one successful end-to-end GitHub Actions workflow run

### Wave 0 Gaps
- None for Python code — existing test infrastructure is sufficient.
- The workflow YAML itself is not testable via pytest; manual CI observation is the verification method.

---

## Sources

### Primary (HIGH confidence)
- [GitHub Actions: Using jobs in a workflow](https://docs.github.com/en/actions/using-jobs/using-jobs-in-a-workflow) — `needs:` keyword syntax, job dependency behavior, UI display
- [tailscale/github-action GitHub repository](https://github.com/tailscale/github-action) — v4 current version (v4.1.2), `ping:` parameter, authkey usage
- [Tailscale GitHub Actions KB](https://tailscale.com/kb/1276/github-actions) — ephemeral/reusable key requirements, runner compatibility
- [Wandalen/wretry.action GitHub Marketplace](https://github.com/marketplace/actions/retry-action) — `attempt_limit`, `attempt_delay` parameter names

### Secondary (MEDIUM confidence)
- [Docker `docker inspect` healthcheck pattern](https://www.australtech.net/docker-healthcheck-instruction/) — `{{.State.Health.Status}}` format string
- Existing `docker-compose.yml` in project — healthcheck timing values (30s interval, 20s start_period, 3 retries) used to calculate MAX_WAIT=120s

### Tertiary (LOW confidence)
- Community discussions on GitHub Actions job splitting patterns — multiple sources agree on `needs:` as the correct mechanism

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — tailscale/github-action v4 and wretry.action verified via official GitHub repositories
- Architecture: HIGH — `needs:` keyword is documented official GitHub Actions behavior; health check pattern is standard docker inspect usage
- Pitfalls: MEDIUM — Tailscale v2→v4 migration verified; apt dependency requirement for unstructured is inferred from Dockerfile but not directly tested in CI context

**Research date:** 2026-03-17
**Valid until:** 2026-06-17 (stable tooling; review tailscale/github-action version on use)
