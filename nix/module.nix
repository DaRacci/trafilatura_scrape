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
        Environment = [
          "SCRAPE_HOST=${cfg.host}"
          "SCRAPE_PORT=${toString cfg.port}"
        ];

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
