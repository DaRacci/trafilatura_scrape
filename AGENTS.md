# AGENTS.md — Agent Guide for trafilatura-scrape

**Repo root:** `/data/workspace/projects/trafilatura-scrape`

## Structure

```
├── flake.nix                  # Nix flake (primary build)
├── default.nix                # Nix derivation (for overlays / callPackage)
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
nix build            # via flake
nix build .#default  # explicit
```

No hash-fixing needed — `trafilatura` is available in nixpkgs directly
as `python3XXPackages.trafilatura`. The flake pins to `python312Packages`;
if your nixpkgs has it under 3.13, change `python312Packages` to
`python313Packages` in `flake.nix` or override in your integration.

## Running

```bash
# From the Nix build
./result/bin/trafilatura-scrape

# Or via Python directly
uv run trafilatura-scrape
```

## Nix integration with Hermes

In your nix-config:

```nix
services.hermes-agent = {
  enable = true;
  package = pkgs.hermes-agent.override {
    extraPythonPackages = with pkgs.python312Packages; [
      (callPackage /path/to/trafilatura-scrape { })
      (callPackage /path/to/trafilatura-scrape/trafilatura.nix { })  # if trafilatura dep is extracted
    ];
  };
  settings = {
    web.extract_backend = "firecrawl";
  };
  environment = {
    FIRECRAWL_API_URL = "http://127.0.0.1:8766";
  };
};
```

## Secrets

No secrets in this repo — it's a stateless HTTP server with no auth.

## Git

- Conventional Commits (`feat:`, `fix:`, `refactor:`, etc.)
- Push to Codeberg/GitHub as needed
