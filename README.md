# EditorWatch

[live server](https://editorwatch.up.railway.app/)

**Code authenticity monitor for programming assignments** - Track how students write code, not just what they write.

## Quick Deploy

### Option 1: Railway (Recommended - Free Tier Available)

1. Fork this repo
2. Go to [Railway.app](https://railway.com?referralCode=ZIdvo-) → New Project → Deploy from GitHub
3. Add these environment variables:
   ```
   DATABASE_URL=<railway-postgres-url>
   REDIS_URL=<railway-redis-url>
   SECRET_KEY=<random-string>
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=<your-password>
   ```
4. Railway auto-detects the Procfile and deploys server
5. For workers, custom start command:
```bash
rq worker analysis --url $REDIS_URL
```
1GB RAM, 1GB Memory
   
![Image description](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/12t02pxi2zupbis816re.png)
### Option 2: Your Own Server

```bash
git clone https://github.com/Vic-Nas/EditorWatch
cd EditorWatch

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL='postgresql://user:pass@host/db'
export REDIS_URL='redis://host:6379'
export SECRET_KEY='your-secret-key'
export ADMIN_USERNAME='admin'
export ADMIN_PASSWORD='your-password'

# Run migrations
python -c "from app import app, db; app.app_context().push(); db.create_all()"

# Start web server
gunicorn app:app &

# Start worker
python -m rq.worker analysis --url $REDIS_URL
```
## Usage

### For Educators

1. **Login** to dashboard at `https://your-server.com`
2. **Create assignment**:
   - Enter course name, assignment name, deadline
   - Customize file patterns to track (e.g., `*.py`, `*.js`)
   - Paste student list (email,first,last format)
   - System generates unique access codes
3. **Download files**:
   - `editorwatch` config file → share with all students
   - `codes.csv` → contains all student access codes
   - - Editable template email + toggle mailto(s)
4. **Students submit** → Auto-analyzed in background
5. **Review submissions** → See scores, flags, visualizations

### For Students

1. Install "EditorWatch" extension from VS Code Marketplace
2. Place `editorwatch` file in assignment folder root
3. Enter your access code when prompted
4. Code normally - extension tracks in background
5. Click 👁️ icon to submit when done

## What Gets Analyzed

- **Incremental Score** (0-10): Gradual vs sudden code appearance
- **Typing Variance** (0-10): Natural vs robotic patterns
- **Error Correction** (0-10): Trial-and-error vs perfect-first-time
- **Work Sessions** (0-10): Multiple sessions vs one continuous session
- **Paste Bursts**: Count of large code insertions
- **Overall Score** (0-10): Weighted combination of above

**Scoring**: 0-3 = Suspicious | 4-6 = Review | 7-10 = Likely Authentic

## Architecture

```
┌─────────────────┐
│  VS Code Ext    │ → Tracks edits
│  (student side) │ → Submits events to server
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Flask Server   │ → Receives submissions
│                 │ → Queues analysis jobs
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RQ Worker      │ → Analyzes patterns
│  (background)   │ → Generates visualizations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Dashboard      │ → Teacher reviews results
│  (web UI)       │ → Export data as JSON
└─────────────────┘
```

## Files Explained

- `app.py` - Flask web server (REST API + dashboard)
- `models.py` - Database schema (SQLAlchemy)
- `analysis/metrics.py` - Core detection algorithms
- `analysis/worker.py` - Background analysis queue (RQ)
- `analysis/visualizer.py` - Plotly charts
- `templates/` - Web UI (dashboard, submission detail)

## API: Verify submission hashes
The server exposes two related endpoints used for submission and verification when teachers need to confirm that files submitted to their LMS/platform match what was analyzed by EditorWatch.

- Endpoint (submit): `POST /api/submit`
  - Accepts the normal `code`, `assignment_id`, and `events` payloads from the extension.
  - Optional: include a `files` object mapping `{ "relative/or/base/filename.py": "<file contents>", ... }`.
  - When present, the server compresses (gzip) and base64-encodes each file content, then encrypts and stores the snapshot alongside the submission. These compressed snapshots are used later for verification.

- Endpoint (verify): `POST /api/verify-submission`
  - Auth: requires admin session (teacher must be logged into the dashboard).
  - Request JSON:
     - `assignment_id` (string) — assignment identifier
     - `email` (string) — student email
     - `files` (object) — mapping `{ "filename.py": "<file contents>", ... }` containing the files the teacher received from the student (e.g., from the LMS)
  - Response JSON (when snapshots exist):
     - `student` — email provided
     - `tracked_files` — list of filenames that were seen in the student's recorded events
     - `verification` — mapping per uploaded file: `{ uploaded_hash, recorded_hash, matches, was_tracked }`

How it works: if a submission included file snapshots at submit time, EditorWatch stores compressed+encrypted snapshots keyed by filename. When you POST to `/api/verify-submission` with the files you received from a student, the server compresses and hashes each uploaded file (SHA256 over the compressed bytes) and compares that hash to the stored snapshot's hash. The response contains both hashes, a `matches` boolean, and `was_tracked` to indicate whether that filename appeared in the recorded event timeline.

Important notes:
- The server will return an error if no stored file snapshots are available for a submission — for reliable verification, students must submit snapshots via the extension (or another client) at the time they submit their timeline.
- Filenames are normalized to their basename by default in this version. If you need path-aware verification (relative paths), consider enabling/adding full-path support in both the extension and server (recommended for courses where multiple students may use identical basenames in nested folders).
- This verification is intended as an evidence aid — it helps detect mismatches between what was analyzed and what was submitted to an LMS, but it does not legally prove authorship.

## Tech Stack

- **Backend**: Flask, PostgreSQL, Redis
- **Analysis**: NumPy, custom metrics
- **Visualization**: Plotly
- **Queue**: RQ (Redis Queue)
- **Extension**: TypeScript, VS Code API

## License

Dual license:
- **Free** for non-profit education (MIT)
- **Paid** for commercial use

See [LICENCE.md](LICENCE.md)

## Limitations

- Requires VS Code
- Students must explicitly consent
- Use as ONE tool alongside code reviews, oral exams

## Support

- 🐛 [Report Issues](https://github.com/Vic-Nas/EditorWatch/issues)
- 💬 [Discussions](https://github.com/Vic-Nas/EditorWatch/discussions)
