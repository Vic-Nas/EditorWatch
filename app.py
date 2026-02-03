import os
import csv
from io import StringIO
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, Response, send_from_directory
from models import db, Submission, Assignment, StudentCode, AnalysisResult, init_db, Admin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from cryptography.fernet import Fernet
import json
from utils import (
    encrypt_data,
    decrypt_data,
    get_events_from_submission,
    files_from_events,
    compress_text_to_b64,
    sha256_of_b64,
)
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
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///editorwatch.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Encryption
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())
if isinstance(ENCRYPTION_KEY, str):
    ENCRYPTION_KEY = ENCRYPTION_KEY.encode()
cipher = Fernet(ENCRYPTION_KEY)

# Redis / RQ
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
redis_conn = redis.from_url(redis_url)
task_queue = Queue('analysis', connection=redis_conn)

init_db(app)

# Env-level admin fallback
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _ensure_current_admin():
    """Return Admin instance for current session, or env-fallback admin. Create if missing."""
    username = session.get('admin_username')
    if username:
        admin = Admin.query.filter_by(username=username).first()
        if admin:
            return admin

    # Fallback to env admin
    env_user = os.environ.get('ADMIN_USERNAME')
    if env_user:
        admin = Admin.query.filter_by(username=env_user).first()
        if not admin:
            env_pass = os.environ.get('ADMIN_PASSWORD') or secrets.token_hex(8)
            admin = Admin(username=env_user, password_hash=generate_password_hash(env_pass))
            db.session.add(admin)
            db.session.commit()
        return admin

    return None


def _require_assignment_owner(assignment_id):
    """
    Fetch assignment by ID and verify the current session owns it.
    Returns the Assignment on success.
    Raises 404 if not found, returns a JSON 403 response if not owner.
    """
    assignment = Assignment.query.filter_by(assignment_id=assignment_id).first_or_404()
    current_admin = _ensure_current_admin()
    if not current_admin or assignment.owner_id != current_admin.id:
        return None  # caller must return 403
    return assignment


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def generate_codes_csv(students_with_codes):
    """Generate CSV content with student codes."""
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


# ---------------------------------------------------------------------------
# Static / pages
# ---------------------------------------------------------------------------

@app.route('/extension/<path:filename>')
def serve_extension_files(filename):
    """Serve extension static files."""
    extension_path = os.path.join(os.path.dirname(__file__), 'extension')
    return send_from_directory(extension_path, filename)


@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Signup flow
        if request.form.get('action') == 'signup':
            username = request.form.get('username')
            password = request.form.get('password')
            if not username or not password:
                return render_template('login.html', error='Missing username or password')
            if Admin.query.filter_by(username=username).first():
                return render_template('login.html', error='Username already exists')
            admin = Admin(username=username, password_hash=generate_password_hash(password))
            db.session.add(admin)
            db.session.commit()
            session['logged_in'] = True
            session['admin_username'] = username
            session['is_env_admin'] = False
            return redirect(url_for('index'))

        # Login flow: DB first, then env fallback
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            admin = Admin.query.filter_by(username=username).first()
            if admin and check_password_hash(admin.password_hash, password):
                session['logged_in'] = True
                session['admin_username'] = username
                session['is_env_admin'] = False
                return redirect(url_for('index'))

            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                # Ensure Admin row exists for env admin
                admin = Admin.query.filter_by(username=username).first()
                if not admin:
                    admin = Admin(username=username, password_hash=generate_password_hash(password))
                    db.session.add(admin)
                    db.session.commit()
                session['logged_in'] = True
                session['admin_username'] = username
                session['is_env_admin'] = True
                return redirect(url_for('index'))

        return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------

@app.route('/init-db')
def initialize_database():
    try:
        db.create_all()
        return jsonify({'success': True, 'message': 'Database tables created successfully'})
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Submissions (extension-facing)
# ---------------------------------------------------------------------------

@app.route('/api/submit', methods=['POST'])
def submit_assignment():
    """Accept submission from VS Code extension."""
    try:
        data = request.json

        required = ['code', 'assignment_id', 'events']
        if not all(field in data for field in required):
            return jsonify({'error': 'Missing required fields'}), 400

        # Verify access code
        student_code = StudentCode.query.filter_by(
            assignment_id=data['assignment_id'],
            code=data['code']
        ).first()
        if not student_code:
            return jsonify({'error': 'Invalid access code'}), 403

        # Check deadline
        assignment = Assignment.query.filter_by(assignment_id=data['assignment_id']).first()
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        if datetime.utcnow() > assignment.deadline:
            return jsonify({'error': 'Deadline has passed'}), 403

        # Encrypt events (compact format from extension)
        events_encrypted = encrypt_data({'base_time': data.get('base_time', 0), 'events': data['events']})

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

        # Store file snapshots if provided (gzip + base64, then encrypted)
        try:
            files_payload = data.get('files')
            if files_payload and isinstance(files_payload, dict):
                compressed = {
                    fname.split('/')[-1]: compress_text_to_b64(content or '')
                    for fname, content in files_payload.items()
                }
                submission.files_encrypted = encrypt_data(compressed)
        except Exception as e:
            logger.warning(f"Failed to process file snapshots: {e}")

        db.session.commit()

        # Queue background analysis
        task_queue.enqueue('analysis.worker.analyze_submission', submission.id)

        return jsonify({'success': True, 'submission_id': submission.id}), 201

    except Exception as e:
        logger.error(f"Error in submit_assignment: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Assignments (teacher-facing)
# ---------------------------------------------------------------------------

@app.route('/api/assignments', methods=['GET', 'POST'])
def assignments():
    """List or create assignments."""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    if request.method == 'POST':
        try:
            data = request.json

            # Auto-generate assignment ID
            course_prefix = data.get('course', 'COURSE').replace(' ', '').upper()[:10]
            assignment_id = f"{course_prefix}_{secrets.token_hex(4)}"

            current_admin = _ensure_current_admin()
            assignment = Assignment(
                assignment_id=assignment_id,
                course=data.get('course', ''),
                name=data['name'],
                track_patterns=json.dumps(data.get('track_patterns', ['*.py', '*.js'])),
                deadline=datetime.fromisoformat(data['deadline']),
                owner_id=current_admin.id if current_admin else None
            )
            db.session.add(assignment)
            db.session.commit()

            # Generate codes for each student
            students = data.get('students', [])
            students_with_codes = []

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
                db.session.add(StudentCode(
                    assignment_id=assignment_id,
                    email=email,
                    first_name=first_name or None,
                    last_name=last_name or None,
                    code=code
                ))

                students_with_codes.append({
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'code': code
                })

            db.session.commit()

            return jsonify({
                'success': True,
                'assignment_id': assignment.assignment_id,
                'students': students_with_codes,
                'config_url': url_for('download_config', assignment_id=assignment_id, _external=True)
            }), 201

        except Exception as e:
            logger.error(f"Error creating assignment: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    # GET — list current user's assignments
    current_admin = _ensure_current_admin()
    if current_admin:
        assignment_list = Assignment.query.filter_by(owner_id=current_admin.id).all()
    else:
        assignment_list = Assignment.query.all()

    result = []
    for a in assignment_list:
        total_students = StudentCode.query.filter_by(assignment_id=a.assignment_id).count()
        submitted_count = (
            Submission.query
            .with_entities(func.count(Submission.id))
            .filter_by(assignment_id=a.assignment_id)
            .scalar() or 0
        )
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
    """Delete an assignment and all related data."""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    assignment = _require_assignment_owner(assignment_id)
    if not assignment:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        from sqlalchemy import delete
        from sqlalchemy.exc import SQLAlchemyError

        subq = db.session.query(Submission.id).filter(Submission.assignment_id == assignment_id).subquery()
        db.session.execute(delete(AnalysisResult).where(AnalysisResult.submission_id.in_(subq)))
        db.session.execute(delete(Submission).where(Submission.assignment_id == assignment_id))
        db.session.execute(delete(StudentCode).where(StudentCode.assignment_id == assignment_id))
        db.session.execute(delete(Assignment).where(Assignment.assignment_id == assignment_id))
        db.session.commit()

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception(f"Failed to delete assignment {assignment_id}: {e}")
        return jsonify({'error': 'Failed to delete assignment due to database constraint.'}), 500

    logger.info(f"Deleted assignment {assignment_id}")
    return jsonify({'success': True})


@app.route('/api/assignments/<assignment_id>/codes.csv')
def download_codes_csv(assignment_id):
    """Download CSV with all student codes."""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    assignment = _require_assignment_owner(assignment_id)
    if not assignment:
        return jsonify({'error': 'Unauthorized'}), 403

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
        mimetype='application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename={assignment_id}_codes.csv',
            'Content-Transfer-Encoding': 'binary'
        }
    )


@app.route('/assignments/<assignment_id>/mailtos')
def assignment_mailtos(assignment_id):
    """Render mailto page with editable message template and per-student links."""
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    assignment = _require_assignment_owner(assignment_id)
    if not assignment:
        return "Unauthorized", 403

    students = StudentCode.query.filter_by(assignment_id=assignment_id).all()
    students_data = [{
        'email': s.email,
        'first_name': s.first_name or '',
        'last_name': s.last_name or '',
        'code': s.code
    } for s in students]

    subject = f"EditorWatch Code - {assignment.name}"
    default_body = (
        f"Your EditorWatch access code for '{assignment.name}':\n\n"
        "{{code}}\n\n"
        "Enter this code in VS Code when prompted to enable monitoring."
    )

    return render_template(
        'mailtos.html',
        assignment_id=assignment_id,
        assignment_name=assignment.name,
        students=students_data,
        subject=subject,
        default_body=default_body
    )


@app.route('/api/assignments/<assignment_id>/config')
def download_config(assignment_id):
    """Download .editorwatch config file."""
    assignment = _require_assignment_owner(assignment_id)
    if not assignment:
        return jsonify({'error': 'Unauthorized'}), 403

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
    """Get all submissions for an assignment with status."""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    assignment = _require_assignment_owner(assignment_id)
    if not assignment:
        return jsonify({'error': 'Unauthorized'}), 403

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
            if any(f.get('severity') == 'high' for f in flags):
                status = 'suspicious'
            elif any(f.get('severity') == 'medium' for f in flags):
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


# ---------------------------------------------------------------------------
# Submission detail / export
# ---------------------------------------------------------------------------

@app.route('/submission/<int:submission_id>')
def view_submission_detail(submission_id):
    """Render detailed submission page."""
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()

    # Use get_events_from_submission — returns compact format that event_parser expects
    events = get_events_from_submission(submission)

    student_code = StudentCode.query.filter_by(
        assignment_id=submission.assignment_id,
        email=submission.email
    ).first()

    student_name = submission.email
    if student_code and student_code.first_name:
        student_name = f"{student_code.first_name} {student_code.last_name}".strip()

    flags = json.loads(analysis.flags) if analysis and analysis.flags else []

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
    """Export raw submission data as JSON."""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    submission = Submission.query.get_or_404(submission_id)
    analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()

    # Raw decrypt here intentionally — export wants the full payload as-is
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


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

@app.route('/api/verify-submission', methods=['POST'])
def verify_submission():
    """Compare uploaded files against stored snapshots for a student."""
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}
    assignment_id = data.get('assignment_id')
    student_email = data.get('email')
    uploaded_files = data.get('files', {})

    if not assignment_id or not student_email:
        return jsonify({'error': 'Missing assignment_id or email'}), 400

    submission = Submission.query.filter_by(
        assignment_id=assignment_id,
        email=student_email
    ).first()
    if not submission:
        return jsonify({'error': 'No submission found'}), 404

    # File list from compact event data
    event_data = get_events_from_submission(submission)
    tracked_files = set(files_from_events(event_data))

    # Load stored compressed snapshots
    stored_compressed = {}
    if getattr(submission, 'files_encrypted', None):
        try:
            stored_compressed = decrypt_data(submission.files_encrypted) or {}
        except Exception as e:
            logger.warning(f"Failed to decrypt stored file snapshots: {e}")

    if not stored_compressed:
        return jsonify({
            'error': 'No stored file snapshots for this submission. '
                     'Require students to submit file snapshots with their timeline.'
        }), 400

    # Compare uploaded vs stored by hash
    results = {}
    for filename, content in (uploaded_files or {}).items():
        base = filename.split('/')[-1]
        try:
            uploaded_hash = sha256_of_b64(compress_text_to_b64(content or ''))
        except Exception:
            uploaded_hash = None

        recorded_b64 = stored_compressed.get(base)
        recorded_hash = sha256_of_b64(recorded_b64) if recorded_b64 else None

        results[base] = {
            'uploaded_hash': uploaded_hash,
            'recorded_hash': recorded_hash,
            'matches': (uploaded_hash is not None and recorded_hash is not None and uploaded_hash == recorded_hash),
            'was_tracked': base in tracked_files
        }

    return jsonify({
        'student': student_email,
        'tracked_files': list(tracked_files),
        'verification': results
    })


# ---------------------------------------------------------------------------
# Similarity graph
# ---------------------------------------------------------------------------

@app.route('/assignments/<assignment_id>/graph')
def assignment_graph(assignment_id):
    """Render assignment similarity graph (Jaccard over files)."""
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    assignment = _require_assignment_owner(assignment_id)
    if not assignment:
        return "Unauthorized", 403

    submissions = Submission.query.filter_by(assignment_id=assignment_id).all()

    students = []
    for sub in submissions:
        ev = get_events_from_submission(sub)
        files = files_from_events(ev)

        student_code = StudentCode.query.filter_by(assignment_id=assignment_id, email=sub.email).first()
        student_name = sub.email
        if student_code and student_code.first_name:
            student_name = f"{student_code.first_name} {student_code.last_name}".strip()

        analysis = AnalysisResult.query.filter_by(submission_id=sub.id).first()
        students.append({
            'id': sub.id,
            'label': student_name,
            'files': files,
            'overall_score': analysis.overall_score if analysis else None
        })

    # Pairwise Jaccard edges
    nodes = [{'id': s['id'], 'label': s['label']} for s in students]
    edges = []
    for i in range(len(students)):
        for j in range(i + 1, len(students)):
            a = set(students[i]['files'])
            b = set(students[j]['files'])
            union = a | b
            if not union:
                continue
            weight = len(a & b) / len(union)
            if weight > 0:
                edges.append({'from': students[i]['id'], 'to': students[j]['id'], 'weight': round(weight, 4)})

    graph_data = {'nodes': nodes, 'edges': edges, 'students': students}
    return render_template('assignment_graph.html', assignment=assignment, graph_data=graph_data)


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))