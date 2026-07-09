{ lib, buildPythonPackage, fetchPypi, python312Packages, callPackage }:

let
  # trafilatura is not in nixpkgs; build from PyPI
  trafilatura = python312Packages.buildPythonPackage rec {
    pname = "trafilatura";
    version = "2.1.0";
    src = fetchPypi {
      inherit pname version;
      hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="; # FIXME
    };
    propagatedBuildInputs = with python312Packages; [
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
in
buildPythonPackage rec {
  pname = "trafilatura-scrape";
  version = "1.0.0";
  src = ./.;
  propagatedBuildInputs = with python312Packages; [
    trafilatura
    requests
  ];
  doCheck = false;
  pythonImportsCheck = [ "trafilatura_scrape" ];
  meta = with lib; {
    description = "Firecrawl-compatible web scrape server backed by trafilatura";
    homepage = "https://github.com/NousResearch/hermes-agent";
    license = licenses.mit;
    maintainers = [ ];
  };
}
