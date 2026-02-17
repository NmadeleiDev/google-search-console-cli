# google-search-console-cli

CLI for Google Search Console using the official Google API Python client.

## Highlights
- Native OAuth login: no mandatory `gcloud` setup
- `pipx`-friendly install (`gsc` available globally)
- Site operations: list/get/add
- Analytics queries by date/query/page with Search Console filters
- Output formats: table, json, csv
- Diagnostics: `gsc doctor`

## Install (Recommended)

Install with `pipx` so `gsc` is available globally on your PATH.

If you do not have `pipx` yet:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Restart your shell, then install:

```bash
pipx install google-search-console-cli
```

Verify:

```bash
gsc --version
```

Upgrade later:

```bash
pipx upgrade google-search-console-cli
```

Uninstall:

```bash
pipx uninstall google-search-console-cli
```

## Install From Source

If you cloned this repository and want to run from source, use one of these options.

Option 1: Local virtualenv (best for development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Fish shell activation:

```fish
. .venv/bin/activate.fish
```

Then run:

```bash
gsc --help
```

Option 2: Install from source with `pipx` (best for day-to-day CLI usage)

```bash
pipx install -e /absolute/path/to/google-search-console-cli
```

## OAuth Setup (Recommended)

Create a Google OAuth client of type **Desktop app**, then run:

```bash
gsc auth login --client-secret /absolute/path/to/client_secret.json
```

Verify:

```bash
gsc auth whoami
gsc doctor
```

## Optional: Set Default Site

```bash
gsc config set default-site sc-domain:example.com
gsc config get default-site
```

After this, you can omit `--site` in commands that need a property.

## Usage

### Sites
```bash
gsc site list
gsc site get --site sc-domain:example.com
gsc site add --site sc-domain:example.com
```

### Analytics
```bash
gsc analytics query \
  --site sc-domain:example.com \
  --start-date 2026-01-01 \
  --end-date 2026-01-31 \
  --dimension date \
  --dimension query \
  --filter query:contains:brand \
  --filter device:equals:MOBILE
```

Save as CSV:

```bash
gsc analytics query \
  --site sc-domain:example.com \
  --start-date 2026-01-01 \
  --end-date 2026-01-31 \
  --dimension page \
  --output csv \
  --csv-path ./analytics.csv
```

## Filter Syntax

Use repeatable filters in this format:

```text
dimension:operator:expression
```

Supported filter dimensions:
- `country`
- `device`
- `page`
- `query`
- `searchAppearance`

Supported operators:
- `contains`
- `equals`
- `notContains`
- `notEquals`
- `includingRegex`
- `excludingRegex`

## Convenience Script (Repo Local)

If you cloned this repo and want one command setup:

```bash
./scripts/setup.sh /absolute/path/to/client_secret.json
```

## Credentials and Config Paths

By default:
- Credentials: `~/.config/gsc-cli/credentials.json`
- Config: `~/.config/gsc-cli/config.json`

Override with env vars:
- `GSC_CREDENTIALS_FILE`
- `GSC_APP_CONFIG_FILE`
- `GSC_CONFIG_DIR`

## ADC Fallback (Optional)

If you prefer ADC via `gcloud`, the CLI still supports it:

```bash
gcloud auth application-default login \
  --client-id-file=/absolute/path/to/client_secret.json \
  --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/webmasters
```

## Notes
- Use Search Console property formats like `sc-domain:example.com` or URL-prefix properties.
- `site add` requires write scope (`webmasters`).
- `analytics query --aggregation-type byProperty` cannot be combined with `page` grouping/filtering.

## Publishing

### Trusted Publishing via GitHub Actions (Recommended)

This repo includes `.github/workflows/publish.yml` that:
- builds `sdist` + `wheel`
- publishes to PyPI using OpenID Connect (no API token needed in GitHub secrets)

To enable it:

1. In PyPI, open project settings for `google-search-console-cli`.
2. Add a **Trusted Publisher** with:
   - Owner: `NmadeleiDev`
   - Repository: `google-search-console-cli`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. In GitHub, keep/create environment `pypi` (optional protection rules as you prefer).

Release flow:

1. Bump version in `pyproject.toml`.
2. Commit and push.
3. Create and push a tag like `v0.1.1`:

```bash
git tag v0.1.1
git push origin v0.1.1
```

The workflow will publish automatically.

### Manual Publishing (Fallback)

```bash
. .venv/bin/activate.fish
python -m build
python -m twine upload dist/*
```
