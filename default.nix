{ lib, buildPythonPackage, pythonPackages }:

buildPythonPackage rec {
  pname = "trafilatura-scrape";
  version = "1.0.0";
  src = ./.;
  propagatedBuildInputs = with pythonPackages; [
    trafilatura
    requests
  ];
  doCheck = false;
  pythonImportsCheck = [ "trafilatura_scrape" ];
  meta = with lib; {
    description = "Firecrawl-compatible web scrape server backed by trafilatura";
    homepage = "https://codeberg.org/racci/trafilatura_scrape";
    license = licenses.mit;
    maintainers = [ ];
  };
}
