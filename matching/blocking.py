# -*- coding: utf-8 -*-
"""
Blocking Strategy Module.

Implements multi-level blocking to reduce comparison space
and avoid O(n²) comparisons for efficient name matching.
"""

from typing import List, Dict, Set, Optional
from collections import defaultdict

try:
    from metaphone import doublemetaphone
    METAPHONE_AVAILABLE = True
except ImportError:
    METAPHONE_AVAILABLE = False

from .normalization import NordicNormalizer


class BlockingStrategy:
    """
    Implement blocking strategies to reduce comparison space.
    
    Blocking groups similar names into "blocks" so that only names
    within the same block need to be compared, dramatically reducing
    the number of comparisons needed.
    
    Strategies:
    - 'none': No blocking, compare all pairs
    - 'character': Block by first N characters
    - 'phonetic': Block by phonetic code
    - 'multi_level': Combine character, phonetic, and token blocking
    """
    
    VALID_STRATEGIES = {'none', 'character', 'phonetic', 'multi_level'}
    
    def __init__(
        self,
        strategy: str = 'multi_level',
        char_prefix_length: int = 3,
        normalizer: Optional[NordicNormalizer] = None
    ) -> None:
        """
        Initialize the blocking strategy.
        
        Args:
            strategy: Blocking strategy to use
            char_prefix_length: Number of characters for character blocking
            normalizer: NordicNormalizer instance
        """
        if strategy not in self.VALID_STRATEGIES:
            raise ValueError(
                f"Invalid strategy: {strategy}. "
                f"Valid options: {self.VALID_STRATEGIES}"
            )
        
        self.strategy = strategy
        self.char_prefix_length = char_prefix_length
        self.normalizer = normalizer or NordicNormalizer()
        self._block_cache: Dict[str, Dict[str, List[str]]] = {}
    
    def clear_cache(self) -> None:
        """Clear the block cache."""
        self._block_cache.clear()
    
    def _get_char_blocks(self, name: str) -> List[str]:
        """Get character-based block keys for a name."""
        normalized = self.normalizer.normalize(name)
        if not normalized:
            return []
        
        keys = []
        # Primary: first N characters
        prefix = normalized[:self.char_prefix_length]
        if len(prefix) >= 2:
            keys.append(f"char_{prefix}")
        
        # Also add v/w variants
        if 'v' in prefix:
            keys.append(f"char_{prefix.replace('v', 'w')}")
        if 'w' in prefix:
            keys.append(f"char_{prefix.replace('w', 'v')}")
        
        return keys
    
    def _get_phonetic_blocks(self, name: str) -> List[str]:
        """Get phonetic-based block keys for a name."""
        if not METAPHONE_AVAILABLE:
            return []
        
        normalized = self.normalizer.normalize(name)
        if not normalized:
            return []
        
        keys = []
        
        # Get codes for main name
        primary, secondary = doublemetaphone(normalized)
        if primary:
            keys.append(f"phon_{primary}")
        if secondary:
            keys.append(f"phon_{secondary}")
        
        # Get codes for v/w variants
        variants = self.normalizer.generate_variants(name)
        for variant in variants:
            if variant != normalized:
                p, s = doublemetaphone(variant)
                if p and f"phon_{p}" not in keys:
                    keys.append(f"phon_{p}")
                if s and f"phon_{s}" not in keys:
                    keys.append(f"phon_{s}")
        
        return keys
    
    def _get_token_blocks(self, name: str) -> List[str]:
        """Get token-based block keys for multi-word names."""
        normalized = self.normalizer.normalize(name)
        if not normalized:
            return []
        
        keys = []
        tokens = normalized.split()
        
        for token in tokens:
            if len(token) >= 3:  # Skip very short tokens
                keys.append(f"token_{token}")
                
                # Add v/w variants
                if 'v' in token:
                    keys.append(f"token_{token.replace('v', 'w')}")
                if 'w' in token:
                    keys.append(f"token_{token.replace('w', 'v')}")
        
        return keys
    
    def get_block_keys(self, name: str) -> List[str]:
        """
        Get all block keys for a name based on the strategy.
        
        Args:
            name: The name to get block keys for
            
        Returns:
            List of block keys this name belongs to
        """
        if self.strategy == 'none':
            return ['all']
        
        keys = []
        
        if self.strategy in ('character', 'multi_level'):
            keys.extend(self._get_char_blocks(name))
        
        if self.strategy in ('phonetic', 'multi_level'):
            keys.extend(self._get_phonetic_blocks(name))
        
        if self.strategy == 'multi_level':
            keys.extend(self._get_token_blocks(name))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keys = []
        for key in keys:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)
        
        return unique_keys if unique_keys else ['all']
    
    def create_blocks(
        self,
        names: List[str]
    ) -> Dict[str, List[str]]:
        """
        Group names into blocks for efficient comparison.
        
        Args:
            names: List of names to group
            
        Returns:
            Dictionary mapping block_key -> list of names in that block
        """
        # Create cache key from sorted names
        cache_key = hash(tuple(sorted(names)))
        
        if cache_key in self._block_cache:
            return self._block_cache[cache_key]
        
        if self.strategy == 'none':
            result = {'all': list(names)}
            self._block_cache[cache_key] = result
            return result
        
        blocks: Dict[str, List[str]] = defaultdict(list)
        
        for name in names:
            block_keys = self.get_block_keys(name)
            for key in block_keys:
                if name not in blocks[key]:
                    blocks[key].append(name)
        
        result = dict(blocks)
        self._block_cache[cache_key] = result
        return result
    
    def get_comparison_candidates(
        self,
        query: str,
        all_candidates: List[str]
    ) -> List[str]:
        """
        Get subset of candidates that should be compared with query.
        
        This is the main method to use for filtering candidates before
        detailed comparison.
        
        Args:
            query: The query name
            all_candidates: All possible candidate names
            
        Returns:
            Filtered list of candidates that share blocks with query
        """
        if self.strategy == 'none':
            return list(all_candidates)
        
        # Create blocks for all candidates
        blocks = self.create_blocks(all_candidates)
        
        # Find which blocks the query belongs to
        query_blocks = set(self.get_block_keys(query))
        
        # Collect all candidates from relevant blocks
        candidates_set: Set[str] = set()
        
        for block_key in query_blocks:
            if block_key in blocks:
                candidates_set.update(blocks[block_key])
        
        # If no candidates found through blocking, fall back to all
        if not candidates_set:
            return list(all_candidates)
        
        return list(candidates_set)
    
    def get_blocking_stats(
        self,
        query: str,
        all_candidates: List[str]
    ) -> Dict:
        """
        Get statistics about blocking effectiveness.
        
        Useful for debugging and tuning blocking parameters.
        
        Args:
            query: The query name
            all_candidates: All possible candidate names
            
        Returns:
            Dictionary with blocking statistics
        """
        total = len(all_candidates)
        
        if self.strategy == 'none':
            return {
                'strategy': self.strategy,
                'total_candidates': total,
                'blocked_candidates': total,
                'reduction_percent': 0.0,
                'query_blocks': ['all'],
            }
        
        blocked_candidates = self.get_comparison_candidates(
            query, all_candidates
        )
        blocked_count = len(blocked_candidates)
        query_blocks = self.get_block_keys(query)
        
        reduction = ((total - blocked_count) / total * 100) if total > 0 else 0
        
        return {
            'strategy': self.strategy,
            'total_candidates': total,
            'blocked_candidates': blocked_count,
            'reduction_percent': round(reduction, 1),
            'query_blocks': query_blocks,
        }
    
    def explain_blocking(
        self,
        query: str,
        candidate: str
    ) -> Dict:
        """
        Explain why a query and candidate would (or wouldn't) be compared.
        
        Args:
            query: The query name
            candidate: The candidate name
            
        Returns:
            Dictionary explaining the blocking decision
        """
        query_blocks = set(self.get_block_keys(query))
        candidate_blocks = set(self.get_block_keys(candidate))
        
        shared_blocks = query_blocks & candidate_blocks
        
        return {
            'query': query,
            'candidate': candidate,
            'query_blocks': list(query_blocks),
            'candidate_blocks': list(candidate_blocks),
            'shared_blocks': list(shared_blocks),
            'would_compare': bool(shared_blocks) or self.strategy == 'none',
        }
