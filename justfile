# This repository's recipes, run inside its devShell: `nix develop --command just <recipe>`.
# Projects get their own justfile from template/justfile.jinja.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List the recipes
default:
    @just --list

# Build the environment from uv.lock
setup: _devshell
    uv sync --locked

# The gate: CI runs exactly this
check: _devshell lint typecheck test licensing

# Rewrite what the formatters and linters can fix
fix: _devshell
    uv run --locked ruff format .
    uv run --locked ruff check --fix .
    markdownlint-cli2 --fix
    nixfmt flake.nix nix/*.nix

lint: _devshell
    uv run --locked ruff format --check .
    uv run --locked ruff check .
    markdownlint-cli2
    nixfmt --check flake.nix nix/*.nix

typecheck: _devshell
    uv run --locked basedpyright

# Every test, including the integration tests that build rendered projects' devShells
test: _devshell
    uv run --locked pytest

# The tests that only render the template (seconds, no network)
test-fast: _devshell
    uv run --locked pytest -m "not integration"

licensing: _devshell
    reuse lint

# A tool found elsewhere on the PATH would run at another version than CI's.
_devshell:
    @[ "${TOOLS_DEVSHELL:-}" = 1 ] || { echo "run inside the devShell: nix develop --command just <recipe>" >&2; exit 1; }
