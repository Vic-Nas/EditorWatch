import os
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, Response, send_from_directory
from models import db, Submission, Assignment, StudentCode, StudentSheet, AnalysisResult, init_db
from cryptography.fernet import Fernet
import json
from datetime import datetime
import redis
from rq import Queue
import secrets
import logging

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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

# SMTP configuration
SMTP_ENABLED = all([
    os.environ.get('SMTP_HOST'),
    os.environ.get('SMTP_PORT'),
    os.environ.get('SMTP_USER'),
    os.environ.get('SMTP_PASSWORD'),
    os.environ.get('SMTP_FROM')
])

init_db(app)

# Simple auth
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


def send_code_email(email, code, assignment_name):
    """Send access code via email - fails gracefully if SMTP not configured"""
    if not SMTP_ENABLED:
        logger.info(f"[SMTP disabled] Code for {email}: {code}")
        return False
    
    try:
        subject = f'EditorWatch Code - {assignment_name}'
        body = f"""Your EditorWatch access code for "{assignment_name}":

{code}

Enter this code in VS Code when prompted to enable monitoring.

This code is unique to you and should not be shared.
"""
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = os.environ.get('SMTP_FROM')
        msg['To'] = email
        
        with smtplib.SMTP(os.environ.get('SMTP_HOST'), int(os.environ.get('SMTP_PORT', 587))) as server:
            server.starttls()
            server.login(os.environ.get('SMTP_USER'), os.environ.get('SMTP_PASSWORD'))
            server.send_message(msg)
        
        logger.info(f"✅ Sent code to {email}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {email}: {e}")
        return False


# Serve static files (including favicon)
@app.route('/extension/<path:filename>')
def serve_extension_files(filename):
    """Serve extension static files"""
    extension_path = os.path.join(os.path.dirname(__file__), 'extension')
    return send_from_directory(extension_path, filename)


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
    """Initialize database tables"""
    try:
        db.create_all()
        return jsonify({'success': True, 'message': 'Database tables created successfully'})
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/submit', methods=['POST'])
def submit_assignment():
    """Accept submission from VS Code extension"""
    try:
        data = request.json
        
        # Validate required fields
        required = ['code', 'assignment_id', 'events']
        if not all(field in data for field in required):
            logger.warning(f"Missing required fields in submission")
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Verify code and get student email
        student_code = StudentCode.query.filter_by(
            assignment_id=data['assignment_id'],
            code=data['code']
        ).first()
        
        if not student_code:
            logger.warning(f"Invalid access code for assignment {data['assignment_id']}")
            return jsonify({'error': 'Invalid access code'}), 403
        
        # Check assignment exists and deadline hasn't passed
        assignment = Assignment.query.filter_by(assignment_id=data['assignment_id']).first()
        if not assignment:
            logger.warning(f"Assignment not found: {data['assignment_id']}")
            return jsonify({'error': 'Assignment not found'}), 404
        
        if datetime.utcnow() > assignment.deadline:
            logger.warning(f"Deadline passed for {data['assignment_id']}")
            return jsonify({'error': 'Deadline has passed'}), 403
        
        # Encrypt events
        events_encrypted = encrypt_data(data['events'])
        
        # Check if submission exists (we keep only latest)
        submission = Submission.query.filter_by(
            assignment_id=data['assignment_id'],
            email=student_code.email
        ).first()
        
        if submission:
            # Update existing submission
            logger.info(f"Updating submission for {student_code.email} in {data['assignment_id']}")
            submission.events_encrypted = events_encrypted
            submission.submitted_at = datetime.utcnow()
            
            # Delete old analysis result
            AnalysisResult.query.filter_by(submission_id=submission.id).delete()
        else:
            # Create new submission
            logger.info(f"New submission from {student_code.email} for {data['assignment_id']}")
            submission = Submission(
                email=student_code.email,
                assignment_id=data['assignment_id'],
                events_encrypted=events_encrypted
            )
            db.session.add(submission)
        
        db.session.commit()
        
        # Queue analysis job
        task_queue.enqueue('analysis.worker.analyze_submission', submission.id)
        logger.info(f"Queued analysis for submission {submission.id}")
        
        return jsonify({
            'success': True,
            'submission_id': submission.id,
            'message': 'Submission received and queued for analysis'
        }), 201
        
    except Exception as e:
        logger.error(f"Error in submit_assignment: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/assignments/<assignment_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_assignment(assignment_id):
    """Get, update, or delete an assignment"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    assignment = Assignment.query.filter_by(assignment_id=assignment_id).first_or_404()
    
    if request.method == 'GET':
        return jsonify({
            'assignment_id': assignment.assignment_id,
            'course': assignment.course,
            'name': assignment.name,
            'deadline': assignment.deadline.isoformat(),
            'track_patterns': json.loads(assignment.track_patterns),
            'created_at': assignment.created_at.isoformat()
        })
    
    elif request.method == 'PUT':
        # Update assignment
        data = request.json
        
        if 'name' in data:
            assignment.name = data['name']
        if 'course' in data:
            assignment.course = data['course']
        if 'deadline' in data:
            assignment.deadline = datetime.fromisoformat(data['deadline'])
        if 'track_patterns' in data:
            assignment.track_patterns = json.dumps(data['track_patterns'])
        
        db.session.commit()
        logger.info(f"Updated assignment {assignment_id}")
        return jsonify({'success': True, 'message': 'Assignment updated'})
    
    elif request.method == 'DELETE':
        # Delete assignment, student codes, and all submissions
        StudentCode.query.filter_by(assignment_id=assignment_id).delete()
        Submission.query.filter_by(assignment_id=assignment_id).delete()
        db.session.delete(assignment)
        db.session.commit()
        logger.info(f"Deleted assignment {assignment_id}")
        return jsonify({'success': True, 'message': 'Assignment deleted'})


@app.route('/api/assignments', methods=['GET', 'POST'])
def assignments():
    """List or create assignments"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'POST':
        try:
            data = request.json
            logger.info(f"Creating assignment with data: {data}")
            
            # Auto-generate assignment ID
            course_prefix = data.get('course', 'COURSE').replace(' ', '').upper()[:10]
            assignment_id = f"{course_prefix}_{secrets.token_hex(4)}"
            
            assignment = Assignment(
                assignment_id=assignment_id,
                course=data.get('course', ''),
                name=data['name'],
                track_patterns=json.dumps(data.get('track_patterns', ['*.py'])),
                deadline=datetime.fromisoformat(data['deadline'])
            )
            db.session.add(assignment)
            db.session.commit()
            logger.info(f"Created assignment {assignment_id}")
            
            # Generate and send codes to students
            students = data.get('students', [])
            codes_sent = 0
            codes_failed = []
            
            for student in students:
                # Handle both dict format {email, first_name, last_name} and string format
                if isinstance(student, dict):
                    email = student.get('email', '').strip()
                    first_name = student.get('first_name', '').strip()
                    last_name = student.get('last_name', '').strip()
                else:
                    email = str(student).strip()
                    first_name = ''
                    last_name = ''
                
                if not email:
                    continue
                
                # Generate unique code
                code = secrets.token_hex(3).upper()  # 6 character code
                
                # Store code
                student_code = StudentCode(
                    assignment_id=assignment_id,
                    email=email,
                    first_name=first_name or None,
                    last_name=last_name or None,
                    code=code
                )
                db.session.add(student_code)
                
                # Try to send email
                if send_code_email(email, code, assignment.name):
                    codes_sent += 1
                else:
                    codes_failed.append({
                        'email': email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'code': code
                    })
            
            db.session.commit()
            logger.info(f"Generated {len(students)} codes, sent {codes_sent} emails")
            
            return jsonify({
                'success': True, 
                'assignment_id': assignment.assignment_id,
                'codes_sent': codes_sent,
                'codes_failed': codes_failed,
                'smtp_enabled': SMTP_ENABLED,
                'config_url': url_for('download_config', assignment_id=assignment_id, _external=True)
            }), 201
        
        except Exception as e:
            logger.error(f"Error creating assignment: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    assignments = Assignment.query.all()
    return jsonify([{
        'assignment_id': a.assignment_id,
        'course': a.course,
        'name': a.name,
        'deadline': a.deadline.isoformat(),
        'created_at': a.created_at.isoformat()
    } for a in assignments])


@app.route('/api/sheets', methods=['GET', 'POST'])
def sheets():
    """List or create student sheets"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'POST':
        try:
            data = request.json
            
            sheet = StudentSheet(
                name=data['name'],
                students=json.dumps(data['students'])
            )
            db.session.add(sheet)
            db.session.commit()
            logger.info(f"Created student sheet: {data['name']}")
            
            return jsonify({
                'success': True,
                'id': sheet.id,
                'name': sheet.name
            }), 201
        
        except Exception as e:
            logger.error(f"Error creating sheet: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    # GET
    sheets = StudentSheet.query.all()
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'students': s.students,
        'student_count': len(json.loads(s.students)),
        'created_at': s.created_at.isoformat()
    } for s in sheets])


@app.route('/api/assignments/<assignment_id>/config')
def download_config(assignment_id):
    """Download .editorwatch config file for an assignment"""
    assignment = Assignment.query.filter_by(assignment_id=assignment_id).first_or_404()
    
    # Get server URL - force HTTPS for production
    server_url = os.environ.get('SERVER_URL')
    if not server_url:
        # Build from request
        # Railway sets X-Forwarded-Proto header, always use it if present
        if request.headers.get('X-Forwarded-Proto'):
            scheme = 'https'
        else:
            scheme = request.scheme
        server_url = f"{scheme}://{request.host}"
    
    # Ensure HTTPS for production
    if 'railway.app' in server_url and server_url.startswith('http://'):
        server_url = server_url.replace('http://', 'https://', 1)
    
    config = {
        'assignment_id': assignment.assignment_id,
        'name': assignment.name,
        'course': assignment.course,
        'deadline': assignment.deadline.isoformat(),
        'server': server_url,
        'track_patterns': json.loads(assignment.track_patterns)
    }
    
    # Use editorwatch as filename (no leading dot for better compatibility)
    return Response(
        json.dumps(config, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition': 'attachment; filename="editorwatch"'
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
        
        # Get student name
        student_code = StudentCode.query.filter_by(
            assignment_id=assignment_id,
            email=sub.email
        ).first()
        
        student_name = sub.email
        if student_code and student_code.first_name:
            student_name = f"{student_code.first_name} {student_code.last_name}".strip()
        
        # Determine overall status
        status = 'pending'
        if analysis:
            flags = json.loads(analysis.flags) if analysis.flags else []
            high_severity = any(f.get('severity') == 'high' for f in flags)
            medium_severity = any(f.get('severity') == 'medium' for f in flags)
            
            if high_severity:
                status = 'suspicious'
            elif medium_severity:
                status = 'warning'
            else:
                status = 'clean'
        
        results.append({
            'id': sub.id,
            'email': sub.email,
            'student_name': student_name,
            'submitted_at': sub.submitted_at.isoformat(),
            'status': status,
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
    """Get detailed submission data"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
    
    events = decrypt_data(submission.events_encrypted)
    
    result = {
        'id': submission.id,
        'email': submission.email,
        'assignment_id': submission.assignment_id,
        'submitted_at': submission.submitted_at.isoformat(),
        'events': events,
        'analysis': {
            'incremental_score': analysis.incremental_score,
            'typing_variance': analysis.typing_variance,
            'error_correction_ratio': analysis.error_correction_ratio,
            'paste_burst_count': analysis.paste_burst_count,
            'flags': json.loads(analysis.flags) if analysis.flags else [],
            'timeline_html': analysis.timeline_html
        } if analysis else None
    }
    
    return jsonify(result)


@app.route('/submission/<int:submission_id>')
def view_submission_detail(submission_id):
    """View detailed submission page"""
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
    
    events = decrypt_data(submission.events_encrypted)
    
    # Get student name
    student_code = StudentCode.query.filter_by(
        assignment_id=submission.assignment_id,
        email=submission.email
    ).first()
    
    student_name = submission.email
    if student_code and student_code.first_name:
        student_name = f"{student_code.first_name} {student_code.last_name}".strip()
    
    flags = []
    if analysis and analysis.flags:
        flags = json.loads(analysis.flags)
    
    # Generate timeline
    from analysis.event_parser import parse_events_to_timeline, format_timeline_for_display, get_event_summary
    from analysis.data_export import export_for_llm_analysis, generate_llm_prompt
    timeline = parse_events_to_timeline(events)
    timeline_html = format_timeline_for_display(timeline)
    work_summary = get_event_summary(events)
    
    return render_template('submission_detail.html',
                         submission=submission,
                         analysis=analysis,
                         events=events,
                         flags=flags,
                         student_name=student_name,
                         timeline_html=timeline_html,
                         work_summary=work_summary)


@app.route('/api/submissions/<int:submission_id>/export/json')
def export_submission_json(submission_id):
    """Export submission data as clean JSON for LLM analysis (from database)"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
    
    if not analysis:
        return jsonify({'error': 'Analysis not complete yet'}), 404
    
    if not analysis.llm_export_json:
        return jsonify({'error': 'LLM export not available - reanalyze submission'}), 404
    
    return Response(
        analysis.llm_export_json,
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename="submission_{submission_id}_data.json"'
        }
    )


@app.route('/api/submissions/<int:submission_id>/export/prompt')
def export_submission_prompt(submission_id):
    """Export LLM-ready prompt for analyzing this submission (from database)"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
    
    if not analysis:
        return jsonify({'error': 'Analysis not complete yet'}), 404
    
    if not analysis.llm_export_prompt:
        return jsonify({'error': 'LLM prompt not available - reanalyze submission'}), 404
    
    return Response(
        analysis.llm_export_prompt,
        mimetype='text/plain',
        headers={
            'Content-Disposition': f'attachment; filename="submission_{submission_id}_llm_prompt.txt"'
        }
    )


# OPTIONAL: Batch export endpoint
@app.route('/api/assignments/<assignment_id>/export/batch')
def export_assignment_batch(assignment_id):
    """Export all submissions for an assignment as a zip file"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    import zipfile
    from io import BytesIO
    
    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()
    
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for submission in submissions:
            analysis = AnalysisResult.query.filter_by(submission_id=submission.id).first()
            if analysis and analysis.llm_export_json and analysis.llm_export_prompt:
                zf.writestr(f'{submission.email}_data.json', analysis.llm_export_json)
                zf.writestr(f'{submission.email}_prompt.txt', analysis.llm_export_prompt)
    
    memory_file.seek(0)
    return Response(
        memory_file.read(),
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{assignment_id}_exports.zip"'}
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))