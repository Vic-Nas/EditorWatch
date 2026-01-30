# EditorWatch Architecture

## Philosophy: Simple by Design

Most academic integrity tools are bloated. EditorWatch focuses on one insight: **the timeline of how code was written reveals everything.**

**Total scope:**
- Extension: ~150 lines JavaScript
- Backend: ~500 lines Python  
- Analysis: ~300 lines Python
- **Total: ~1000 lines**

The power is in the idea, not complexity.

---

## System Overview

```
┌─────────────────────────────────────┐
│  VS Code Extension                  │
│  - Event logger                     │
│  - Local SQLite buffer              │
│  - One-time opt-in                  │
└──────────────┬──────────────────────┘
               │ HTTPS
               ↓
┌─────────────────────────────────────┐
│  Backend (Python/Flask)             │
│  - Accept submissions               │
│  - PostgreSQL storage               │
│  - Queue analysis jobs              │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  Analysis (Python)                  │
│  - Pattern detection                │
│  - Generate visualizations          │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  Dashboard (Simple HTML/Plotly)     │
│  - View timelines                   │
│  - See metrics                      │
└─────────────────────────────────────┘
```

---

## Assignment Distribution

### Teacher Creates Assignment

```
1. Create in dashboard:
   - Assignment name: "Homework 3 - Binary Trees"
   - Track files: *.py
   - Deadline: 2024-02-15 23:59:59 UTC

2. Download generated starter.zip:
   ├── .editorwatch       (config file)
   ├── main.py            (starter code)
   └── README.md

3. Upload to LMS (Canvas, Moodle, etc.)
```

### .editorwatch File Format

```json
{
  "assignment_id": "cs101_hw3_a8f2b9",
  "server": "https://editorwatch.yourdomain.com",
  "track_patterns": ["*.py"],
  "deadline": "2024-02-15T23:59:59Z",
  "course": "CS 101",
  "name": "Homework 3"
}
```

### Student Workflow

```
1. Download homework3_starter.zip
2. Open folder in VS Code
3. Extension detects .editorwatch
4. Popup: "Enable monitoring for Homework 3?"
5. Click "Enable" (one time only)
6. Work normally
7. Click "Submit" when done
```

**Setup time: One click.**

---

## One-Time Opt-In

Extension stores consent locally:

```javascript
// Stored in VS Code globalState
{
  "accepted_assignments": {
    "cs101_hw3_a8f2b9": {
      "accepted_at": 1706745000000,
      "workspace": "/home/student/homework3"
    }
  }
}
```

**Behavior:**
- ✅ Show popup once per assignment
- ✅ Never ask again after opt-in
- ✅ Silent resume on next VS Code open
- ✅ Don't show if deadline passed

---

## Offline-First Design

Students shouldn't need internet to code.

### Works Offline
✅ Opening assignment (reads `.editorwatch`)  
✅ Logging events (writes to local SQLite)  
✅ Deadline checking (from local file)  
✅ All coding work

### Needs Internet
❌ Submitting (uploads to server)

### Example: Student with No Internet

```
Monday (at library with WiFi):
1. Download homework3_starter.zip

Tuesday-Friday (offline at home):
2. Open folder, extension reads .editorwatch
3. Click "Enable monitoring"
4. Code all week
5. Events logged to local SQLite

Saturday (at coffee shop):
6. Click "Submit" → uploads
```

---

## Tech Stack (Minimal)

### Extension
```
- Plain JavaScript (~150 lines)
- VS Code Extension API
- better-sqlite3 (local storage)
- No TypeScript, no build step
```

### Backend
```
- Flask (lightweight API)
- PostgreSQL (data storage)
- RQ + Redis (job queue)
- cryptography (encrypt data)
```

### Analysis
```
- NumPy (metrics)
- Plotly (charts)
- OpenAI SDK (optional LLM)
```

### Dashboard
```
- Flask templates + Plotly
- Or React if I want
```

---

## Extension Core Logic

**Complete extension in ~150 lines:**

```javascript
// extension.js
const vscode = require('vscode');
const Database = require('better-sqlite3');

let db, currentAssignment, statusBarItem;

function activate(context) {
    checkForAssignment(context);
    
    vscode.workspace.onDidChangeTextDocument(event => {
        if (currentAssignment) logEvent(event);
    });
    
    vscode.commands.registerCommand('editorwatch.submit', 
        () => submitAssignment(context)
    );
}

function checkForAssignment(context) {
    const editorwatchPath = findEditorwatchFile();
    if (!editorwatchPath) return;
    
    const config = JSON.parse(fs.readFileSync(editorwatchPath));
    const accepted = context.globalState.get('accepted_assignments', {});
    
    if (accepted[config.assignment_id]) {
        startMonitoring(config, context);
        return;
    }
    
    if (new Date() > new Date(config.deadline)) return;
    
    showOptInPrompt(config, context);
}

function logEvent(event) {
    const change = event.contentChanges[0];
    if (!change) return;
    
    db.prepare(`
        INSERT INTO events (timestamp, type, file, char_count)
        VALUES (?, ?, ?, ?)
    `).run(Date.now(), 
           change.text ? 'insert' : 'delete',
           event.document.fileName,
           Math.abs(change.text?.length || change.rangeLength || 0));
}

async function submitAssignment(context) {
    const events = db.prepare('SELECT * FROM events').all();
    const code = await getCodeFiles();
    
    await fetch(`${currentAssignment.server}/api/submit`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            assignment_id: currentAssignment.assignment_id,
            events, code
        })
    });
}
```

---

## Backend Schema

### Submissions Table
```sql
CREATE TABLE submissions (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(50),
    assignment_id VARCHAR(50),
    events_encrypted TEXT,
    code_encrypted TEXT,
    submitted_at TIMESTAMP DEFAULT NOW()
);
```

### Analysis Results
```sql
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER REFERENCES submissions(id),
    incremental_score FLOAT,
    typing_variance FLOAT,
    error_correction_ratio FLOAT,
    paste_burst_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Pattern Detection

```python
# metrics.py
def incremental_score(events):
    """Low score = sudden large insertions"""
    insert_events = [e for e in events if e['type'] == 'insert']
    large_inserts = sum(1 for e in insert_events if e['char_count'] > 100)
    return 1 - (large_inserts / len(insert_events))

def paste_burst_detection(events):
    """Count rapid large insertions"""
    bursts = 0
    last_time = 0
    
    for e in events:
        if e['type'] == 'insert' and e['char_count'] > 100:
            if (e['timestamp'] - last_time) < 2000:  # 2 seconds
                bursts += 1
        last_time = e['timestamp']
    
    return bursts
```

---

## Visualization

```python
# visualizer.py
import plotly.graph_objects as go

def create_timeline(events):
    fig = go.Figure()
    
    for event_type in ['insert', 'delete', 'save']:
        filtered = [(e['timestamp'], 1) 
                   for e in events if e['type'] == event_type]
        
        if filtered:
            fig.add_trace(go.Scatter(
                x=[t for t, _ in filtered],
                y=[1] * len(filtered),
                mode='markers',
                name=event_type
            ))
    
    return fig.to_html()
```

---

## Deployment: Railway

**Why:** Simple Python deployment, ~$5/month.

```bash
# Setup
npm install -g @railway/cli
railway login
railway init

# Add services
railway add postgresql
railway add redis

# Deploy
railway up
```

**Auto-generated URL:** `https://editorwatch-production.up.railway.app`

### Use Your Domain

If I have a reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name ew.mydomain.com;
    
    location / {
        proxy_pass https://editorwatch-production.up.railway.app;
    }
}
```

---

## Security: Data Over Trust

I don't prevent tampering. I detect it.

### What Students Can't Fake
❌ Server deadline (validated server-side)  
❌ Timeline patterns (analysis detects inconsistencies)  
❌ Code-to-events ratio (500 lines with 10 events = flag)

### What Students Can Fake (But Doesn't Help)
✅ Local deadline → Server rejects anyway  
✅ Track patterns → Missing events = red flag  
✅ Server URL → Can't submit to wrong server

**The disruption in the data IS the evidence.**

---

## Privacy Design

- Only logs editor events in assignment workspace
- No screen capture
- No clipboard access
- Student sees all data before submission
- Data encrypted at rest
- Auto-deleted after semester

---

## Why This Is Hard to Game

1. **Multiple correlated metrics** - Gaming one doesn't help
2. **Time investment** - Faking realistic work takes effort
3. **Transparency** - Algorithm is public
4. **Human review** - Instructor makes final call

If you're smart enough to fake incremental development convincingly, you've learned enough to do the assignment.

---

## Limitations

### Can't Catch
- Manual transcription
- Offline coding → paste result
- Pair programming
- AI-assisted with manual edits

### False Positives
- Experienced coders (fast, few errors)
- Legitimate copy-paste from docs
- Different work styles (ADHD, dyslexia)

---

## Implementation Roadmap

**MVP (2 weeks):**
- Extension: Event logging
- Extension: CSV export
- Backend: Accept submissions

**Beta (4 weeks):**
- Backend: Authentication
- Analysis: Core metrics
- Dashboard: Simple table

**V1 (8 weeks):**
- Analysis: Visualizations
- Dashboard: Interactive charts
- Deploy to Railway

**Total: ~2.5 months**

---

## Files to Create

```
extension/
├── package.json
├── extension.js      (~150 lines)
└── .vscodeignore

backend/
├── app.py
├── models.py
├── routes/
│   ├── submit.py
│   └── analysis.py
└── requirements.txt

analysis/
├── metrics.py
├── visualizer.py
└── worker.py
```

---

## Cost Estimates

**Railway deployment:**
- $5/month base
- Includes PostgreSQL + Redis
- $0.10/GB bandwidth

**Total: ~$5-10/month for 100 students**

---

*Simple by design. The complexity is in the insight, not the code.*
