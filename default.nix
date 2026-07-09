{ lib, buildPythonPackage, python312Packages }:

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
