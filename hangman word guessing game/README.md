# Console Hangman Word Guessing Game

A terminal-based Hangman game developed in Python where the player attempts to guess a secret word letter by letter within **6 allowed mistakes**.

---

## 🎮 Features

- **Visual ASCII Gallows Art:** 7 progressive stages (0 to 6 mistakes) that dynamically update with each incorrect guess.
- **Masked Word Display:** Hidden letters shown with underscores and revealed letters capitalized with spacing (e.g. `_ A _ H E O N`).
- **Guessed Letters Tracking:** Displays all previously guessed letters in alphabetical order.
- **Duplicate Penalty Prevention:** Entering an already guessed letter alerts the player and deducts **zero** penalty attempts.
- **Input Validation:** Gracefully rejects blank inputs, numbers, multi-character strings, or special symbols without penalty.
- **Customizable Word List:** Loads words from `words.txt` with a comprehensive built-in fallback word list.
- **Session Score Tracker:** Tracks your wins and total games across multiple rounds.
- **Cross-Platform Compatibility:** Runs seamlessly across Windows (PowerShell, CMD), macOS, and Linux terminals.

---

## 🚀 How to Run

Ensure you have Python 3 installed, then run:

```bash
python hangman.py
```

### Running Tests
To run the automated unit and integration tests:

```bash
python -m unittest test_hangman.py
```

---

## 📂 Project Structure

```text
├── hangman.py         # Main game script containing all game logic & ASCII art
├── words.txt          # Word list categorized by topics (customizable)
├── test_hangman.py    # Unit & integration test suite
└── README.md          # Documentation & instructions
```

---

## 📝 Customizing the Secret Words

You can easily add your own words to `words.txt`. Simply add one word per line (letters only). Empty lines and lines starting with `#` are treated as comments and ignored.
