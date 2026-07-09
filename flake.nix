{
  description = "trafilatura-scrape: Firecrawl-compatible web scrape server";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonPkgs = pkgs.python3Packages;
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
            homepage = "https://codeberg.org/racci/trafilatura_scrape";
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
