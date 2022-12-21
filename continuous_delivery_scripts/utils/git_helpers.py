#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utility script to abstract git operations for our CI scripts."""
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional, List, Union, Any, Tuple

from git import Repo, Actor, GitCommandError
from packaging import version

from .configuration import configuration, ConfigurationVariable
from .filesystem_helpers import TemporaryDirectory

logger = logging.getLogger(__name__)


class GitWrapper:
    """Wrapper class to provide convenient methods for performing git actions."""

    def __init__(self, path: Path, repo: Repo) -> None:
        """Creates an instance of GitWrapper.

        Args:
            path: path to repository.
            repo: GitPython repository.
        """
        self._root_path = path
        self.repo = repo
        self.author = Actor(
            configuration.get_value(ConfigurationVariable.BOT_USERNAME),
            configuration.get_value(ConfigurationVariable.BOT_EMAIL),
        )

    def _git_url_ssh_to_https(self, url: str) -> str:
        """Changes repository URL to use authorisation token.

        Converts the git url to use the GitHub token:
        See https://github.blog/2012-09-21-easier-builds-and-deployments-using-git-over-https-and-oauth/

        Returns:
            new URL
        """
        path = url.split("github.com", 1)[1][1:].strip()
        new = "https://{GITHUB_TOKEN}:x-oauth-basic@github.com/%s" % path
        logger.info("rewriting git url to: %s" % new)
        return new.format(GITHUB_TOKEN=configuration.get_value(ConfigurationVariable.GIT_TOKEN))

    def clone(self, path: Path) -> "GitWrapper":
        """Clones this repository to the path.

        Args:
            path: path where to put the clone

        Returns:
            a wrapper over the cloned repository
        """
        try:
            git_clone = self.repo.clone_from(
                url=self.get_remote_url(), to_path=str(path), multi_options=["--recurse-submodules"]
            )
        except GitCommandError as e:
            logger.info("failed cloning repository: %s" % e)
            logger.info("trying with authentication")
            git_clone = self.repo.clone_from(
                url=self._git_url_ssh_to_https(self.get_remote_url()),
                to_path=str(path),
                multi_options=["--recurse-submodules"],
            )

        clone = GitWrapper(path=path, repo=git_clone)
        clone.set_remote_url(self.get_remote_url())
        clone.fetch()
        return clone

    @property
    def root(self) -> Path:
        """Gets repository root folder.

        Returns:
            repository root folder.
        """
        return self._root_path

    def configure_author(self) -> None:
        """Sets the author."""
        self.repo.config_writer().set_value("user", "name", self.author.name).release()
        self.repo.config_writer().set_value("user", "email", self.author.email).release()

    def checkout_branch(self, branch_name: str) -> Any:
        """Checks out a branch from its name.

        Args:
            branch_name: name of the branch

        Returns:
            corresponding branch if found; None otherwise.
        """
        logger.debug(f"Checking out {branch_name}")
        local_branch = self.get_branch(branch_name)
        if local_branch:
            self.checkout(local_branch)
        return local_branch

    def checkout(self, branch: Any) -> None:
        """Checks out a branch.

        Args:
            branch: branch to check out

        """
        self.repo.git.checkout(branch)

    def _add_one_file_or_one_dir(self, path: str) -> None:
        if not path:
            raise ValueError("Unspecified path.")
        self._add_one_path(Path(path))

    def _add_one_path(self, path_model: Path) -> None:
        if not path_model.is_absolute():
            path_model = Path(self.root).joinpath(path_model)
        if not path_model.exists():
            logger.warning(f"[Git] {path_model} cannot be added because not found.")
            return
        relative_path = str(path_model.relative_to(self.root))
        unix_relative_path = relative_path.replace("\\", "/")
        if path_model.is_dir():
            unix_relative_path = f"{unix_relative_path}/*"
        logger.info(f"Adding {unix_relative_path} to repository.")
        self.repo.git.add(unix_relative_path)

    def add(self, path: Union[list, set, str]) -> None:
        """Adds a file or a list of files.

        Args:
            path: file path or list of file paths
        """
        if isinstance(path, list) or isinstance(path, set):
            for element in path:
                self.add(element)
        else:
            self._add_one_file_or_one_dir(path)

    def commit(self, message: str, **kwargs: Optional[Tuple[str, Any]]) -> None:
        """Commits changes to the repository.

        Args:
            message: commit message
            **kwargs: extra parameters
        """
        logger.info("Committing changes")
        self.repo.index.commit(message, author=self.author, **kwargs)

    def get_master_branch(self) -> Any:
        """Gets the `master` branch.

        Returns:
            corresponding branch
        """
        main = configuration.get_value(ConfigurationVariable.MASTER_BRANCH)
        branch = self.get_branch(main)
        if branch:
            return branch
        return self.get_remote_branch(main)

    def get_beta_branch(self) -> Any:
        """Gets the `beta` branch.

        Returns:
            corresponding branch
        """
        beta = configuration.get_value(ConfigurationVariable.BETA_BRANCH)
        branch = self.get_branch(beta)
        if branch:
            return branch
        return self.get_remote_branch(beta)

    def is_release_branch(self, branch_name: Optional[str]) -> bool:
        """Checks whether the branch is a `release` branch or not.

        Args:
            branch_name: name of the branch

        Returns:
            True if the branch is used for `release` code; False otherwise
        """
        branch_pattern = configuration.get_value(ConfigurationVariable.RELEASE_BRANCH_PATTERN)
        is_release, _ = self._is_branch_of_type(branch_name, branch_pattern)
        return is_release

    def fetch(self) -> None:
        """Fetches latest changes."""
        self.repo.git.fetch(all=True, tags=True, force=True)

    def get_branch(self, branch_name: str) -> Any:
        """Gets a specific local branch.

        Args:
            branch_name: name of the branch to look for

        Returns:
            corresponding branch or `None`
            if no branches with this `branch_name` were found
        """
        branch = self._get_branch_reference(branch_name)
        if branch:
            return branch
        self.fetch()
        return self._get_branch_reference(branch_name)

    def _get_branch_reference(self, branch_name: str) -> Any:
        try:
            return self.repo.heads[str(branch_name)]
        except (IndexError, ValueError) as e:
            logger.warning(e)
            return None

    def get_current_branch(self) -> Any:
        """Gets the current branch.

        Returns:
            the current branch
        """
        # Workaround  for this GitPython issue https://github.com/gitpython-developers/GitPython/issues/510
        try:
            return self.repo.active_branch
        except TypeError as e:
            logger.warning(f"Could not determine the branch name using GitPython: {e}")
        current_branch = self._get_branch_from_advanced_feature()
        if not current_branch:
            current_branch = self._get_branch_from_abbreviation("HEAD")
        return current_branch

    def _get_branch_from_advanced_feature(self) -> Any:
        if version.parse(self.git_version()) >= version.parse("2.22"):
            current_branch = self.repo.git.branch(show_current=True)
            current_branch = current_branch if isinstance(current_branch, str) else current_branch.decode("utf-8")
            return self.get_branch(current_branch)
        return None

    def _get_branch_from_abbreviation(self, abbreviation: str) -> Any:
        current_branch = self.repo.git.rev_parse("--abbrev-ref", abbreviation)
        current_branch = current_branch if isinstance(current_branch, str) else current_branch.decode("utf-8")
        return self.get_branch(current_branch.strip())

    def get_commit_count(self) -> int:
        """Gets current commit count.

        Gets a number stating how many commits would have been listed
        before the current commit.

        Returns:
            number of commits before this current one.
        """
        current_commit = self.get_current_commit()
        return int(current_commit.count()) if current_commit else 0

    def get_commit_hash(self) -> str:
        """Gets the hash of the current commit.

        Returns:
             a hash.
        """
        return str(self.get_current_commit())

    def get_current_commit(self) -> Any:
        """Gets the current commit.

        Returns:
            the current commit.
        """
        return self.repo.commit(self.get_current_branch())

    def get_branch_point(self, commit1: Any, commit2: Any) -> Any:
        """Finds the common ancestor.

        See https://git-scm.com/docs/git-merge-base

        Args:
            commit1: commit1
            commit2: commit2

        Returns:
            the branch point.
        """
        return self.repo.merge_base(commit1, commit2).pop()

    def merge(self, branch: Any) -> None:
        """Merges `branch` to current branch.

        Args:
            branch: branch to merge
        """
        current_branch = self.get_current_branch()
        merge_base = self.repo.merge_base(branch, current_branch)
        self.repo.index.merge_tree(current_branch, base=merge_base)
        self.commit(f"Merge from {str(branch)}", parent_commits=(branch.commit, current_branch.commit))

    def get_remote_url(self) -> str:
        """Gets the URL of the remote repository.

        Returns:
            the corresponding URL.
        """
        remote = self._get_remote()
        if not remote:
            raise ValueError("Undefined remote repository")
        url = remote.url
        if not url:
            raise ValueError("Undefined remote repository URL")
        return str(url)

    def cherry_pick(self, commit: Any) -> None:
        """Cherry picks a specific commit.

        Args:
            commit: commit to cherry pick
        """
        self.repo.git.cherry_pick(str(commit))

    def set_remote_url(self, url: str) -> None:
        """Sets the URL of the remote repository.

        Args:
            url: URL
        """
        remote = self._get_remote()
        if remote:
            self.repo.delete_remote(str(remote))
        self.repo.create_remote(configuration.get_value(ConfigurationVariable.REMOTE_ALIAS), url=url)

    def get_remote_branch(self, branch_name: str) -> Optional[Any]:
        """Gets the branch present in the remote repository.

        Args:
            branch_name: name of the branch

        Returns:
            corresponding branch if exists. `None` otherwise
        """
        remote = self._get_remote()
        if not remote:
            return None
        try:
            return remote.refs[str(branch_name)]
        except (IndexError, ValueError) as e:
            logger.warning(e)
            return None

    def set_upstream_branch(self, branch_name: str) -> None:
        """Sets the upstream branch of the current branch.

        Args:
            branch_name: name of the remote branch.
        """
        if self.remote_branch_exists(branch_name):
            self.repo.git.branch("--set-upstream-to", self.get_remote_branch(branch_name))

    def delete_branch(self, branch: Any) -> None:
        """Deletes a branch.

        Args:
            branch: branch to delete
        """
        self.repo.delete_head(branch)

    def list_branches(self) -> list:
        """Gets the list of branches.

        Returns:
            list of branches

        """
        return [b for b in self.repo.heads]

    def branch_exists(self, branch_name: str) -> bool:
        """Checks whether a branch in the repository exists.

        Args:
            branch_name: name of the branch

        Returns:
            True if there is a branch called `branch_name`; False otherwise
        """
        return self.get_branch(branch_name) is not None

    def remote_branch_exists(self, branch_name: str) -> bool:
        """Checks whether a branch in the remote repository exists.

        Args:
            branch_name: name of the branch

        Returns:
            True if there is a remote branch called `branch_name`; False otherwise

        """
        return self.get_remote_branch(branch_name) is not None

    def _get_specific_changes(self, change_type: Optional[str], commit1: Any, commit2: Any) -> List[str]:
        diff = commit1.diff(commit2)
        if change_type:
            change_type = change_type.upper()
            change_type = change_type if change_type in diff.change_type else None
        diff_iterator = diff.iter_change_type(change_type) if change_type else diff
        changes = [change.a_path if change.a_path else change.b_path for change in diff_iterator]
        return changes

    def get_changes_list(
        self, commit1: Any, commit2: Any, change_type: Optional[str] = None, dir: Optional[str] = None
    ) -> List[str]:
        """Gets change list.

        Gets a list of all the changes that happened between two commits:
        list of the paths of the files which changed

        Args:
            commit1: commit
            commit2: other commit
            change_type: type of change e.g. 'A' for added files, 'D' for deleted files
            dir: directory of interest. if None the whole repository is considered

        Returns:
            list of paths
        """
        changes = self._get_specific_changes(change_type, commit1, commit2)
        if dir:
            windows_path = dir.replace("/", "\\")
            linux_path = dir.replace("\\", "/")
            return [change for change in changes if (linux_path in change) or (windows_path in change)]
        else:
            return changes

    def pull_all(self) -> None:
        """Pulls all changes from all remotes."""
        self.repo.git.pull(all=True, force=True, quiet=True)

    def pull(self) -> None:
        """Pulls changes on current branch from the remote repository."""
        if self.remote_branch_exists(self.get_current_branch()):
            self.repo.git.pull(self._get_remote(), self.get_current_branch(), quiet=True)

    def force_pull(self) -> None:
        """Force pulls changes from the remote repository."""
        self.repo.git.pull(self._get_remote(), self.get_current_branch(), quiet=True, force=True)

    def push(self) -> None:
        """Pushes commits.

        Pushes changes to the remote repository.
        Pushes also relevant annotated tags when pushing branches out.
        """
        self.repo.git.push("--follow-tags", "--set-upstream", self._get_remote(), self.get_current_branch())

    def push_tag(self) -> None:
        """Pushes commits and tags.

        Pushes changes to the remote repository.
        Tags are also pushed as part of the process
        """
        self.repo.git.push(tags=True)

    def force_push(self) -> None:
        """Pushes commits with force.

        Performs a force push.
        """
        self.repo.git.push(force=True)

    def force_push_tag(self) -> None:
        """Pushes commits and tags with force.

        Performs a force push.
        Tags are also pushed as part of the process
        """
        self.repo.git.push(force=True, tags=True)

    def is_dirty(self) -> bool:
        """Determines whether repository is dirty.

        Repository is considered dirty when git status returns elements which are not committed.
        """
        return self.repo.is_dirty(untracked_files=True)

    def clean(self) -> None:
        """Cleans the repository.

        Performs a force clean.
        """
        if self.is_dirty():
            self.repo.git.clean(force=True, x=True, d=True)

    def stash(self) -> None:
        """Stashes the repository.

        Performs a stash.
        """
        self.repo.git.stash(all=True, quiet=True)

    def configure_for_github(self) -> None:
        """Reconfigures the repository.

        Configures the repository so that we can commit back to GitHub
        """
        self.configure_author()
        self.set_remote_url(self._git_url_ssh_to_https(self.get_remote_url()))

    def create_tag(self, tag_name: str, message: Optional[str] = None) -> Any:
        """Creates a new tag.

        Args:
            tag_name: name of the tag
            message: tag annotation (https://git-scm.com/book/en/v2/Git-Basics-Tagging#_annotated_tags)

        Returns:
            corresponding tag
        """
        return self.repo.create_tag(tag_name, message=message, force=True)

    def create_branch(self, branch_name: str) -> Any:
        """Creates a new branch.

        Args:
             branch_name: name of the branch

        Returns:
             corresponding branch
        """
        logger.info(f"Creating branch {branch_name}")
        return self.repo.create_head(branch_name)

    def git_version(self) -> str:
        """Gets git version.

        Returns:
            the version of git in use.
        """
        return ".".join([str(element) for element in self.repo.git.version_info])

    def _get_remote(self) -> Optional[Any]:
        try:
            return self.repo.remote(configuration.get_value(ConfigurationVariable.REMOTE_ALIAS))
        except (IndexError, ValueError) as e:
            logger.warning(e)
            return None

    def list_files_added_on_current_branch(self) -> List[str]:
        """Returns a list of files changed against master branch."""
        master_branch = self.get_master_branch()
        beta_branch = self.get_beta_branch()
        master_branch_commit = self.repo.commit(master_branch)
        beta_branch_commit = self.repo.commit(beta_branch)
        current_branch_commit = self.repo.commit(self.get_current_branch())
        # Finding the baseline branch to consider
        master_branch_point = self.repo.commit(self.get_branch_point(master_branch_commit, current_branch_commit))
        beta_branch_point = self.repo.commit(self.get_branch_point(beta_branch_commit, current_branch_commit))
        branch_point = master_branch_point
        if not master_branch:
            branch_point = beta_branch_point
        elif beta_branch and master_branch:
            if beta_branch_point.committed_datetime > master_branch_point.committed_datetime:
                # The branch point off `beta` is more recent than off `master`.
                # Hence, the difference between current and `beta` should be considered.
                branch_point = beta_branch_point
        changes = self.get_changes_list(branch_point, current_branch_commit, change_type="a")
        return changes

    def is_current_branch_feature(self) -> bool:
        """Returns boolean indicating if current branch is considered a feature."""
        current_branch = self.get_current_branch()
        is_master = current_branch == self.get_master_branch()
        is_beta = current_branch == self.get_beta_branch()
        is_release = self.is_release_branch(current_branch)
        return not (is_master or is_beta or is_release)

    def is_current_branch_of_type(self, pattern: str) -> (bool, Optional[List[Any]]):
        """Returns boolean indicating whether the current branch follows the pattern and the list of groups if any."""
        return self._is_branch_of_type(self.get_current_branch(), pattern)

    def _is_branch_of_type(self, branch_name: Optional[str], pattern: Optional[str]) -> (bool, Optional[List[Any]]):
        if not pattern:
            return False, None
        if not branch_name:
            return False, None
        match = re.search(pattern, str(branch_name))
        return True if match else False, match.groups() if match else None

    @property
    def uncommitted_changes(self) -> List[Path]:
        """Gets list of uncommitted files.

        Returns:
             list of uncommitted
        """
        status = self.repo.git.status(porcelain=True, untracked_files=True)
        if not status:
            return []

        return [Path(self.root).joinpath(line.strip().split(" ")[-1]) for line in status.splitlines()]

    @property
    def uncommitted_staged_changes(self) -> List[Path]:
        """Gets list of uncommitted staged changes.

        Returns:
             list of uncommitted staged changes
        """
        staged = self.repo.git.diff(staged=True, name_only=True)
        if not staged:
            return []

        return [Path(self.root).joinpath(line.strip()) for line in staged.splitlines()]

    @staticmethod
    def _apply_modifications(destination: Path, modified_file: Path) -> None:
        logger.info(f"Applying change in {modified_file} to {destination}")
        if not destination.parent.exists():
            os.makedirs(str(destination.parent), exist_ok=True)
        shutil.copy2(src=str(modified_file), dst=str(destination))

    @staticmethod
    def _apply_deletions(destination: Path) -> None:
        logger.info(f"Removing {destination}")
        if destination.exists():
            destination.unlink()

    def apply_uncommitted_changes(self, other_repo: "GitWrapper") -> None:
        """Applies the uncommitted changes found in current repository to another.

        Args:
            other_repo: repository to apply changes to
        """
        dest_root = other_repo.root
        for f in self.uncommitted_changes:
            destination = dest_root.joinpath(f.relative_to(self.root))
            if f.exists():
                GitWrapper._apply_modifications(destination, f)
            else:
                GitWrapper._apply_deletions(destination)
        for f in self.uncommitted_staged_changes:
            other_repo.add(f.relative_to(self.root))

    def get_corresponding_path(self, path_in_initial_repo: Path) -> Path:
        """Gets the path in current repository corresponding to path in initial repository.

        If current repository is not a clone, then identical absolute path is returned.

        Args:
            path_in_initial_repo: path to a file/directory in initial repository.

        Returns:
             corresponding path.
        """
        return (
            path_in_initial_repo
            if path_in_initial_repo.is_absolute()
            else Path(self.root).joinpath(path_in_initial_repo)
        )


class ProjectGitWrapper(GitWrapper):
    """Wrapper class over project's repository."""

    def __init__(self) -> None:
        """Creates a Git Wrapper."""
        super().__init__(
            path=Path(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)),
            repo=Repo(configuration.get_value(ConfigurationVariable.PROJECT_ROOT)),
        )


class LocalProjectRepository:
    """Context manager providing a git wrapper over the current project's repository."""

    def __init__(self) -> None:
        """Constructor."""
        self._repo = ProjectGitWrapper()

    def __enter__(self) -> ProjectGitWrapper:
        """Context manager entry point."""
        return self._repo

    def __exit__(self, type: Any, value: Any, traceback: Any) -> None:
        """Context manager exit point."""
        pass


class GitClone(GitWrapper):
    """Cloned repository.

    It behaves exactly like the repository it is based on but
    is in a completely different location.
    """

    def __init__(self, path: Path, initial_path: Path, repo: Repo) -> None:
        """Creates an instance of GitWrapper.

        Args:
            path: path to repository.
            repo: GitPython repository.
            initial_path: path to the repository the clone is based on.
        """
        super().__init__(path, repo)
        self._initial_path = initial_path

    @staticmethod
    def wrap(repo: GitWrapper, initial_location: Path) -> "GitClone":
        """Wraps around around a repository."""
        return GitClone(repo=repo.repo, path=repo.root, initial_path=initial_location)

    @property
    def initial_location(self) -> Path:
        """Gets the path to the repository it is based on."""
        return self._initial_path

    def _add_one_path(self, path_model: Path) -> None:
        super()._add_one_path(self.get_corresponding_path(path_model))

    def get_corresponding_path(self, path_in_initial_repo: Path) -> Path:
        """Gets the path in cloned repository corresponding to path in initial repository.

        Args:
            path_in_initial_repo: path to a file/directory in initial repository.

        Returns:
             corresponding path.
        """
        if not path_in_initial_repo.is_absolute():
            return Path(self.root).joinpath(path_in_initial_repo)
        try:
            # Tyring to find if the path corresponds to a file/directory present in intial repository
            return Path(self.root).joinpath(path_in_initial_repo.relative_to(self.initial_location))
        except ValueError:
            return path_in_initial_repo


class GitTempClone:
    """Context manager providing a temporary cloned repository."""

    def __init__(self, desired_branch_name: Optional[str], repository_to_clone: GitWrapper):
        """Constructor.

        Args:
            desired_branch_name: the branch to consider. I
            repository_to_clone: the repository to clone. If not specified, the project repository will be used.
        """
        self._temporary_dir = TemporaryDirectory()
        logger.info(f"Creating a temporary repository in {self._temporary_dir}")
        self._repo = repository_to_clone
        _current_branch_name = desired_branch_name if desired_branch_name else str(self._repo.get_current_branch())
        self._clone = GitClone.wrap(self._repo.clone(self._temporary_dir.path), initial_location=self._repo.root)
        self._clone.checkout(_current_branch_name)
        self._repo.apply_uncommitted_changes(self._clone)

    def __enter__(self) -> GitClone:
        """Context manager entry point."""
        return self._clone

    def __exit__(self, type: Any, value: Any, traceback: Any) -> None:
        """Context manager exit point.

        As described in
        https://github.com/gitpython-developers/GitPython/blob/60acfa5d8d454a7c968640a307772902d211f043/git/repo/base.py#L223,
        Tempfiles objects on Windows are holding references to open files until
        they are collected by the garbage collector, thus preventing deletion.
        """
        self._repo.repo.close()
        self._temporary_dir.cleanup()


class ProjectTempClone(GitTempClone):
    """Temporary cloned repository for current project."""

    def __init__(self, desired_branch_name: Optional[str] = None):
        """Constructor.

        Args:
            desired_branch_name: the branch to consider. if not specified, the
            system will try to identify the current branch in the repository which
            will work in most cases but probably not on CI.
        """
        super().__init__(desired_branch_name=desired_branch_name, repository_to_clone=ProjectGitWrapper())
