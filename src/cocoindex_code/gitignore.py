from __future__ import annotations

from pathlib import Path, PurePath
from typing import Protocol

from pathspec.gitignore import GitIgnoreSpec


class FilePathMatcher(Protocol):
    def is_dir_included(self, path: PurePath) -> bool: ...

    def is_file_included(self, path: PurePath) -> bool: ...


class GitIgnoreFilePathMatcher:
    def __init__(
        self,
        *,
        root_path: Path,
        included_patterns: list[str],
        excluded_patterns: list[str],
        git_root_path: Path | None,
        static_matcher: FilePathMatcher | None = None,
    ) -> None:
        self._root_path: Path = root_path.resolve()
        self._git_root_path: Path | None = (
            git_root_path.resolve() if git_root_path is not None else None
        )
        if static_matcher is None:
            from cocoindex.resources.file import PatternFilePathMatcher

            self._static_matcher: FilePathMatcher = PatternFilePathMatcher(
                included_patterns=included_patterns,
                excluded_patterns=excluded_patterns,
            )
        else:
            self._static_matcher = static_matcher
        self._specs_by_dir: dict[Path, GitIgnoreSpec | None] = {}

    def is_dir_included(self, path: PurePath) -> bool:
        return self._static_matcher.is_dir_included(path)

    def is_file_included(self, path: PurePath) -> bool:
        if not self._static_matcher.is_file_included(path):
            return False
        return self._is_file_included_by_gitignore(path)

    def _is_file_included_by_gitignore(self, path: PurePath) -> bool:
        if self._git_root_path is None:
            return True

        absolute_path = (self._root_path / Path(path)).resolve()
        try:
            _ = absolute_path.relative_to(self._git_root_path)
        except ValueError:
            return True

        include = True
        for directory in self._iter_rule_directories(absolute_path.parent):
            spec = self._load_spec(directory)
            if spec is None:
                continue
            relative_path = absolute_path.relative_to(directory).as_posix()
            result = spec.check_file(relative_path)
            if result.include is not None:
                include = not result.include
        return include

    def _iter_rule_directories(self, directory: Path) -> list[Path]:
        if self._git_root_path is None:
            return []

        directories: list[Path] = []
        current = directory.resolve()
        while True:
            try:
                _ = current.relative_to(self._git_root_path)
            except ValueError:
                break
            directories.append(current)
            if current == self._git_root_path:
                break
            parent = current.parent
            if parent == current:
                break
            current = parent
        directories.reverse()
        return directories

    def _load_spec(self, directory: Path) -> GitIgnoreSpec | None:
        if directory in self._specs_by_dir:
            return self._specs_by_dir[directory]

        gitignore_path = directory / ".gitignore"
        if not gitignore_path.is_file():
            self._specs_by_dir[directory] = None
            return None

        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
        spec = GitIgnoreSpec.from_lines(lines)
        self._specs_by_dir[directory] = spec
        return spec
