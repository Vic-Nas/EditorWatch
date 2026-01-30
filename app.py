import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, Response
from models import db, Submission, Assignment, AnalysisResult, init_db
from cryptography.fernet import Fernet
import json
from datetime import datetime
import redis
from rq import Queue

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///editorwatch.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Encryption key
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())
if isinstance(ENCRYPTION_KEY, str):
    ENCRYPTION_KEY = ENCRYPTION_KEY.encode()
cipher = Fernet(ENCRYPTION_KEY)

# Redis and RQ setup
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
redis_conn = redis.from_url(redis_url)
task_queue = Queue('analysis', connection=redis_conn)

init_db(app)

# Simple auth (replace with proper auth in production)
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')


def encrypt_data(data):
    """Encrypt data for storage"""
    json_data = json.dumps(data)
    return cipher.encrypt(json_data.encode()).decode()


def decrypt_data(encrypted_data):
    """Decrypt data from storage"""
    decrypted = cipher.decrypt(encrypted_data.encode())
    return json.loads(decrypted.decode())


@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if (request.form.get('username') == ADMIN_USERNAME and 
            request.form.get('password') == ADMIN_PASSWORD):
            session['logged_in'] = True
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/init-db')
def initialize_database():
    """Initialize database tables (run once after first deploy)"""
    try:
        db.create_all()
        return jsonify({'success': True, 'message': 'Database tables created successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/submit', methods=['POST'])
def submit_assignment():
    """Accept submission from VS Code extension"""
    try:
        data = request.json
        
        # Validate required fields
        required = ['student_id', 'assignment_id', 'events', 'code']
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check assignment exists and deadline hasn't passed
        assignment = Assignment.query.filter_by(assignment_id=data['assignment_id']).first()
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        
        if datetime.utcnow() > assignment.deadline:
            return jsonify({'error': 'Deadline has passed'}), 403
        
        # Encrypt sensitive data
        events_encrypted = encrypt_data(data['events'])
        code_encrypted = encrypt_data(data['code'])
        
        # Save submission
        submission = Submission(
            student_id=data['student_id'],
            assignment_id=data['assignment_id'],
            events_encrypted=events_encrypted,
            code_encrypted=code_encrypted
        )
        db.session.add(submission)
        db.session.commit()
        
        # Queue analysis job (FIXED: correct import path)
        task_queue.enqueue('analysis.worker.analyze_submission', submission.id)
        
        return jsonify({
            'success': True,
            'submission_id': submission.id,
            'message': 'Submission received and queued for analysis'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/assignments', methods=['GET', 'POST'])
def assignments():
    """List or create assignments"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'POST':
        data = request.json
        assignment = Assignment(
            assignment_id=data['assignment_id'],
            course=data.get('course', ''),
            name=data['name'],
            track_patterns=json.dumps(data.get('track_patterns', ['*.py'])),
            deadline=datetime.fromisoformat(data['deadline'])
        )
        db.session.add(assignment)
        db.session.commit()
        return jsonify({'success': True, 'assignment_id': assignment.assignment_id}), 201
    
    assignments = Assignment.query.all()
    return jsonify([{
        'assignment_id': a.assignment_id,
        'course': a.course,
        'name': a.name,
        'deadline': a.deadline.isoformat(),
        'created_at': a.created_at.isoformat()
    } for a in assignments])


@app.route('/api/assignments/<assignment_id>/config')
def download_config(assignment_id):
    """Download .editorwatch config file for an assignment"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    assignment = Assignment.query.filter_by(assignment_id=assignment_id).first_or_404()
    
    # Get server URL from environment or construct from request
    server_url = os.environ.get('SERVER_URL')
    if not server_url:
        # Fallback: construct from current request
        server_url = request.url_root.rstrip('/')
    
    config = {
        'assignment_id': assignment.assignment_id,
        'name': assignment.name,
        'course': assignment.course,
        'deadline': assignment.deadline.isoformat(),
        'server': server_url,
        'track_patterns': json.loads(assignment.track_patterns)
    }
    
    return Response(
        json.dumps(config, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition': 'attachment; filename=.editorwatch'
        }
    )


@app.route('/api/assignments/<assignment_id>/submissions')
def get_submissions(assignment_id):
    """Get all submissions for an assignment"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    
    results = []
    for sub in submissions:
        analysis = AnalysisResult.query.filter_by(submission_id=sub.id).first()
        results.append({
            'id': sub.id,
            'student_id': sub.student_id,
            'submitted_at': sub.submitted_at.isoformat(),
            'analysis': {
                'incremental_score': analysis.incremental_score if analysis else None,
                'typing_variance': analysis.typing_variance if analysis else None,
                'error_correction_ratio': analysis.error_correction_ratio if analysis else None,
                'paste_burst_count': analysis.paste_burst_count if analysis else None
            } if analysis else None
        })
    
    return jsonify(results)


@app.route('/api/submissions/<int:submission_id>')
def get_submission_detail(submission_id):
    """Get detailed submission data with decrypted events and code"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
    
    events = decrypt_data(submission.events_encrypted)
    code = decrypt_data(submission.code_encrypted)
    
    return jsonify({
        'id': submission.id,
        'student_id': submission.student_id,
        'assignment_id': submission.assignment_id,
        'submitted_at': submission.submitted_at.isoformat(),
        'events': events,
        'code': code,
        'analysis': {
            'incremental_score': analysis.incremental_score,
            'typing_variance': analysis.typing_variance,
            'error_correction_ratio': analysis.error_correction_ratio,
            'paste_burst_count': analysis.paste_burst_count,
            'timeline_html': analysis.timeline_html
        } if analysis else None
    })


@app.route('/submission/<int:submission_id>')
def view_submission_detail(submission_id):
    """View detailed submission page with timeline (NEW ROUTE)"""
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
    
    events = decrypt_data(submission.events_encrypted)
    code = decrypt_data(submission.code_encrypted)
    
    return render_template('submission_detail.html',
                         submission=submission,
                         analysis=analysis,
                         events=events,
                         code=code)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))