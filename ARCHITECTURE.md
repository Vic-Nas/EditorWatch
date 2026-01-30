# EditorWatch Architecture

## System Overview

```
┌─────────────────────────────────────┐
│  1. VS Code Extension (Client)     │
│     - Event Logger                  │
│     - Local SQLite Buffer           │
│     - Manual Submit                 │
└──────────────┬──────────────────────┘
               │ HTTPS (user trigger)
               ↓
┌─────────────────────────────────────┐
│  2. Backend Server (Python)         │
│     - Flask API                     │
│     - PostgreSQL (encrypted)        │
│     - Job Queue (RQ/Redis)          │
└──────────────┬──────────────────────┘
               │ instructor request
               ↓
┌─────────────────────────────────────┐
│  3. Analysis Pipeline (Python)      │
│     - Pattern Detection (NumPy)     │
│     - Visualization (Plotly)        │
│     - LLM Summarizer (optional)     │
└──────────────┬──────────────────────┘
               │ web dashboard
               ↓
┌─────────────────────────────────────┐
│  4. Instructor Dashboard (React)    │
│     - Timeline Viz                  │
│     - Anomaly Highlights            │
│     - Read-only Access              │
└─────────────────────────────────────┘
```

---

## Tech Stack (Minimal & Python-First)

### Extension (TypeScript)
```
Language: TypeScript
Framework: VS Code Extension API
Storage: SQLite (better-sqlite3)
HTTP: fetch/axios
Build: esbuild
```

**Why TypeScript?** VS Code extensions require it. But the code is simple—mostly event listeners and database writes.

### Backend (Python)
```
API: Flask (simple, lightweight)
Database: PostgreSQL + SQLAlchemy
Queue: RQ (Redis Queue)
Auth: Flask-Login
Crypto: cryptography library
```

**Why Flask?** You know Python. Flask is minimal. No Django complexity needed.

**Alternative:** FastAPI if you want async, but Flask is easier to start.

### Analysis (Python)
```
Math: NumPy, Pandas
Visualization: Plotly (interactive charts)
LLM: OpenAI Python SDK (optional)
Stats: SciPy (for outlier detection)
```

**Why Plotly?** Generates interactive HTML charts without JavaScript knowledge.

### Dashboard (React)
```
Framework: Create React App
UI: Material-UI (pre-built components)
Charts: Plotly.js (matches backend)
State: React hooks (no Redux complexity)
```

**Why React?** Industry standard, tons of examples. You can use a template.

**Simpler Alternative:** Just serve static HTML from Flask + Plotly charts.

---

## Component Details

### 1. VS Code Extension

**Files to create:**
```
extension/
├── package.json          # Extension manifest
├── src/
│   ├── extension.ts      # Main entry point
│   ├── logger.ts         # Event capture logic
│   ├── storage.ts        # SQLite operations
│   └── submitter.ts      # Upload to server
└── database/
    └── schema.sql        # SQLite schema
```

**Core Logic:**

```typescript
// Event types to capture
type EditorEvent = {
  timestamp: number;
  type: 'insert' | 'delete' | 'save' | 'focus_change';
  file: string;
  line_start: number;
  line_end: number;
  char_count: number;
  typing_speed?: number;  // chars/sec over last 10s
};

// Capture on text change
vscode.workspace.onDidChangeTextDocument((event) => {
  const change = event.contentChanges[0];
  logEvent({
    timestamp: Date.now(),
    type: change.text ? 'insert' : 'delete',
    file: event.document.fileName,
    char_count: Math.abs(change.text.length || change.rangeLength),
    // ... calculate typing speed
  });
});

// Submit when student clicks "Submit Analytics"
async function submitToServer() {
  const events = await getLocalEvents();
  const finalCode = await getFinalCodeSnapshot();
  
  await fetch('https://your-server.com/api/submit', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${studentToken}` },
    body: JSON.stringify({
      student_id: '...',
      assignment_id: '...',
      events: events,
      final_code: finalCode
    })
  });
}
```

**Privacy Design:**
- Only logs editor events in assignment workspace
- No full code snapshots except on save
- No clipboard access
- No screen capture
- Student sees all data before submission

---

### 2. Backend Server

**Files to create:**
```
backend/
├── app.py                # Flask app
├── models.py             # SQLAlchemy models
├── routes/
│   ├── submit.py         # Handle submissions
│   ├── analysis.py       # Trigger analysis jobs
│   └── dashboard.py      # Serve dashboard data
├── config.py             # DB connection, secrets
└── requirements.txt
```

**Core Models:**

```python
# models.py
from flask_sqlalchemy import SQLAlchemy
from cryptography.fernet import Fernet

db = SQLAlchemy()

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), nullable=False)
    assignment_id = db.Column(db.String(50), nullable=False)
    
    # Encrypted JSON blob of events
    events_encrypted = db.Column(db.Text, nullable=False)
    final_code_encrypted = db.Column(db.Text, nullable=False)
    
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyzed = db.Column(db.Boolean, default=False)
    
    def set_events(self, events_list, key):
        cipher = Fernet(key)
        self.events_encrypted = cipher.encrypt(
            json.dumps(events_list).encode()
        ).decode()
    
    def get_events(self, key):
        cipher = Fernet(key)
        decrypted = cipher.decrypt(self.events_encrypted.encode())
        return json.loads(decrypted)

class AnalysisResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submission.id'))
    
    # Metrics
    incremental_score = db.Column(db.Float)
    typing_variance = db.Column(db.Float)
    error_correction_ratio = db.Column(db.Float)
    paste_burst_count = db.Column(db.Integer)
    
    # LLM summary (optional)
    llm_summary = db.Column(db.Text, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Submission Endpoint:**

```python
# routes/submit.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

submit_bp = Blueprint('submit', __name__)

@submit_bp.route('/api/submit', methods=['POST'])
@login_required
def submit_assignment():
    data = request.json
    
    # Validate student owns this submission
    if data['student_id'] != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Create submission
    submission = Submission(
        student_id=data['student_id'],
        assignment_id=data['assignment_id']
    )
    
    # Encrypt and store
    encryption_key = app.config['ENCRYPTION_KEY']
    submission.set_events(data['events'], encryption_key)
    submission.set_final_code(data['final_code'], encryption_key)
    
    db.session.add(submission)
    db.session.commit()
    
    return jsonify({'status': 'submitted', 'id': submission.id})
```

**Analysis Job Queue:**

```python
# Use RQ (Redis Queue) for async analysis
from rq import Queue
from redis import Redis

redis_conn = Redis()
q = Queue(connection=redis_conn)

# In routes/analysis.py
@analysis_bp.route('/api/analyze/<assignment_id>', methods=['POST'])
@login_required  # Only instructors
def trigger_analysis(assignment_id):
    submissions = Submission.query.filter_by(
        assignment_id=assignment_id
    ).all()
    
    for sub in submissions:
        # Queue analysis job for each student
        q.enqueue(analyze_submission, sub.id)
    
    return jsonify({'status': 'queued', 'count': len(submissions)})
```

---

### 3. Analysis Pipeline

**Files to create:**
```
analysis/
├── worker.py             # RQ worker process
├── metrics.py            # Pattern detection functions
├── visualizer.py         # Plotly chart generation
└── llm_summarizer.py     # Optional LLM integration
```

**Pattern Detection Functions:**

```python
# metrics.py
import numpy as np
from scipy import stats

def incremental_score(events):
    """
    Measures how gradually code was built.
    Low score = sudden large insertions
    """
    insert_events = [e for e in events if e['type'] == 'insert']
    sizes = [e['char_count'] for e in insert_events]
    
    # Large insertions are suspicious
    large_inserts = sum(1 for s in sizes if s > 100)
    total_inserts = len(sizes)
    
    # Return ratio (0=all large, 1=all small)
    return 1 - (large_inserts / total_inserts) if total_inserts > 0 else 0

def typing_variance(events):
    """
    Measures consistency of typing speed.
    Low variance = suspiciously robotic
    """
    speeds = [e.get('typing_speed', 0) for e in events if e.get('typing_speed')]
    
    if len(speeds) < 10:
        return 0  # Not enough data
    
    return np.std(speeds)

def error_correction_ratio(events):
    """
    Ratio of deletions to insertions.
    Too low = no mistakes (suspicious)
    """
    deletes = sum(1 for e in events if e['type'] == 'delete')
    inserts = sum(1 for e in events if e['type'] == 'insert')
    
    return deletes / inserts if inserts > 0 else 0

def paste_burst_detection(events):
    """
    Count rapid large insertions.
    >100 chars in <2 seconds = paste
    """
    bursts = 0
    last_timestamp = 0
    
    for e in events:
        if e['type'] == 'insert' and e['char_count'] > 100:
            time_delta = (e['timestamp'] - last_timestamp) / 1000  # ms to sec
            if time_delta < 2:
                bursts += 1
        last_timestamp = e['timestamp']
    
    return bursts

def analyze_submission(submission_id):
    """
    Main analysis function (run by RQ worker)
    """
    from models import Submission, AnalysisResult
    
    sub = Submission.query.get(submission_id)
    events = sub.get_events(app.config['ENCRYPTION_KEY'])
    
    # Calculate all metrics
    result = AnalysisResult(
        submission_id=submission_id,
        incremental_score=incremental_score(events),
        typing_variance=typing_variance(events),
        error_correction_ratio=error_correction_ratio(events),
        paste_burst_count=paste_burst_detection(events)
    )
    
    # Optional: LLM summary
    if app.config.get('USE_LLM'):
        result.llm_summary, result.confidence_score = generate_llm_summary(result)
    
    db.session.add(result)
    db.session.commit()
```

**Visualization:**

```python
# visualizer.py
import plotly.graph_objects as go
import plotly.express as px

def create_timeline_chart(events):
    """
    Interactive timeline of coding activity
    """
    timestamps = [e['timestamp'] for e in events]
    types = [e['type'] for e in events]
    
    fig = go.Figure()
    
    # Add scatter for each event type
    for event_type in ['insert', 'delete', 'save', 'focus_change']:
        filtered = [(t, types.index(event_type)) for t, ty in zip(timestamps, types) if ty == event_type]
        if filtered:
            fig.add_trace(go.Scatter(
                x=[t for t, _ in filtered],
                y=[1] * len(filtered),  # All on same line
                mode='markers',
                name=event_type,
                marker=dict(size=8)
            ))
    
    fig.update_layout(
        title="Coding Timeline",
        xaxis_title="Time",
        yaxis_title="Activity"
    )
    
    return fig.to_html()
```

**LLM Summarizer (Optional):**

```python
# llm_summarizer.py
from openai import OpenAI

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def generate_llm_summary(analysis_result):
    """
    Feed metrics to LLM for natural language summary
    """
    prompt = f"""
Analyze this coding behavior for an academic assignment:

Metrics:
- Incremental development score: {analysis_result.incremental_score:.2f} (0=sudden, 1=gradual)
- Typing variance: {analysis_result.typing_variance:.2f} (low=robotic)
- Error correction ratio: {analysis_result.error_correction_ratio:.2f} (low=no mistakes)
- Paste bursts detected: {analysis_result.paste_burst_count}

Typical student scores:
- Incremental: 0.6-0.9
- Typing variance: 0.3-0.8
- Error correction: 0.1-0.3
- Paste bursts: 0-3

Provide:
1. Confidence score (0-100) for non-incremental work
2. Brief explanation (2-3 sentences)
3. Recommendation (investigate/normal/exemplary)

Format: JSON with keys: confidence, explanation, recommendation
"""
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an academic integrity analyst. Be fair and nuanced."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    return result['explanation'], result['confidence']
```

---

### 4. Instructor Dashboard

**Minimal Option (No React):**

Just serve static HTML from Flask with Plotly charts:

```python
# routes/dashboard.py
@dashboard_bp.route('/dashboard/<assignment_id>')
@login_required  # Only instructors
def view_dashboard(assignment_id):
    results = AnalysisResult.query.join(Submission).filter(
        Submission.assignment_id == assignment_id
    ).all()
    
    # Create comparison chart
    scores = [r.incremental_score for r in results]
    fig = px.histogram(scores, title="Incremental Score Distribution")
    chart_html = fig.to_html()
    
    # Render template with chart embedded
    return render_template('dashboard.html', chart=chart_html, results=results)
```

**React Option (If You Want):**

```javascript
// dashboard/src/App.js
import React, { useEffect, useState } from 'react';
import Plot from 'react-plotly.js';

function Dashboard({ assignmentId }) {
  const [results, setResults] = useState([]);
  
  useEffect(() => {
    fetch(`/api/dashboard/${assignmentId}`)
      .then(r => r.json())
      .then(data => setResults(data));
  }, [assignmentId]);
  
  const scores = results.map(r => r.incremental_score);
  
  return (
    <div>
      <h1>Analysis Results</h1>
      <Plot
        data={[{
          type: 'histogram',
          x: scores,
          name: 'Incremental Score'
        }]}
        layout={{ title: 'Class Distribution' }}
      />
      
      <table>
        {results.map(r => (
          <tr key={r.id}>
            <td>{r.student_id}</td>
            <td>{r.incremental_score}</td>
            <td>{r.confidence_score}%</td>
          </tr>
        ))}
      </table>
    </div>
  );
}
```

---

## Data Schema

### Events Table (In Extension's SQLite)

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    type TEXT NOT NULL,  -- 'insert', 'delete', 'save', 'focus_change'
    file TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    char_count INTEGER,
    typing_speed REAL,
    submitted BOOLEAN DEFAULT 0
);
```

### Submissions Table (In PostgreSQL)

```sql
CREATE TABLE submissions (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(50) NOT NULL,
    assignment_id VARCHAR(50) NOT NULL,
    events_encrypted TEXT NOT NULL,
    final_code_encrypted TEXT NOT NULL,
    submitted_at TIMESTAMP DEFAULT NOW(),
    analyzed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_student_assignment ON submissions(student_id, assignment_id);
```

### Analysis Results Table

```sql
CREATE TABLE analysis_results (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER REFERENCES submissions(id),
    incremental_score FLOAT,
    typing_variance FLOAT,
    error_correction_ratio FLOAT,
    paste_burst_count INTEGER,
    llm_summary TEXT,
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Deployment Strategy

### Local Development

```bash
# 1. Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run

# 2. Extension
cd extension
npm install
npm run watch  # Auto-recompile on changes

# 3. Worker (separate terminal)
cd backend
rq worker
```

### Production (Simple)

**Option 1: Single VPS (DigitalOcean/AWS)**
- Flask app (Gunicorn)
- PostgreSQL (managed service or local)
- Redis (managed service or local)
- Nginx (reverse proxy)
- SSL via Let's Encrypt

**Option 2: Heroku (Easiest)**
- Deploy Flask app
- Add Heroku Postgres
- Add Heroku Redis
- Worker dyno for RQ

**Cost:** ~$20-50/month for small deployment (100 students)

---

## Security Considerations

### Encryption
```python
# Generate key once, store in environment
from cryptography.fernet import Fernet
key = Fernet.generate_key()
# Store in .env as ENCRYPTION_KEY=<key>

# All sensitive data encrypted at rest
cipher = Fernet(os.getenv('ENCRYPTION_KEY'))
encrypted = cipher.encrypt(data.encode())
```

### Authentication
```python
# Use Flask-Login for session management
# Students: username/password or SSO
# Instructors: separate role check

@login_required
@instructor_only
def sensitive_route():
    # Only instructors can access
    pass
```

### Data Retention
```python
# Auto-delete after semester ends
@app.cli.command()
def cleanup_old_data():
    cutoff = datetime.now() - timedelta(days=120)  # 4 months
    Submission.query.filter(
        Submission.submitted_at < cutoff
    ).delete()
    db.session.commit()
```

---

## Why This Design Is Hard to Game

### 1. Multiple Correlated Metrics
Gaming one metric doesn't help if others still flag you:
- Slow paste → Still shows low error correction
- Add fake typos → Still shows paste bursts
- Perfect metrics → Too perfect is suspicious

### 2. Time Investment
To fake realistic coding:
- Must read code thoroughly (learning happens)
- Must simulate thinking pauses (time investment)
- Must create plausible error patterns (engagement)

At this point, just doing the assignment is easier.

### 3. Transparency
Public algorithm means:
- Students know what's measured
- Students can audit for bias
- Students self-regulate knowing detection exists

### 4. Human Review
LLM provides summary, but instructor makes final call:
- No automatic punishment
- Context matters (ADHD, different work styles)
- Pattern is evidence, not verdict

---

## Ethical Safeguards

### Student Protections
1. **Opt-in at course level** (stated in syllabus)
2. **Full transparency** (see all data before submission)
3. **Right to explain** (flagged patterns start conversation, not accusation)
4. **Data deletion** (auto-purge after grading)
5. **No retroactive use** (can't analyze past semesters)

### Instructor Training
Before deploying, instructors must:
1. Understand metrics (what they mean, what they don't)
2. Recognize false positives (neurodivergent work styles, legitimate bursts)
3. Use as diagnostic, not prosecutorial (help struggling students, not just catch cheaters)

### Public Code
Entire system is open source:
- Students can audit for bias
- Community can propose improvements
- No black-box magic

---

## Limitations & Known Issues

### What This Can't Catch
1. **Manual transcription** - Student types code out slowly from source
2. **AI-assisted writing** - ChatGPT generates, student edits (but edits are shallow)
3. **Pair programming** - Legitimate collaboration looks like copying
4. **Offline work** - Student codes elsewhere, pastes final result

### False Positives
1. **Experienced coders** - Write correct code quickly with few errors
2. **Copy-paste from docs** - Legitimate use of examples
3. **Refactoring** - Major rewrites look like replacements
4. **Different work styles** - ADHD hyperfocus, dyslexic voice-coding

### Technical Limits
1. **Network issues** - Lost events if WiFi drops
2. **Extension bugs** - Crashes lose data
3. **Storage costs** - Events add up at scale
4. **Analysis speed** - LLM calls are slow/expensive

---

## Future Improvements

### Phase 1 Additions
- [ ] Offline mode (submit later)
- [ ] Progress indicator (show current metrics)
- [ ] Export data (students download their own)

### Phase 2 Features
- [ ] Team project support (per-student timelines)
- [ ] IDE support beyond VS Code (IntelliJ, PyCharm)
- [ ] Real-time feedback ("Hey, you've been idle 2 hours")

### Research Questions
- How do typing patterns vary by programming language?
- Can we detect AI-assisted coding reliably?
- What's the optimal threshold to minimize false positives?

---

## Implementation Roadmap

### MVP (4 weeks)
- [ ] Extension: Basic event logging to SQLite
- [ ] Extension: Manual CSV export
- [ ] Backend: Accept CSV uploads
- [ ] Analysis: Calculate 3 core metrics
- [ ] Dashboard: Simple table view

### Beta (8 weeks from start)
- [ ] Extension: Automatic upload to server
- [ ] Backend: User authentication
- [ ] Analysis: Full metric suite + visualizations
- [ ] Dashboard: Interactive charts
- [ ] Deploy to test server

### V1 (16 weeks from start)
- [ ] LLM integration
- [ ] Instructor training materials
- [ ] Pilot with 1-2 courses
- [ ] Gather feedback, iterate

### V2 (24 weeks from start)
- [ ] Team project features
- [ ] Multi-language support
- [ ] Public release
- [ ] Research paper

---

## Tech Debt to Avoid

### Don't Over-Engineer
- ❌ Don't use microservices (Flask monolith is fine)
- ❌ Don't build custom auth (use Flask-Login)
- ❌ Don't write your own crypto (use `cryptography` library)
- ❌ Don't optimize prematurely (100 students ≠ scale problem)

### Do Keep It Simple
- ✅ Use SQLite for extension (it's enough)
- ✅ Use Plotly for charts (no D3.js needed)
- ✅ Use Flask templates (React is optional)
- ✅ Use Heroku/Render (no Kubernetes needed)

---

## Questions & Answers

### Q: Can students run this locally without a server?
A: Yes! MVP is CSV export. They can analyze their own data.

### Q: How do I handle ADHD students who code erratically?
A: High variance should *lower* suspicion, not raise it. LLM should flag "irregular but consistent with hyperfocus".

### Q: What if students complain about privacy?
A: Make it opt-in. Those who opt out can use alternative assignments (oral exams, live coding).

### Q: Is this legal under FERPA/GDPR?
A: Consult your institution's legal team. Data is encrypted, access-controlled, and deleted after grading. Should be compliant, but verify.

### Q: What's the expected false positive rate?
A: Unknown (needs research). Target <5% with manual review.

---

## Contributing

This is an open research project. We need:

- **Students** - Tell us how this would affect you
- **Instructors** - Share edge cases and ethical concerns
- **Researchers** - Help validate metrics
- **Developers** - Improve the code

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT License - Audit the code. Fork it. Improve it. Question it.

---

## Contact

Questions? [Open an issue](https://github.com/yourusername/editorwatch/issues).

Ethical concerns? Email: ethics@editorwatch.dev

---

*Built with the understanding that perfect academic integrity is impossible, but genuine learning is always the goal.*
