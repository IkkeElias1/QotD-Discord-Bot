# -*- coding: utf-8 -*-
"""
Nordic Character Normalization Module.

Handles Danish/Norwegian/Swedish character normalization and v/w interchange
for accurate name matching across Nordic language variations.
"""

import unicodedata
from typing import List, Callable


class NordicNormalizer:
    """
    Handle Nordic character normalization and v/w interchange.
    
    This class provides methods to normalize text containing Nordic characters
    (æ, ø, å, Æ, Ø, Å) and generate variants for v/w phonetic similarity.
    """
    
    # Nordic character mappings for normalization
    NORDIC_CHAR_MAP = {
        'æ': 'ae',
        'ø': 'o',
        'å': 'a',
        'ä': 'a',
        'ö': 'o',
        'ü': 'u',
        'ß': 'ss',
    }
    
    def __init__(self) -> None:
        """Initialize the Nordic normalizer."""
        # Build reverse mapping for uppercase
        self._char_map = {}
        for lower_char, replacement in self.NORDIC_CHAR_MAP.items():
            self._char_map[lower_char] = replacement
            self._char_map[lower_char.upper()] = replacement.upper()
    
    def normalize(self, text: str) -> str:
        """
        Normalize text with Unicode decomposition and Nordic character handling.
        
        This method:
        1. Converts to lowercase
        2. Strips whitespace
        3. Applies NFKD Unicode normalization (removes accents/diacritics)
        4. Maps Nordic characters to ASCII equivalents
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text in lowercase with Nordic characters replaced
        """
        if not text:
            return ""
        
        # First apply Nordic character mapping
        result = text.lower()
        for char, replacement in self._char_map.items():
            if char.lower() in result:
                result = result.replace(char.lower(), replacement.lower())
        
        # Apply NFKD decomposition to handle remaining accents
        normalized = ''.join(
            c for c in unicodedata.normalize('NFKD', result)
            if not unicodedata.combining(c)
        )
        
        # Clean up whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized.strip()
    
    def normalize_preserve_structure(self, text: str) -> str:
        """
        Normalize text but preserve internal structure (spaces, casing pattern).
        
        Useful when you need to maintain word boundaries but normalize characters.
        
        Args:
            text: The text to normalize
            
        Returns:
            Normalized text with original structure preserved
        """
        if not text:
            return ""
        
        result = text
        
        # Apply Nordic character mapping preserving case
        for char, replacement in self._char_map.items():
            result = result.replace(char, replacement)
        
        # Apply NFKD decomposition
        normalized = ''.join(
            c for c in unicodedata.normalize('NFKD', result)
            if not unicodedata.combining(c)
        )
        
        return normalized.strip()
    
    def generate_variants(self, text: str) -> List[str]:
        """
        Generate phonetic variants for v/w interchange.
        
        In Nordic languages (particularly Danish), 'v' and 'w' are often
        phonetically similar or interchangeable in certain contexts.
        
        Args:
            text: The text to generate variants for
            
        Returns:
            List of variants including the original (normalized) form
        """
        normalized = self.normalize(text)
        variants = {normalized}
        
        # Generate v -> w variant
        if 'v' in normalized:
            variants.add(normalized.replace('v', 'w'))
        
        # Generate w -> v variant
        if 'w' in normalized:
            variants.add(normalized.replace('w', 'v'))
        
        # Handle mixed v/w cases - generate all combinations
        if 'v' in normalized and 'w' in normalized:
            # All v's to w's
            all_w = normalized.replace('v', 'w')
            variants.add(all_w)
            # All w's to v's  
            all_v = normalized.replace('w', 'v')
            variants.add(all_v)
        
        return list(variants)
    
    def generate_nordic_variants(self, text: str) -> List[str]:
        """
        Generate variants with and without Nordic character expansion.
        
        Useful for matching names that might be written with or without
        Nordic characters (e.g., "Tørst" vs "Torst").
        
        Args:
            text: The text to generate variants for
            
        Returns:
            List of variants with different Nordic character treatments
        """
        variants = set()
        
        # Original lowercased
        lower_text = text.lower().strip()
        variants.add(lower_text)
        
        # Fully normalized (Nordic chars expanded)
        normalized = self.normalize(text)
        variants.add(normalized)
        
        # Add v/w variants for both
        for base in list(variants):
            if 'v' in base:
                variants.add(base.replace('v', 'w'))
            if 'w' in base:
                variants.add(base.replace('w', 'v'))
        
        return list(variants)
    
    def match_with_variants(
        self,
        query: str,
        candidate: str,
        similarity_func: Callable[[str, str], float]
    ) -> float:
        """
        Match query against candidate using all generated variants.
        
        Compares all combinations of query variants with candidate variants
        and returns the highest similarity score.
        
        Args:
            query: The search query
            candidate: The candidate name to match against
            similarity_func: A function that takes two strings and returns
                           a similarity score (0.0 to 1.0)
            
        Returns:
            The highest similarity score across all variant combinations
        """
        query_variants = self.generate_variants(query)
        candidate_variants = self.generate_variants(candidate)
        
        max_score = 0.0
        
        for q_var in query_variants:
            for c_var in candidate_variants:
                score = similarity_func(q_var, c_var)
                max_score = max(max_score, score)
        
        return max_score
    
    def are_equivalent(self, name1: str, name2: str) -> bool:
        """
        Check if two names are equivalent after normalization.
        
        This is a quick check for exact matches after normalizing
        Nordic characters and case.
        
        Args:
            name1: First name to compare
            name2: Second name to compare
            
        Returns:
            True if names are equivalent after normalization
        """
        norm1 = self.normalize(name1)
        norm2 = self.normalize(name2)
        
        if norm1 == norm2:
            return True
        
        # Check v/w variants
        variants1 = self.generate_variants(name1)
        variants2 = self.generate_variants(name2)
        
        return bool(set(variants1) & set(variants2))
    
    def get_sort_key(self, text: str) -> str:
        """
        Get a normalized sort key for ordering names.
        
        Useful for sorting lists of names in a consistent order
        regardless of Nordic character variations.
        
        Args:
            text: The text to get a sort key for
            
        Returns:
            A normalized string suitable for sorting
        """
        return self.normalize(text)
