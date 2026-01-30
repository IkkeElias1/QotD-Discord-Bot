# -*- coding: utf-8 -*-
"""
String Similarity Algorithms Module.

Provides weighted hybrid scoring using RapidFuzz library for
accurate name matching with multiple algorithms.
"""

from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

from .normalization import NordicNormalizer


@dataclass
class SimilarityResult:
    """Result of a similarity calculation."""
    final_score: float
    individual_scores: Dict[str, float]
    query_normalized: str
    candidate_normalized: str


class StringSimilarity:
    """
    String similarity calculations using multiple algorithms.
    
    Combines Jaro-Winkler, Levenshtein, token sort, and token set ratios
    with configurable weights for optimal name matching.
    """
    
    DEFAULT_WEIGHTS = {
        'jaro_winkler': 0.35,
        'levenshtein': 0.25,
        'token_sort': 0.20,
        'token_set': 0.20,
    }
    
    DEFAULT_THRESHOLDS = {
        'jaro_winkler_min': 0.85,
        'levenshtein_min': 0.80,
        'token_set_min': 0.75,
        'token_sort_min': 0.80,
    }
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        thresholds: Optional[Dict[str, float]] = None,
        normalizer: Optional[NordicNormalizer] = None
    ) -> None:
        """
        Initialize the string similarity calculator.
        
        Args:
            weights: Custom weights for each algorithm (should sum to 1.0)
            thresholds: Minimum thresholds for each algorithm
            normalizer: NordicNormalizer instance for text normalization
        """
        if not RAPIDFUZZ_AVAILABLE:
            raise ImportError(
                "rapidfuzz library is required for string similarity. "
                "Install with: pip install rapidfuzz"
            )
        
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS.copy()
        self.normalizer = normalizer or NordicNormalizer()
        
        # Validate weights sum to approximately 1.0
        weight_sum = sum(self.weights.values())
        if not 0.99 <= weight_sum <= 1.01:
            # Normalize weights if they don't sum to 1
            for key in self.weights:
                self.weights[key] /= weight_sum
    
    def update_weights(self, weights: Dict[str, float]) -> None:
        """Update algorithm weights."""
        self.weights.update(weights)
        # Normalize
        weight_sum = sum(self.weights.values())
        if weight_sum > 0:
            for key in self.weights:
                self.weights[key] /= weight_sum
    
    def update_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update algorithm thresholds."""
        self.thresholds.update(thresholds)
    
    def calculate_individual_scores(
        self,
        name1: str,
        name2: str,
        pre_normalized: bool = False
    ) -> Dict[str, float]:
        """
        Calculate individual algorithm scores.
        
        Args:
            name1: First name to compare
            name2: Second name to compare
            pre_normalized: If True, skip normalization step
            
        Returns:
            Dictionary mapping algorithm names to scores (0.0 to 1.0)
        """
        if not pre_normalized:
            n1 = self.normalizer.normalize(name1)
            n2 = self.normalizer.normalize(name2)
        else:
            n1, n2 = name1, name2
        
        if not n1 or not n2:
            return {
                'jaro_winkler': 0.0,
                'levenshtein': 0.0,
                'token_sort': 0.0,
                'token_set': 0.0,
            }
        
        return {
            'jaro_winkler': fuzz.WRatio(n1, n2) / 100.0,
            'levenshtein': fuzz.ratio(n1, n2) / 100.0,
            'token_sort': fuzz.token_sort_ratio(n1, n2) / 100.0,
            'token_set': fuzz.token_set_ratio(n1, n2) / 100.0,
        }
    
    def calculate_hybrid_score(
        self,
        name1: str,
        name2: str,
        use_variants: bool = True
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate weighted hybrid similarity score.
        
        Combines multiple algorithms with configurable weights for
        optimal name matching accuracy.
        
        Args:
            name1: First name to compare
            name2: Second name to compare
            use_variants: If True, also check v/w variants
            
        Returns:
            Tuple of (final_weighted_score, individual_scores_dict)
        """
        # Normalize both names
        n1 = self.normalizer.normalize(name1)
        n2 = self.normalizer.normalize(name2)
        
        # Calculate base scores
        scores = self.calculate_individual_scores(n1, n2, pre_normalized=True)
        
        # If using variants and we have v or w, calculate variants and take max
        if use_variants and ('v' in n1 or 'w' in n1 or 'v' in n2 or 'w' in n2):
            n1_variants = self.normalizer.generate_variants(name1)
            n2_variants = self.normalizer.generate_variants(name2)
            
            for v1 in n1_variants:
                for v2 in n2_variants:
                    variant_scores = self.calculate_individual_scores(
                        v1, v2, pre_normalized=True
                    )
                    # Update scores if better
                    for key, value in variant_scores.items():
                        scores[key] = max(scores[key], value)
        
        # Calculate weighted final score
        final_score = sum(
            scores[algo] * weight
            for algo, weight in self.weights.items()
            if algo in scores
        )
        
        return final_score, scores
    
    def passes_threshold(
        self,
        scores: Dict[str, float],
        mode: str = 'any'
    ) -> bool:
        """
        Check if scores pass the configured thresholds.
        
        Args:
            scores: Dictionary of algorithm scores
            mode: 'any' (at least one passes), 'all' (all must pass),
                  or 'weighted' (weighted average passes)
                  
        Returns:
            True if thresholds are met according to the mode
        """
        if mode == 'any':
            for algo, score in scores.items():
                threshold_key = f'{algo}_min'
                if threshold_key in self.thresholds:
                    if score >= self.thresholds[threshold_key]:
                        return True
            return False
        
        elif mode == 'all':
            for algo, score in scores.items():
                threshold_key = f'{algo}_min'
                if threshold_key in self.thresholds:
                    if score < self.thresholds[threshold_key]:
                        return False
            return True
        
        elif mode == 'weighted':
            weighted_score = sum(
                scores[algo] * self.weights.get(algo, 0.25)
                for algo in scores
            )
            # Use average of thresholds as the weighted threshold
            avg_threshold = sum(self.thresholds.values()) / len(self.thresholds)
            return weighted_score >= avg_threshold
        
        return False
    
    def find_best_matches(
        self,
        query: str,
        candidates: List[str],
        limit: int = 5,
        score_cutoff: float = 0.0
    ) -> List[Tuple[str, float, Dict[str, float]]]:
        """
        Find the best matching candidates for a query.
        
        Args:
            query: The name to search for
            candidates: List of candidate names
            limit: Maximum number of results to return
            score_cutoff: Minimum score threshold
            
        Returns:
            List of (candidate, final_score, individual_scores) tuples,
            sorted by score descending
        """
        results = []
        
        for candidate in candidates:
            final_score, individual_scores = self.calculate_hybrid_score(
                query, candidate
            )
            
            if final_score >= score_cutoff:
                results.append((candidate, final_score, individual_scores))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:limit]
    
    def quick_ratio(self, name1: str, name2: str) -> float:
        """
        Quick similarity check using just WRatio.
        
        Useful for blocking/filtering before full calculation.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        n1 = self.normalizer.normalize(name1)
        n2 = self.normalizer.normalize(name2)
        return fuzz.WRatio(n1, n2) / 100.0


def calculate_hybrid_score(
    name1: str,
    name2: str,
    weights: Optional[Dict[str, float]] = None,
    normalizer: Optional[NordicNormalizer] = None
) -> Tuple[float, Dict[str, float]]:
    """
    Convenience function for calculating hybrid similarity score.
    
    Creates a temporary StringSimilarity instance if needed.
    
    Args:
        name1: First name to compare
        name2: Second name to compare
        weights: Optional custom weights
        normalizer: Optional NordicNormalizer instance
        
    Returns:
        Tuple of (final_weighted_score, individual_scores_dict)
    """
    similarity = StringSimilarity(weights=weights, normalizer=normalizer)
    return similarity.calculate_hybrid_score(name1, name2)
