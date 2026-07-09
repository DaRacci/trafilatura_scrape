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
        # trafilatura is in nixpkgs under python3XXPackages.trafilatura.
        # Pin to the Hermes Python version (3.12 or 3.13).
        pythonPkgs = pkgs.python312Packages;
      in
      {
        packages.default = pythonPkgs.buildPythonPackage rec {
          pname = "trafilatura-scrape";
          version = "1.0.0";
          src = ./.;
          propagatedBuildInputs = with pythonPkgs; [
            trafilatura
            requests
          ];
          doCheck = false;
          pythonImportsCheck = [ "trafilatura_scrape" ];
          meta = with pkgs.lib; {
            description = "Firecrawl-compatible web scrape server backed by trafilatura";
            homepage = "https://github.com/NousResearch/hermes-agent";
            license = licenses.mit;
            mainProgram = "trafilatura-scrape";
          };
        };

        apps.default = flake-utils.lib.mkApp {
          drv = self.packages.${system}.default;
        };
      }
    );
}
