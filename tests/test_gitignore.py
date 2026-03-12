from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from cocoindex_code.config import Config
from cocoindex_code.gitignore import GitIgnoreFilePathMatcher


class StaticMatcher:
    def is_dir_included(self, path: PurePosixPath) -> bool:
        return not any(part.startswith(".") for part in path.parts)

    def is_file_included(self, path: PurePosixPath) -> bool:
        return path.suffix == ".py" and not any(part.startswith(".") for part in path.parts)


def make_matcher(root_path: Path, git_root_path: Path | None) -> GitIgnoreFilePathMatcher:
    return GitIgnoreFilePathMatcher(
        root_path=root_path,
        included_patterns=["**/*.py"],
        excluded_patterns=["**/.cocoindex_code", "**/.*"],
        git_root_path=git_root_path,
        static_matcher=StaticMatcher(),
    )


class TestConfigGitRootPath:
    def test_detects_git_root_from_explicit_codebase_root(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        codebase_root = repo_root / "packages" / "api"
        codebase_root.mkdir(parents=True)

        with patch.dict(os.environ, {"COCOINDEX_CODE_ROOT_PATH": str(codebase_root)}):
            config = Config.from_env()

        assert config.codebase_root_path == codebase_root.resolve()
        assert config.git_root_path == repo_root.resolve()

    def test_leaves_git_root_empty_outside_repo(self, tmp_path: Path) -> None:
        codebase_root = tmp_path / "standalone"
        codebase_root.mkdir()

        with patch.dict(os.environ, {"COCOINDEX_CODE_ROOT_PATH": str(codebase_root)}):
            config = Config.from_env()

        assert config.codebase_root_path == codebase_root.resolve()
        assert config.git_root_path is None


class TestGitIgnoreFilePathMatcher:
    def test_excludes_file_from_root_gitignore(self, tmp_path: Path) -> None:
        root_path = tmp_path / "repo"
        root_path.mkdir()
        (root_path / ".git").mkdir()
        (root_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")

        matcher = make_matcher(root_path, root_path)

        assert matcher.is_file_included(PurePosixPath("kept.py"))
        assert not matcher.is_file_included(PurePosixPath("ignored.py"))

    def test_excludes_file_from_nested_gitignore(self, tmp_path: Path) -> None:
        root_path = tmp_path / "repo"
        nested_path = root_path / "pkg"
        nested_path.mkdir(parents=True)
        (root_path / ".git").mkdir()
        (nested_path / ".gitignore").write_text("generated.py\n", encoding="utf-8")

        matcher = make_matcher(root_path, root_path)

        assert matcher.is_file_included(PurePosixPath("pkg/kept.py"))
        assert not matcher.is_file_included(PurePosixPath("pkg/generated.py"))

    def test_honors_negated_gitignore_pattern(self, tmp_path: Path) -> None:
        root_path = tmp_path / "repo"
        root_path.mkdir()
        (root_path / ".git").mkdir()
        (root_path / ".gitignore").write_text(
            "generated/\n!generated/keep.py\n",
            encoding="utf-8",
        )

        matcher = make_matcher(root_path, root_path)

        assert matcher.is_file_included(PurePosixPath("generated/keep.py"))
        assert not matcher.is_file_included(PurePosixPath("generated/drop.py"))

    def test_stops_at_closest_git_root(self, tmp_path: Path) -> None:
        outer_root = tmp_path / "outer"
        inner_root = outer_root / "subrepo"
        inner_root.mkdir(parents=True)
        (outer_root / ".git").mkdir()
        (outer_root / ".gitignore").write_text("subrepo/blocked.py\n", encoding="utf-8")
        (inner_root / ".git").mkdir()

        matcher = make_matcher(inner_root, inner_root)

        assert matcher.is_file_included(PurePosixPath("blocked.py"))

    def test_ignores_gitignore_files_without_repo_boundary(self, tmp_path: Path) -> None:
        root_path = tmp_path / "standalone"
        root_path.mkdir()
        (root_path / ".gitignore").write_text("ignored.py\n", encoding="utf-8")

        matcher = make_matcher(root_path, None)

        assert matcher.is_file_included(PurePosixPath("ignored.py"))
