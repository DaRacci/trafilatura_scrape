{
  lib,
  python3Packages,
}:

let
  pyproject = lib.importTOML ../pyproject.toml;
in

python3Packages.buildPythonPackage {
  pname = pyproject.project.name;
  version = pyproject.project.version;
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
  meta = {
    description = pyproject.project.description;
    homepage = pyproject.project.urls.Homepage;
    license = lib.licenses.${lib.toLower pyproject.project.license.text};
    maintainers = [ ];
    mainProgram = pyproject.project.name;
  };
}
