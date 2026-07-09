{
  description = "trafilatura-scrape: Firecrawl-compatible web scrape server";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;

        # trafilatura is NOT in nixpkgs (as of Jul 2026).
        # Build it from PyPI with its full dependency tree.
        trafilatura = python.pkgs.buildPythonPackage rec {
          pname = "trafilatura";
          version = "2.1.0";
          src = python.pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="; # FIXME: set after `nix build 2>&1 | grep 'got:'`
          };
          # trafilatura deps — all are in nixpkgs or light
          propagatedBuildInputs = with python.pkgs; [
            courlan
            dateparser
            htmldate
            justext
            lxml
            lxml-html-clean
          ];
          doCheck = false;
          pythonImportsCheck = [ "trafilatura" ];
        };

        scrape-server = python.pkgs.buildPythonPackage rec {
          pname = "trafilatura-scrape";
          version = "1.0.0";
          src = ./.;
          propagatedBuildInputs = with python.pkgs; [
            trafilatura
            requests
          ];
          doCheck = false;
          pythonImportsCheck = [ "trafilatura_scrape" ];
        };
      in
      {
        packages.default = scrape-server;

        apps.default = flake-utils.lib.mkApp {
          drv = scrape-server;
          exePath = "/bin/trafilatura-scrape";
        };

        # Convenience: nix develop gives you a shell with all deps
        devShells.default = python.pkgs.buildPythonPackage {
          name = "trafilatura-scrape-dev";
          src = ./.;
          propagatedBuildInputs = with python.pkgs; [
            trafilatura
            requests
            pytest
          ];
          doCheck = false;
        };
      }
    );
}
