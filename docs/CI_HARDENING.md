# CI Hardening

## What's running

### GitHub Actions CI (`.github/workflows/ci.yml`)

| Job | Trigger | What it does |
|-----|---------|---------------|
| `lint` | every push/PR | `ruff check app tests scripts` |
| `test` | after lint | pytest on Python 3.11 + 3.13, offline smoke |
| `dep-audit` | after lint | `scripts/audit_dependencies.py` — flags deps installed outside pyproject.toml upper bounds |
| `secret-scan` | after lint | Gitleaks full-history scan + `.gitleaks.toml` rules |
| `docker` | after test+dep-audit+secret-scan | Docker build, paper-mode container smoke, `/health` check |
| `compose` | after test+dep-audit+secret-scan | `docker compose config` validation + compose-up smoke |
| `conventional-commits` | PR only, after test+dep-audit+secret-scan | Enforces `<type>(<scope>): description` PR titles |

Jobs run in parallel where possible; Docker/compose wait for the dependency and security gates to pass first.

### Pre-commit hooks (`.pre-commit-config.yaml`)

Install once: `pip install pre-commit && pre-commit install`

| Hook | What it catches |
|------|----------------|
| `trailing-whitespace` | accidental trailing spaces |
| `end-of-file-fixer` | files not ending with newline |
| `check-yaml` / `check-toml` / `check-json` | malformed config files |
| `check-added-large-files` | commits > 512 KB |
| `check-case-conflict` | files that differ only by case (breaks macOS) |
| `detect-aws-credentials` | AWS keys in `.env*` files |
| `detect-private-key` | any PEM private key in staging |
| `ruff` + `ruff-format` | lint errors and formatting issues (auto-fixed on commit) |
| `python-check-blanket-noqa` | bare `# noqa` without a specific error code |
| `gitleaks --staged --no-git` | secrets in staged changes (local gate before push) |

### Gitleaks (`.gitleaks.toml`)

Runs both in CI (full history) and pre-commit (staged files only). Custom rules cover: Binance API keys, JWTs, Telegram tokens, PEM private keys, AWS keys, GitHub PATs, and connection strings with embedded passwords. `.env.example` and `docs/` are on the allowlist because they contain realistic-looking placeholder values.

## Why these gates exist

- **No duplicate secret scanners** — Gitleaks in CI + pre-commit. The `scripts/release_check.py` entropy scan is a local-only fallback for devs without gitleaks installed.
- **Dependency audit is a separate job** — it can fail independently of tests (out-of-date upper bounds in pyproject.toml).
- **Gitleaks allowlist for `.env.example`** — realistic placeholders would otherwise trigger the generic high-entropy rules. The allowlist is scoped to that file only.
- **Conventional commits on PR titles only** — commit messages are not enforced (many contributors use non-conventional formats); the PR title is the contractual interface for the changelog.
- **Pre-commit gitleaks scans staged changes, not the working tree** — this avoids false positives from files you haven't staged yet.
- **`cancel-in-progress: true` on concurrency** — a new push to a branch cancels the previous CI run for that ref, saving minutes.

## Local-only checks (not in CI)

These run locally via `make ci-local` or `make release-check` and require a Python venv:

```bash
make ci-local           # lint + test + smoke + release-check
make release-check      # release-readiness checks only
make audit-deps         # dependency upper-bound audit only
```

`scripts/release_check.py` also does its own high-entropy scan (complementing gitleaks).

## Adding a new dependency

1. Add it to the appropriate `[project.optional-dependencies]` section in `pyproject.toml` with an upper bound (e.g. `"requests>=2.28,<3"`).
2. Run `make audit-deps` to verify it doesn't exceed the bound.
3. Update `.env.example` if the dependency adds a new env var.
4. The `dep-audit` CI job will catch if someone installs a version that violates the upper bound.

## GitHub repo settings (manual — not code)

After merging, also configure on GitHub:

1. **Branch protection** on `master`: require PR + at least 1 approving review, block force-push.
2. **GitHub Advanced Security** (Settings → Security): enable Dependency review, Secret scanning, and Code scanning. Secret scanning push protection is also available — turn it on to block pushes that contain detected secrets.
3. **CODEOWNERS**: add a `CODEOWNERS` file so certain paths (e.g. `.github/`, `app/`) require review from specific team members.
4. **Dependabot**: enable in Settings → Code security and analysis → Dependabot. It will open PRs when dependencies have known vulnerabilities.

## CI failure triage

| Symptom | Likely cause |
|---------|--------------|
| `dep-audit` fails | pip installed a package version newer than the upper bound in pyproject.toml. Update the bound or downgrade the package. |
| `secret-scan` fails | A real secret was committed or `.env.example` contains something that matches a gitleaks rule. Check `.gitleaks-report.json`. |
| `conventional-commits` fails | PR title doesn't match the pattern. Rename the PR title on GitHub. |
| `docker` fails but local build works | CI uses Python 3.13-slim base image. Check that your code has no Python version-specific imports. |
| `compose` fails at config validation | `docker compose config -q` is strict. Run it locally before pushing. |
