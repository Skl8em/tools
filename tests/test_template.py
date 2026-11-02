"""The template renders the files each language needs, and nothing it does not.

These tests run copier and nix from this repository's devShell, at the versions
a project will run them: `nix develop --command just test`.
"""

import ast
import json
import os
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Final, TypeGuard

import pytest

ROOT: Final = Path(__file__).resolve().parent.parent

Answers = dict[str, str | bool | list[str]]

BASE_ANSWERS: Final[Answers] = {
    "project_name": "example-project",
    "copyright_holder": "Jane Doe",
    "tools_flake": "github:example/tools",
}

COMMON_FILES: Final = {
    ".copier-answers.yml",
    ".github/workflows/checks.yml",
    ".gitignore",
    ".vscode/extensions.json",
    ".vscode/settings.json",
    ".zed/settings.json",
    "REUSE.toml",
    "flake.nix",
    "justfile",
}
PYTHON_CONFIG_FILES: Final = {"ruff.toml", "pyrightconfig.json", "ty.toml"}
PYTHON_SKELETON_FILES: Final = {
    "pyproject.toml",
    "src/example_project/__init__.py",
    "src/example_project/py.typed",
    "tests/test_import.py",
}
MARKDOWN_FILES: Final = {".markdownlint-cli2.jsonc"}

# The files this repository keeps identical to what the template renders for it,
# so that the configuration it distributes is the one its own code is checked with.
MIRRORED_FILES: Final = (
    ".github/workflows/checks.yml",
    ".gitignore",
    ".markdownlint-cli2.jsonc",
    ".vscode/extensions.json",
    ".vscode/settings.json",
    ".zed/settings.json",
    "pyrightconfig.json",
    "ruff.toml",
    "ty.toml",
)
REPO_ANSWERS_FILE: Final = ROOT / "tests" / "repo-answers.json"


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


@pytest.fixture(scope="session", autouse=True)
def in_devshell() -> None:
    if os.environ.get("TOOLS_DEVSHELL") != "1" or shutil.which("copier") is None:
        pytest.fail("run the tests inside the devShell: nix develop --command just test")


@pytest.fixture(scope="session")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The template as a plain directory, so copier renders the working tree, not a git ref."""
    source = tmp_path_factory.mktemp("template")
    shutil.copy(ROOT / "copier.yml", source / "copier.yml")
    shutil.copytree(ROOT / "template", source / "template")
    return source


@pytest.fixture(scope="session")
def tools_flake(tmp_path_factory: pytest.TempPathFactory) -> str:
    """This repository's flake, outside git, so its uncommitted state is the one evaluated."""
    flake = tmp_path_factory.mktemp("tools-flake")
    shutil.copy(ROOT / "flake.nix", flake / "flake.nix")
    shutil.copy(ROOT / "flake.lock", flake / "flake.lock")
    shutil.copytree(ROOT / "nix", flake / "nix")
    return f"path:{flake}"


def render_from_file(template: Path, destination: Path, data_file: Path) -> subprocess.CompletedProcess[str]:
    return run(
        ["copier", "copy", "--defaults", "--quiet", "--data-file", str(data_file), str(template), str(destination)],
        cwd=destination.parent,
    )


def render(template: Path, destination: Path, answers: Answers) -> subprocess.CompletedProcess[str]:
    # JSON is YAML, so the answers need no YAML writer.
    data_file = destination.parent / f"{destination.name}-answers.yml"
    data_file.write_text(json.dumps(answers))
    return render_from_file(template, destination, data_file)


def rendered(template: Path, destination: Path, answers: Answers) -> Path:
    result = render(template, destination, answers)
    assert result.returncode == 0, output(result)
    return destination


def files_under(directory: Path) -> set[str]:
    return {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}


def load_jsonc(path: Path) -> object:
    """Parse JSON with whole-line `//` comments, the only kind the template writes."""
    lines = [line for line in path.read_text().splitlines() if not line.lstrip().startswith("//")]
    parsed: object = json.loads("\n".join(lines))  # pyright: ignore[reportAny] -- json is untyped; callers narrow
    return parsed


def is_mapping(value: object) -> TypeGuard[dict[object, object]]:
    return isinstance(value, dict)


def is_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


@pytest.mark.parametrize(
    ("languages", "python_skeleton", "expected"),
    [
        pytest.param(
            ["python", "markdown"],
            True,
            COMMON_FILES | PYTHON_CONFIG_FILES | PYTHON_SKELETON_FILES | MARKDOWN_FILES,
            id="python+markdown, new package",
        ),
        pytest.param(
            ["python", "markdown"],
            False,
            COMMON_FILES | PYTHON_CONFIG_FILES | MARKDOWN_FILES,
            id="python+markdown, existing package",
        ),
        pytest.param(["python"], True, COMMON_FILES | PYTHON_CONFIG_FILES | PYTHON_SKELETON_FILES, id="python only"),
        pytest.param(["markdown"], True, COMMON_FILES | MARKDOWN_FILES, id="markdown only"),
    ],
)
def test_renders_exactly_the_files_of_the_selected_languages(
    template: Path, tmp_path: Path, languages: list[str], python_skeleton: bool, expected: set[str]
) -> None:
    answers: Answers = {**BASE_ANSWERS, "languages": languages, "python_skeleton": python_skeleton}
    project = rendered(template, tmp_path / "project", answers)
    assert files_under(project) == expected


def test_rendered_json_files_parse(template: Path, tmp_path: Path) -> None:
    project = rendered(template, tmp_path / "project", {**BASE_ANSWERS, "languages": ["python", "markdown"]})
    json_files = [path for path in project.rglob("*") if path.suffix in {".json", ".jsonc"}]
    assert json_files
    for path in json_files:
        load_jsonc(path)


def test_no_template_syntax_is_left_unrendered(template: Path, tmp_path: Path) -> None:
    project = rendered(template, tmp_path / "project", {**BASE_ANSWERS, "languages": ["python", "markdown"]})
    leftovers = [
        path.relative_to(project).as_posix()
        for path in project.rglob("*")
        if path.is_file() and any(marker in path.read_text() for marker in ("{{", "{%"))
    ]
    assert leftovers == []


@pytest.mark.parametrize(
    ("languages", "recommended", "not_recommended"),
    [
        pytest.param(
            ["python", "markdown"],
            {
                "detachhead.basedpyright",
                "astral-sh.ty",
                "charliermarsh.ruff",
                "ms-python.python",
                "davidanson.vscode-markdownlint",
            },
            set[str](),
            id="python+markdown",
        ),
        pytest.param(
            ["markdown"],
            {"davidanson.vscode-markdownlint"},
            {"detachhead.basedpyright", "astral-sh.ty", "charliermarsh.ruff", "ms-python.python"},
            id="markdown only",
        ),
    ],
)
def test_vscode_recommends_the_extensions_of_the_selected_languages(
    template: Path, tmp_path: Path, languages: list[str], recommended: set[str], not_recommended: set[str]
) -> None:
    project = rendered(template, tmp_path / "project", {**BASE_ANSWERS, "languages": languages})
    extensions = load_jsonc(project / ".vscode/extensions.json")
    assert is_mapping(extensions)
    recommendations = extensions.get("recommendations")
    assert is_list(recommendations)
    lowered = {str(item).lower() for item in recommendations}
    assert recommended <= lowered
    assert not (not_recommended & lowered)


# The owner's VS Code base stack (UPSTREAM-DECISIONS D2), Claude Code aside: a rendered project
# is often public, and contributors don't have the base stack, so it recommends from this list.
# An extension outside it needs a `//` reason in extensions.json, and an entry here.
BASE_STACK: Final = {
    "anthropic.claude-code",
    "astral-sh.ty",
    "detachhead.basedpyright",
    "charliermarsh.ruff",
    "ms-python.python",
    "ms-python.debugpy",
    "ms-python.vscode-python-envs",
    "tamasfe.even-better-toml",
    "davidanson.vscode-markdownlint",
}


def test_vscode_recommends_only_extensions_of_the_base_stack(template: Path, tmp_path: Path) -> None:
    project = rendered(template, tmp_path / "project", {**BASE_ANSWERS, "languages": ["python", "markdown"]})
    extensions = load_jsonc(project / ".vscode/extensions.json")
    assert is_mapping(extensions)
    recommendations = extensions.get("recommendations")
    assert is_list(recommendations)
    assert {str(item).lower() for item in recommendations} - BASE_STACK == set()


def test_vscode_runs_ty_and_basedpyright_from_the_venv_and_no_other_language_server(
    template: Path, tmp_path: Path
) -> None:
    project = rendered(template, tmp_path / "project", {**BASE_ANSWERS, "languages": ["python"]})
    settings = load_jsonc(project / ".vscode/settings.json")
    assert is_mapping(settings)
    assert settings.get("ty.path") == ["${workspaceFolder}/.venv/bin/ty"]
    assert settings.get("ruff.path") == ["${workspaceFolder}/.venv/bin/ruff"]
    assert settings.get("basedpyright.importStrategy") == "fromEnvironment"
    # ty serves completion, hover and go-to; basedpyright reports diagnostics only.
    assert settings.get("basedpyright.disableLanguageServices") is True
    assert settings.get("python.languageServer") == "None"


def test_zed_runs_ty_beside_basedpyright(template: Path, tmp_path: Path) -> None:
    project = rendered(template, tmp_path / "project", {**BASE_ANSWERS, "languages": ["python"]})
    settings = load_jsonc(project / ".zed/settings.json")
    assert is_mapping(settings)
    languages = settings.get("languages")
    assert is_mapping(languages)
    python = languages.get("Python")
    assert is_mapping(python)
    servers = python.get("language_servers")
    assert is_list(servers)
    assert {"basedpyright", "ty", "ruff"} <= set(servers)
    assert "!ty" not in servers


def python_tool_bounds(requirements: list[str]) -> dict[str, str]:
    """`name>=version` requirements, by name."""
    bounds: dict[str, str] = {}
    for requirement in requirements:
        name, _, version = requirement.partition(">=")
        bounds[name] = version
    return bounds


def test_the_python_tool_lower_bounds_are_the_same_here_and_in_the_template() -> None:
    justfile = (ROOT / "template/justfile.jinja").read_text()
    added = [line.split() for line in justfile.splitlines() if line.strip().startswith("uv add --dev ")]
    assert len(added) == 1
    template_bounds = python_tool_bounds([word.strip('"') for word in added[0][3:]])
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    groups = pyproject.get("dependency-groups")
    assert is_mapping(groups)
    dev = groups.get("dev")
    assert is_list(dev)
    assert python_tool_bounds([str(item) for item in dev]) == template_bounds
    assert set(template_bounds) == {"basedpyright", "pytest", "ruff", "ty"}


# The probe of the owner's record 0003: what ty must catch before basedpyright can go.
TY_PROBE: Final = """\
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
"""


def flagged_functions(probe: Path, lines: set[int]) -> set[str]:
    """The probe's functions that contain at least one of the flagged lines."""
    tree = ast.parse(probe.read_text())
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and any(node.lineno <= line <= (node.end_lineno or 0) for line in lines)
    }


def concise_lines(result: subprocess.CompletedProcess[str], probe: Path) -> set[int]:
    """Line numbers of `<file>:<line>:<column>: ...` diagnostics, the concise output of ty and ruff."""
    prefix = f"{probe.name}:"
    return {
        int(line.removeprefix(prefix).split(":")[0]) for line in output(result).splitlines() if line.startswith(prefix)
    }


@pytest.mark.xfail(
    reason="ty 0.0.95 misses an implicit Any carried through a variable into an argument (`passes`):"
    " when this passes, check the other exit criteria of README's type-checking decision",
    strict=True,
)
def test_ty_with_ruff_annotations_catches_every_function_basedpyright_catches(tmp_path: Path) -> None:
    """Per function, not per line: ty reports an Any where it is returned, basedpyright where it enters."""
    probe = tmp_path / "probe.py"
    probe.write_text(TY_PROBE)
    for config in ("ty.toml", "pyrightconfig.json"):
        shutil.copy(ROOT / config, tmp_path / config)
    tools = Path(sys.executable).parent
    ty = run([str(tools / "ty"), "check", "--output-format", "concise", probe.name], cwd=tmp_path)
    ruff = run(
        [str(tools / "ruff"), "check", "--isolated", "--select", "ANN", "--output-format", "concise", probe.name],
        cwd=tmp_path,
    )
    basedpyright = run([str(tools / "basedpyright"), "--outputjson", probe.name], cwd=tmp_path)
    report: object = json.loads(basedpyright.stdout)  # pyright: ignore[reportAny] -- json is untyped; narrowed below
    assert is_mapping(report), output(basedpyright)
    diagnostics = report.get("generalDiagnostics")
    assert is_list(diagnostics)
    basedpyright_lines: set[int] = set()
    for diagnostic in diagnostics:
        assert is_mapping(diagnostic)
        where = diagnostic.get("range")
        assert is_mapping(where)
        start = where.get("start")
        assert is_mapping(start)
        line = start.get("line")
        assert isinstance(line, int)
        basedpyright_lines.add(line + 1)
    caught_by_basedpyright = flagged_functions(probe, basedpyright_lines)
    # Fail loud if a tool silently checked nothing: each catches something today.
    assert caught_by_basedpyright == {"untyped", "explicit", "leak", "wrong", "passes"}, output(basedpyright)
    caught_by_ty = flagged_functions(probe, concise_lines(ty, probe) | concise_lines(ruff, probe))
    assert caught_by_ty >= {"untyped", "explicit", "leak", "wrong"}, output(ty) + output(ruff)
    assert caught_by_basedpyright - caught_by_ty == set()


def test_existing_pyproject_is_never_overwritten(template: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    pyproject = project / "pyproject.toml"
    pyproject.write_text('[project]\nname = "mine"\n')
    rendered(template, project, {**BASE_ANSWERS, "languages": ["python"], "python_skeleton": True})
    assert pyproject.read_text() == '[project]\nname = "mine"\n'


@pytest.mark.parametrize("missing", ["project_name", "copyright_holder", "tools_flake"])
def test_a_required_answer_without_default_fails_the_copy(template: Path, tmp_path: Path, missing: str) -> None:
    answers = {key: value for key, value in BASE_ANSWERS.items() if key != missing}
    result = render(template, tmp_path / "project", answers)
    assert result.returncode != 0
    assert not (tmp_path / "project" / "justfile").exists()


def test_justfile_refuses_to_run_outside_the_devshell(template: Path, tmp_path: Path) -> None:
    project = rendered(template, tmp_path / "project", {**BASE_ANSWERS, "languages": ["markdown"]})
    environment = {key: value for key, value in os.environ.items() if key != "TOOLS_DEVSHELL"}
    result = run(["just", "check"], cwd=project, env=environment)
    assert result.returncode != 0
    assert "nix develop" in output(result)


def test_this_repository_uses_the_configuration_it_distributes(template: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    result = render_from_file(template, project, REPO_ANSWERS_FILE)
    assert result.returncode == 0, output(result)
    differing = [name for name in MIRRORED_FILES if (project / name).read_text() != (ROOT / name).read_text()]
    assert differing == [], "re-render them from the template: README, section 'Changing the template'"


GIT_IDENTITY: Final = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def git_commit_all(repository: Path, *tag: str) -> None:
    environment = {**os.environ, **GIT_IDENTITY}
    commands = [["git", "init", "--quiet"], ["git", "add", "--all"], ["git", "commit", "--quiet", "-m", "change"]]
    for command in commands + ([["git", "tag", *tag]] if tag else []):
        result = run(command, cwd=repository, env=environment)
        assert result.returncode == 0, output(result)


def test_update_merges_a_new_template_version_into_local_edits(template: Path, tmp_path: Path) -> None:
    source = tmp_path / "template-repository"
    shutil.copytree(template, source)
    git_commit_all(source, "v0.1.0")
    answers: Answers = {**BASE_ANSWERS, "languages": ["python", "markdown"], "python_skeleton": True}
    project = rendered(source, tmp_path / "project", answers)
    pyproject = (project / "pyproject.toml").read_text()
    # The project edits a template-owned file, and deletes a skeleton file it owns.
    with (project / ".gitignore").open("a") as gitignore:
        gitignore.write("local-cache/\n")
    (project / "tests/test_import.py").unlink()
    git_commit_all(project)

    # The template changes a configuration file, and the skeleton files a project owns.
    ruff = source / "template/{% if use_python %}ruff.toml{% endif %}.jinja"
    ruff.write_text(ruff.read_text().replace("line-length = 120", "line-length = 100"))
    for skeleton in (
        "template/{% if use_python and python_skeleton %}pyproject.toml{% endif %}.jinja",
        "template/{% if use_python and python_skeleton %}tests{% endif %}/test_import.py.jinja",
    ):
        with (source / skeleton).open("a") as file:
            file.write("# changed in v0.2.0\n")
    git_commit_all(source, "v0.2.0")

    result = run(["copier", "update", "--defaults", "--quiet"], cwd=project, env={**os.environ, **GIT_IDENTITY})
    assert result.returncode == 0, output(result)
    assert "line-length = 100" in (project / "ruff.toml").read_text()
    assert "local-cache/" in (project / ".gitignore").read_text()
    assert not (project / "tests/test_import.py").exists()
    assert (project / "pyproject.toml").read_text() == pyproject
    assert "_commit: v0.2.0" in (project / ".copier-answers.yml").read_text()


def test_mkdevshell_refuses_an_unknown_language(tools_flake: str, tmp_path: Path) -> None:
    expression = (
        f'(builtins.getFlake "{tools_flake}").lib.mkDevShell'
        ' { system = builtins.currentSystem; languages = [ "cobol" ]; }'
    )
    result = run(["nix", "eval", "--impure", "--raw", "--expr", f"({expression}).drvPath"], cwd=tmp_path)
    assert result.returncode != 0
    assert "unknown language(s): cobol" in output(result)


# --- integration: a rendered project's own gate, in its own devShell ---------------------------


def in_project_shell(project: Path, *command: str) -> subprocess.CompletedProcess[str]:
    # This repository's own .venv, active under `uv run`, is not the project's.
    environment = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    return run(["nix", "develop", str(project), "--command", *command], cwd=project, env=environment)


def committed(project: Path) -> None:
    """Nix sees only the files git tracks, so the project is staged before each evaluation."""
    for command in (["git", "init", "--quiet"], ["git", "add", "--all"]):
        result = run(command, cwd=project)
        assert result.returncode == 0, output(result)


@pytest.fixture(scope="module")
def python_project(template: Path, tools_flake: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    answers: Answers = {**BASE_ANSWERS, "languages": ["python", "markdown"], "tools_flake": tools_flake}
    project = rendered(template, tmp_path_factory.mktemp("integration") / "project", answers)
    committed(project)
    setup = in_project_shell(project, "just", "setup")
    assert setup.returncode == 0, output(setup)
    committed(project)
    return project


@pytest.mark.integration
def test_rendered_flake_is_nixfmt_formatted(python_project: Path) -> None:
    result = run(["nixfmt", "--check", "flake.nix"], cwd=python_project)
    assert result.returncode == 0, output(result)


@pytest.mark.integration
def test_rendered_python_project_passes_its_own_gate(python_project: Path) -> None:
    result = in_project_shell(python_project, "just", "check")
    assert result.returncode == 0, output(result)


@pytest.fixture
def planted(python_project: Path, request: pytest.FixtureRequest) -> Iterator[Path]:
    relative, content = request.param  # pyright: ignore[reportAny] -- indirect parameter, unpacked as typed below
    assert isinstance(relative, str)
    assert isinstance(content, str)
    path = python_project / relative
    path.write_text(content)
    committed(python_project)
    yield python_project
    path.unlink()
    committed(python_project)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("planted", "diagnostic"),
    [
        pytest.param(("src/example_project/bad.py", "x=1\n"), "would be reformatted", id="unformatted python"),
        pytest.param(("src/example_project/bad.py", "import os\n"), "F401", id="lint error"),
        pytest.param(
            ("src/example_project/bad.py", "def double(x):\n    return x * 2\n"),
            # ruff's ANN rules, which keep this check once basedpyright goes; lint runs before typecheck.
            "ANN001",
            id="unannotated function, ruff",
        ),
        # Both checkers run even when the first fails, so each one is shown to catch it.
        pytest.param(
            ("src/example_project/bad.py", 'def wrong() -> int:\n    return "s"\n'),
            "reportReturnType",
            id="ill-typed return, basedpyright",
        ),
        pytest.param(
            ("src/example_project/bad.py", 'def wrong() -> int:\n    return "s"\n'),
            "invalid-return-type",
            id="ill-typed return, ty",
        ),
        pytest.param(
            ("src/example_project/bad.py", "from typing import Any\n\n\ndef f(v: Any) -> None:\n    pass\n"),
            "ANN401",
            id="explicit Any, ruff",
        ),
        pytest.param(
            ("tests/test_bad.py", "def test_fails() -> None:\n    assert sum([1, 1]) == 3\n"),
            "1 failed",
            id="failing test",
        ),
        pytest.param(("notes.md", "#No space\n"), "MD018", id="markdown defect"),
        pytest.param(("notes.txt", "SPDX-License-Identifier: MIT\n"), "MIT", id="licence text missing"),
    ],
    indirect=["planted"],
)
def test_rendered_gate_fails_on_a_planted_defect(planted: Path, diagnostic: str) -> None:
    result = in_project_shell(planted, "just", "check")
    assert result.returncode != 0
    assert diagnostic in output(result)


@pytest.mark.integration
def test_rendered_markdown_project_passes_its_own_gate(template: Path, tools_flake: str, tmp_path: Path) -> None:
    answers: Answers = {**BASE_ANSWERS, "languages": ["markdown"], "tools_flake": tools_flake}
    project = rendered(template, tmp_path / "project", answers)
    (project / "README.md").write_text("# Example\n\nA project with no Python.\n")
    committed(project)
    for recipe in ("setup", "check"):
        result = in_project_shell(project, "just", recipe)
        assert result.returncode == 0, output(result)
