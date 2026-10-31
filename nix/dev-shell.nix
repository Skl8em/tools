# The devShell a project gets from this repository: the tools of the languages
# it declares, at the versions this flake's nixpkgs pins. A project's flake calls
# `tools.lib.mkDevShell { inherit system; languages = [ ... ]; }`, so bumping the
# `tools` input in its flake.lock is the one way its tool versions change.
{ nixpkgs }:
{
  system,
  languages,
  # project-specific additions, on top of the shared toolchain
  packages ? [ ],
}:
let
  pkgs = nixpkgs.legacyPackages.${system};
  inherit (pkgs) lib;
  python = pkgs.python3;

  byLanguage = {
    python = {
      # uv installs the Python tools (ruff, basedpyright, pytest) that uv.lock
      # pins, into a .venv built on this interpreter, never on one it downloads.
      packages = [
        python
        pkgs.uv
      ];
      env = {
        UV_PYTHON = "${python}/bin/python3";
        UV_PYTHON_DOWNLOADS = "never";
      };
    };
    markdown = {
      packages = [ pkgs.markdownlint-cli2 ];
      env = { };
    };
  };

  unknown = builtins.filter (language: !(byLanguage ? ${language})) languages;
  selected = map (language: byLanguage.${language}) languages;
in
assert lib.assertMsg (unknown == [ ])
  "mkDevShell: unknown language(s): ${toString unknown}; known: ${toString (builtins.attrNames byLanguage)}";
pkgs.mkShell {
  packages = [
    pkgs.just # the recipes: the same gate locally and in CI
    pkgs.reuse # licensing of every file
    pkgs.copier # renders and updates the project's configuration from this repository
    pkgs.git # copier update merges through git
  ]
  ++ builtins.concatMap (language: language.packages) selected
  ++ packages;

  # The justfile refuses to run without it: a tool found elsewhere on the PATH
  # would run at another version than the one CI runs.
  env = {
    TOOLS_DEVSHELL = "1";
  }
  // lib.mergeAttrsList (map (language: language.env) selected);
}
