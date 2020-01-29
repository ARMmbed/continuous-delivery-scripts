"""Utility script to abstract git operations for our CI scripts."""
import logging
import os
import re
from git import Repo, Actor
from typing import Optional, List, Union, Any, Tuple

from .configuration import configuration, ConfigurationVariable

logger = logging.getLogger(__name__)


class GitWrapper:
    """Wrapper class to provide convenient methods for performing git actions."""

    def __init__(self) -> None:
        """Creates an instance of GitWrapper."""
        self.repo = Repo(
            configuration.get_value(ConfigurationVariable.PROJECT_ROOT))
        self.author = Actor(
            configuration.get_value(ConfigurationVariable.BOT_USERNAME),
            configuration.get_value(ConfigurationVariable.BOT_EMAIL))

    def _git_url_ssh_to_https(self, url: str) -> str:
        """Changes repository URL to use authorisation token.

        Converts the git url to use the GitHub token:
        See https://github.blog/2012-09-21-easier-builds-and-deployments-using-git-over-https-and-oauth/

        Returns:
            new URL
        """
        path = url.split('github.com', 1)[1][1:].strip()
        new = 'https://{GITHUB_TOKEN}:x-oauth-basic@github.com/%s' % path
        logger.info('rewriting git url to: %s' % new)
        return new.format(GITHUB_TOKEN=configuration.get_value(
            ConfigurationVariable.GIT_TOKEN))

    def configure_author(self) -> None:
        """Sets the author."""
        self.repo.config_writer().set_value("user", "name",
                                            self.author.name).release()
        self.repo.config_writer().set_value("user", "email",
                                            self.author.email).release()

    def checkout(self, branch: Any) -> None:
        """Checks out a branch.

        Args:
            branch: branch to check out

        """
        self.repo.git.checkout(branch)

    def _add_one_file_or_one_dir(self, path: str) -> None:
        if not path:
            raise ValueError('Unspecified path.')
        if not os.path.exists(path):
            logger.warning(f'[Git] {path} cannot be added because not found.')
            return
        relative_path = os.path.relpath(path, start=configuration.get_value(
            ConfigurationVariable.PROJECT_ROOT))
        unix_relative_path = relative_path.replace('\\', '/')
        if os.path.isdir(unix_relative_path):
            unix_relative_path = f'{unix_relative_path}/*'
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

    def commit(self, message: str,
               **kwargs: Optional[Tuple[str, Any]]) -> None:
        """Commits changes to the repository.

        Args:
            message: commit message
            **kwargs: extra parameters
        """
        self.repo.index.commit(
            message,
            author=self.author,
            **kwargs
        )

    def get_master_branch(self) -> Any:
        """Gets the `master` branch.

        Returns:
            corresponding branch
        """
        return self.get_branch(configuration.get_value(
            ConfigurationVariable.MASTER_BRANCH))

    def get_beta_branch(self) -> Any:
        """Gets the `beta` branch.

        Returns:
            corresponding branch
        """
        return self.get_branch(configuration.get_value(
            ConfigurationVariable.BETA_BRANCH))

    def is_release_branch(self, branch_name: Optional[str]) -> bool:
        """Checks whether the branch is a `release` branch or not.

        Args:
            branch_name: name of the branch

        Returns:
            True if the branch is used for `release` code; False otherwise
        """
        branch_pattern = configuration.get_value(
            ConfigurationVariable.RELEASE_BRANCH_PATTERN)
        if not branch_pattern or not branch_name:
            return False
        is_release: Optional[Any] = re.search(branch_pattern,
                                              str(branch_name))
        return True if is_release else False

    def fetch(self) -> None:
        """Fetches latest changes."""
        self.repo.git.fetch(tags=True, force=True)

    def get_branch(self, branch_name: str) -> Any:
        """Gets a specific branch.

        Args:
            branch_name: name of the branch to look for

        Returns:
            corresponding branch or `None`
            if no branches with this `branch_name` were found
        """
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
            logger.warning(
                f'Could not determine the branch name using GitPython: {e}'
            )
        return self.get_branch(
            self.repo.git.rev_parse('--abbrev-ref', 'HEAD').decode(
                'utf-8').strip()
        )

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
        self.commit(f'Merge from {str(branch)}',
                    parent_commits=(branch.commit, current_branch.commit))

    def get_remote_url(self) -> str:
        """Gets the URL of the remote repository.

        Returns:
            the corresponding URL.
        """
        remote = self._get_remote()
        if not remote:
            raise ValueError('Undefined remote repository')
        url = remote.url
        if not url:
            raise ValueError('Undefined remote repository URL')
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
        self.repo.create_remote(configuration.get_value(
            ConfigurationVariable.REMOTE_ALIAS), url=url)

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
            self.repo.git.branch(
                '--set-upstream-to', self.get_remote_branch(branch_name)
            )

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

    def _get_specific_changes(self, change_type: Optional[str], commit1: Any,
                              commit2: Any) -> List[str]:
        diff = commit1.diff(commit2)
        if change_type:
            change_type = change_type.upper()
            change_type = change_type if change_type in diff.change_type else None
        diff_iterator = diff.iter_change_type(
            change_type) if change_type else diff
        changes = [change.a_path if change.a_path else change.b_path for change
                   in diff_iterator]
        return changes

    def get_changes_list(self, commit1: Any, commit2: Any,
                         change_type: Optional[str] = None,
                         dir: Optional[str] = None) -> List[str]:
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
            windows_path = dir.replace('/', '\\')
            linux_path = dir.replace('\\', '/')
            return [
                change for change in changes if
                (linux_path in change) or (windows_path in change)
            ]
        else:
            return changes

    def pull(self) -> None:
        """Pulls changes from the remote repository."""
        if self.remote_branch_exists(self.get_current_branch()):
            self.repo.git.pull(self._get_remote(), self.get_current_branch(),
                               '--quiet')

    def force_pull(self) -> None:
        """Force pulls changes from the remote repository."""
        self.repo.git.pull(self._get_remote(), self.get_current_branch(),
                           quiet=True, force=True)

    def push(self) -> None:
        """Pushes commits.

        Pushes changes to the remote repository.
        Pushes also relevant annotated tags when pushing branches out.
        """
        self.repo.git.push('--follow-tags', '--set-upstream',
                           self._get_remote(),
                           self.get_current_branch())

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
        return self.repo.create_head(branch_name)

    def _get_remote(self) -> Optional[Any]:
        try:
            return self.repo.remote(
                configuration.get_value(ConfigurationVariable.REMOTE_ALIAS))
        except (IndexError, ValueError) as e:
            logger.warning(e)
            return None
