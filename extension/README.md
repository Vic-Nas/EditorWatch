# EditorWatch VS Code Extension

Monitor coding process for programming assignments to discourage cheating.

## For Students

### Installation

1. Download the extension from VS Code Marketplace (search "EditorWatch")
2. Or install locally:
   ```bash
   cd extension
   npm install
   code --install-extension .
   ```

### Usage

1. **Get the `.editorwatch` file from your professor**
   - They will give you a file like `CS101_abc123.editorwatch`

2. **Place it in your project folder**
   ```
   your-homework/
   ├── .editorwatch          ← Put it here (rename to just .editorwatch)
   ├── main.py
   └── ...
   ```

3. **Open the folder in VS Code**
   ```bash
   code your-homework
   ```

4. **Accept the monitoring prompt**
   - A popup will appear asking you to enable monitoring
   - Click "Enable" to start tracking

5. **You'll see an eye icon** (👁️) in the bottom-right status bar
   - This means monitoring is active
   - Click it anytime to submit

6. **Work on your assignment normally**
   - The extension tracks your edits silently
   - No interruptions while you code

7. **When done, click the eye icon to submit**
   - Enter your matricule (and any other required info)
   - Click "Submit"
   - ✅ Done!

### Troubleshooting

**Extension doesn't activate?**
- Make sure the file is named exactly `.editorwatch` (no extra characters)
- Check it's in the root of your workspace folder
- Reload VS Code: `Cmd+Shift+P` → "Reload Window"
- Check Output panel: View → Output → Select "EditorWatch"

**Eye icon doesn't appear?**
- Open the folder (not just the file)
- The `.editorwatch` file must be in the root
- Deadline hasn't passed
- Run command: `Cmd+Shift+P` → "EditorWatch: Status"

**Submit button does nothing?**
- Make sure you've written some code
- Check you have internet connection
- Verify the server URL in `.editorwatch` is correct

**Can't find the .editorwatch file after downloading?**
- It might be in your Downloads folder
- It might have been renamed (like `CS101_abc123.editorwatch`)
- Rename it to just `.editorwatch` (with the dot)
- On Windows, you might need to "show hidden files" to see it

### Commands

- `EditorWatch: Submit Assignment` - Submit your work
- `EditorWatch: Disable Monitoring` - Stop tracking (can't submit after this)
- `EditorWatch: Status` - Check if monitoring is active

### Privacy

- Only tracked while you work on THIS specific assignment
- Only files matching the patterns in `.editorwatch` are tracked (e.g., `*.py`)
- Code is encrypted before upload
- Data deleted after grading period

---

## For Professors

### Setup

1. Deploy the EditorWatch server (see main README)
2. Install this extension from source:
   ```bash
   cd extension
   npm install
   npm run compile  # If using TypeScript
   code --install-extension .
   ```

### Creating Assignments

1. Login to your EditorWatch dashboard
2. Click "Create Assignment"
3. Fill in details:
   - Assignment name
   - Course
   - Deadline
   - Required student info (matricule, name, email)
   - File patterns to track (e.g., `*.py`, `*.js`)
4. Click "Create"
5. **Download the `.editorwatch` config file**
6. Share this file with students (via email, LMS, etc.)

### Viewing Submissions

1. Dashboard → Click "View Submissions" for any assignment
2. See list of all submissions with metrics
3. Click "View Detail" to see:
   - Student info
   - Code timeline visualization
   - Submitted code
   - Analysis metrics (typing patterns, paste detection, etc.)

### Metrics Explained

- **Incremental Score (0-1)**: How gradually the code was written. Low = suspicious large pastes
- **Typing Variance (0-1)**: Natural human typing variation. Low = robotic/pasted
- **Error Correction Ratio (0-1)**: Amount of trial/error. Low = no mistakes (suspicious)
- **Paste Burst Count**: Number of large paste events. High = likely copied

---

## Development

### Building from source

```bash
cd extension
npm install
npm run compile  # For TypeScript

# Package
vsce package

# Install locally
code --install-extension editorwatch-0.1.0.vsix
```

### Testing

```bash
# Open extension folder in VS Code
code extension/

# Press F5 to launch Extension Development Host
# This opens a new VS Code window with the extension loaded

# Create test project:
mkdir test-project
cp example.editorwatch test-project/.editorwatch
code test-project/  # Open in the Extension Development Host
```

### Publishing

```bash
vsce publish
```

---

## FAQ

**Q: Can students bypass this?**
A: No system is perfect, but:
- Extension requires explicit consent (ethical)
- Tracks detailed keystroke patterns hard to fake
- Detects paste bursts and unusual patterns
- Combine with other integrity measures

**Q: What if a student doesn't use VS Code?**
A: They can use any editor they want. EditorWatch is optional and students must consent. Consider it one tool among many for academic integrity.

**Q: Is this spyware?**
A: No:
- Students must explicitly enable it
- Only tracks specific assignment files
- Data encrypted and deleted after grading
- Open source - you can verify what it does

**Q: What if students collaborate legitimately?**
A: Metrics help identify copy/paste, not collaboration. Use your judgment. The timeline visualization helps you see if they wrote it themselves.

---

## License

See `LICENCE.md` in root - Free for education, paid for commercial use.

## Support

- GitHub Issues: https://github.com/Vic-Nas/EditorWatch
- Email: [Your Email]