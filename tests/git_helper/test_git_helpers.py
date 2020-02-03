from unittest import TestCase

from mbed_tools_ci_scripts.utils.configuration import configuration, \
    ConfigurationVariable
from mbed_tools_ci_scripts.utils.git_helpers import ProjectTempClone, \
    GitTempClone, \
    GitWrapper, ProjectGitWrapper
from uuid import uuid4
from pathlib import Path


class TestGitWrapper(TestCase):

    def test_basic_properties(self):
        """Checks basic properties are set as expected."""
        git = ProjectGitWrapper()
        self.assertEqual(
            configuration.get_value(ConfigurationVariable.PROJECT_ROOT),
            str(git.root))
        version = git.git_version()
        self.assertIsNotNone(version)
        self.assertTrue('.' in version)
        self.assertTrue(git.get_commit_count() > 0)
        self.assertIsNotNone(git.uncommitted_changes)
        self.assertIsNotNone(git.get_remote_url())


class TestGitTempClone(TestCase):

    def test_git_clone(self):
        """Ensures a fully fledged clone is created."""
        with ProjectTempClone(desired_branch_name='master') as clone:
            self.assertTrue(isinstance(clone, GitWrapper))
            self.assertEqual('master', str(clone.get_current_branch()))
            self.assertNotEqual(
                configuration.get_value(ConfigurationVariable.PROJECT_ROOT),
                str(clone.root))

    def test_git_clone_independent(self):
        """Ensures the clone is independent from repository it is based on."""
        git = ProjectGitWrapper()
        with GitTempClone(repository_to_clone=git,
                          desired_branch_name='master') as clone:
            self.assertEqual(git.get_remote_url(), clone.get_remote_url())
            self.assertNotEqual(git.root, clone.root)

    def test_git_branch_actions(self):
        """Test basic git branch actions on the clone."""
        with ProjectTempClone(desired_branch_name='master') as clone:
            branch = clone.create_branch(f'test-{uuid4()}')
            self.assertIsNotNone(branch)
            self.assertEqual(branch, clone.get_branch(str(branch)))
            self.assertIsNone(clone.get_remote_branch(str(branch)))
            self.assertTrue(branch in clone.list_branches())
            self.assertNotEqual(str(clone.get_current_branch()), branch)
            self.assertFalse(clone.is_current_branch_feature())
            clone.checkout_branch(str(branch))
            self.assertEqual(clone.get_current_branch(), branch)
            self.assertTrue(clone.is_current_branch_feature())
            self.assertTrue(
                len(clone.list_files_added_on_current_branch()) == 0)

    def test_file_addition(self):
        """Test basic git branch actions on the clone."""
        with ProjectTempClone(desired_branch_name='master') as clone:
            branch = clone.create_branch(f'test-{uuid4()}')
            clone.checkout(branch)
            self.assertTrue(
                len(clone.list_files_added_on_current_branch()) == 0)
            previous_hash = clone.get_commit_hash()
            previous_count = clone.get_commit_count()
            test_file = Path(clone.root).joinpath(f'branch-test-{uuid4()}.txt')
            test_file.touch()
            uncommitted_changes = clone.uncommitted_changes
            self.assertTrue(test_file in uncommitted_changes)
            clone.add(test_file)
            clone.commit('Test commit')
            self.assertNotEqual(previous_hash, clone.get_commit_hash())
            self.assertEqual(previous_count + 1, clone.get_commit_count())
            added_files = [Path(clone.root).joinpath(f) for f in
                           clone.list_files_added_on_current_branch()]
            self.assertTrue(test_file in added_files)

    def test_file_addition_with_paths_to_initial_repository(self):
        """Test basic git add on the clone."""
        git = ProjectGitWrapper()
        test_file = Path(git.root).joinpath(f'a_test_file-{uuid4()}.txt')
        test_file.touch()
        with GitTempClone(repository_to_clone=git,
                          desired_branch_name='master') as clone:
            test_file.unlink()
            branch = clone.create_branch(f'branch-test-{uuid4()}')
            clone.checkout(branch)
            uncommitted_changes = clone.uncommitted_changes
            self.assertTrue(
                clone.get_corresponding_path(test_file) in uncommitted_changes)
            clone.add(test_file)
            clone.commit('Test commit')
            added_files = [Path(git.root).joinpath(f) for f in
                           clone.list_files_added_on_current_branch()]
        self.assertTrue(test_file in added_files)
