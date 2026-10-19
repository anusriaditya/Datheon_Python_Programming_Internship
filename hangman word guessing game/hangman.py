#!/usr/bin/env python3
"""
Hangman Word Guessing Game (Console)
====================================
A classic terminal-based Hangman game where the player attempts to guess
a secret word letter by letter within 6 attempts.

Features:
- Visual ASCII gallows art that updates with each incorrect guess (0 to 6 mistakes).
- Masked word display with spaces (e.g. '_ A _ H E O N').
- Guessed letters tracking with duplicate penalty prevention.
- Input validation (alphabetical single character only).
- Word pool loaded from 'words.txt' with robust built-in fallback.
- Multi-round session tracking (Wins / Losses score).
- Clean, cross-platform terminal output (compatible with Windows cp1252 / UTF-8).
"""

import os
import random
import sys

# Ensure UTF-8 output encoding where supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Maximum incorrect attempts allowed before game over
MAX_MISTAKES = 6

# ASCII stages corresponding to mistakes 0 through 6
STAGES = [
    # 0 mistakes: Empty gallows
    r"""
      +---+
      |   |
          |
          |
          |
          |
    =========
    """,
    # 1 mistake: Head
    r"""
      +---+
      |   |
      O   |
          |
          |
          |
    =========
    """,
    # 2 mistakes: Head and torso
    r"""
      +---+
      |   |
      O   |
      |   |
          |
          |
    =========
    """,
    # 3 mistakes: Head, torso, and left arm
    r"""
      +---+
      |   |
      O   |
     /|   |
          |
          |
    =========
    """,
    # 4 mistakes: Head, torso, and both arms
    r"""
      +---+
      |   |
      O   |
     /|\  |
          |
          |
    =========
    """,
    # 5 mistakes: Head, torso, both arms, and left leg
    r"""
      +---+
      |   |
      O   |
     /|\  |
     /    |
          |
    =========
    """,
    # 6 mistakes: Full hangman (Game Over)
    r"""
      +---+
      |   |
      O   |
     /|\  |
     / \  |
          |
    =========
    """,
]

# Fallback word list if words.txt is missing or empty
DEFAULT_WORDS = [
    # Animals
    "ELEPHANT", "GIRAFFE", "KANGAROO", "DOLPHIN", "CHEETAH", "PENGUIN",
    "CHAMELEON", "OCTOPUS", "FLAMINGO", "HEDGEHOG", "SQUIRREL", "LEOPARD",
    # Science & Tech
    "ALGORITHM", "COMPUTER", "PYTHON", "VARIABLE", "FUNCTION", "DATABASE",
    "GRAVITY", "ASTRONOMY", "MOLECULE", "QUANTUM", "ROBOTICS", "SATELLITE",
    # Nature & Geography
    "VOLCANO", "GLACIER", "MOUNTAIN", "WATERFALL", "HORIZON", "RAINBOW",
    "BLIZZARD", "AVALANCHE", "ISLAND", "CANYON", "HURRICANE", "FOREST",
    # Everyday & Adventure
    "TREASURE", "MYSTERY", "ADVENTURE", "LABYRINTH", "CHALLENGE", "JOURNEY",
    "PHANTOM", "VOYAGE", "FORTRESS", "DISCOVERY", "ECLIPSE", "PYRAMID",
    "UMBRELLA", "TELESCOPE", "BACKPACK", "COMPASS", "LIGHTHOUSE", "SANDWICH",
]


def load_words(filepath="words.txt"):
    """
    Load a list of secret words from a file.
    Falls back to DEFAULT_WORDS if the file cannot be read or is empty.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, filepath)

    if os.path.isfile(full_path):
        try:
            with open(full_path, "r", encoding="utf-8") as file:
                words = [
                    line.strip().upper()
                    for line in file
                    if line.strip() and not line.strip().startswith("#") and line.strip().isalpha()
                ]
                if words:
                    return words
        except Exception as error:
            print(f"[Warning] Could not load words from '{filepath}': {error}")

    return DEFAULT_WORDS


def get_random_word(word_list):
    """
    Select and return a random word from the provided word list.
    """
    return random.choice(word_list).upper()


def get_masked_word(secret_word, guessed_letters):
    """
    Generate masked string representation of the word (e.g. '_ A _ H E O N').
    Reveals letters present in guessed_letters, masks unrevealed letters with '_'.
    """
    return " ".join(letter if letter in guessed_letters else "_" for letter in secret_word)


def is_word_guessed(secret_word, guessed_letters):
    """
    Check if all unique letters of the secret word have been guessed.
    """
    return set(secret_word).issubset(guessed_letters)


def display_game_screen(mistakes, secret_word, guessed_letters):
    """
    Render current game state: ASCII art, masked word, attempts remaining, and guessed letters.
    """
    print("\n" + "=" * 45)
    print(STAGES[mistakes])
    print(f" Word: {get_masked_word(secret_word, guessed_letters)}")
    print(f" Remaining Mistakes Allowed: {MAX_MISTAKES - mistakes} / {MAX_MISTAKES}")

    if guessed_letters:
        sorted_guesses = sorted(guessed_letters)
        print(f" Guessed Letters: {', '.join(sorted_guesses)}")
    else:
        print(" Guessed Letters: (None yet)")
    print("=" * 45)


def get_valid_guess(guessed_letters):
    """
    Prompt the user for a single letter guess and validate it.
    Prevents duplicate penalty deduction by reprompting if already guessed.
    """
    while True:
        try:
            raw_input = input("\n>>> Enter your guess (A-Z): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGame interrupted. Exiting... Goodbye!")
            sys.exit(0)

        # Check for empty input
        if not raw_input:
            print("[!] No input detected. Please enter a single letter.")
            continue

        # Check for multi-character or non-alphabetic input
        if len(raw_input) != 1 or not raw_input.isalpha():
            print("[!] Invalid input! Please enter a single alphabetical character (A-Z).")
            continue

        guess = raw_input.upper()

        # Check if already guessed (prevents duplicate penalty deduction)
        if guess in guessed_letters:
            print(f"[*] You already guessed '{guess}'. No penalty deducted! Try a different letter.")
            continue

        return guess


def play_round(secret_word):
    """
    Execute a single round of Hangman.
    Returns True if the player won, False if the player lost.
    """
    mistakes = 0
    guessed_letters = set()

    print("\n[*] A secret word has been selected! Good luck!")

    while mistakes < MAX_MISTAKES:
        display_game_screen(mistakes, secret_word, guessed_letters)

        guess = get_valid_guess(guessed_letters)
        guessed_letters.add(guess)

        if guess in secret_word:
            print(f"[+] Excellent! Letter '{guess}' is in the word!")
            if is_word_guessed(secret_word, guessed_letters):
                # Player won!
                display_game_screen(mistakes, secret_word, guessed_letters)
                print("\n" + "*" * 45)
                print("   CONGRATULATIONS! YOU WON!   ")
                print(f"   You guessed the word: '{secret_word}'!   ")
                print("*" * 45)
                return True
        else:
            mistakes += 1
            print(f"[-] Oops! Letter '{guess}' is NOT in the word.")

    # Max mistakes reached -> Game Over
    display_game_screen(mistakes, secret_word, guessed_letters)
    print("\n" + "!" * 45)
    print("   GAME OVER! You've run out of attempts!   ")
    print(f"   The secret word was: '{secret_word}'   ")
    print("!" * 45)
    return False


def print_banner():
    """Print the welcome banner for the Hangman game."""
    banner = r"""
  _    _                                         
 | |  | |                                        
 | |__| | __ _ _ __   __ _ _ __ ___   __ _ _ __  
 |  __  |/ _` | '_ \ / _` | '_ ` _ \ / _` | '_ \ 
 | |  | | (_| | | | | (_| | | | | | | (_| | | | |
 |_|  |_|\__,_|_| |_|\__, |_| |_| |_|\__,_|_| |_|
                      __/ |                      
                     |___/                       
    """
    print(banner)
    print("Welcome to Terminal Hangman!")
    print(f"Guess the hidden word letter by letter within {MAX_MISTAKES} mistakes.")
    print("Duplicate guesses will NOT deduct any attempts.")


def main():
    """Main game loop managing replayability and session score."""
    print_banner()
    words = load_words("words.txt")

    games_played = 0
    games_won = 0

    while True:
        secret_word = get_random_word(words)
        won = play_round(secret_word)

        games_played += 1
        if won:
            games_won += 1

        print("\n" + "-" * 30)
        print(f"Session Score: {games_won} Win(s) / {games_played} Game(s)")
        print("-" * 30)

        # Ask to play again
        while True:
            try:
                choice = input("\nWould you like to play again? (y/n): ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\n\nThanks for playing! Goodbye!")
                return

            if choice in ("y", "yes"):
                break
            elif choice in ("n", "no", "q", "quit", "exit"):
                print("\nThanks for playing Hangman! See you next time!")
                return
            else:
                print("Please enter 'y' to play again or 'n' to quit.")


if __name__ == "__main__":
    main()
