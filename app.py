import os
import smtplib
import csv
from io import StringIO
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, Response, send_from_directory
from models import db, Submission, Assignment, StudentCode, AnalysisResult, init_db
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
    """Send access code via email"""
    if not SMTP_ENABLED:
        return False
    
    try:
        subject = f'EditorWatch Code - {assignment_name}'
        body = f"""Your EditorWatch access code for "{assignment_name}":

{code}

Enter this code in VS Code when prompted to enable monitoring.
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


def generate_codes_csv(students_with_codes):
    """Generate CSV file with student codes"""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'First Name', 'Last Name', 'Access Code'])
    
    for student in students_with_codes:
        writer.writerow([
            student['email'],
            student.get('first_name', ''),
            student.get('last_name', ''),
            student['code']
        ])
    
    return output.getvalue()


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
        
        required = ['code', 'assignment_id', 'events']
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Verify code
        student_code = StudentCode.query.filter_by(
            assignment_id=data['assignment_id'],
            code=data['code']
        ).first()
        
        if not student_code:
            return jsonify({'error': 'Invalid access code'}), 403
        
        # Check assignment deadline
        assignment = Assignment.query.filter_by(assignment_id=data['assignment_id']).first()
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        
        if datetime.utcnow() > assignment.deadline:
            return jsonify({'error': 'Deadline has passed'}), 403
        
        # Encrypt events
        events_encrypted = encrypt_data(data['events'])
        
        # Update or create submission
        submission = Submission.query.filter_by(
            assignment_id=data['assignment_id'],
            email=student_code.email
        ).first()
        
        if submission:
            logger.info(f"Updating submission for {student_code.email}")
            submission.events_encrypted = events_encrypted
            submission.submitted_at = datetime.utcnow()
            AnalysisResult.query.filter_by(submission_id=submission.id).delete()
        else:
            logger.info(f"New submission from {student_code.email}")
            submission = Submission(
                email=student_code.email,
                assignment_id=data['assignment_id'],
                events_encrypted=events_encrypted
            )
            db.session.add(submission)
        
        db.session.commit()
        
        # Queue analysis
        task_queue.enqueue('analysis.worker.analyze_submission', submission.id)
        
        return jsonify({
            'success': True,
            'submission_id': submission.id
        }), 201
        
    except Exception as e:
        logger.error(f"Error in submit_assignment: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/assignments', methods=['GET', 'POST'])
def assignments():
    """List or create assignments"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'POST':
        try:
            data = request.json
            
            # Auto-generate assignment ID
            course_prefix = data.get('course', 'COURSE').replace(' ', '').upper()[:10]
            assignment_id = f"{course_prefix}_{secrets.token_hex(4)}"
            
            assignment = Assignment(
                assignment_id=assignment_id,
                course=data.get('course', ''),
                name=data['name'],
                track_patterns=json.dumps(data.get('track_patterns', ['*.py', '*.js'])),
                deadline=datetime.fromisoformat(data['deadline'])
            )
            db.session.add(assignment)
            db.session.commit()
            
            # Generate codes for students
            students = data.get('students', [])
            students_with_codes = []
            codes_sent = 0
            
            for student in students:
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
                
                code = secrets.token_hex(3).upper()
                
                student_code = StudentCode(
                    assignment_id=assignment_id,
                    email=email,
                    first_name=first_name or None,
                    last_name=last_name or None,
                    code=code
                )
                db.session.add(student_code)
                
                # Try to send email
                email_sent = send_code_email(email, code, assignment.name)
                if email_sent:
                    codes_sent += 1
                
                students_with_codes.append({
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'code': code,
                    'email_sent': email_sent
                })
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'assignment_id': assignment.assignment_id,
                'codes_sent': codes_sent,
                'smtp_enabled': SMTP_ENABLED,
                'students': students_with_codes,
                'config_url': url_for('download_config', assignment_id=assignment_id, _external=True)
            }), 201
        
        except Exception as e:
            logger.error(f"Error creating assignment: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    # GET - list assignments
    assignments = Assignment.query.all()
    result = []
    
    for a in assignments:
        total_students = StudentCode.query.filter_by(assignment_id=a.assignment_id).count()
        submitted_count = Submission.query.filter_by(assignment_id=a.assignment_id).count()
        
        result.append({
            'assignment_id': a.assignment_id,
            'course': a.course,
            'name': a.name,
            'deadline': a.deadline.isoformat(),
            'created_at': a.created_at.isoformat(),
            'total_students': total_students,
            'submitted_count': submitted_count
        })
    
    return jsonify(result)


@app.route('/api/assignments/<assignment_id>', methods=['DELETE'])
def delete_assignment(assignment_id):
    """Delete an assignment"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    assignment = Assignment.query.filter_by(assignment_id=assignment_id).first_or_404()
    
    StudentCode.query.filter_by(assignment_id=assignment_id).delete()
    Submission.query.filter_by(assignment_id=assignment_id).delete()
    db.session.delete(assignment)
    db.session.commit()
    
    logger.info(f"Deleted assignment {assignment_id}")
    return jsonify({'success': True})


@app.route('/api/assignments/<assignment_id>/codes.csv')
def download_codes_csv(assignment_id):
    """Download CSV with all student codes"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    assignment = Assignment.query.filter_by(assignment_id=assignment_id).first_or_404()
    students = StudentCode.query.filter_by(assignment_id=assignment_id).all()
    
    students_data = [{
        'email': s.email,
        'first_name': s.first_name or '',
        'last_name': s.last_name or '',
        'code': s.code
    } for s in students]
    
    csv_content = generate_codes_csv(students_data)
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{assignment_id}_codes.csv"'}
    )


@app.route('/api/assignments/<assignment_id>/config')
def download_config(assignment_id):
    """Download .editorwatch config file"""
    assignment = Assignment.query.filter_by(assignment_id=assignment_id).first_or_404()
    
    server_url = os.environ.get('SERVER_URL')
    if not server_url:
        scheme = 'https' if request.headers.get('X-Forwarded-Proto') else request.scheme
        server_url = f"{scheme}://{request.host}"
    
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
    
    return Response(
        json.dumps(config, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename="editorwatch"'}
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
        
        student_code = StudentCode.query.filter_by(
            assignment_id=assignment_id,
            email=sub.email
        ).first()
        
        student_name = sub.email
        if student_code and student_code.first_name:
            student_name = f"{student_code.first_name} {student_code.last_name}".strip()
        
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
            'overall_score': analysis.overall_score if analysis else None
        })
    
    return jsonify(results)


@app.route('/submission/<int:submission_id>')
def view_submission_detail(submission_id):
    """View detailed submission page"""
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
    
    events = decrypt_data(submission.events_encrypted)
    
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
    
    from analysis.event_parser import get_event_summary
    work_summary = get_event_summary(events)
    
    return render_template('submission_detail.html',
                         submission=submission,
                         analysis=analysis,
                         events=events,
                         flags=flags,
                         student_name=student_name,
                         work_summary=work_summary)


@app.route('/api/submissions/<int:submission_id>/export')
def export_submission_data(submission_id):
    """Export raw submission data as JSON"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
    
    events = decrypt_data(submission.events_encrypted)
    
    export_data = {
        'student_email': submission.email,
        'assignment_id': submission.assignment_id,
        'submitted_at': submission.submitted_at.isoformat(),
        'events': events,
        'analysis': {
            'overall_score': analysis.overall_score,
            'incremental_score': analysis.incremental_score,
            'typing_variance': analysis.typing_variance,
            'error_correction_ratio': analysis.error_correction_ratio,
            'paste_burst_count': analysis.paste_burst_count,
            'session_consistency': analysis.session_consistency,
            'velocity_avg': analysis.velocity_avg,
            'velocity_max': analysis.velocity_max,
            'flags': json.loads(analysis.flags) if analysis.flags else []
        } if analysis else None
    }
    
    return Response(
        json.dumps(export_data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="submission_{submission_id}.json"'}
    )


@app.route('/api/verify-submission', methods=['POST'])
def verify_submission():
    """Get hashes of student's tracked submission for verification"""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json or {}
    assignment_id = data.get('assignment_id')
    student_email = data.get('email')
    uploaded_files = data.get('files', {})  # {filename: content}
    
    # Validate inputs
    if not assignment_id or not student_email:
        return jsonify({'error': 'Missing assignment_id or email'}), 400
    
    # Get student's submission
    submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        email=student_email
    ).first()
    
    if not submission:
        return jsonify({'error': 'No submission found'}), 404
    
    # Decrypt events to get file list
    try:
        events = decrypt_data(submission.events_encrypted)
    except Exception as e:
        logger.error(f"Error decrypting events for verification: {e}")
        return jsonify({'error': 'Failed to decrypt submission events'}), 500

    tracked_files = set(e.get('file', '').split('/')[-1] for e in events if e.get('file'))
    
    # Compare uploaded files
    import hashlib
    results = {}
    for filename, content in (uploaded_files or {}).items():
        try:
            uploaded_hash = hashlib.sha256(content.encode()).hexdigest()
        except Exception:
            # If content is bytes already or cannot be encoded, try hashing bytes
            try:
                uploaded_hash = hashlib.sha256(content).hexdigest()
            except Exception:
                uploaded_hash = None
        results[filename] = {
            'hash': uploaded_hash,
            'was_tracked': filename in tracked_files
        }
    
    return jsonify({
        'student': student_email,
        'tracked_files': list(tracked_files),
        'verification': results
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))