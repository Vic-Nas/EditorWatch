# EditorWatch

**Making cheating harder than learning.**

A code process monitor for programming assignments. It observes *how* code is written, not just the final result—making academic dishonesty require the same effort as honest learning.

## The Idea

Traditional plagiarism detection only sees the destination. EditorWatch sees the journey.

By logging coding patterns (typing rhythm, edit sequences, focus changes), it creates an "effort barrier": to game the system, students must invest enough time and cognitive load that they might as well just learn the material.

## What It Is

- 🔌 **VS Code Extension** - Logs editor events during assignment work
- 🔒 **Privacy-First** - No webcam, no mic, no system-wide monitoring
- 📊 **Pattern Analysis** - Detects copy-paste bursts, unnatural typing, missing corrections
- 🎓 **Pedagogical** - Designed to encourage learning, not just catch cheaters

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

## How It Works

**For Students:**
1. Download assignment folder (contains `.editorwatch` config)
2. Open in VS Code
3. Extension shows one-time popup: "Enable monitoring?"
4. Work normally - events logged locally
5. Click "Submit" when done

**For Instructors:**
1. Create assignment in dashboard
2. Generate starter.zip with config file
3. Upload to LMS
4. Review submissions after deadline
5. See timeline visualizations and metrics

## Example Metrics

```
Incremental Score: 0.85 (0=sudden, 1=gradual)
Typing Variance: 0.62 (low=robotic)
Error Correction: 0.18 (low=no mistakes)
Paste Bursts: 2
```

Normal student: gradual development, varied typing, some errors.  
Suspicious: large paste bursts, perfect code, no corrections.

## Status

**Early prototype. Intentionally simple.**

Total scope: ~1000 lines (150 JS + 850 Python).

If you're:
- **A student** - This would catch patterns, but understands gray areas
- **An instructor** - This gives you data to start conversations, not verdicts
- **A developer** - Read [ARCHITECTURE.md](ARCHITECTURE.md) to see how simple it is

## Installation

**Not ready yet.** Currently documenting the design.

When ready:
1. Install VS Code extension from marketplace
2. Deploy backend (Railway template)
3. Configure assignment in dashboard

## Philosophy

> "If you're smart enough to convincingly fake incremental development, you've learned enough to do the assignment."

I'm not trying to catch every cheater. I'm trying to make cheating require genuine engagement with the material.

## Privacy

- Only logs editor events in assignment workspace
- No screen/webcam/microphone access
- Student sees all data before submission
- Data encrypted at rest
- Auto-deleted after grading period

## Limitations

**Can't detect:**
- Manual transcription (student types from source)
- Offline coding → paste final result
- AI-assisted with careful editing
- Legitimate pair programming

**May flag incorrectly:**
- Fast, experienced coders
- Different work styles (ADHD, dyslexia)
- Legitimate copy-paste from documentation

**Not a silver bullet.** Just one more data point for instructors.

## License

Dual-licensed: MIT for education, paid for commercial use.

See [LICENSE.md](LICENSE.md) for details.

## Links

- [Architecture](ARCHITECTURE.md) - Technical design
- [Issues](../../issues) - Discussions on ethics, implementation, gaming

## Should This Exist?

Good question. Read the docs, think about the tradeoffs, decide for yourself.

The code is transparent. The design is debatable. The conversation is necessary.

---

*"Your effort is the signal."*
