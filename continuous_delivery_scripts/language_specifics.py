#
# Copyright (C) 2020-2021 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Language plugins Loader."""

import logging
from typing import Optional, Dict, cast

from continuous_delivery_scripts.utils.configuration import configuration, ConfigurationVariable
from continuous_delivery_scripts.utils.language_specifics_base import BaseLanguage

# this import is needed for plugin subclass detection
from continuous_delivery_scripts.plugins import *  # noqa

logger = logging.getLogger(__name__)


def _all_language_plugins() -> Dict[str, BaseLanguage]:
    """Get all language plugins which inherit from BaseLanguage (with the exception of other base class).

    :return: A list of classes containing language plugins
    """
    all_plugins = BaseLanguage.__subclasses__()
    return {
        la.get_related_language().lower().strip(): la
        for la in [lang() for lang in all_plugins if lang != BaseLanguage]  # type: ignore
    }


def _sanitise_program_language() -> str:
    return str(configuration.get_value(ConfigurationVariable.PROGRAMMING_LANGUAGE)).lower().strip()


def _fetch_project_language_specifics() -> BaseLanguage:
    return cast(BaseLanguage, _all_language_plugins().get(_sanitise_program_language()))


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
