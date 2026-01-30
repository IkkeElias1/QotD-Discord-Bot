# -*- coding: utf-8 -*-
"""
Entity Resolution Module.

Implements clustering and disambiguation to group name variations
under unique Person IDs and distinguish between different people
with the same name.
"""

from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter

from .normalization import NordicNormalizer


@dataclass
class PersonCluster:
    """Represents a cluster of name variations for a single person."""
    person_id: str
    canonical_name: str
    aliases: List[str] = field(default_factory=list)
    discord_id: Optional[str] = None
    quote_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class EntityResolver:
    """
    Resolve entities and build cluster maps.
    
    Groups different name variations that refer to the same person,
    and distinguishes between different people who may have similar names.
    """
    
    def __init__(
        self,
        clustering_threshold: float = 0.75,
        normalizer: Optional[NordicNormalizer] = None
    ) -> None:
        """
        Initialize the entity resolver.
        
        Args:
            clustering_threshold: Minimum similarity for clustering names
            normalizer: NordicNormalizer instance
        """
        self.clustering_threshold = clustering_threshold
        self.normalizer = normalizer or NordicNormalizer()
        self._cluster_map: Dict[str, PersonCluster] = {}
    
    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        return self.normalizer.normalize(name)
    
    def _build_similarity_graph(
        self,
        names: List[str],
        matcher: Any  # NameMatcher - avoiding circular import
    ) -> Dict[str, Set[str]]:
        """
        Build undirected graph where edges connect similar names.
        
        Args:
            names: List of unique author names
            matcher: NameMatcher instance for similarity calculations
            
        Returns:
            Graph as adjacency list (name -> set of similar names)
        """
        graph: Dict[str, Set[str]] = {name: set() for name in names}
        
        # Compare all pairs
        for i, name1 in enumerate(names):
            for name2 in names[i + 1:]:
                # Use matcher to determine if these are the same person
                match_results = matcher.match(
                    name1,
                    [name2],
                    return_scores=True
                )
                
                if match_results:
                    # Check if confidence is high enough
                    _, confidence, _ = match_results[0]
                    if confidence >= self.clustering_threshold:
                        graph[name1].add(name2)
                        graph[name2].add(name1)
        
        return graph
    
    def _find_connected_components(
        self,
        graph: Dict[str, Set[str]]
    ) -> List[List[str]]:
        """
        Find connected components using DFS.
        
        Args:
            graph: Adjacency list representation of similarity graph
            
        Returns:
            List of components (each component is a list of names)
        """
        visited: Set[str] = set()
        components: List[List[str]] = []
        
        def dfs(node: str, component: List[str]) -> None:
            visited.add(node)
            component.append(node)
            for neighbor in graph[node]:
                if neighbor not in visited:
                    dfs(neighbor, component)
        
        for node in graph:
            if node not in visited:
                component: List[str] = []
                dfs(node, component)
                components.append(component)
        
        return components
    
    def _select_canonical_name(
        self,
        cluster: List[str],
        quotes: List[Dict]
    ) -> str:
        """
        Select the canonical name for a cluster.
        
        Uses heuristics:
        1. Most commonly used name
        2. Longest name (likely most complete)
        3. Alphabetically first (for consistency)
        
        Args:
            cluster: List of name variations
            quotes: List of quote objects for frequency counting
            
        Returns:
            Selected canonical name
        """
        if not cluster:
            return "Unknown"
        
        if len(cluster) == 1:
            return cluster[0]
        
        # Count frequency of each name in quotes
        name_counts: Counter = Counter()
        normalized_to_original: Dict[str, str] = {}
        
        for name in cluster:
            normalized = self._normalize_name(name)
            normalized_to_original[normalized] = name
        
        for quote in quotes:
            author = quote.get('author', '')
            normalized_author = self._normalize_name(author)
            if normalized_author in normalized_to_original:
                name_counts[normalized_to_original[normalized_author]] += 1
        
        # Get most common
        if name_counts:
            most_common = name_counts.most_common(1)[0][0]
            # Prefer title case
            return most_common.title()
        
        # Fall back to longest name (likely most complete)
        longest = max(cluster, key=len)
        return longest.title()
    
    def _find_discord_id(
        self,
        cluster: List[str],
        discord_id_map: Dict[str, str]
    ) -> Optional[str]:
        """
        Find Discord ID associated with a cluster.
        
        Args:
            cluster: List of name variations
            discord_id_map: Mapping from Discord IDs to names
            
        Returns:
            Discord ID if found, None otherwise
        """
        # Invert the map for lookup
        name_to_id: Dict[str, str] = {}
        for discord_id, name in discord_id_map.items():
            normalized = self._normalize_name(name)
            name_to_id[normalized] = str(discord_id)
        
        # Check each name in cluster
        for name in cluster:
            normalized = self._normalize_name(name)
            if normalized in name_to_id:
                return name_to_id[normalized]
        
        return None
    
    def build_cluster_map(
        self,
        quotes: List[Dict],
        matcher: Any,  # NameMatcher
        discord_id_map: Optional[Dict[str, str]] = None
    ) -> Dict[str, Dict]:
        """
        Build cluster map grouping all name variations by person.
        
        Args:
            quotes: List of quote objects with 'author' field
            matcher: NameMatcher instance for similarity calculations
            discord_id_map: Optional mapping from Discord IDs to names
            
        Returns:
            Cluster map dictionary:
            {
                "Person_1": {
                    "canonical_name": "Jonathan",
                    "aliases": ["jonathan", "jon", "jona"],
                    "discord_id": "123...",
                    "quote_count": 47
                },
                ...
            }
        """
        discord_id_map = discord_id_map or {}
        
        # Extract all unique author names
        author_names = list(set(
            q.get('author', '') 
            for q in quotes 
            if q.get('author') and q.get('author') != 'Anonym'
        ))
        
        if not author_names:
            return {}
        
        # Build similarity graph
        graph = self._build_similarity_graph(author_names, matcher)
        
        # Find connected components (clusters)
        clusters = self._find_connected_components(graph)
        
        # Create cluster map
        cluster_map: Dict[str, Dict] = {}
        
        for i, cluster in enumerate(clusters, 1):
            person_id = f"Person_{i}"
            
            # Determine canonical name
            canonical = self._select_canonical_name(cluster, quotes)
            
            # Count quotes for this cluster
            cluster_normalized = {self._normalize_name(n) for n in cluster}
            quote_count = sum(
                1 for q in quotes
                if self._normalize_name(q.get('author', '')) in cluster_normalized
            )
            
            # Find Discord ID
            discord_id = self._find_discord_id(cluster, discord_id_map)
            
            cluster_map[person_id] = {
                "canonical_name": canonical,
                "aliases": sorted(cluster, key=lambda x: self._normalize_name(x)),
                "discord_id": discord_id,
                "quote_count": quote_count
            }
        
        self._cluster_map = {
            pid: PersonCluster(
                person_id=pid,
                canonical_name=data["canonical_name"],
                aliases=data["aliases"],
                discord_id=data["discord_id"],
                quote_count=data["quote_count"]
            )
            for pid, data in cluster_map.items()
        }
        
        return cluster_map
    
    def find_person_by_name(self, name: str) -> Optional[str]:
        """
        Find the Person ID that a name belongs to.
        
        Args:
            name: Name to search for
            
        Returns:
            Person ID or None if not found
        """
        normalized = self._normalize_name(name)
        
        for person_id, cluster in self._cluster_map.items():
            cluster_normalized = {
                self._normalize_name(alias) 
                for alias in cluster.aliases
            }
            if normalized in cluster_normalized:
                return person_id
        
        return None
    
    def get_canonical_name(self, name: str) -> Optional[str]:
        """
        Get the canonical name for any name variation.
        
        Args:
            name: Name to look up
            
        Returns:
            Canonical name or None if not found
        """
        person_id = self.find_person_by_name(name)
        
        if person_id and person_id in self._cluster_map:
            return self._cluster_map[person_id].canonical_name
        
        return None
    
    def get_all_aliases(self, canonical_name: str) -> List[str]:
        """
        Get all aliases for a canonical name.
        
        Args:
            canonical_name: The canonical name to look up
            
        Returns:
            List of all known aliases
        """
        normalized = self._normalize_name(canonical_name)
        
        for cluster in self._cluster_map.values():
            if self._normalize_name(cluster.canonical_name) == normalized:
                return list(cluster.aliases)
        
        return []
    
    def get_cluster_map(self) -> Dict[str, Dict]:
        """
        Get the current cluster map.
        
        Returns:
            Dictionary representation of cluster map
        """
        return {
            pid: {
                "canonical_name": cluster.canonical_name,
                "aliases": cluster.aliases,
                "discord_id": cluster.discord_id,
                "quote_count": cluster.quote_count
            }
            for pid, cluster in self._cluster_map.items()
        }
    
    def merge_clusters(
        self,
        person_id_1: str,
        person_id_2: str
    ) -> Optional[str]:
        """
        Manually merge two clusters into one.
        
        Useful for disambiguation corrections.
        
        Args:
            person_id_1: First person ID
            person_id_2: Second person ID to merge into first
            
        Returns:
            Resulting person ID or None if merge failed
        """
        if person_id_1 not in self._cluster_map:
            return None
        if person_id_2 not in self._cluster_map:
            return None
        
        cluster1 = self._cluster_map[person_id_1]
        cluster2 = self._cluster_map[person_id_2]
        
        # Merge aliases
        merged_aliases = list(set(cluster1.aliases + cluster2.aliases))
        
        # Sum quote counts
        merged_count = cluster1.quote_count + cluster2.quote_count
        
        # Use the first cluster's canonical name (or the one with more quotes)
        if cluster2.quote_count > cluster1.quote_count:
            canonical = cluster2.canonical_name
        else:
            canonical = cluster1.canonical_name
        
        # Update cluster 1
        self._cluster_map[person_id_1] = PersonCluster(
            person_id=person_id_1,
            canonical_name=canonical,
            aliases=merged_aliases,
            discord_id=cluster1.discord_id or cluster2.discord_id,
            quote_count=merged_count
        )
        
        # Remove cluster 2
        del self._cluster_map[person_id_2]
        
        return person_id_1
    
    def split_cluster(
        self,
        person_id: str,
        names_to_split: List[str]
    ) -> Optional[str]:
        """
        Split names from a cluster into a new cluster.
        
        Useful for disambiguation corrections.
        
        Args:
            person_id: Person ID to split from
            names_to_split: Names to move to new cluster
            
        Returns:
            New person ID or None if split failed
        """
        if person_id not in self._cluster_map:
            return None
        
        cluster = self._cluster_map[person_id]
        names_normalized = {self._normalize_name(n) for n in names_to_split}
        
        # Find aliases to split
        to_split = []
        to_keep = []
        
        for alias in cluster.aliases:
            if self._normalize_name(alias) in names_normalized:
                to_split.append(alias)
            else:
                to_keep.append(alias)
        
        if not to_split or not to_keep:
            return None
        
        # Create new person ID
        max_id = max(
            int(pid.split('_')[1]) 
            for pid in self._cluster_map.keys()
        )
        new_person_id = f"Person_{max_id + 1}"
        
        # Update original cluster
        self._cluster_map[person_id] = PersonCluster(
            person_id=person_id,
            canonical_name=to_keep[0].title(),
            aliases=to_keep,
            discord_id=cluster.discord_id,
            quote_count=0  # Would need to recalculate
        )
        
        # Create new cluster
        self._cluster_map[new_person_id] = PersonCluster(
            person_id=new_person_id,
            canonical_name=to_split[0].title(),
            aliases=to_split,
            discord_id=None,
            quote_count=0
        )
        
        return new_person_id
