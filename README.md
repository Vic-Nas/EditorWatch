# EditorWatch

**Code authenticity monitor for programming assignments** - Track how students write code, not just what they write.

## Quick Deploy

### Option 1: Railway (Recommended - Free Tier Available)

1. Fork this repo
2. Go to [Railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add these environment variables:
   ```
   DATABASE_URL=<railway-postgres-url>
   REDIS_URL=<railway-redis-url>
   SECRET_KEY=<random-string>
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=<your-password>
   ```
4. Railway auto-detects the Procfile and deploys both web + worker

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

### Optional: SMTP Email (otherwise generates CSV with codes)

```bash
export SMTP_HOST='smtp.gmail.com'
export SMTP_PORT='587'
export SMTP_USER='your-email@gmail.com'
export SMTP_PASSWORD='your-app-password'
export SMTP_FROM='your-email@gmail.com'
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

- Not foolproof - determined students can bypass
- Requires VS Code
- Students must explicitly consent
- Use as ONE tool alongside code reviews, oral exams

## Support

- 🐛 [Report Issues](https://github.com/Vic-Nas/EditorWatch/issues)
- 💬 [Discussions](https://github.com/Vic-Nas/EditorWatch/discussions)