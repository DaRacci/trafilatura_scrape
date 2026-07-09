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
│   └── server.py              # HTTP server
├── tests/
│   ├── __init__.py
│   └── test_server.py
├── README.md
└── .gitignore
```

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
