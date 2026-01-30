# EditorWatch Extension

Monitor your coding process for programming assignments.

## For Students

### Installation

**From VS Code Marketplace:**
1. Open VS Code
2. Press `Ctrl+Shift+X` (or `Cmd+Shift+X` on Mac)
3. Search "EditorWatch"
4. Click "Install"

### How to Use

1. **Get files from your professor:**
   - `.editorwatch` config file
   - Your access code (via email)

2. **Place `.editorwatch` in your assignment folder:**
   ```
   my-homework/
   ├── .editorwatch    ← Put it here
   ├── main.py
   └── ...
   ```

3. **Open the folder in VS Code:**
   ```bash
   code my-homework
   ```

4. **Enter your access code** when prompted

5. **Code normally** - you'll see 👁️ in the status bar

6. **Submit when done** by clicking the 👁️ icon

### Troubleshooting

**Extension not activating?**
- Ensure `.editorwatch` is in the root folder
- File must be named exactly `.editorwatch`
- Reload VS Code: `Ctrl+Shift+P` → "Reload Window"

**Can't submit?**
- Check internet connection
- Verify deadline hasn't passed
- Make sure you've written some code

## For Professors

See the main [README](../README.md) for server setup and assignment creation.

## Privacy

- Only active when `.editorwatch` file is present
- You must explicitly enable monitoring
- Only tracks files matching patterns (e.g., `*.py`)
- Data deleted after grading period
- Open source - see what it does: [GitHub](https://github.com/Vic-Nas/EditorWatch)

## Commands

- `EditorWatch: Submit Assignment` - Submit your work
- `EditorWatch: Disable Monitoring` - Stop tracking
- `EditorWatch: Status` - Check monitoring status

## License

Free for educational use. See [LICENCE.md](../LICENCE.md).