# EditorWatch

**Making cheating harder than learning.**

EditorWatch is an educational code process monitor for programming assignments. It observes *how* code is written, not just the final result—making academic dishonesty require the same effort as honest learning.

## The Core Idea

Traditional plagiarism detection only sees the destination. EditorWatch sees the journey.

By logging coding patterns (typing rhythm, edit sequences, focus changes), it creates an "effort barrier": students who try to game the system must invest enough time and cognitive load that they might as well just learn the material.

## What It Is

- 🔌 **VS Code Extension**: Logs editor events during assignment work
- 🔒 **Privacy-First**: No webcam, no mic, no system-wide monitoring
- 📊 **Pattern Analysis**: Detects copy-paste bursts, unnatural typing, and missing corrections
- 🎓 **Pedagogical**: Designed to encourage learning, not just catch cheaters

## What It Isn't

- ❌ Not automatic punishment
- ❌ Not foolproof detection
- ❌ Not surveillance theater
- ❌ Not a replacement for good pedagogy
- ❌ Not complex (intentionally ~1000 lines of code)

## Tech Stack

**Simple and minimal:**
- Extension: Plain JavaScript (~150 lines)
- Backend: Python/Flask (~500 lines)
- Analysis: NumPy/Plotly (~300 lines)
- Database: PostgreSQL + SQLite
- Deploy: Railway (~$5/month)

No TypeScript. No React (optional). No microservices. No bloat.

## Status

**Early prototype. Intentionally simple.**

Total scope: ~1000 lines of code (150 JS + 850 Python). The power is in the idea, not complexity.

If you're:
- A student who's copied code before → This tool would catch patterns, but also understands gray areas
- An instructor → This gives you data to start conversations, not verdicts
- A developer → Read ARCHITECTURE.md to see how simple it actually is

## Philosophy

> "If you're smart enough to convincingly fake incremental development, you've learned enough to just do the assignment."

We're not trying to catch every cheater. We're trying to make cheating require genuine engagement with the material.

## Quick Links

- [Architecture Overview](ARCHITECTURE.md) - System design and technical details
- [Open Issues](https://github.com/yourusername/editorwatch/issues) - Discussions on ethics, implementation, gaming
- [License](LICENSE) - MIT (open source, audit the code yourself)

## Should This Exist?

Good question. Read the architecture docs, think about the tradeoffs, and decide for yourself.

The code is transparent. The design is debatable. The conversation is necessary.

---

*"Your effort is the signal."*
