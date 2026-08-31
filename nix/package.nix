{ lib, python3Packages }:

python3Packages.buildPythonPackage rec {
  pname = "trafilatura-scrape";
  version = "1.0.0";
  src = ./..;
  pyproject = true;
  build-system = [ python3Packages.setuptools ];
  propagatedBuildInputs = with python3Packages; [
    pypdf
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
    mainProgram = "trafilatura-scrape";
  };
}
