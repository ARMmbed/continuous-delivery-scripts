#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Language plugins Loader."""

import logging
from typing import Optional, Dict, cast, Set, Type

from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.language_specifics_base import BaseLanguage

# this import is needed for plugin subclass detection
from continuous_delivery_scripts.plugins import *  # noqa

logger = logging.getLogger(__name__)


def _retrieve_all_subclasses(subclass: Type[BaseLanguage]) -> Set[Type[BaseLanguage]]:
    subclasses = set()
    if not subclass:
        return subclasses
    if subclass != BaseLanguage:
        subclasses.add(subclass)
    for s in subclass.__subclasses__():
        subclasses.update(_retrieve_all_subclasses(s))
    return subclasses


def all_language_plugins() -> Dict[str, BaseLanguage]:
    """Fetches all language plugins which inherit from BaseLanguage.

    Returns:
         A list of classes containing language plugins
    """
    all_plugins = _retrieve_all_subclasses(BaseLanguage)
    return {la.get_related_language().lower().strip(): la for la in [lang() for lang in all_plugins]}  # type: ignore


def fetch_project_language_plugin(all_plugins: Dict[str, BaseLanguage], language: str) -> BaseLanguage:
    """Fetches a language CD flow.

    Arguments:
        all_plugins: all the plugins at disposal
        language: the language to select

    Returns:
         A language plugin corresponding to the language requested
    """
    return cast(BaseLanguage, all_plugins.get(_sanitise_program_language(language)))


def _sanitise_program_language(language: str) -> str:
    return language.lower().strip()


def _fetch_project_language_specifics() -> BaseLanguage:
    return fetch_project_language_plugin(
        all_language_plugins(), str(configuration.get_value(ConfigurationVariable.PROGRAMMING_LANGUAGE))
    )


class PluginLoader:
    """Plugin loader."""

    _instance: Optional[BaseLanguage] = None

    def __init__(self) -> None:
        """Initialiser."""
        if not PluginLoader._instance:
            PluginLoader._instance = _fetch_project_language_specifics()

    @property
    def languageSpecifics(self) -> BaseLanguage:
        """Gets project language specifics."""
        return cast(BaseLanguage, PluginLoader._instance)


def get_language_specifics() -> BaseLanguage:
    """Gets the language specific actions."""
    return PluginLoader().languageSpecifics
