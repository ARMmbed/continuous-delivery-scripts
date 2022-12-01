#
# Copyright (C) 2020-2022 Arm Limited or its affiliates and Contributors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Utilities regarding string handling."""
from functools import total_ordering

import jellyfish
from dataclasses import dataclass
from typing import Iterable, Tuple


@total_ordering
@dataclass(frozen=True)
class MatchingStats:
    """Definition of matching statistics for two strings. .

    Attributes:
        string1: a string
        string2: another string
        damerau_levenshtein_distance: the Damerau Levenshtein distance between the two strings.
        jaro_winkler_distance: the Jaro Winkler distance between the two strings.
        match_rating_approach_comparison: the match rating approach comparison.
        exact_match: whether the two strings match exactly.
    """

    string1: str
    string2: str
    damerau_levenshtein_distance: int
    jaro_winkler_distance: float
    match_rating_approach_comparison: bool
    exact_match: bool

    def __lt__(self, other: "MatchingStats") -> bool:
        """Redefines Less than.

        The stats are "smaller" if the distance between the two strings is smaller.
        In other words, the stats are smaller if the strings are more likely to match.
        """
        if self.jaro_winkler_distance > other.jaro_winkler_distance:
            return True
        return self.damerau_levenshtein_distance < other.damerau_levenshtein_distance

    def __eq__(self, other: object) -> bool:
        """Redefines equal."""
        if not isinstance(other, MatchingStats):
            return False
        return (self.exact_match == other.exact_match) or (
            self.match_rating_approach_comparison == other.match_rating_approach_comparison
        )


def determine_matching_stats(string1: str, string2: str) -> MatchingStats:
    """Determines the different distances between two strings."""
    return MatchingStats(
        string1=string1,
        string2=string2,
        damerau_levenshtein_distance=jellyfish.damerau_levenshtein_distance(string1, string2),
        jaro_winkler_distance=jellyfish.jaro_winkler_similarity(string1, string2),
        match_rating_approach_comparison=jellyfish.match_rating_comparison(string1, string2),
        exact_match=string1.strip().lower() == string2.strip().lower(),
    )


def determine_similar_string_from_list(string: str, strings: Iterable[str]) -> Tuple[float, str]:
    """Determines the closest string to a string from a list."""
    string_to_assess = string.strip()
    ordered_list = sorted([determine_matching_stats(string_to_assess, s) for s in strings])
    most_similar_string = ordered_list[0]
    return (most_similar_string.jaro_winkler_distance, most_similar_string.string2)
