# Upstream decisions

Decisions taken outside this repository, in the owner's workstation configuration, that this repository must follow.
Each one says what was decided, why in brief, and what it changes here; the records themselves live in a private repository, cited by number for traceability.
Valid until each item's "Here" list is done; then fold the decision into the README's [Decisions](README.md#decisions) and drop it from this file.

## D1. Python type checking: basedpyright stays the gate, ty runs beside it until it can replace it

Decided 2026-11-02 (record 0003).

The owner wants to move to ty (Astral, Rust, MIT).
On a probe file, ty 0.0.95 with `[rules] all = "error"` and ruff's `ANN` rules caught missing annotations, explicit `Any`, wrong return types, and an `Any` reaching a typed `return` (`unsound-return-statement`).
It did not catch an implicit `Any` entering at an untyped boundary (`json.loads`) and spreading through a variable and an argument, which basedpyright 1.40.2 in strict mode with `reportAny` reports.
That is the guarantee `pyrightconfig.json` exists for, and ty is still beta (PyPI "Development Status :: 4 - Beta").

So both run, both are gates, and basedpyright is removed when all of these hold, checked at each ty minor release:

- ty has left beta (classifier "Production/Stable", or a 1.0);
- ty, with ruff `ANN`, flags every line of the probe that basedpyright flags, the three implicit-`Any` lines included;
- no finding reported by basedpyright alone remains unexplained on the projects that run both.

The probe:

```python
import json
from typing import Any


def untyped(x, y=1):
    return x + y


def explicit(v: Any) -> int:
    return v.whatever


def leak() -> int:
    data = json.loads("{}")
    return data["n"].oops()


def wrong() -> int:
    return "s"


def takes_int(n: int) -> int:
    return n


def passes() -> int:
    data = json.loads("{}")
    m = data["m"]
    return takes_int(m)
```

Here:

- [ ] `template/justfile.jinja`: `just setup` adds `"ty>=0.0.95"`; `typecheck` runs `uv run --locked ty check` after basedpyright. The same in this repository's `pyproject.toml` and `justfile`, which makes [PLAN](PLAN.md) step 5 (one source for the lower bounds) more pressing.
- [ ] A `ty.toml` in the template, beside `ruff.toml` and `pyrightconfig.json`, so the rules stay in the tool's own file: `[environment] python-version = "{{ python_min }}"` and `[rules] all = "error"`. Checked with ty 0.0.95: `ty.toml` takes precedence over a `[tool.ty]` table in `pyproject.toml`. Mirror it here, and add it to the mirrored files of `test_this_repository_uses_the_configuration_it_distributes`, the README's re-render command and `REUSE.toml`'s CC0 list.
- [ ] `ruff.toml`: add `"ANN"` to `select`. It duplicates basedpyright's annotation checks today and is what keeps them once basedpyright goes.
- [ ] `.vscode/extensions.json`: recommend `astral-sh.ty`.
- [ ] `.vscode/settings.json`: `"ty.path": ["${workspaceFolder}/.venv/bin/ty"]` (by path, like ruff: a missing `.venv` is an error), `"python.languageServer": "None"` and `"basedpyright.disableLanguageServices": true`. ty then serves completion, hover and go-to, basedpyright shows diagnostics only, and both appear side by side in the Problems panel. A rendered project is often public, and contributors don't have the owner's user settings, so the project carries these itself.
- [ ] `.zed/settings.json` disables ty today (`"!ty"`), which contradicts D1. Enable it from `.venv` alongside basedpyright. How Zed is told to use the `.venv` binary for ty is to verify against Zed's documentation.
- [ ] Tests: the recommended-extensions test, and a planted defect that each of the two checkers catches, so both are shown red in a rendered project's gate.
- [ ] README: ty under "Tools in use", and the implicit-`Any` gap under "Known gaps" until the exit criteria hold.

## D2. Editor extensions: one base stack; public repositories recommend explicitly, private ones explain divergence

Decided 2026-11-02.

The owner's VS Code runs a fixed list of extensions at pinned versions, the same on macOS and NixOS: Claude Code, ty, basedpyright, ruff, Python (with debugpy and python-envs), Even Better TOML, markdownlint.
Nothing is installed from the editor's UI.
The rule for repositories:

- public (a GitHub remote): commit `.vscode/extensions.json` recommending every extension the project needs, base-stack ones included, since contributors don't have the base stack;
- private (any other remote): either no `.vscode/extensions.json`, meaning the base stack, or every extension outside it (in `recommendations` or `unwantedRecommendations`) has a `//` comment on its line or the line above saying why.

This repository passes, and so does every project it renders, public or private: the rendered list is inside the base stack, and the Pylance entry in `unwantedRecommendations` is explained by the comment above it.

Here:

- [ ] Keep that property: an extension added to the template outside the base stack gets its `//` reason on its line or the line above.
- [ ] Decide whether rendered projects recommend `ms-python.python`. The owner's typing guidelines list it for public repositories; the template does not, while `python.defaultInterpreterPath` in the rendered settings is a setting of that extension and does nothing without it. Align one with the other.
- [ ] Twelve of the owner's public repositories have no `.vscode/extensions.json`. Adopting this template ([PLAN](PLAN.md) step 3) is the way to give them one, rather than writing each list by hand.
- The base stack's other settings (built-in AI off, extension auto-update off) are the user's business, not the project's: they stay out of the template.

## D3. VSCodium is no longer used

Decided 2026-11-02.

The owner's editors are VS Code and Zed.

Here:

- [ ] README, "IDEs to support": VS Code and Zed. Keeping every recommended extension available on Open VSX is still worth it for contributors who use VSCodium, so keep the comment in `.vscode/extensions.json` and check each new extension there: `astral-sh.ty` 2026.86.0 and `detachhead.basedpyright` 1.40.2 are on Open VSX (checked 2026-11-02).

## D4. Git identity: the forge's noreply address, history rewritten

Decided 2026-10-31 (record 0002).

One name; on a GitHub remote, the GitHub noreply address; no global address, so a repository without a known forge refuses to commit until it sets one.
Existing history in repositories only the owner uses is rewritten (`git filter-repo --mailmap`), not masked with a `.mailmap`.

The existing commits predate this decision and carry an address it replaces.
This repository is in the rewrite inventory, prepared but not yet run.
New commits already get the noreply address from the owner's configuration.

Here:

- [ ] Run the rewrite **before tagging v0.1.0** ([PLAN](PLAN.md) step 2). Projects record the template version they were rendered from in `.copier-answers.yml`, and an untagged reference is a commit hash a rewrite would invalidate. Rewriting before any project adopts the template costs nothing but a force-push.

## D5. The `x86_64-darwin` horizon

Decided before this repository: the owner's Intel Mac is being migrated to NixOS (`x86_64-linux`). Its configuration is on nixpkgs 26.05, the last release with `x86_64-darwin`, as this repository is, until then.

Here:

- [ ] [PLAN](PLAN.md) step 4 leaves the choice open; the owner's direction is its third option (development moves off `x86_64-darwin`, by migrating the machine itself). Record it there when the migration date is known, and follow 26.11 once the machine runs Linux.
