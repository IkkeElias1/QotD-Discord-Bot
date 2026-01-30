# -*- coding: utf-8 -*-
"""
Nickname Dictionary Module.

Provides standard nickname mappings and expansion functionality
for common name variations.
"""

from typing import Dict, List, Set, Optional

# Try to import the nicknames library
try:
    import nicknames as nick_lib
    NICKNAMES_AVAILABLE = True
except ImportError:
    NICKNAMES_AVAILABLE = False


class NicknameDictionary:
    """
    Standard nickname dictionary for common name variations.
    
    Provides mappings between formal names and their common nicknames,
    with support for bidirectional lookup.
    """
    
    # Built-in common name mappings (fallback if nicknames library unavailable)
    # Includes Nordic-specific variations
    BUILTIN_MAPPINGS: Dict[str, List[str]] = {
        # Common English/Danish names
        'alexander': ['alex', 'xander', 'sansen'],
        'andreas': ['andy', 'dansen'],
        'benjamin': ['ben', 'benji', 'bansen'],
        'christian': ['chris', 'chransen'],
        'christopher': ['chris', 'kansen'],
        'daniel': ['dan', 'danny'],
        'david': ['dave', 'davey'],
        'edward': ['ed', 'eddie', 'ted', 'teddy'],
        'elizabeth': ['liz', 'lizzy', 'beth', 'betty'],
        'frederick': ['fred', 'freddy', 'fritz'],
        'gabriel': ['gabe', 'gabby'],
        'gustav': ['gansen'],
        'henrik': ['hansen'],
        'jacob': ['jake', 'jansen'],
        'james': ['jim', 'jimmy', 'jamie'],
        'jennifer': ['jen', 'jenny'],
        'jessica': ['jess', 'jessie'],
        'johannes': ['johan', 'jansen'],
        'jonathan': ['jon', 'jonny', 'johnny', 'jona', 'nansen'],
        'joseph': ['joe', 'joey'],
        'katherine': ['kate', 'kathy', 'katie', 'kit'],
        'kristian': ['kansen'],
        'magnus': ['mansen'],
        'margaret': ['maggie', 'meg', 'peggy'],
        'mathias': ['mathansen'],
        'matthew': ['matt', 'matty'],
        'michael': ['mike', 'mikey', 'mick'],
        'nicholas': ['nick', 'nicky'],
        'oliver': ['ollie'],
        'patrick': ['pat', 'paddy'],
        'peter': ['pete', 'petey', 'pedansen'],
        'phillip': ['phil'],
        'rasmus': ['ransen'],
        'richard': ['rick', 'ricky', 'dick'],
        'robert': ['rob', 'robby', 'bob', 'bobby'],
        'samuel': ['sam', 'sammy'],
        'sebastian': ['seb', 'bansen'],
        'simon': ['sansen'],
        'thomas': ['tom', 'tommy', 'tansen'],
        'valdemar': ['vansen'],
        'william': ['will', 'willy', 'bill', 'billy', 'liam'],
    }
    
    def __init__(self, use_library: bool = True) -> None:
        """
        Initialize the nickname dictionary.
        
        Args:
            use_library: If True, try to use the nicknames library
        """
        self.use_library = use_library and NICKNAMES_AVAILABLE
        self._custom_mappings: Dict[str, List[str]] = {}
        
        # Build reverse lookup
        self._reverse_map: Dict[str, Set[str]] = {}
        self._build_reverse_map(self.BUILTIN_MAPPINGS)
    
    def _build_reverse_map(self, mappings: Dict[str, List[str]]) -> None:
        """Build reverse lookup from nicknames to formal names."""
        for formal, nicks in mappings.items():
            formal_lower = formal.lower()
            for nick in nicks:
                nick_lower = nick.lower()
                if nick_lower not in self._reverse_map:
                    self._reverse_map[nick_lower] = set()
                self._reverse_map[nick_lower].add(formal_lower)
    
    def add_custom_mapping(
        self,
        formal_name: str,
        nicknames: List[str]
    ) -> None:
        """
        Add a custom nickname mapping.
        
        Args:
            formal_name: The formal/canonical name
            nicknames: List of nicknames for this name
        """
        formal_lower = formal_name.lower()
        
        if formal_lower not in self._custom_mappings:
            self._custom_mappings[formal_lower] = []
        
        for nick in nicknames:
            nick_lower = nick.lower()
            if nick_lower not in self._custom_mappings[formal_lower]:
                self._custom_mappings[formal_lower].append(nick_lower)
            
            # Update reverse map
            if nick_lower not in self._reverse_map:
                self._reverse_map[nick_lower] = set()
            self._reverse_map[nick_lower].add(formal_lower)
    
    def get_nicknames(self, formal_name: str) -> List[str]:
        """
        Get all nicknames for a formal name.
        
        Args:
            formal_name: The formal name to look up
            
        Returns:
            List of nicknames (may be empty)
        """
        formal_lower = formal_name.lower()
        nicknames = set()
        
        # Check custom mappings first
        if formal_lower in self._custom_mappings:
            nicknames.update(self._custom_mappings[formal_lower])
        
        # Check built-in mappings
        if formal_lower in self.BUILTIN_MAPPINGS:
            nicknames.update(self.BUILTIN_MAPPINGS[formal_lower])
        
        # Try nicknames library
        if self.use_library:
            try:
                lib_nicks = nick_lib.nicknames(formal_name)
                if lib_nicks:
                    nicknames.update(n.lower() for n in lib_nicks)
            except Exception:
                pass
        
        return list(nicknames)
    
    def get_formal_names(self, nickname: str) -> List[str]:
        """
        Get all formal names that a nickname could refer to.
        
        Args:
            nickname: The nickname to look up
            
        Returns:
            List of possible formal names
        """
        nick_lower = nickname.lower()
        formal_names = set()
        
        # Check reverse map
        if nick_lower in self._reverse_map:
            formal_names.update(self._reverse_map[nick_lower])
        
        # Try nicknames library reverse lookup
        if self.use_library:
            try:
                lib_formals = nick_lib.canonicals(nickname)
                if lib_formals:
                    formal_names.update(n.lower() for n in lib_formals)
            except Exception:
                pass
        
        return list(formal_names)
    
    def are_related(self, name1: str, name2: str) -> bool:
        """
        Check if two names are related (nickname/formal relationship).
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            True if names are related
        """
        name1_lower = name1.lower()
        name2_lower = name2.lower()
        
        # Direct match
        if name1_lower == name2_lower:
            return True
        
        # Check if name1 is a nickname for name2
        name2_nicks = self.get_nicknames(name2)
        if name1_lower in name2_nicks:
            return True
        
        # Check if name2 is a nickname for name1
        name1_nicks = self.get_nicknames(name1)
        if name2_lower in name1_nicks:
            return True
        
        # Check if both resolve to same formal name
        name1_formals = set(self.get_formal_names(name1))
        name2_formals = set(self.get_formal_names(name2))
        
        if name1_formals & name2_formals:
            return True
        
        return False
    
    def expand_name(self, name: str) -> List[str]:
        """
        Expand a name to include all related variations.
        
        Args:
            name: Name to expand
            
        Returns:
            List of all related name variations
        """
        name_lower = name.lower()
        variations = {name_lower}
        
        # Add nicknames
        nicknames = self.get_nicknames(name)
        variations.update(nicknames)
        
        # Add formal names
        formals = self.get_formal_names(name)
        variations.update(formals)
        
        # For each formal name, also add their other nicknames
        for formal in formals:
            variations.update(self.get_nicknames(formal))
        
        return list(variations)
    
    def find_matches(
        self,
        query: str,
        candidates: List[str]
    ) -> List[str]:
        """
        Find candidates that are nickname-related to the query.
        
        Args:
            query: Name to search for
            candidates: List of candidate names
            
        Returns:
            List of matching candidates
        """
        query_expanded = set(self.expand_name(query))
        matches = []
        
        for candidate in candidates:
            candidate_expanded = set(self.expand_name(candidate))
            
            if query_expanded & candidate_expanded:
                matches.append(candidate)
        
        return matches
    
    def get_all_mappings(self) -> Dict[str, List[str]]:
        """
        Get all current nickname mappings.
        
        Returns:
            Dictionary of formal names to nicknames
        """
        all_mappings = {}
        
        # Start with built-in
        for formal, nicks in self.BUILTIN_MAPPINGS.items():
            all_mappings[formal] = list(nicks)
        
        # Override/extend with custom
        for formal, nicks in self._custom_mappings.items():
            if formal in all_mappings:
                all_mappings[formal] = list(set(all_mappings[formal] + nicks))
            else:
                all_mappings[formal] = list(nicks)
        
        return all_mappings
