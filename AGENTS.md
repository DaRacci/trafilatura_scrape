# AGENTS.md — Agent Guide for trafilatura-scrape

**Repo root:** `/data/workspace/projects/trafilatura-scrape`

## Structure

```
├── flake.nix                  # Nix flake (primary build)
├── default.nix                # Nix derivation (for callPackage)
├── pyproject.toml             # PEP 621 metadata
├── trafilatura_scrape/
│   ├── __init__.py
│   ├── __main__.py            # Entry point
│   ├── server.py              # Compat shim (re-exports scrape/handler)
│   ├── scrape.py              # extract(), batch_extract() — fetch + trafilatura/pypdf
│   ├── handler.py             # _Handler, create_app(), serve() — routing
│   ├── search.py              # /v2/search + /v1/search via SearXNG JSON API
│   ├── map.py                 # /v2/map via sitemap + page links
│   └── parse.py               # parse_pdf() via pypdf (text layer only)
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # in-process server fixture (port 0)
│   ├── test_server.py
│   ├── test_scrape.py
│   ├── test_routes.py
│   ├── test_search.py
│   ├── test_batch.py
│   ├── test_map.py
│   └── test_parse.py
├── README.md
└── .gitignore
```

## API endpoints

- `GET  /health` — liveness
- `POST /v2/scrape` (alias `/v1/scrape`) — one URL, formats: markdown/html/rawHtml/links/images/summary; PDF URLs auto-parse via pypdf
- `POST /v2/batch/scrape` — sync multi-URL scrape, per-URL error isolation (max 50)
- `POST /v2/map` — sitemap + page links for a site
- `POST /v2/parse` — PDF URL → markdown (pypdf, text layer only)
- `POST /v2/search` (alias `/v1/search`, bare-array response) — web/news search via SearXNG (`SEARXNG_URL` required)

Env: `SCRAPE_HOST`, `SCRAPE_PORT`, `SEARXNG_URL`, `SCRAPE_LANG`, `SCRAPE_MAX_WORKERS`.

Not supported (deliberate): screenshots/actions (no browser), LLM formats (json/query/branding/product — return `warning`), changeTracking (stateless), `/v2/crawl` and async job endpoints (sync only), multipart `/parse` upload.

## Building

```bash
nix build
nix build .#default
```

## Running

```bash
./result/bin/trafilatura-scrape
uv run trafilatura-scrape
```

## Git

- Conventional Commits (`feat:`, `fix:`, `refactor:`, etc.)
- Push to `codeberg.org/racci/trafilatura_scrape`
