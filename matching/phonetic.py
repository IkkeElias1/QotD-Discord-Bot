# -*- coding: utf-8 -*-
"""
Phonetic Matching Module.

Implements Double Metaphone algorithm for phonetic name matching,
handling sound-alike variations like "walmart" → "Valdemar".
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

try:
    from metaphone import doublemetaphone
    METAPHONE_AVAILABLE = True
except ImportError:
    METAPHONE_AVAILABLE = False

from .normalization import NordicNormalizer


@dataclass
class PhoneticMatchResult:
    """Result of a phonetic match."""
    name: str
    confidence: float
    match_level: str  # 'strong', 'normal', 'weak'
    query_codes: Tuple[str, str]
    candidate_codes: Tuple[str, str]


class PhoneticMatcher:
    """
    Phonetic name matching using Double Metaphone algorithm.
    
    Provides hierarchical confidence scoring based on primary/secondary
    code matches for handling phonetic variations of names.
    """
    
    # Default confidence levels for different match types
    DEFAULT_CONFIDENCE = {
        'strong': 0.95,   # Primary-to-Primary match
        'normal': 0.85,   # Primary-to-Secondary or Secondary-to-Primary
        'weak': 0.70,     # Secondary-to-Secondary match
    }
    
    DEFAULT_THRESHOLDS = {
        'phonetic_primary_min': 0.95,
        'phonetic_normal_min': 0.85,
        'phonetic_weak_min': 0.70,
    }
    
    def __init__(
        self,
        thresholds: Optional[Dict[str, float]] = None,
        normalizer: Optional[NordicNormalizer] = None
    ) -> None:
        """
        Initialize the phonetic matcher.
        
        Args:
            thresholds: Custom thresholds for match acceptance
            normalizer: NordicNormalizer instance for text preparation
        """
        if not METAPHONE_AVAILABLE:
            raise ImportError(
                "metaphone library is required for phonetic matching. "
                "Install with: pip install metaphone"
            )
        
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
        self.normalizer = normalizer or NordicNormalizer()
        self._code_cache: Dict[str, Tuple[str, str]] = {}
    
    def update_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update matching thresholds."""
        self.thresholds.update(thresholds)
    
    def clear_cache(self) -> None:
        """Clear the phonetic code cache."""
        self._code_cache.clear()
    
    def get_phonetic_codes(self, name: str) -> Tuple[str, str]:
        """
        Get Double Metaphone codes for a name.
        
        Results are cached for performance.
        
        Args:
            name: The name to get codes for
            
        Returns:
            Tuple of (primary_code, secondary_code)
        """
        # Normalize before looking up
        normalized = self.normalizer.normalize(name)
        
        if normalized in self._code_cache:
            return self._code_cache[normalized]
        
        # Generate codes
        primary, secondary = doublemetaphone(normalized)
        
        # Cache the result
        self._code_cache[normalized] = (primary or '', secondary or '')
        
        return self._code_cache[normalized]
    
    def get_phonetic_codes_with_variants(
        self,
        name: str
    ) -> List[Tuple[str, str]]:
        """
        Get phonetic codes for all v/w variants of a name.
        
        Args:
            name: The name to get codes for
            
        Returns:
            List of (primary_code, secondary_code) tuples for all variants
        """
        variants = self.normalizer.generate_variants(name)
        codes = []
        
        for variant in variants:
            code = self.get_phonetic_codes(variant)
            if code not in codes:
                codes.append(code)
        
        return codes
    
    def determine_match_level(
        self,
        query_codes: Tuple[str, str],
        candidate_codes: Tuple[str, str]
    ) -> Tuple[Optional[str], float]:
        """
        Determine the match level between two sets of phonetic codes.
        
        Match hierarchy:
        1. Strong: Primary-to-Primary match
        2. Normal: Primary-to-Secondary or Secondary-to-Primary
        3. Weak: Secondary-to-Secondary match
        
        Args:
            query_codes: (primary, secondary) codes for query
            candidate_codes: (primary, secondary) codes for candidate
            
        Returns:
            Tuple of (match_level, confidence) or (None, 0.0) if no match
        """
        q_primary, q_secondary = query_codes
        c_primary, c_secondary = candidate_codes
        
        # Check for empty codes
        if not q_primary and not q_secondary:
            return None, 0.0
        if not c_primary and not c_secondary:
            return None, 0.0
        
        # Strong match: Primary-to-Primary
        if q_primary and c_primary and q_primary == c_primary:
            return 'strong', self.DEFAULT_CONFIDENCE['strong']
        
        # Normal match: Cross primary/secondary
        if q_primary and c_secondary and q_primary == c_secondary:
            return 'normal', self.DEFAULT_CONFIDENCE['normal']
        if q_secondary and c_primary and q_secondary == c_primary:
            return 'normal', self.DEFAULT_CONFIDENCE['normal']
        
        # Weak match: Secondary-to-Secondary
        if q_secondary and c_secondary and q_secondary == c_secondary:
            return 'weak', self.DEFAULT_CONFIDENCE['weak']
        
        return None, 0.0
    
    def match(
        self,
        query: str,
        candidates: List[str],
        include_variants: bool = True
    ) -> List[PhoneticMatchResult]:
        """
        Match a query against candidates using phonetic similarity.
        
        Args:
            query: The name to search for
            candidates: List of candidate names
            include_variants: If True, also check v/w variants
            
        Returns:
            List of PhoneticMatchResult for matches that pass thresholds,
            sorted by confidence descending
        """
        results = []
        
        # Get query codes (with variants if enabled)
        if include_variants:
            query_code_sets = self.get_phonetic_codes_with_variants(query)
        else:
            query_code_sets = [self.get_phonetic_codes(query)]
        
        for candidate in candidates:
            best_match = None
            best_confidence = 0.0
            best_codes = (('', ''), ('', ''))
            
            # Get candidate codes (with variants if enabled)
            if include_variants:
                candidate_code_sets = self.get_phonetic_codes_with_variants(
                    candidate
                )
            else:
                candidate_code_sets = [self.get_phonetic_codes(candidate)]
            
            # Compare all code combinations
            for query_codes in query_code_sets:
                for candidate_codes in candidate_code_sets:
                    match_level, confidence = self.determine_match_level(
                        query_codes, candidate_codes
                    )
                    
                    if match_level and confidence > best_confidence:
                        best_match = match_level
                        best_confidence = confidence
                        best_codes = (query_codes, candidate_codes)
            
            # Check against threshold
            if best_match:
                threshold_key = f'phonetic_{best_match}_min'
                threshold = self.thresholds.get(threshold_key, 0.0)
                
                if best_confidence >= threshold:
                    results.append(PhoneticMatchResult(
                        name=candidate,
                        confidence=best_confidence,
                        match_level=best_match,
                        query_codes=best_codes[0],
                        candidate_codes=best_codes[1]
                    ))
        
        # Sort by confidence descending
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results
    
    def are_phonetically_similar(
        self,
        name1: str,
        name2: str,
        min_level: str = 'weak'
    ) -> bool:
        """
        Quick check if two names are phonetically similar.
        
        Args:
            name1: First name
            name2: Second name
            min_level: Minimum match level ('strong', 'normal', 'weak')
            
        Returns:
            True if names are phonetically similar at or above min_level
        """
        level_order = {'strong': 3, 'normal': 2, 'weak': 1}
        min_order = level_order.get(min_level, 1)
        
        results = self.match(name1, [name2])
        
        if results:
            match_order = level_order.get(results[0].match_level, 0)
            return match_order >= min_order
        
        return False
    
    def get_similar_sounding_groups(
        self,
        names: List[str]
    ) -> List[List[str]]:
        """
        Group names by phonetic similarity.
        
        Useful for finding all names that might sound similar.
        
        Args:
            names: List of names to group
            
        Returns:
            List of groups where each group contains similar-sounding names
        """
        # Build mapping from primary codes to names
        code_to_names: Dict[str, List[str]] = {}
        
        for name in names:
            codes = self.get_phonetic_codes(name)
            primary = codes[0]
            
            if primary:
                if primary not in code_to_names:
                    code_to_names[primary] = []
                if name not in code_to_names[primary]:
                    code_to_names[primary].append(name)
        
        # Return groups with more than one name
        return [
            names_list 
            for names_list in code_to_names.values() 
            if len(names_list) > 1
        ]
    
    def explain_match(
        self,
        name1: str,
        name2: str
    ) -> Dict:
        """
        Provide detailed explanation of phonetic match between two names.
        
        Useful for debugging and understanding match decisions.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Dictionary with match details
        """
        codes1 = self.get_phonetic_codes(name1)
        codes2 = self.get_phonetic_codes(name2)
        
        match_level, confidence = self.determine_match_level(codes1, codes2)
        
        return {
            'name1': name1,
            'name2': name2,
            'name1_normalized': self.normalizer.normalize(name1),
            'name2_normalized': self.normalizer.normalize(name2),
            'name1_codes': {
                'primary': codes1[0],
                'secondary': codes1[1]
            },
            'name2_codes': {
                'primary': codes2[0],
                'secondary': codes2[1]
            },
            'match_level': match_level,
            'confidence': confidence,
            'passes_threshold': (
                confidence >= self.thresholds.get(
                    f'phonetic_{match_level}_min', 0.0
                )
                if match_level else False
            )
        }
