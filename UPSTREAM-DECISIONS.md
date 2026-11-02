# Upstream decisions

Decisions taken outside this repository, in the owner's workstation configuration, that this repository must follow.
Each one says what was decided, why in brief, and what it changes here; the records themselves live in a private repository, cited by number for traceability.
Valid until each item's "Here" list is done; then fold the decision into the README's [Decisions](README.md#decisions) and drop it from this file.

## D2. Editor extensions: one base stack; public repositories recommend explicitly, private ones explain divergence

Decided 2026-11-02.
Applied to the template and folded into the README's [Decisions](README.md#decisions), except:

- [ ] Twelve of the owner's public repositories have no `.vscode/extensions.json`. Adopting this template ([PLAN](PLAN.md) step 3) is the way to give them one, rather than writing each list by hand.

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
