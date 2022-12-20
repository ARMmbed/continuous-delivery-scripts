#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities in charge of fetching configuration values for the ci scripts."""
import enum
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, List, Union, Optional, Dict

import dotenv
import toml

from .filesystem_helpers import find_file_in_tree
from .news_file import NewsType

logger = logging.getLogger(__name__)


class ConfigurationVariable(enum.Enum):
    """Project's configuration variables."""

    PROJECT_ROOT = 1
    """Relative path to the root of the project from pyproject.toml."""
    PROJECT_CONFIG = 2
    """Relative path to the file comprising project's configuration."""
    NEWS_DIR = 3
    """Relative path to the directory comprising news files."""
    VERSION_FILE_PATH = 4
    """Relative path to the file comprising project's version."""
    CHANGELOG_FILE_PATH = 5
    """Relative path to the changelog file."""
    MODULE_TO_DOCUMENT = 6
    """Name of the module to generate documentation for."""
    DOCUMENTATION_DEFAULT_OUTPUT_PATH = 7
    DOCUMENTATION_PRODUCTION_OUTPUT_PATH = 8
    """Relative path to the folder where documentation will be generated."""
    GIT_TOKEN = 9
    """GIT token allowing committing back to the repository."""
    BETA_BRANCH = 10
    """Name of beta/QA branch."""
    MASTER_BRANCH = 11
    """Name of the main/production branch."""
    RELEASE_BRANCH_PATTERN = 12
    """Pattern of release branches."""
    REMOTE_ALIAS = 13
    """Git's remote alias."""
    LOGGER_FORMAT = 14
    """Tools' logger format."""
    BOT_USERNAME = 15
    """Username of the Git bot account."""
    BOT_EMAIL = 16
    """Email of the Git bot account."""
    ORGANISATION = 17
    """Name of the organisation managing the project."""
    ORGANISATION_EMAIL = 18
    """Email of the organisation managing the project."""
    AWS_BUCKET = 19
    """AWS bucket to use if needed."""
    PROJECT_NAME = 21
    """Name of the project."""
    PROJECT_UUID = 22
    """UUID of the project to use in SPDX reports."""
    PACKAGE_NAME = 23
    """Name of the package."""
    SOURCE_DIR = 24
    """Relative path to the source of the project."""
    IGNORE_REPOSITORY_TEST_UPLOAD = 25
    """States whether to release package to a test registry (e.g. pypi test) test before release."""
    FILE_LICENCE_IDENTIFIER = 26
    """SPDX identifier for the project's licence."""
    COPYRIGHT_START_DATE = 27
    """Project's copyright start year."""
    ACCEPTED_THIRD_PARTY_LICENCES = 28
    """List of accepted 3rd party licences for dependencies."""
    PACKAGES_WITH_CHECKED_LICENCE = 29
    """List of dependencies whose licence was manually checked."""
    PROGRAMMING_LANGUAGE = 30
    """Project's programming language."""
    AUTOGENERATE_NEWS_FILE_ON_DEPENDENCY_UPDATE = 31
    """States whether news file should be generated on dependency updates."""
    DEPENDENCY_UPDATE_BRANCH_PATTERN = 32
    """Pattern of branches comprising dependency updates (e.g. dependabot)."""
    DEPENDENCY_UPDATE_NEWS_MESSAGE = 33
    """Pattern of the news message for dependency update."""
    DEPENDENCY_UPDATE_NEWS_TYPE = 34
    """News file type for dependency update."""
    TAG_LATEST = 35
    """States whether the release should be tagged with `latest`"""
    TAG_VERSION_SHORTCUTS = 36
    """States whether the release should be tagged with shortcuts i.e. major, major+minor"""

    @staticmethod
    def choices() -> List[str]:
        """Gets a list of all possible configuration variables.

        Returns:
            a list of configuration variables
        """
        return [t.name.upper() for t in ConfigurationVariable]

    @staticmethod
    def parse(type_str: str) -> "ConfigurationVariable":
        """Determines the configuration variable from a string.

        Args:
            type_str: string to parse.

        Returns:
            corresponding configuration variable.
        """
        try:
            return ConfigurationVariable[type_str.upper()]
        except KeyError as e:
            raise ValueError(f"Unknown configuration variable: {type_str}. {e}")


class Undefined(Exception):
    """Exception raised when a configuration value is not defined."""

    pass


class GenericConfig(ABC):
    """Abstract Class for determining configuration values."""

    @abstractmethod
    def _fetch_value(self, key: str) -> Any:
        self._raise_undefined(key)

    def _raise_undefined(self, key: Optional[str]) -> None:
        raise Undefined(f"Undefined key: {key}")

    def get_value(self, key: Union[str, ConfigurationVariable]) -> Any:
        """Gets a configuration value.

        If the variable was not defined, an exception is raised.

        Args:
            key: variable key. This can be a string or a ConfigurationVariable
            element.

        Returns:
            configuration value corresponding to the key.
        """
        if not key:
            raise KeyError(key)
        key_str = key.name if isinstance(key, ConfigurationVariable) else key
        return self._fetch_value(key_str)

    def get_value_or_default(self, key: Union[str, ConfigurationVariable], default_value: Any) -> Any:
        """Gets a configuration value.

        If the variable was not defined, the default value is returned.

        Args:
            key: variable key. This can be a string or a ConfigurationVariable
            element.
            default_value: value to default to if the variable was not defined.

        Returns:
            configuration value corresponding to the key.
            default value if the variable is not defined.
        """
        try:
            return self.get_value(key)
        except Undefined as e:
            logger.debug(e)
            return default_value


class StaticConfig(GenericConfig):
    """Configuration with default values.

    Only variables which are not likely do be different from a project to
    another are defined here. They can be overridden by values in the
    configuration file though. This should simply the number of variables
    defined in toml.
    """

    BETA_BRANCH = "beta"
    MASTER_BRANCH = "master"
    RELEASE_BRANCH_PATTERN = r"^release.*$"
    REMOTE_ALIAS = "origin"
    LOGGER_FORMAT = "%(levelname)s: %(message)s"
    BOT_USERNAME = "Monty Bot"
    BOT_EMAIL = "monty-bot@arm.com"
    ORGANISATION = "Arm Limited"
    ORGANISATION_EMAIL = "support@arm.com"
    FILE_LICENCE_IDENTIFIER = "Apache-2.0"
    COPYRIGHT_START_DATE = 2020
    PROGRAMMING_LANGUAGE = "NoOp"
    AWS_BUCKET = "Unknown"
    AUTOGENERATE_NEWS_FILE_ON_DEPENDENCY_UPDATE = True
    TAG_LATEST = False
    TAG_VERSION_SHORTCUTS = False
    DEPENDENCY_UPDATE_NEWS_MESSAGE = "Dependency upgrade: {message}"
    DEPENDENCY_UPDATE_NEWS_TYPE = NewsType.bugfix
    DEPENDENCY_UPDATE_BRANCH_PATTERN = r"^\s*[Dd]ependabot\/.+\/(?P<DEPENDENCY>.+)"
    ACCEPTED_THIRD_PARTY_LICENCES = ["Apache-2.0", "BSD*", "JSON", "MIT", "Python-2.0", "PSF-2.0", "MPL-2.0"]
    PACKAGES_WITH_CHECKED_LICENCE: List[str] = []

    def _fetch_value(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            self._raise_undefined(key)


class EnvironmentConfig(GenericConfig):
    """Configuration set in environment variables.

    This also uses dotEnv mechanism.
    """

    def __init__(self) -> None:
        """Constructor."""
        dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True, raise_error_if_not_found=False))

    def _fetch_value(self, key: str) -> Any:
        environment_value = os.getenv(key)
        if not environment_value:
            self._raise_undefined(key)
        return environment_value


class FileConfig(GenericConfig):
    """Configuration set in toml file.

    Note: any variable which relates to a PATH
    i.e. variable comprising one of the tokens in (PATH_TOKEN)
     will be modified and transformed in order to become absolute paths
     rather than relative paths as relative paths in the file are relative to
     the file location whereas relative paths when used by tools are relative .
     to current directory (i.e. os.getcwd()).
    """

    CONFIG_SECTION = "ProjectConfig"
    PATH_TOKEN = {"DIR", "ROOT", "PATH"}
    CONFIG_FILE_NAME = "pyproject.toml"

    def __init__(self, file_path: str = None) -> None:
        """Constructor.

        Args:
            file_path: path to the toml configuration file.
        """
        self._file_path: Optional[str] = file_path
        self._config: Optional[dict] = None

    def _adjust_path_values(self, variable_name: str, value: str) -> str:
        """Works out the correct values for path variables.

        Paths in the configuration file are relative to the configuration
        file location. This method ensures the path values are therefore
        evaluated properly
        Args:
            variable_name: name of the variable in the configuration file
            value: variable value

        Returns:
            a valid path or the value unchanged if the variable is not a path

        """
        if not self._file_path:
            return value
        for token in FileConfig.PATH_TOKEN:
            if token in variable_name:
                config_file_dir = os.path.dirname(self._file_path)
                resolved_path = os.path.join(config_file_dir, value)
                value = os.path.realpath(resolved_path)
                break
        return value

    @staticmethod
    def _look_for_config_file_walking_up_tree() -> Optional[str]:
        try:
            return find_file_in_tree(FileConfig.CONFIG_FILE_NAME, top=True)
        except FileNotFoundError as e:
            logger.warning(e)
        return None

    @staticmethod
    def _find_config_file(file_path: Optional[str]) -> Optional[str]:
        if file_path and os.path.exists(file_path):
            return file_path
        try:
            return find_file_in_tree(FileConfig.CONFIG_FILE_NAME)
        except FileNotFoundError:
            return FileConfig._look_for_config_file_walking_up_tree()

    @staticmethod
    def _load_config_from_file(file_path: str) -> Dict[str, Any]:
        config: dict = toml.load(file_path).get(FileConfig.CONFIG_SECTION, dict())
        config[ConfigurationVariable.PROJECT_CONFIG.name] = file_path
        return config

    @property
    def config(self) -> dict:
        """Gets the file configuration."""
        if not self._config:
            self._file_path = FileConfig._find_config_file(self._file_path)
            self._config = FileConfig._load_config_from_file(self._file_path) if self._file_path else dict()
        return self._config

    def _fetch_value(self, key: str) -> Any:
        try:
            return self._adjust_path_values(key, self.config[key])
        except KeyError:
            self._raise_undefined(key)


class ProjectConfiguration(GenericConfig):
    """Overall project's configuration."""

    def __init__(self, sources: List[GenericConfig]):
        """Constructor.

        Args:
            sources: list of configuration sources
        """
        self._config_sources: list = sources

    def _fetch_value(self, key: str) -> Any:
        for config in self._config_sources:
            try:
                return config.get_value(key)
            except Undefined:
                pass
        else:
            self._raise_undefined(key)


# Project configuration
configuration: GenericConfig = ProjectConfiguration([FileConfig(), EnvironmentConfig(), StaticConfig()])
