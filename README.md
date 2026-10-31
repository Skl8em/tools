# tools

This repository collects the configurations and tools that align the IDEs and development ecosystems of my projects.

## Aim

Languages to support:

- markdown
- python
- R
- rust
- javascript
- quarto
- latex

Tools in use:

- Nix devShell
- just
- uv
- reuse
- ruff
- basedpyright
- markdownlint
- pytest

IDEs to support:

- VS Code (and/or VSCodium)
- Zed

Principles:

- Only open-source tools, preferably of the GPL family when two solutions are otherwise similar.
- A strong preference for tools redesigned around a Rust core, especially when speed matters.
- Configurations are stored inside each project, so that editors with their plugins and CI in the cloud produce the same results, errors and recommendations.
- One dedicated file per IDE in each project, holding all the project-relevant configuration of that IDE.

Supported so far: Python and Markdown.
The other languages are added when a real project needs them (see [candidates](#candidate-tools-for-the-other-languages)).

## How it works

Three things must agree for the editor and CI to report the same thing, and this repository provides each one:

1. **Tool versions** come from one place.
   `flake.nix` exports `lib.mkDevShell`, which a project's own `flake.nix` calls with the languages it uses.
   The versions are those of this repository's nixpkgs pin, so `nix flake update tools` in a project is the one way they change.
   Python tools (ruff, basedpyright, pytest) are locked in the project's `uv.lock`, in a `.venv` built on the devShell's interpreter.
2. **Configuration** lives in the project, rendered from [`template/`](template) by [Copier](https://copier.readthedocs.io), which records the answers in `.copier-answers.yml`.
   `copier update` merges a newer template into the project three ways, keeping the project's own edits.
   The rules live in the tools' own files (`ruff.toml`, `pyrightconfig.json`, `.markdownlint-cli2.jsonc`); `.vscode/settings.json` and `.zed/settings.json` only point the editors at the `.venv` binaries.
3. **Invocation** is the same everywhere: `just check`, inside the devShell, locally and in CI (`.github/workflows/checks.yml`).
   The justfile refuses to run outside the devShell, where another version of a tool could be on the PATH.

A project gets:

| File | Owned by | Purpose |
| --- | --- | --- |
| `flake.nix` | template | devShell from `tools.lib.mkDevShell` |
| `justfile` | template | `setup`, `check`, `fix` and the steps of `check` |
| `.github/workflows/checks.yml` | template | `nix develop --command just check` |
| `REUSE.toml` | template | the project's licence for every file without its own header |
| `.vscode/settings.json`, `.vscode/extensions.json` | template | VS Code runs the `.venv` binaries |
| `.zed/settings.json` | template | Zed runs the same language servers |
| `ruff.toml`, `pyrightconfig.json` | template | Python rules (Python projects) |
| `.markdownlint-cli2.jsonc` | template | Markdown rules (Markdown projects) |
| `pyproject.toml`, `src/<package>/`, `tests/test_import.py` | project | skeleton of a new package, rendered once, never updated |

## Using it in a project

`<tools>` stands for this repository's location: its git URL once published, or `~/Documents/Projects/tools` locally.
Copier renders the latest git tag of the template; add `--vcs-ref HEAD` to render the latest commit instead.

A new project:

```sh
mkdir my-project && cd my-project
nix develop <tools> --command copier copy <tools> .
git init && git add --all          # nix sees only the files git tracks
nix develop --command just setup   # adds the Python tools to uv.lock, fetches the licence texts
nix develop --command just check
```

The `tools_flake` question asks for the flake reference of this repository, e.g. `github:<owner>/tools` or `git+file:///Users/bnc/Documents/Projects/tools`.

An existing project: answer *no* to the Python skeleton question, then review `git diff`, since Copier asks before overwriting a file the project already has.
Move any `[tool.ruff]` or `[tool.basedpyright]` table out of `pyproject.toml`: `ruff.toml` and `pyrightconfig.json` take precedence and those tables would be silently ignored.

Later:

```sh
nix develop --command copier update   # newer configuration, merged with local edits
nix develop --command just setup      # when the template raised a tool's lower bound
nix flake update tools                # newer tool versions
```

## Changing the template

```sh
nix develop --command just test-fast   # renders the template, seconds
nix develop --command just check       # everything, including rendering projects and running their own gate
```

Tag a release (`git tag v0.2.0`) for projects to receive it through `copier update`.

This repository uses the configuration it distributes: a test fails when its own `ruff.toml`, `pyrightconfig.json`, `.markdownlint-cli2.jsonc`, `.gitignore`, `.vscode/`, `.zed/` or CI workflow differ from what the template renders with [`tests/repo-answers.json`](tests/repo-answers.json).
To re-render them after a template change:

```sh
tmp=$(mktemp -d) && cp -r copier.yml template "$tmp/" \
  && copier copy --defaults --quiet --data-file tests/repo-answers.json "$tmp" "$tmp/out" \
  && for f in .github/workflows/checks.yml .gitignore .markdownlint-cli2.jsonc .vscode/extensions.json \
      .vscode/settings.json .zed/settings.json pyrightconfig.json ruff.toml; do cp "$tmp/out/$f" "$f"; done
```

Adding a language means an entry in `byLanguage` in [`nix/dev-shell.nix`](nix/dev-shell.nix), a choice in `copier.yml`, its files in `template/`, and the tests that render them.

## Decisions

- **[ANCHOR]** Configuration is distributed as a Copier template and the toolchain as a Nix flake, both versioned together in this repository.
  A dedicated Python package with its own CLI was rejected: it would re-implement copy, update and the three-way merge.
  Runtime inheritance (`extend` pointing outside the project) was rejected: configuration must live in the project.
- **[ANCHOR]** nixpkgs is pinned to `nixos-26.05`, the last release that supports `x86_64-darwin`.
  From 26.11 on, an Intel Mac can no longer follow nixpkgs updates; the pin can stay, but its tools will age.
- Copier (MIT) and most current tools are permissively licensed, not GPL; no GPL alternative of similar scope was found.
- Upstream Nix in CI (`cachix/install-nix-action`), not a vendor distribution; actions are pinned by commit.
- Licensing: this repository's code is GPL-3.0-or-later; what projects receive (the template and the files mirrored from it) is CC0-1.0, so it imposes nothing on a project's own licence.

## Known gaps

- The VS Code markdownlint extension bundles its own markdownlint engine, which can be newer than the CLI the devShell pins; Zed has no markdownlint integration here.
  [rumdl](https://github.com/rvben/rumdl) (Rust, MIT, has a language server) could close both gaps: worth evaluating.
- `.venv` links to the devShell's interpreter in the Nix store; after `nix-collect-garbage`, re-run `just setup`.
- Projects whose CI is not GitHub Actions need their own workflow file.

## Candidate tools for the other languages

To be reviewed when a real project needs them.
Versions are those of nixpkgs 26.05; licences and activity were checked in October 2026.

| Language | Formatter | Linter | Language server | Notes |
| --- | --- | --- | --- | --- |
| Rust | rustfmt | clippy | rust-analyzer | the official toolchain, MIT/Apache-2.0; `cargo-deny` (Apache-2.0) for dependency licences and advisories |
| R | [air](https://github.com/posit-dev/air) 0.9 | [jarl](https://github.com/etiennebacher/jarl) 0.5, or lintr | air | air and jarl: Rust, MIT, young; lintr (R, MIT) is the mature fallback |
| LaTeX | [tex-fmt](https://github.com/WGUNDERWOOD/tex-fmt) 0.5 | ChkTeX (GPL) | [texlab](https://github.com/latex-lsp/texlab) 5.25 | tex-fmt: Rust, MIT; texlab: Rust, GPL-3.0 |
| JavaScript | [Biome](https://github.com/biomejs/biome) 2.4 | Biome, or [oxlint](https://github.com/oxc-project/oxc) 1.65 | Biome | both Rust; Biome (Apache-2.0) formats and lints in one tool; oxlint (MIT) covers more ESLint rules |
| Quarto | [panache](https://github.com/jolars/panache) 2.47 | panache | panache | Rust, MIT, young; `quarto` itself (1.9) renders and checks |
| Markdown | rumdl | rumdl | rumdl | alternative to markdownlint-cli2, see [known gaps](#known-gaps) |
