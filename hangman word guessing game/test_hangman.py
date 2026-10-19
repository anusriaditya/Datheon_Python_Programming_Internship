"""
Unit and Integration Tests for Hangman Game
"""

import unittest
from unittest.mock import patch
import hangman

class TestHangmanGame(unittest.TestCase):
    def test_stages_count(self):
        """Verify we have exactly 7 stages (0 through 6 mistakes)."""
        self.assertEqual(len(hangman.STAGES), 7)
        self.assertEqual(hangman.MAX_MISTAKES, 6)

    def test_masked_word(self):
        """Verify masked word string formatting."""
        secret = "PYTHON"
        self.assertEqual(hangman.get_masked_word(secret, set()), "_ _ _ _ _ _")
        self.assertEqual(hangman.get_masked_word(secret, {"P", "O"}), "P _ _ _ O _")
        self.assertEqual(hangman.get_masked_word(secret, {"P", "Y", "T", "H", "O", "N"}), "P Y T H O N")
        
        # Test masking when some letters are revealed
        secret2 = "PANTHEON"
        guessed = {"A", "H", "E", "O", "N"}
        # P -> _, A -> A, N -> N, T -> _, H -> H, E -> E, O -> O, N -> N
        self.assertEqual(hangman.get_masked_word(secret2, guessed), "_ A N _ H E O N")

    def test_is_word_guessed(self):
        """Verify word guessed completion check."""
        secret = "CODE"
        self.assertFalse(hangman.is_word_guessed(secret, {"C", "O"}))
        self.assertFalse(hangman.is_word_guessed(secret, {"C", "O", "D"}))
        self.assertTrue(hangman.is_word_guessed(secret, {"C", "O", "D", "E"}))
        self.assertTrue(hangman.is_word_guessed(secret, {"C", "O", "D", "E", "Z"}))

    def test_load_words(self):
        """Verify word loader reads from words.txt and strips non-words."""
        words = hangman.load_words("words.txt")
        self.assertGreater(len(words), 20)
        for w in words:
            self.assertTrue(w.isalpha())
            self.assertTrue(w.isupper())

    def test_load_words_fallback(self):
        """Verify fallback when file does not exist."""
        words = hangman.load_words("non_existent_file.xyz")
        self.assertEqual(words, hangman.DEFAULT_WORDS)

    @patch("builtins.input", side_effect=["", "123", "ab", "!", "e"])
    def test_get_valid_guess_rejection_and_acceptance(self, mock_input):
        """Verify invalid inputs (empty, numbers, multi-character, symbols) are rejected until a single letter is given."""
        guessed = set()
        guess = hangman.get_valid_guess(guessed)
        self.assertEqual(guess, "E")

    @patch("builtins.input", side_effect=["a", "A", "b"])
    def test_duplicate_guess_prevention(self, mock_input):
        """Verify duplicate guess does not get returned as new guess."""
        guessed = {"A"}
        guess = hangman.get_valid_guess(guessed)
        self.assertEqual(guess, "B")

    @patch("hangman.get_valid_guess", side_effect=["C", "A", "T"])
    def test_play_round_win(self, mock_guess):
        """Simulate a winning round."""
        won = hangman.play_round("CAT")
        self.assertTrue(won)

    @patch("hangman.get_valid_guess", side_effect=["Z", "X", "Y", "W", "V", "U"])
    def test_play_round_lose(self, mock_guess):
        """Simulate a losing round after 6 mistakes."""
        won = hangman.play_round("CAT")
        self.assertFalse(won)

    @patch("hangman.get_valid_guess", side_effect=["C", "Z", "A", "X", "T"])
    def test_play_round_mixed_win(self, mock_guess):
        """Simulate a round with both correct and incorrect guesses resulting in a win."""
        won = hangman.play_round("CAT")
        self.assertTrue(won)


if __name__ == "__main__":
    unittest.main()
