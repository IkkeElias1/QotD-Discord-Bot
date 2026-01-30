# -*- coding: utf-8 -*-
"""
Core NameMatcher Module.

Main class for nickname resolution with multi-algorithm matching
using a cascading fallback strategy.
"""

from typing import List, Dict, Tuple, Optional, Union, Any
from dataclasses import dataclass, field
import os

from .normalization import NordicNormalizer
from .algorithms import StringSimilarity
from .phonetic import PhoneticMatcher, PhoneticMatchResult
from .blocking import BlockingStrategy
from .dictionaries import NicknameDictionary
from .config_manager import ConfigManager
from .debug import DebugLogger


@dataclass
class MatchResult:
    """Result of a name matching operation."""
    name: str
    confidence: float
    match_type: str
    algorithm_scores: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None
    person_id: Optional[str] = None
    
    def to_tuple(self) -> Tuple[str, float, Dict]:
        """Convert to tuple format (name, score, debug_info)."""
        return (
            self.name,
            self.confidence,
            {
                'match_type': self.match_type,
                'algorithm_scores': self.algorithm_scores,
                'notes': self.notes,
                'person_id': self.person_id,
            }
        )


class NameMatcher:
    """
    Main class for nickname resolution with multi-algorithm matching.
    
    Implements a cascading fallback strategy that tries multiple
    matching approaches in order of reliability:
    
    1. Exact match (case-insensitive)
    2. Custom alias lookup (manual_overrides)
    3. Discord ID resolution
    4. Fuzzy string matching (if enabled)
    5. Phonetic matching (if enabled)
    6. Standard nickname dictionary (if enabled)
    
    Configuration is hot-reloadable for tuning without restart.
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        aliases_path: Optional[str] = None
    ) -> None:
        """
        Initialize the name matcher with configuration.
        
        Args:
            config_path: Path to matching_config.json
            aliases_path: Path to aliases.json (new enhanced format)
        """
        # Initialize configuration manager
        self._config_manager = ConfigManager(
            config_path=config_path,
            aliases_path=aliases_path
        )
        
        # Initialize components
        self._normalizer = NordicNormalizer()
        self._string_sim: Optional[StringSimilarity] = None
        self._phonetic: Optional[PhoneticMatcher] = None
        self._blocking: Optional[BlockingStrategy] = None
        self._nicknames: Optional[NicknameDictionary] = None
        self._debug_logger = DebugLogger(
            enabled=self._config_manager.debug_mode,
            thresholds=self._config_manager.thresholds
        )
        
        # Initialize enabled components
        self._init_components()
    
    def _init_components(self) -> None:
        """Initialize matching components based on configuration."""
        config = self._config_manager.config
        
        # String similarity
        try:
            self._string_sim = StringSimilarity(
                weights=config.weights,
                thresholds=config.thresholds,
                normalizer=self._normalizer
            )
        except ImportError:
            self._string_sim = None
        
        # Phonetic matcher
        try:
            self._phonetic = PhoneticMatcher(
                thresholds=config.thresholds,
                normalizer=self._normalizer
            )
        except ImportError:
            self._phonetic = None
        
        # Blocking strategy
        self._blocking = BlockingStrategy(
            strategy=config.blocking_strategy,
            normalizer=self._normalizer
        )
        
        # Nickname dictionary
        self._nicknames = NicknameDictionary(use_library=True)
        
        # Update debug logger
        self._debug_logger.set_thresholds(config.thresholds)
        self._debug_logger.set_enabled(config.debug_mode)
    
    @property
    def config(self) -> Dict[str, Any]:
        """Get current configuration as dictionary."""
        cfg = self._config_manager.config
        return {
            'matching_layers': cfg.matching_layers,
            'thresholds': cfg.thresholds,
            'weights': cfg.weights,
            'blocking_strategy': cfg.blocking_strategy,
            'debug_mode': cfg.debug_mode,
        }
    
    @property
    def manual_overrides(self) -> Dict[str, Dict]:
        """Get manual override mappings."""
        return self._config_manager.manual_overrides
    
    @property
    def discord_id_map(self) -> Dict[str, str]:
        """Get Discord ID to name mappings."""
        return self._config_manager.discord_id_to_name
    
    @property
    def normalizer(self) -> NordicNormalizer:
        """Get the normalizer instance."""
        return self._normalizer
    
    def reload_config(self) -> bool:
        """
        Hot-reload configuration without restart.
        
        Returns:
            True if reload was successful
        """
        success = self._config_manager.reload()
        self._init_components()
        return success
    
    def match(
        self,
        query: str,
        candidates: List[str],
        return_scores: bool = False,
        debug: bool = False
    ) -> Union[List[str], List[Tuple[str, float, Dict]]]:
        """
        Match query against candidates using cascading strategy.
        
        Args:
            query: Name to search for
            candidates: List of canonical names to match against
            return_scores: If True, return (name, score, debug_info) tuples
            debug: Enable debug logging for this call
            
        Returns:
            List of matching names, optionally with scores and debug info
        """
        if not query or not candidates:
            return []
        
        # Temporarily enable debug if requested
        original_debug = self._debug_logger.enabled
        if debug:
            self._debug_logger.set_enabled(True)
        
        try:
            self._debug_logger.start_match(query)
            
            # Run cascade matching
            results = self._match_cascade(query, candidates)
            
            self._debug_logger.end_match(results)
            
            if return_scores:
                return [r.to_tuple() for r in results]
            else:
                return [r.name for r in results]
                
        finally:
            # Restore original debug setting
            self._debug_logger.set_enabled(original_debug)
    
    def _match_cascade(
        self,
        query: str,
        candidates: List[str]
    ) -> List[MatchResult]:
        """
        Cascading matching strategy with fallbacks.
        
        Order of operations:
        1. Exact match (case-insensitive)
        2. Custom alias lookup (manual_overrides)
        3. Discord ID resolution
        4. Fuzzy string matching (if enabled)
        5. Phonetic matching (if enabled)
        6. Standard nickname dictionary (if enabled)
        """
        config = self._config_manager.config
        cascade_steps = []
        step_num = 0
        
        # Step 1: Exact match
        step_num += 1
        exact_results = self._exact_match(query, candidates)
        if exact_results:
            self._debug_logger.log_cascade_step(
                step_num, "Exact Match", True,
                len(exact_results), "Found exact match"
            )
            cascade_steps.append("Exact Match ✓")
            return exact_results
        self._debug_logger.log_cascade_step(
            step_num, "Exact Match", True, 0, "No exact match"
        )
        cascade_steps.append("Exact Match ✗")
        
        # Step 2: Check manual overrides
        step_num += 1
        if config.matching_layers.get('custom_aliases', True):
            override_results = self._check_manual_overrides(query, candidates)
            if override_results:
                self._debug_logger.log_cascade_step(
                    step_num, "Manual Overrides", True,
                    len(override_results), "Found in manual overrides"
                )
                cascade_steps.append("Manual Overrides ✓")
                return override_results
            self._debug_logger.log_cascade_step(
                step_num, "Manual Overrides", True, 0, "Not in overrides"
            )
            cascade_steps.append("Manual Overrides ✗")
        else:
            self._debug_logger.log_cascade_step(
                step_num, "Manual Overrides", False, 0, "Layer disabled"
            )
        
        # Step 3: Discord ID resolution
        step_num += 1
        discord_results = self._check_discord_id(query, candidates)
        if discord_results:
            self._debug_logger.log_cascade_step(
                step_num, "Discord ID", True,
                len(discord_results), "Found Discord mapping"
            )
            cascade_steps.append("Discord ID ✓")
            return discord_results
        self._debug_logger.log_cascade_step(
            step_num, "Discord ID", True, 0, "No Discord mapping"
        )
        cascade_steps.append("Discord ID ✗")
        
        # Step 4: Check name aliases from config
        step_num += 1
        if config.matching_layers.get('custom_aliases', True):
            alias_results = self._check_name_aliases(query, candidates)
            if alias_results:
                self._debug_logger.log_cascade_step(
                    step_num, "Name Aliases", True,
                    len(alias_results), "Found in name aliases"
                )
                cascade_steps.append("Name Aliases ✓")
                return alias_results
            self._debug_logger.log_cascade_step(
                step_num, "Name Aliases", True, 0, "Not in aliases"
            )
            cascade_steps.append("Name Aliases ✗")
        
        # Apply blocking before expensive comparisons
        if self._blocking:
            blocked_candidates = self._blocking.get_comparison_candidates(
                query, candidates
            )
            stats = self._blocking.get_blocking_stats(query, candidates)
            self._debug_logger.log_blocking_info(
                query,
                stats['total_candidates'],
                stats['blocked_candidates'],
                stats['query_blocks']
            )
        else:
            blocked_candidates = candidates
        
        # Step 5: Fuzzy string matching (if enabled)
        step_num += 1
        if config.matching_layers.get('fuzzy_string', True):
            if self._string_sim:
                fuzzy_results = self._fuzzy_match(query, blocked_candidates)
                if fuzzy_results:
                    self._debug_logger.log_cascade_step(
                        step_num, "Fuzzy String", True,
                        len(fuzzy_results), "Found fuzzy matches"
                    )
                    cascade_steps.append("Fuzzy String ✓")
                    return fuzzy_results
                self._debug_logger.log_cascade_step(
                    step_num, "Fuzzy String", True, 0, "No matches above threshold"
                )
                cascade_steps.append("Fuzzy String ✗")
            else:
                self._debug_logger.log_cascade_step(
                    step_num, "Fuzzy String", False, 0, "RapidFuzz not available"
                )
        else:
            self._debug_logger.log_cascade_step(
                step_num, "Fuzzy String", False, 0, "Layer disabled"
            )
        
        # Step 6: Phonetic matching (if enabled)
        step_num += 1
        if config.matching_layers.get('phonetic', True):
            if self._phonetic:
                phonetic_results = self._phonetic_match(query, blocked_candidates)
                if phonetic_results:
                    self._debug_logger.log_cascade_step(
                        step_num, "Phonetic", True,
                        len(phonetic_results), "Found phonetic matches"
                    )
                    cascade_steps.append("Phonetic ✓")
                    return phonetic_results
                self._debug_logger.log_cascade_step(
                    step_num, "Phonetic", True, 0, "No phonetic matches"
                )
                cascade_steps.append("Phonetic ✗")
            else:
                self._debug_logger.log_cascade_step(
                    step_num, "Phonetic", False, 0, "Metaphone not available"
                )
        else:
            self._debug_logger.log_cascade_step(
                step_num, "Phonetic", False, 0, "Layer disabled"
            )
        
        # Step 7: Standard nickname dictionary (if enabled)
        step_num += 1
        if config.matching_layers.get('standard_nicknames', False):
            if self._nicknames:
                nickname_results = self._nickname_match(query, blocked_candidates)
                if nickname_results:
                    self._debug_logger.log_cascade_step(
                        step_num, "Nickname Dictionary", True,
                        len(nickname_results), "Found in nickname dictionary"
                    )
                    cascade_steps.append("Nickname Dictionary ✓")
                    return nickname_results
                self._debug_logger.log_cascade_step(
                    step_num, "Nickname Dictionary", True, 0, "No nickname matches"
                )
                cascade_steps.append("Nickname Dictionary ✗")
        else:
            self._debug_logger.log_cascade_step(
                step_num, "Nickname Dictionary", False, 0, "Layer disabled"
            )
        
        # Log cascade path
        self._debug_logger.log_cascade_path(cascade_steps)
        
        return []  # No matches found
    
    def _exact_match(
        self,
        query: str,
        candidates: List[str]
    ) -> List[MatchResult]:
        """Check for exact match (case-insensitive, normalized)."""
        normalized_query = self._normalizer.normalize(query)
        query_variants = self._normalizer.generate_variants(query)
        
        self._debug_logger.log_normalization(
            query, normalized_query, query_variants
        )
        
        for candidate in candidates:
            normalized_candidate = self._normalizer.normalize(candidate)
            candidate_variants = self._normalizer.generate_variants(candidate)
            
            # Check all variant combinations
            for q_var in query_variants:
                for c_var in candidate_variants:
                    if q_var == c_var:
                        self._debug_logger.log_match_attempt(
                            query, candidate, {},
                            True, "Exact match (normalized)",
                            "exact"
                        )
                        return [MatchResult(
                            name=candidate,
                            confidence=1.0,
                            match_type="exact",
                            algorithm_scores={}
                        )]
        
        return []
    
    def _check_manual_overrides(
        self,
        query: str,
        candidates: List[str]
    ) -> List[MatchResult]:
        """Check manual override mappings."""
        query_lower = query.lower().strip()
        overrides = self._config_manager.manual_overrides
        
        if query_lower in overrides:
            override = overrides[query_lower]
            canonical = override['canonical_name']
            
            self._debug_logger.log_alias_lookup(
                query, True, canonical, "manual_overrides"
            )
            
            # Find the candidate that matches the canonical name
            normalized_canonical = self._normalizer.normalize(canonical)
            for candidate in candidates:
                if self._normalizer.normalize(candidate) == normalized_canonical:
                    return [MatchResult(
                        name=candidate,
                        confidence=override.get('confidence', 1.0),
                        match_type=override.get('match_type', 'manual_override'),
                        algorithm_scores={},
                        notes=override.get('notes')
                    )]
            
            # If canonical name not in candidates, return it anyway
            return [MatchResult(
                name=canonical,
                confidence=override.get('confidence', 1.0),
                match_type=override.get('match_type', 'manual_override'),
                algorithm_scores={},
                notes=override.get('notes')
            )]
        
        self._debug_logger.log_alias_lookup(query, False)
        return []
    
    def _check_discord_id(
        self,
        query: str,
        candidates: List[str]
    ) -> List[MatchResult]:
        """Check Discord ID to name mapping."""
        # Check if query looks like a Discord ID or mention
        discord_id = None
        
        # Raw ID
        if query.isdigit() and len(query) > 15:
            discord_id = query
        
        # Mention format <@123> or <@!123>
        elif query.startswith('<@') and query.endswith('>'):
            discord_id = query.strip('<@!>')
        
        if discord_id:
            id_map = self._config_manager.discord_id_to_name
            
            if discord_id in id_map:
                name = id_map[discord_id]
                self._debug_logger.log_discord_lookup(discord_id, True, name)
                
                # Find matching candidate
                normalized_name = self._normalizer.normalize(name)
                for candidate in candidates:
                    if self._normalizer.normalize(candidate) == normalized_name:
                        return [MatchResult(
                            name=candidate,
                            confidence=1.0,
                            match_type="discord_id",
                            algorithm_scores={}
                        )]
                
                # Return the mapped name even if not in candidates
                return [MatchResult(
                    name=name,
                    confidence=1.0,
                    match_type="discord_id",
                    algorithm_scores={}
                )]
            
            self._debug_logger.log_discord_lookup(discord_id, False)
        
        return []
    
    def _check_name_aliases(
        self,
        query: str,
        candidates: List[str]
    ) -> List[MatchResult]:
        """Check name_aliases configuration."""
        query_lower = self._normalizer.normalize(query)
        name_aliases = self._config_manager.name_aliases
        
        # Check if query is an alias for any canonical name
        for canonical, aliases in name_aliases.items():
            normalized_aliases = [self._normalizer.normalize(a) for a in aliases]
            if query_lower in normalized_aliases or query_lower == self._normalizer.normalize(canonical):
                # Find matching candidate
                normalized_canonical = self._normalizer.normalize(canonical)
                for candidate in candidates:
                    if self._normalizer.normalize(candidate) == normalized_canonical:
                        self._debug_logger.log_alias_lookup(
                            query, True, canonical, "name_aliases"
                        )
                        return [MatchResult(
                            name=candidate,
                            confidence=0.95,
                            match_type="name_alias",
                            algorithm_scores={}
                        )]
                
                # Check if canonical is in candidates (partial match)
                for candidate in candidates:
                    cand_norm = self._normalizer.normalize(candidate)
                    if normalized_canonical in cand_norm or cand_norm in normalized_canonical:
                        self._debug_logger.log_alias_lookup(
                            query, True, candidate, "name_aliases"
                        )
                        return [MatchResult(
                            name=candidate,
                            confidence=0.90,
                            match_type="name_alias_partial",
                            algorithm_scores={}
                        )]
        
        # Also check cluster_map
        cluster_map = self._config_manager.cluster_map
        for person_id, cluster_data in cluster_map.items():
            aliases = cluster_data.get('aliases', [])
            normalized_aliases = [self._normalizer.normalize(a) for a in aliases]
            
            if query_lower in normalized_aliases:
                canonical = cluster_data.get('canonical_name', '')
                if not canonical:
                    continue
                normalized_canonical = self._normalizer.normalize(canonical)
                
                for candidate in candidates:
                    if self._normalizer.normalize(candidate) == normalized_canonical:
                        self._debug_logger.log_alias_lookup(
                            query, True, canonical, f"cluster_map ({person_id})"
                        )
                        return [MatchResult(
                            name=candidate,
                            confidence=0.95,
                            match_type="cluster_alias",
                            algorithm_scores={},
                            person_id=person_id
                        )]
        
        return []
    
    def _fuzzy_match(
        self,
        query: str,
        candidates: List[str]
    ) -> List[MatchResult]:
        """Perform fuzzy string matching."""
        if not self._string_sim:
            return []
        
        config = self._config_manager.config
        min_threshold = config.thresholds.get('hybrid_min', 0.75)
        
        results = []
        
        for candidate in candidates:
            final_score, individual_scores = self._string_sim.calculate_hybrid_score(
                query, candidate, use_variants=True
            )
            
            passes = final_score >= min_threshold
            
            self._debug_logger.log_match_attempt(
                query, candidate, individual_scores,
                passes,
                f"Hybrid score: {final_score:.3f}",
                "fuzzy_string"
            )
            
            if passes:
                results.append(MatchResult(
                    name=candidate,
                    confidence=final_score,
                    match_type="fuzzy_string",
                    algorithm_scores=individual_scores
                ))
        
        # Sort by confidence descending
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results
    
    def _phonetic_match(
        self,
        query: str,
        candidates: List[str]
    ) -> List[MatchResult]:
        """Perform phonetic matching."""
        if not self._phonetic:
            return []
        
        phonetic_results = self._phonetic.match(
            query, candidates, include_variants=True
        )
        
        results = []
        for pr in phonetic_results:
            self._debug_logger.log_match_attempt(
                query, pr.name,
                {
                    'phonetic_level': pr.match_level,
                    'confidence': pr.confidence
                },
                True,
                f"Phonetic {pr.match_level} match",
                "phonetic"
            )
            
            results.append(MatchResult(
                name=pr.name,
                confidence=pr.confidence,
                match_type=f"phonetic_{pr.match_level}",
                algorithm_scores={
                    'query_codes': pr.query_codes,
                    'candidate_codes': pr.candidate_codes
                }
            ))
        
        return results
    
    def _nickname_match(
        self,
        query: str,
        candidates: List[str]
    ) -> List[MatchResult]:
        """Match using standard nickname dictionary."""
        if not self._nicknames:
            return []
        
        matches = self._nicknames.find_matches(query, candidates)
        
        results = []
        for match in matches:
            self._debug_logger.log_match_attempt(
                query, match, {},
                True, "Nickname dictionary match",
                "nickname_dictionary"
            )
            
            results.append(MatchResult(
                name=match,
                confidence=0.80,
                match_type="nickname_dictionary",
                algorithm_scores={}
            ))
        
        return results
    
    def find_person_id(self, name: str) -> Optional[str]:
        """
        Find which Person_ID this name belongs to.
        
        Args:
            name: Name to look up
            
        Returns:
            Person ID string or None if not found
        """
        normalized = self._normalizer.normalize(name)
        cluster_map = self._config_manager.cluster_map
        
        for person_id, cluster_data in cluster_map.items():
            aliases = cluster_data.get('aliases', [])
            normalized_aliases = [self._normalizer.normalize(a) for a in aliases]
            
            if normalized in normalized_aliases:
                return person_id
        
        return None
    
    def get_all_aliases(self, canonical_name: str) -> List[str]:
        """
        Get all known aliases for a canonical name.
        
        Args:
            canonical_name: The canonical name to look up
            
        Returns:
            List of all known aliases
        """
        normalized = self._normalizer.normalize(canonical_name)
        aliases = set()
        
        # Check name_aliases
        name_aliases = self._config_manager.name_aliases
        if normalized in name_aliases or canonical_name.lower() in name_aliases:
            key = normalized if normalized in name_aliases else canonical_name.lower()
            aliases.update(name_aliases[key])
        
        # Check cluster_map
        cluster_map = self._config_manager.cluster_map
        for cluster_data in cluster_map.values():
            if self._normalizer.normalize(cluster_data.get('canonical_name', '')) == normalized:
                aliases.update(cluster_data.get('aliases', []))
        
        # Check manual_overrides (reverse lookup)
        for alias, override in self._config_manager.manual_overrides.items():
            if self._normalizer.normalize(override.get('canonical_name', '')) == normalized:
                aliases.add(alias)
        
        return list(aliases)
    
    def get_canonical_name(self, name: str) -> Optional[str]:
        """
        Get the canonical name for any alias.
        
        Args:
            name: Name or alias to look up
            
        Returns:
            Canonical name or None if not found
        """
        # Check manual overrides first
        if name.lower() in self._config_manager.manual_overrides:
            return self._config_manager.manual_overrides[name.lower()]['canonical_name']
        
        # Check cluster_map
        normalized = self._normalizer.normalize(name)
        cluster_map = self._config_manager.cluster_map
        
        for cluster_data in cluster_map.values():
            aliases = cluster_data.get('aliases', [])
            normalized_aliases = [self._normalizer.normalize(a) for a in aliases]
            
            if normalized in normalized_aliases:
                return cluster_data.get('canonical_name')
        
        return None
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current configuration.
        
        Returns:
            Dictionary with configuration summary
        """
        return self._config_manager.get_config_summary()
    
    def get_debug_output(self) -> str:
        """
        Get formatted debug output from last match.
        
        Returns:
            Formatted debug string
        """
        return self._debug_logger.format_debug_output()
