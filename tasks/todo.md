# Google Search Console CLI Plan

## Goals
- Build a Python CLI (Click-based) for Google Search Console API v3.
- Authenticate via OAuth user credentials loaded from ADC (`gcloud auth application-default login`).
- Support at minimum:
  - listing accessible properties (domains/sites)
  - getting a single property by `siteUrl`
  - adding a property (`site add`)
  - querying Search Analytics by date/query/page with full supported filters.

## API/Auth Facts (validated against official docs)
- API service name/version for Python client: `searchconsole` / `v1`.
- Base endpoint used by client methods: `https://www.googleapis.com/webmasters/v3/...`.
- Read scopes: `https://www.googleapis.com/auth/webmasters.readonly` or `https://www.googleapis.com/auth/webmasters`.
- Write scope (required for `sites.add`): `https://www.googleapis.com/auth/webmasters`.
- `searchAnalytics.query` supports:
  - dimensions: `country`, `device`, `page`, `query`, `searchAppearance`, plus `date`, `hour` for grouping.
  - operators: `contains`, `equals`, `notContains`, `notEquals`, `includingRegex`, `excludingRegex`.
  - groupType: currently only `and`.
  - type: `web`, `image`, `video`, `news`, `discover`, `googleNews`.
  - aggregationType: `auto`, `byPage`, `byProperty`, `byNewsShowcasePanel` (with constraints).
  - rowLimit 1..25000, startRow >= 0.

## Proposed CLI UX
- Binary entrypoint: `gsc`.
- Command groups:
  - `gsc site list`
  - `gsc site get --site sc-domain:example.com`
  - `gsc site add --site sc-domain:example.com`
  - `gsc analytics query --site sc-domain:example.com --start-date YYYY-MM-DD --end-date YYYY-MM-DD [options]`

### Analytics Options
- `--dimension` (repeatable; preserves order)
- `--type` (`web|image|video|news|discover|googleNews`)
- `--aggregation-type` (`auto|byPage|byProperty|byNewsShowcasePanel`)
- `--row-limit` (default 1000; max 25000)
- `--start-row` (default 0)
- `--data-state` (`final|all|hourly_all`)
- `--filter` (repeatable, DSL format): `dimension:operator:expression`
  - Example: `--filter query:contains:brand --filter device:equals:MOBILE`
- `--output` (`table|json|csv`, default `table`)
- `--csv-path` (required when `--output csv`)

## Filter/Validation Rules
- Parse each `--filter` into `dimensionFilterGroups[0].filters[]` with `groupType="and"`.
- Validate allowed dimensions/operators early in CLI with clear errors.
- Validate date format (`YYYY-MM-DD`) and date ordering (`start <= end`).
- Validate `row-limit` and `start-row` range.
- Guard known invalid combos before API call:
  - if grouping/filtering by `page` and `aggregationType=byProperty`, fail fast.

## Project Structure
- `pyproject.toml` (packaging, deps, entrypoint)
- `gsc_cli/__init__.py`
- `gsc_cli/cli.py` (Click root and subcommands)
- `gsc_cli/auth.py` (ADC credential loading + scope checks)
- `gsc_cli/client.py` (Search Console service builder)
- `gsc_cli/analytics.py` (request construction + response shaping)
- `gsc_cli/output.py` (table/json/csv formatting)
- `tests/` (unit tests for parser/validation and command behavior)
- `README.md` (setup, auth command, examples, troubleshooting)

## Auth Approach
- Use `google.auth.default(scopes=[...])` to load ADC and refresh tokens.
- Build API client via `googleapiclient.discovery.build("searchconsole", "v1", credentials=creds, cache_discovery=False)`.
- Default scope strategy:
  - read commands request readonly scope.
  - write commands request write scope.
- If ADC missing/invalid, show actionable error with example login command:
  - `gcloud auth application-default login --client-id-file=<oauth-client.json> --scopes=https://www.googleapis.com/auth/webmasters`

## Error Handling/Exit Codes
- User/input errors: exit code 2 with actionable message.
- Auth errors: exit code 3 with remediation steps.
- API errors (HttpError): exit code 4 with status + API message.

## Verification Plan
- Unit tests:
  - filter parsing (valid and invalid cases)
  - date/range validation
  - request body generation for analytics query
  - output formatting (json/csv/table)
- Command tests (Click `CliRunner`) with mocked API service:
  - site list/get/add happy paths
  - analytics query with dimensions/filters
  - invalid flag combinations
- Manual smoke tests (real account):
  - `gsc site list`
  - `gsc site get --site <property>`
  - `gsc analytics query ... --dimension date`
  - `gsc analytics query ... --dimension query --filter page:equals:<url>`
  - optional write test: `gsc site add --site sc-domain:<domain>`

## Execution Checklist
- [x] Confirm official API/auth requirements and supported query/filter fields.
- [x] Scaffold Python package and dependency config.
- [x] Implement auth/client modules with scoped credential loading.
- [x] Implement `site list/get/add` commands.
- [x] Implement analytics request builder and filter parser.
- [x] Implement output formatters (table/json/csv).
- [x] Add tests for parser/validation/commands.
- [x] Update README with full setup and examples.
- [x] Run test suite and basic linting.
- [x] Perform manual smoke tests with local ADC.

## OSS UX Improvement Plan

### Goals
- Make onboarding easy for open source users with no `.venv/bin/...` requirement.
- Remove mandatory `gcloud` dependency from normal auth flow.
- Add built-in diagnostics and default-site config to reduce repeated flags.

### Planned CLI Additions
- `gsc auth login --client-secret <path>` for OAuth Installed App flow.
- `gsc auth whoami` to show token file location and scopes.
- `gsc doctor` to validate config/auth/runtime environment.
- `gsc config set default-site <siteUrl>` and `gsc config get default-site`.

### Internal Changes
- Add `google-auth-oauthlib` dependency.
- Implement credential storage at `~/.config/gsc-cli/credentials.json`.
- Update credential loader to prefer app credentials, fallback to ADC.
- Add config storage at `~/.config/gsc-cli/config.json`.
- Resolve `--site` from config when flag is omitted for `site get`, `site add`, `analytics query`.

### Verification
- Unit tests for config store/load and site resolution behavior.
- CLI tests for `auth login` (mocked flow), `doctor`, and config commands.
- Regression tests for existing site/analytics commands.

### Execution Checklist (OSS UX)
- [x] Add OAuth installed-app login module and token persistence.
- [x] Add config module with default-site support.
- [x] Update API client auth loading order (stored creds -> ADC fallback).
- [x] Add `auth` command group and `doctor` command.
- [x] Update `site` and `analytics` commands to use default-site fallback.
- [x] Add tests for new auth/config/doctor/default-site flows.
- [x] Update README for pipx-first installation and new onboarding flow.
- [x] Run full test suite and live smoke tests.

## Sitemaps Feature Plan (2026-02-18)

### Goal
- Add sitemap management to CLI for Search Console properties: list/get/submit/delete.

### API Facts (official docs)
- `sitemaps.list`: `GET /webmasters/v3/sites/{siteUrl}/sitemaps`, optional `sitemapIndex`, read or write scope.
- `sitemaps.get`: `GET /webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}`, read or write scope.
- `sitemaps.submit`: `PUT /webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}`, write scope.
- `sitemaps.delete`: `DELETE /webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}`, write scope.
- Sitemap fields include `path`, `lastSubmitted`, `lastDownloaded`, `isPending`, `isSitemapsIndex`, `type`, `warnings`, `errors`, `contents`.

### Execution Checklist (Sitemaps)
- [x] Add `gsc sitemap` command group with `list/get/submit/delete`.
- [x] Reuse default-site resolution (`--site` optional with config fallback).
- [x] Add output support for sitemap list/get (`table|json|csv`).
- [x] Add unit/CLI tests for sitemap commands and scope usage.
- [x] Update README usage with sitemap examples and notes.
- [x] Run test suite and manual live smoke tests against real credentials.

## URL Inspection Feature Plan (2026-02-18)

### Goal
- Add manual URL index-status check via Search Console URL Inspection API.

### API Facts (official docs)
- `urlInspection.index.inspect`: `POST https://searchconsole.googleapis.com/v1/urlInspection/index:inspect`.
- Request body fields: `inspectionUrl` (required), `siteUrl` (required), `languageCode` (optional, default `en-US`).
- Scopes: `webmasters.readonly` or `webmasters`.

### Execution Checklist (URL Inspection)
- [x] Add `gsc url inspect` command for inspecting one URL in a property.
- [x] Reuse default-site resolution (`--site` optional with config fallback).
- [x] Support `table|json|csv` output with stable field mapping.
- [x] Add unit/CLI tests for request wiring and default-site behavior.
- [x] Update README docs for URL inspection and current feature set.
- [x] Run full tests and live smoke test against real credentials/property.
