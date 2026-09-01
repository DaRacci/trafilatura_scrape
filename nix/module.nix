{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.trafilatura-scrape;
  inherit (lib)
    mkEnableOption
    mkIf
    mkOption
    types
    ;
in
{
  options.services.trafilatura-scrape = {
    enable = mkEnableOption "Firecrawl-compatible web scrape server backed by trafilatura";

    package = mkOption {
      type = types.package;
      default = pkgs.callPackage ./package.nix { };
      description = "The trafilatura-scrape package to run.";
    };

    host = mkOption {
      type = types.str;
      default = "127.0.0.1";
      description = "Address to bind the scrape server to.";
    };

    port = mkOption {
      type = types.port;
      default = 8766;
      description = "Port to listen on.";
    };

    searxng.url = mkOption {
      type = types.nullOr types.str;
      default = null;
      example = "https://searx.example.com";
      description = ''
        Base URL of a SearXNG instance with the JSON format enabled, passed as
        SEARXNG_URL. The /v2/search and /v1/search endpoints return an error
        when this is not set.
      '';
    };

    searxng.language = mkOption {
      type = types.str;
      default = "en";
      example = "de";
      description = "Search result language, passed as SCRAPE_LANG.";
    };

    maxWorkers = mkOption {
      type = types.nullOr types.ints.positive;
      default = null;
      example = 8;
      description = ''
        Maximum concurrent workers for batch scrapes, passed as
        SCRAPE_MAX_WORKERS. The server default is used when null.
      '';
    };

    environmentFile = mkOption {
      type = types.nullOr types.path;
      default = null;
      example = "/run/secrets/trafilatura-scrape.env";
      description = ''
        Environment file loaded by systemd, useful for SCRAPE_* variables
        containing secrets that should not live in the world-readable config.
      '';
    };
  };

  config = mkIf cfg.enable {
    systemd.services.trafilatura-scrape = {
      description = "Firecrawl-compatible web scrape server (trafilatura-scrape)";
      wantedBy = [ "multi-user.target" ];
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];

      serviceConfig = {
        ExecStart = "${lib.getExe cfg.package}";
        Restart = "always";
        RestartSec = 5;
        DynamicUser = true;
        Environment =
          [
            "SCRAPE_HOST=${cfg.host}"
            "SCRAPE_PORT=${toString cfg.port}"
          ]
          ++ lib.optionals (cfg.searxng.url != null) [
            "SEARXNG_URL=${cfg.searxng.url}"
            "SCRAPE_LANG=${cfg.searxng.language}"
          ]
          ++ lib.optionals (cfg.maxWorkers != null) [
            "SCRAPE_MAX_WORKERS=${toString cfg.maxWorkers}"
          ];
        EnvironmentFile = mkIf (cfg.environmentFile != null) [ cfg.environmentFile ];

        # Hardening
        AmbientCapabilities = "";
        NoNewPrivileges = true;
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        RestrictNamespaces = true;
        RestrictRealtime = true;
        RestrictSUIDSGID = true;
      };
    };
  };
}
