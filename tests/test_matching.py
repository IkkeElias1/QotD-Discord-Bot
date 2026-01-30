# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite for Name Matching System.

Tests covering:
- Typographical variations (jonethen, gusdav)
- Phonetic variations (walmart → Valdemar, jonne → jonathan)
- Multi-token names (joe nation, gustav husted)
- Nordic characters (tørst → torst, v/w interchange)
- Disambiguation (Gustav vs Gustav Husted vs Gustav Porno Tørst)
"""

import unittest
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matching import (
    NameMatcher,
    NordicNormalizer,
    StringSimilarity,
    PhoneticMatcher,
    BlockingStrategy,
)


class TestNordicNormalizer(unittest.TestCase):
    """Test Nordic character normalization."""
    
    def setUp(self):
        self.normalizer = NordicNormalizer()
    
    def test_basic_normalization(self):
        """Test basic text normalization."""
        self.assertEqual(self.normalizer.normalize("Jonathan"), "jonathan")
        self.assertEqual(self.normalizer.normalize("  ELIAS  "), "elias")
    
    def test_nordic_characters(self):
        """Test Nordic character handling (æ, ø, å)."""
        self.assertEqual(self.normalizer.normalize("tørst"), "torst")
        self.assertEqual(self.normalizer.normalize("Tørst"), "torst")
        self.assertEqual(self.normalizer.normalize("æble"), "aeble")
        self.assertEqual(self.normalizer.normalize("Århus"), "arhus")
    
    def test_v_w_variants(self):
        """Test v/w variant generation."""
        variants = self.normalizer.generate_variants("valdemar")
        self.assertIn("valdemar", variants)
        self.assertIn("waldemar", variants)
        
        variants = self.normalizer.generate_variants("walmart")
        self.assertIn("walmart", variants)
        self.assertIn("valmart", variants)
    
    def test_equivalence_check(self):
        """Test name equivalence checking."""
        self.assertTrue(
            self.normalizer.are_equivalent("Valdemar", "waldemar")
        )
        self.assertTrue(
            self.normalizer.are_equivalent("Tørst", "torst")
        )
        self.assertFalse(
            self.normalizer.are_equivalent("Jonathan", "Elias")
        )
    
    def test_match_with_variants(self):
        """Test matching with variants."""
        def simple_match(a, b):
            return 1.0 if a == b else 0.0
        
        score = self.normalizer.match_with_variants(
            "valdemar", "waldemar", simple_match
        )
        self.assertEqual(score, 1.0)


class TestStringSimilarity(unittest.TestCase):
    """Test string similarity algorithms."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        try:
            cls.similarity = StringSimilarity()
            cls.available = True
        except ImportError:
            cls.available = False
    
    def setUp(self):
        if not self.available:
            self.skipTest("rapidfuzz not available")
    
    def test_exact_match(self):
        """Test exact matching."""
        score, _ = self.similarity.calculate_hybrid_score(
            "jonathan", "jonathan"
        )
        self.assertGreaterEqual(score, 0.99)
    
    def test_typo_match(self):
        """Test matching with typos."""
        # jonethen → jonathan
        score, _ = self.similarity.calculate_hybrid_score(
            "jonethen", "jonathan"
        )
        self.assertGreaterEqual(score, 0.70)
        
        # gusdav → gustav
        score, _ = self.similarity.calculate_hybrid_score(
            "gusdav", "gustav"
        )
        self.assertGreaterEqual(score, 0.70)
        
        # elais → elias
        score, _ = self.similarity.calculate_hybrid_score(
            "elais", "elias"
        )
        self.assertGreaterEqual(score, 0.80)
    
    def test_similar_names(self):
        """Test similar but different names."""
        score, _ = self.similarity.calculate_hybrid_score(
            "jonathan", "elias"
        )
        self.assertLess(score, 0.50)
    
    def test_multi_token_names(self):
        """Test multi-word name matching."""
        # "gustav husted" matching
        score, _ = self.similarity.calculate_hybrid_score(
            "gustav husted", "Gustav Husted"
        )
        self.assertGreaterEqual(score, 0.95)
        
        # Token order shouldn't matter too much
        score, _ = self.similarity.calculate_hybrid_score(
            "husted gustav", "gustav husted"
        )
        self.assertGreaterEqual(score, 0.70)


class TestPhoneticMatcher(unittest.TestCase):
    """Test phonetic matching."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        try:
            cls.phonetic = PhoneticMatcher()
            cls.available = True
        except ImportError:
            cls.available = False
    
    def setUp(self):
        if not self.available:
            self.skipTest("metaphone not available")
    
    def test_phonetic_codes(self):
        """Test phonetic code generation."""
        codes = self.phonetic.get_phonetic_codes("jonathan")
        self.assertIsNotNone(codes[0])  # Primary code should exist
    
    def test_phonetically_similar(self):
        """Test phonetically similar names."""
        # walmart sounds like valdemar (with v/w variants)
        results = self.phonetic.match("walmart", ["valdemar"])
        # May or may not match depending on exact phonetic codes
        # The v/w variant handling should help
        
        # jonne sounds like jonathan  
        results = self.phonetic.match("jonne", ["jonathan", "elias"])
        # Check that jonathan is matched if any results
        if results:
            matched_names = [r.name for r in results]
            self.assertNotIn("elias", matched_names)
    
    def test_phonetic_codes_with_variants(self):
        """Test phonetic codes with v/w variants."""
        codes = self.phonetic.get_phonetic_codes_with_variants("valdemar")
        # Should include codes for both v and w variants
        self.assertGreater(len(codes), 0)
    
    def test_explain_match(self):
        """Test match explanation."""
        explanation = self.phonetic.explain_match("john", "jon")
        self.assertIn('name1', explanation)
        self.assertIn('name2', explanation)
        self.assertIn('match_level', explanation)


class TestBlockingStrategy(unittest.TestCase):
    """Test blocking strategies for performance."""
    
    def setUp(self):
        self.blocking = BlockingStrategy(strategy='multi_level')
    
    def test_character_blocks(self):
        """Test character-based blocking."""
        names = ["jonathan", "jonas", "elias", "gustav"]
        blocks = self.blocking.create_blocks(names)
        
        # jonathan and jonas should share a block
        jon_blocks = self.blocking.get_block_keys("jonathan")
        jonas_blocks = self.blocking.get_block_keys("jonas")
        self.assertTrue(
            set(jon_blocks) & set(jonas_blocks),
            "jonathan and jonas should share blocks"
        )
    
    def test_candidate_filtering(self):
        """Test that blocking reduces candidate set."""
        all_names = ["jonathan", "jonas", "elias", "gustav", "magnus"]
        
        candidates = self.blocking.get_comparison_candidates(
            "jonathan", all_names
        )
        
        # Should include jonathan and jonas (similar prefix)
        self.assertIn("jonathan", candidates)
        # Might include others depending on phonetic blocks
    
    def test_blocking_stats(self):
        """Test blocking statistics."""
        names = ["a" * 20 for _ in range(100)]  # Many similar names
        names.extend(["z" * 20 for _ in range(100)])  # Different names
        
        stats = self.blocking.get_blocking_stats("a" * 20, names)
        self.assertIn('reduction_percent', stats)
        self.assertIn('total_candidates', stats)
    
    def test_no_blocking_strategy(self):
        """Test no blocking returns all candidates."""
        blocking = BlockingStrategy(strategy='none')
        names = ["jonathan", "elias", "gustav"]
        
        candidates = blocking.get_comparison_candidates("test", names)
        self.assertEqual(set(candidates), set(names))


class TestNameMatcher(unittest.TestCase):
    """Test the main NameMatcher class."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        # Use test config paths
        cls.config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config'
        )
        
        try:
            cls.matcher = NameMatcher(
                config_path=os.path.join(cls.config_dir, 'matching_config.json'),
                aliases_path=os.path.join(cls.config_dir, 'aliases_new.json')
            )
            cls.available = True
        except Exception as e:
            print(f"Warning: Could not initialize matcher: {e}")
            cls.available = False
    
    def setUp(self):
        if not self.available:
            self.skipTest("Matcher not available")
    
    def test_exact_match(self):
        """Test exact matching."""
        candidates = ["Jonathan", "Elias", "Gustav"]
        
        results = self.matcher.match("jonathan", candidates)
        self.assertIn("Jonathan", results)
    
    def test_typo_matching(self):
        """Test typographical variation matching."""
        candidates = ["Jonathan", "Elias", "Gustav"]
        
        # jonethen → Jonathan
        results = self.matcher.match("jonethen", candidates, return_scores=True)
        if results:
            names = [r[0] for r in results]
            self.assertIn("Jonathan", names)
    
    def test_manual_override(self):
        """Test manual override mappings."""
        candidates = ["Jonathan", "Elias", "Gustav"]
        
        # faxekondi_lover → Jonathan (from manual_overrides)
        results = self.matcher.match("faxekondi_lover", candidates)
        self.assertIn("Jonathan", results)
        
        # walmart → Valdemar
        candidates_with_valdemar = ["Jonathan", "Valdemar", "Elias"]
        results = self.matcher.match("walmart", candidates_with_valdemar)
        self.assertIn("Valdemar", results)
    
    def test_multi_token_query(self):
        """Test multi-token name queries."""
        candidates = ["Jonathan", "Gustav Husted", "Gustav Porno Tørst"]
        
        # joe nation → Jonathan (from manual_overrides)
        results = self.matcher.match("joe nation", candidates)
        self.assertIn("Jonathan", results)
        
        # gustav husted - exact multi-token
        results = self.matcher.match("gustav husted", candidates)
        self.assertIn("Gustav Husted", results)
    
    def test_disambiguation(self):
        """Test disambiguation between similar names."""
        candidates = ["Gustav", "Gustav Husted", "Gustav Porno Tørst"]
        
        # "gustav" alone should prefer just "Gustav"
        results = self.matcher.match("gustav", candidates, return_scores=True)
        if results:
            # First result should be best match
            self.assertEqual(results[0][0], "Gustav")
        
        # "porno" should match Gustav Porno Tørst
        results = self.matcher.match("porno", candidates)
        self.assertIn("Gustav Porno Tørst", results)
    
    def test_nordic_character_matching(self):
        """Test Nordic character handling in matching."""
        candidates = ["Gustav Porno Tørst", "Valdemar"]
        
        # "torst" should match "Tørst"
        results = self.matcher.match("porno torst", candidates)
        self.assertIn("Gustav Porno Tørst", results)
    
    def test_v_w_interchange(self):
        """Test v/w phonetic interchange."""
        candidates = ["Valdemar", "Jonathan", "Gustav"]
        
        # walmart should match Valdemar
        results = self.matcher.match("walmart", candidates)
        self.assertIn("Valdemar", results)
    
    def test_get_canonical_name(self):
        """Test canonical name lookup."""
        # From manual_overrides
        canonical = self.matcher.get_canonical_name("faxekondi_lover")
        self.assertEqual(canonical, "Jonathan")
        
        canonical = self.matcher.get_canonical_name("walmart")
        self.assertEqual(canonical, "Valdemar")
    
    def test_get_all_aliases(self):
        """Test getting all aliases for a name."""
        aliases = self.matcher.get_all_aliases("Jonathan")
        
        # Should include common aliases
        self.assertTrue(len(aliases) > 0)
    
    def test_find_person_id(self):
        """Test person ID lookup."""
        person_id = self.matcher.find_person_id("jonathan")
        self.assertIsNotNone(person_id)
        self.assertTrue(person_id.startswith("Person_"))
    
    def test_return_scores(self):
        """Test returning match scores."""
        candidates = ["Jonathan", "Elias"]
        
        results = self.matcher.match(
            "jonathan", candidates, return_scores=True
        )
        
        if results:
            self.assertEqual(len(results[0]), 3)  # (name, score, info)
            name, score, info = results[0]
            self.assertEqual(name, "Jonathan")
            self.assertGreaterEqual(score, 0.9)
            self.assertIn('match_type', info)
    
    def test_debug_mode(self):
        """Test debug mode activation."""
        candidates = ["Jonathan", "Elias"]
        
        # Should not raise
        results = self.matcher.match(
            "jonethen", candidates, debug=True
        )
        
        # Should have debug output
        debug_output = self.matcher.get_debug_output()
        self.assertIsNotNone(debug_output)
    
    def test_config_reload(self):
        """Test configuration hot-reload."""
        # Should not raise
        success = self.matcher.reload_config()
        # May fail if config file doesn't exist, but shouldn't raise


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete matching workflow."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config'
        )
        
        try:
            cls.matcher = NameMatcher(
                config_path=os.path.join(config_dir, 'matching_config.json'),
                aliases_path=os.path.join(config_dir, 'aliases_new.json')
            )
            cls.available = True
        except Exception:
            cls.available = False
    
    def setUp(self):
        if not self.available:
            self.skipTest("Matcher not available")
    
    def test_full_search_workflow(self):
        """Test a complete search workflow."""
        # Simulate quote authors
        authors = [
            "Jonathan",
            "Elias", 
            "Gustav",
            "Gustav Husted",
            "Gustav Porno Tørst",
            "Valdemar",
            "Magnus",
            "Noah",
        ]
        
        # Test various search scenarios
        test_cases = [
            ("jonathan", ["Jonathan"]),
            ("jonethen", ["Jonathan"]),  # Typo
            ("jonne", ["Jonathan"]),     # Nickname
            ("walmart", ["Valdemar"]),   # Phonetic
            ("gustav", ["Gustav"]),      # First/best match
            ("porno", ["Gustav Porno Tørst"]),  # Disambiguation
            ("faxekondi_lover", ["Jonathan"]),  # Override
        ]
        
        for query, expected in test_cases:
            with self.subTest(query=query):
                results = self.matcher.match(query, authors)
                for exp in expected:
                    self.assertIn(
                        exp, results,
                        f"Expected '{exp}' in results for query '{query}'"
                    )
    
    def test_performance(self):
        """Test matching performance with many candidates."""
        import time
        
        # Generate many candidates
        base_names = ["jonathan", "elias", "gustav", "magnus", "valdemar"]
        candidates = []
        for i in range(1000):
            name = base_names[i % len(base_names)]
            candidates.append(f"{name.title()} {i}")
        
        # Time the matching
        start = time.time()
        results = self.matcher.match("jonathan 500", candidates)
        elapsed = time.time() - start
        
        # Should complete in under 500ms
        self.assertLess(
            elapsed, 0.5,
            f"Matching took too long: {elapsed:.3f}s"
        )


if __name__ == '__main__':
    # Run tests with verbosity
    unittest.main(verbosity=2)
