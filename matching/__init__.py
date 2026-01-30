# -*- coding: utf-8 -*-
"""
Matching Module - Sophisticated nickname resolution for QotD Discord Bot.

This module provides multi-layered name matching with:
- Fuzzy string matching (RapidFuzz)
- Phonetic matching (Double Metaphone)
- Nordic character normalization
- Entity disambiguation and clustering
- Configurable thresholds and layers
"""

from .core import NameMatcher, MatchResult
from .normalization import NordicNormalizer
from .algorithms import calculate_hybrid_score, StringSimilarity
from .phonetic import PhoneticMatcher
from .blocking import BlockingStrategy
from .entity_resolution import EntityResolver
from .config_manager import ConfigManager
from .debug import DebugLogger

__all__ = [
    'NameMatcher',
    'MatchResult',
    'NordicNormalizer',
    'StringSimilarity',
    'calculate_hybrid_score',
    'PhoneticMatcher',
    'BlockingStrategy',
    'EntityResolver',
    'ConfigManager',
    'DebugLogger',
]

__version__ = '1.0.0'
