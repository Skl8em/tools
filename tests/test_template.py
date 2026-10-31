"""The template renders the files each language needs, and nothing it does not.

These tests run copier and nix from this repository's devShell, at the versions
a project will run them: `nix develop --command just test`.
"""

import json
import os
import shutil
import subprocess
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
PYTHON_CONFIG_FILES: Final = {"ruff.toml", "pyrightconfig.json"}
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
            {"detachhead.basedpyright", "charliermarsh.ruff", "davidanson.vscode-markdownlint"},
            set[str](),
            id="python+markdown",
        ),
        pytest.param(
            ["markdown"],
            {"davidanson.vscode-markdownlint"},
            {"detachhead.basedpyright", "charliermarsh.ruff"},
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
            "reportMissingParameterType",
            id="unannotated function",
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
