# Plan

Next steps, in the order they unblock each other.
Valid until the first tagged release is in use by a real project; revise it then.

## State at the first commit

- Python and Markdown are supported: template, devShell, and a test suite that renders projects and runs their own gate.
- `just check` passes locally on `x86_64-darwin`.
- Nothing is pushed, no CI run has happened, and there is no tag, so `copier copy` without `--vcs-ref HEAD` has no release to render.

## 1. First CI run

Push to `origin` and watch `.github/workflows/checks.yml` run.
It is the first time the gate runs on `x86_64-linux`, and the integration tests build two devShells from scratch there with no binary cache besides cache.nixos.org.
Expect it to be slow; a run time worth caching is a reason to look at a self-hosted cache before a vendor one.

Done when: the workflow is green on `main`.

## 2. Tag `v0.1.0`

Only after CI is green, since projects receive the tag, not `main`.
Check that `copier copy <tools> .` without `--vcs-ref` renders it.

## 3. Adopt into one real existing project

The template has only ever been rendered into empty directories by the tests.
Adopt it into an existing Python project (`python_skeleton: no`), following the README, and note every step that needed knowledge the README does not give.
Fix the README, or the template, before a second project.

Done when: that project's `just check` passes locally and in its CI, and a `copier update` to a later tag merges cleanly.

## 4. Decide the `x86_64-darwin` horizon

nixpkgs 26.11 is due at the end of November 2026 and drops `x86_64-darwin`, the architecture of the machine this was developed on.
Options to weigh, not settled:

- keep `nixos-26.05` and let the tools age, bumping them through overlays only when needed;
- follow 26.11 on Linux and Apple Silicon, and keep a 26.05 input for `x86_64-darwin` only, at the cost of two toolchains that can drift;
- move development of these projects off the Intel Mac.

The first option is the current default; the decision belongs to the owner of the hardware, not to this repository.

## 5. One source for the Python tool lower bounds

`basedpyright>=1.40`, `pytest>=9.1`, `ruff>=0.17` are written twice: in `template/justfile.jinja` (what `just setup` adds to a project) and in this repository's `pyproject.toml`.
Add a test that fails when they differ, before the first bump makes them differ.

## 6. Evaluate rumdl

See [known gaps](README.md#known-gaps): it could give Zed Markdown diagnostics and remove the engine mismatch with the VS Code extension.
Evaluate against markdownlint-cli2 on a real project's documentation: same findings, same fixes, one binary pinned by the devShell for CLI and editor alike.

## 7. Further languages, when a project needs them

Not before: see [candidates](README.md#candidate-tools-for-the-other-languages).
R and Rust are the likeliest first, given the projects in view.
Each follows the README's recipe: `byLanguage` entry, `copier.yml` choice, template files, rendering and integration tests.
