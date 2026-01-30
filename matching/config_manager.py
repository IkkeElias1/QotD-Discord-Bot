# -*- coding: utf-8 -*-
"""
Configuration Manager Module.

Handles loading, validation, and hot-reloading of matching configuration.
"""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import threading
from datetime import datetime


@dataclass
class MatchingConfig:
    """Matching configuration data structure."""
    matching_layers: Dict[str, bool] = field(default_factory=lambda: {
        'fuzzy_string': True,
        'phonetic': True,
        'standard_nicknames': False,
        'custom_aliases': True,
    })
    thresholds: Dict[str, float] = field(default_factory=lambda: {
        'jaro_winkler_min': 0.85,
        'levenshtein_min': 0.80,
        'token_set_min': 0.75,
        'token_sort_min': 0.80,
        'phonetic_primary_min': 0.95,
        'phonetic_normal_min': 0.85,
        'phonetic_weak_min': 0.70,
    })
    weights: Dict[str, float] = field(default_factory=lambda: {
        'jaro_winkler': 0.35,
        'levenshtein': 0.25,
        'token_sort': 0.20,
        'token_set': 0.20,
    })
    blocking_strategy: str = 'multi_level'
    debug_mode: bool = False
    llm_validation: Dict[str, Any] = field(default_factory=lambda: {
        'enabled': False,
        'ambiguity_range': [0.60, 0.80],
        'provider': None,
    })


@dataclass 
class AliasConfig:
    """Alias configuration data structure."""
    manual_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    name_aliases: Dict[str, list] = field(default_factory=dict)
    discord_id_to_name: Dict[str, str] = field(default_factory=dict)
    cluster_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class ConfigManager:
    """
    Manage matching configuration with hot-reloading support.
    
    Provides centralized configuration management with validation,
    default values, and thread-safe hot-reloading capabilities.
    """
    
    DEFAULT_CONFIG_PATH = 'config/matching_config.json'
    DEFAULT_ALIASES_PATH = 'config/aliases.json'
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        aliases_path: Optional[str] = None,
        auto_reload: bool = False
    ) -> None:
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to matching_config.json
            aliases_path: Path to aliases.json
            auto_reload: Enable automatic file watching (not implemented)
        """
        # Determine base directory (project root)
        self._base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self._config_path = config_path or os.path.join(
            self._base_dir, self.DEFAULT_CONFIG_PATH
        )
        self._aliases_path = aliases_path or os.path.join(
            self._base_dir, self.DEFAULT_ALIASES_PATH
        )
        
        self._lock = threading.RLock()
        self._config: MatchingConfig = MatchingConfig()
        self._aliases: AliasConfig = AliasConfig()
        self._last_loaded: Optional[datetime] = None
        self._load_errors: list = []
        
        # Load configuration
        self.reload()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration dictionary."""
        return {
            'matching_layers': {
                'fuzzy_string': True,
                'phonetic': True,
                'standard_nicknames': False,
                'custom_aliases': True,
            },
            'thresholds': {
                'jaro_winkler_min': 0.85,
                'levenshtein_min': 0.80,
                'token_set_min': 0.75,
                'token_sort_min': 0.80,
                'phonetic_primary_min': 0.95,
                'phonetic_normal_min': 0.85,
                'phonetic_weak_min': 0.70,
            },
            'weights': {
                'jaro_winkler': 0.35,
                'levenshtein': 0.25,
                'token_sort': 0.20,
                'token_set': 0.20,
            },
            'blocking_strategy': 'multi_level',
            'debug_mode': False,
            'llm_validation': {
                'enabled': False,
                'ambiguity_range': [0.60, 0.80],
                'provider': None,
            }
        }
    
    def _get_default_aliases(self) -> Dict[str, Any]:
        """Get default aliases dictionary."""
        return {
            'manual_overrides': {},
            'name_aliases': {},
            'discord_id_to_name': {},
            'cluster_map': {},
        }
    
    def _validate_config(self, config: Dict[str, Any]) -> list:
        """
        Validate configuration values.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Validate thresholds are in valid range
        thresholds = config.get('thresholds', {})
        for key, value in thresholds.items():
            if not isinstance(value, (int, float)):
                errors.append(f"Threshold '{key}' must be a number")
            elif not 0.0 <= value <= 1.0:
                errors.append(f"Threshold '{key}' must be between 0.0 and 1.0")
        
        # Validate weights sum to approximately 1.0
        weights = config.get('weights', {})
        if weights:
            weight_sum = sum(weights.values())
            if not 0.9 <= weight_sum <= 1.1:
                errors.append(
                    f"Weights should sum to ~1.0, got {weight_sum:.2f}"
                )
        
        # Validate blocking strategy
        valid_strategies = {'none', 'character', 'phonetic', 'multi_level'}
        strategy = config.get('blocking_strategy', 'multi_level')
        if strategy not in valid_strategies:
            errors.append(
                f"Invalid blocking_strategy '{strategy}'. "
                f"Valid: {valid_strategies}"
            )
        
        return errors
    
    def _load_json_file(
        self,
        path: str,
        defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Load a JSON file with fallback to defaults.
        
        Args:
            path: Path to JSON file
            defaults: Default values if file not found
            
        Returns:
            Loaded or default dictionary
        """
        if not os.path.exists(path):
            return defaults.copy()
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Merge with defaults (to fill in missing keys)
            result = defaults.copy()
            for key, value in data.items():
                if isinstance(value, dict) and key in result:
                    result[key] = {**result[key], **value}
                else:
                    result[key] = value
            
            return result
            
        except json.JSONDecodeError as e:
            self._load_errors.append(f"JSON parse error in {path}: {e}")
            return defaults.copy()
        except Exception as e:
            self._load_errors.append(f"Error loading {path}: {e}")
            return defaults.copy()
    
    def reload(self) -> bool:
        """
        Reload configuration from files.
        
        Thread-safe hot-reload of both config and aliases.
        
        Returns:
            True if reload was successful
        """
        with self._lock:
            self._load_errors = []
            
            # Load matching config
            config_data = self._load_json_file(
                self._config_path,
                self._get_default_config()
            )
            
            # Validate config
            validation_errors = self._validate_config(config_data)
            self._load_errors.extend(validation_errors)
            
            # Load aliases
            aliases_data = self._load_json_file(
                self._aliases_path,
                self._get_default_aliases()
            )
            
            # Update internal state
            self._config = MatchingConfig(
                matching_layers=config_data.get(
                    'matching_layers', 
                    self._get_default_config()['matching_layers']
                ),
                thresholds=config_data.get(
                    'thresholds',
                    self._get_default_config()['thresholds']
                ),
                weights=config_data.get(
                    'weights',
                    self._get_default_config()['weights']
                ),
                blocking_strategy=config_data.get(
                    'blocking_strategy', 'multi_level'
                ),
                debug_mode=config_data.get('debug_mode', False),
                llm_validation=config_data.get(
                    'llm_validation',
                    self._get_default_config()['llm_validation']
                )
            )
            
            self._aliases = AliasConfig(
                manual_overrides=aliases_data.get('manual_overrides', {}),
                name_aliases=aliases_data.get('name_aliases', {}),
                discord_id_to_name=aliases_data.get('discord_id_to_name', {}),
                cluster_map=aliases_data.get('cluster_map', {})
            )
            
            self._last_loaded = datetime.now()
            
            return len(self._load_errors) == 0
    
    def save_config(self) -> bool:
        """
        Save current configuration to file.
        
        Returns:
            True if save was successful
        """
        with self._lock:
            config_data = {
                'matching_layers': self._config.matching_layers,
                'thresholds': self._config.thresholds,
                'weights': self._config.weights,
                'blocking_strategy': self._config.blocking_strategy,
                'debug_mode': self._config.debug_mode,
                'llm_validation': self._config.llm_validation,
            }
            
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
                
                with open(self._config_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                
                return True
            except Exception as e:
                self._load_errors.append(f"Error saving config: {e}")
                return False
    
    def save_aliases(self) -> bool:
        """
        Save current aliases to file.
        
        Returns:
            True if save was successful
        """
        with self._lock:
            aliases_data = {
                'manual_overrides': self._aliases.manual_overrides,
                'name_aliases': self._aliases.name_aliases,
                'discord_id_to_name': self._aliases.discord_id_to_name,
                'cluster_map': self._aliases.cluster_map,
            }
            
            try:
                os.makedirs(os.path.dirname(self._aliases_path), exist_ok=True)
                
                with open(self._aliases_path, 'w', encoding='utf-8') as f:
                    json.dump(aliases_data, f, indent=2, ensure_ascii=False)
                
                return True
            except Exception as e:
                self._load_errors.append(f"Error saving aliases: {e}")
                return False
    
    @property
    def config(self) -> MatchingConfig:
        """Get current matching configuration."""
        with self._lock:
            return self._config
    
    @property
    def aliases(self) -> AliasConfig:
        """Get current alias configuration."""
        with self._lock:
            return self._aliases
    
    @property
    def matching_layers(self) -> Dict[str, bool]:
        """Get matching layer settings."""
        with self._lock:
            return self._config.matching_layers.copy()
    
    @property
    def thresholds(self) -> Dict[str, float]:
        """Get threshold settings."""
        with self._lock:
            return self._config.thresholds.copy()
    
    @property
    def weights(self) -> Dict[str, float]:
        """Get weight settings."""
        with self._lock:
            return self._config.weights.copy()
    
    @property
    def blocking_strategy(self) -> str:
        """Get blocking strategy."""
        with self._lock:
            return self._config.blocking_strategy
    
    @property
    def debug_mode(self) -> bool:
        """Get debug mode setting."""
        with self._lock:
            return self._config.debug_mode
    
    @property
    def manual_overrides(self) -> Dict[str, Dict]:
        """Get manual override mappings."""
        with self._lock:
            return self._aliases.manual_overrides.copy()
    
    @property
    def name_aliases(self) -> Dict[str, list]:
        """Get name alias mappings."""
        with self._lock:
            return self._aliases.name_aliases.copy()
    
    @property
    def discord_id_to_name(self) -> Dict[str, str]:
        """Get Discord ID to name mappings."""
        with self._lock:
            return self._aliases.discord_id_to_name.copy()
    
    @property
    def cluster_map(self) -> Dict[str, Dict]:
        """Get cluster map."""
        with self._lock:
            return self._aliases.cluster_map.copy()
    
    @property
    def load_errors(self) -> list:
        """Get any errors from last load."""
        with self._lock:
            return list(self._load_errors)
    
    @property
    def last_loaded(self) -> Optional[datetime]:
        """Get timestamp of last successful load."""
        with self._lock:
            return self._last_loaded
    
    def set_debug_mode(self, enabled: bool) -> None:
        """Set debug mode."""
        with self._lock:
            self._config.debug_mode = enabled
    
    def update_threshold(self, key: str, value: float) -> bool:
        """
        Update a single threshold value.
        
        Args:
            key: Threshold key
            value: New threshold value (0.0 to 1.0)
            
        Returns:
            True if update was valid
        """
        if not 0.0 <= value <= 1.0:
            return False
        
        with self._lock:
            self._config.thresholds[key] = value
        
        return True
    
    def update_layer(self, layer: str, enabled: bool) -> bool:
        """
        Enable or disable a matching layer.
        
        Args:
            layer: Layer name
            enabled: Whether to enable the layer
            
        Returns:
            True if layer exists
        """
        with self._lock:
            if layer in self._config.matching_layers:
                self._config.matching_layers[layer] = enabled
                return True
        return False
    
    def add_manual_override(
        self,
        alias: str,
        canonical_name: str,
        confidence: float = 1.0,
        match_type: str = 'associative',
        notes: Optional[str] = None
    ) -> None:
        """
        Add a manual override mapping.
        
        Args:
            alias: The alias to map
            canonical_name: The canonical name it maps to
            confidence: Confidence score (0.0 to 1.0)
            match_type: Type of match
            notes: Optional notes about the mapping
        """
        with self._lock:
            self._aliases.manual_overrides[alias.lower()] = {
                'canonical_name': canonical_name,
                'confidence': confidence,
                'match_type': match_type,
                'notes': notes,
            }
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current configuration.
        
        Useful for displaying to administrators.
        
        Returns:
            Dictionary with configuration summary
        """
        with self._lock:
            return {
                'config_path': self._config_path,
                'aliases_path': self._aliases_path,
                'last_loaded': (
                    self._last_loaded.isoformat() 
                    if self._last_loaded else None
                ),
                'load_errors': list(self._load_errors),
                'matching_layers': dict(self._config.matching_layers),
                'blocking_strategy': self._config.blocking_strategy,
                'debug_mode': self._config.debug_mode,
                'thresholds': dict(self._config.thresholds),
                'weights': dict(self._config.weights),
                'manual_overrides_count': len(self._aliases.manual_overrides),
                'name_aliases_count': len(self._aliases.name_aliases),
                'discord_mappings_count': len(self._aliases.discord_id_to_name),
                'clusters_count': len(self._aliases.cluster_map),
            }
