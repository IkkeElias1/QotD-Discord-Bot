# -*- coding: utf-8 -*-
"""
Debug Logging Module.

Provides comprehensive debug logging for matching decisions
to help administrators understand and tune the system.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import io
import sys


@dataclass
class MatchAttempt:
    """Record of a single match attempt."""
    query: str
    candidate: str
    scores: Dict[str, Any]
    matched: bool
    reason: str
    layer: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class CascadeStep:
    """Record of a cascade step."""
    step_number: int
    layer_name: str
    attempted: bool
    result_count: int
    reason: str


class DebugLogger:
    """
    Detailed logging for matching decisions.
    
    Provides comprehensive output to help administrators understand
    why certain matches succeed or fail, including algorithm scores,
    cascade paths, and blocking statistics.
    """
    
    def __init__(
        self,
        enabled: bool = False,
        output: Optional[io.TextIOBase] = None,
        thresholds: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Initialize the debug logger.
        
        Args:
            enabled: Whether debug logging is enabled
            output: Output stream (defaults to sys.stdout)
            thresholds: Threshold values for comparison display
        """
        self.enabled = enabled
        self.output = output or sys.stdout
        self.thresholds = thresholds or {}
        
        self._match_history: List[MatchAttempt] = []
        self._cascade_history: List[CascadeStep] = []
        self._current_query: Optional[str] = None
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable debug logging."""
        self.enabled = enabled
    
    def set_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update thresholds for display."""
        self.thresholds = thresholds
    
    def clear_history(self) -> None:
        """Clear match and cascade history."""
        self._match_history.clear()
        self._cascade_history.clear()
        self._current_query = None
    
    def start_match(self, query: str) -> None:
        """
        Start logging a new match operation.
        
        Args:
            query: The query being matched
        """
        if not self.enabled:
            return
        
        self._current_query = query
        self._cascade_history.clear()
        
        self._print(f"\n{'='*60}")
        self._print(f"🔍 MATCHING: '{query}'")
        self._print(f"{'='*60}")
    
    def end_match(self, results: List[Any]) -> None:
        """
        End logging for current match operation.
        
        Args:
            results: Final match results
        """
        if not self.enabled:
            return
        
        self._print(f"\n{'─'*40}")
        if results:
            self._print(f"✅ FINAL RESULTS: {len(results)} match(es)")
            for r in results[:5]:  # Show top 5
                if hasattr(r, 'name'):
                    self._print(f"   • {r.name} ({r.confidence:.2%})")
                elif isinstance(r, tuple) and len(r) >= 2:
                    self._print(f"   • {r[0]} ({r[1]:.2%})")
        else:
            self._print("❌ NO MATCHES FOUND")
        self._print(f"{'='*60}\n")
    
    def log_match_attempt(
        self,
        query: str,
        candidate: str,
        scores: Dict[str, Any],
        matched: bool,
        reason: str,
        layer: str = 'unknown'
    ) -> None:
        """
        Log a single matching attempt.
        
        Args:
            query: Query being matched
            candidate: Candidate being compared
            scores: Algorithm scores
            matched: Whether it matched
            reason: Reason for match/no-match
            layer: Which matching layer
        """
        attempt = MatchAttempt(
            query=query,
            candidate=candidate,
            scores=scores,
            matched=matched,
            reason=reason,
            layer=layer
        )
        self._match_history.append(attempt)
        
        if not self.enabled:
            return
        
        status = "✅ MATCH" if matched else "❌ NO MATCH"
        self._print(f"\n{status}: '{query}' vs '{candidate}'")
        self._print(f"   Layer: {layer}")
        self._print(f"   Reason: {reason}")
        
        if scores:
            self._print("   Algorithm Scores:")
            for algo, score in sorted(scores.items()):
                threshold_key = f'{algo}_min'
                threshold = self.thresholds.get(threshold_key, 0.0)
                passed = "✓" if score >= threshold else "✗"
                self._print(
                    f"      {passed} {algo}: {score:.3f} "
                    f"(threshold: {threshold:.3f})"
                )
    
    def log_cascade_step(
        self,
        step_number: int,
        layer_name: str,
        attempted: bool,
        result_count: int = 0,
        reason: str = ""
    ) -> None:
        """
        Log a cascade step.
        
        Args:
            step_number: Step number in cascade
            layer_name: Name of the matching layer
            attempted: Whether the layer was attempted
            result_count: Number of results from this layer
            reason: Reason for result
        """
        step = CascadeStep(
            step_number=step_number,
            layer_name=layer_name,
            attempted=attempted,
            result_count=result_count,
            reason=reason
        )
        self._cascade_history.append(step)
        
        if not self.enabled:
            return
        
        if attempted:
            status = "✓" if result_count > 0 else "○"
            self._print(
                f"   {step_number}. [{status}] {layer_name}: "
                f"{result_count} result(s) - {reason}"
            )
        else:
            self._print(f"   {step_number}. [─] {layer_name}: SKIPPED - {reason}")
    
    def log_cascade_path(self, steps: List[str]) -> None:
        """
        Log the complete cascade path.
        
        Args:
            steps: List of step descriptions
        """
        if not self.enabled:
            return
        
        self._print("\n📋 Cascade Path:")
        for i, step in enumerate(steps, 1):
            self._print(f"   {i}. {step}")
    
    def log_blocking_info(
        self,
        query: str,
        total_candidates: int,
        blocked_candidates: int,
        blocks_used: List[str]
    ) -> None:
        """
        Log blocking statistics.
        
        Args:
            query: Query being matched
            total_candidates: Total number of candidates
            blocked_candidates: Number after blocking
            blocks_used: Block keys that were used
        """
        if not self.enabled:
            return
        
        reduction = (1 - blocked_candidates / total_candidates) * 100 \
            if total_candidates > 0 else 0
        
        self._print("\n📊 Blocking Info:")
        self._print(f"   Query: '{query}'")
        self._print(f"   Total candidates: {total_candidates}")
        self._print(f"   After blocking: {blocked_candidates}")
        self._print(f"   Reduction: {reduction:.1f}%")
        if blocks_used:
            self._print(f"   Blocks used: {', '.join(blocks_used[:5])}")
            if len(blocks_used) > 5:
                self._print(f"   ... and {len(blocks_used) - 5} more")
    
    def log_normalization(
        self,
        original: str,
        normalized: str,
        variants: Optional[List[str]] = None
    ) -> None:
        """
        Log normalization steps.
        
        Args:
            original: Original text
            normalized: Normalized text
            variants: Generated variants
        """
        if not self.enabled:
            return
        
        self._print("\n📝 Normalization:")
        self._print(f"   Original: '{original}'")
        self._print(f"   Normalized: '{normalized}'")
        
        if variants and len(variants) > 1:
            self._print(f"   Variants: {', '.join(repr(v) for v in variants)}")
    
    def log_phonetic_codes(
        self,
        name: str,
        primary: str,
        secondary: str
    ) -> None:
        """
        Log phonetic codes for a name.
        
        Args:
            name: The name
            primary: Primary metaphone code
            secondary: Secondary metaphone code
        """
        if not self.enabled:
            return
        
        self._print(f"   🔊 '{name}' → Primary: {primary}, Secondary: {secondary}")
    
    def log_alias_lookup(
        self,
        query: str,
        found: bool,
        canonical: Optional[str] = None,
        source: str = ""
    ) -> None:
        """
        Log alias lookup attempt.
        
        Args:
            query: Query being looked up
            found: Whether an alias was found
            canonical: Canonical name if found
            source: Source of the alias (e.g., 'manual_overrides')
        """
        if not self.enabled:
            return
        
        if found:
            self._print(f"   📖 Alias found: '{query}' → '{canonical}' ({source})")
        else:
            self._print(f"   📖 No alias found for: '{query}'")
    
    def log_discord_lookup(
        self,
        discord_id: str,
        found: bool,
        name: Optional[str] = None
    ) -> None:
        """
        Log Discord ID lookup.
        
        Args:
            discord_id: Discord ID being looked up
            found: Whether a mapping was found
            name: Name if found
        """
        if not self.enabled:
            return
        
        if found:
            self._print(f"   👤 Discord ID {discord_id} → '{name}'")
        else:
            self._print(f"   👤 Discord ID {discord_id} not found in mappings")
    
    def _print(self, message: str) -> None:
        """Print a message to the output stream."""
        try:
            print(message, file=self.output)
        except UnicodeEncodeError:
            # Fallback for terminals that don't support Unicode
            # Replace emoji with ASCII alternatives
            safe_message = message.encode('ascii', 'replace').decode('ascii')
            print(safe_message, file=self.output)
    
    def get_match_history(self) -> List[MatchAttempt]:
        """Get the match attempt history."""
        return list(self._match_history)
    
    def get_cascade_history(self) -> List[CascadeStep]:
        """Get the cascade step history."""
        return list(self._cascade_history)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the debug session.
        
        Returns:
            Dictionary with debug summary
        """
        total_attempts = len(self._match_history)
        successful = sum(1 for a in self._match_history if a.matched)
        
        layers_used = {}
        for attempt in self._match_history:
            if attempt.layer not in layers_used:
                layers_used[attempt.layer] = {'total': 0, 'matched': 0}
            layers_used[attempt.layer]['total'] += 1
            if attempt.matched:
                layers_used[attempt.layer]['matched'] += 1
        
        return {
            'total_attempts': total_attempts,
            'successful_matches': successful,
            'match_rate': successful / total_attempts if total_attempts else 0,
            'layers_used': layers_used,
            'cascade_steps': len(self._cascade_history),
        }
    
    def format_debug_output(self) -> str:
        """
        Format the debug history as a string.
        
        Useful for sending debug info in Discord messages.
        
        Returns:
            Formatted debug string
        """
        lines = []
        
        if self._current_query:
            lines.append(f"**Query:** `{self._current_query}`")
        
        if self._cascade_history:
            lines.append("\n**Cascade Path:**")
            for step in self._cascade_history:
                status = "✓" if step.attempted and step.result_count > 0 else \
                         "○" if step.attempted else "─"
                lines.append(f"  {step.step_number}. [{status}] {step.layer_name}")
        
        if self._match_history:
            lines.append(f"\n**Match Attempts:** {len(self._match_history)}")
            successful = [a for a in self._match_history if a.matched]
            if successful:
                lines.append(f"**Successful:** {len(successful)}")
                for attempt in successful[:3]:
                    lines.append(f"  • `{attempt.candidate}` via {attempt.layer}")
        
        return '\n'.join(lines)
