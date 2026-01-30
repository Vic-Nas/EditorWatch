from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


def init_db(app):
    """Initialize database"""
    db.init_app(app)
    with app.app_context():
        db.create_all()


class Assignment(db.Model):
    """Assignment configuration"""
    __tablename__ = 'assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.String(50), unique=True, nullable=False)
    course = db.Column(db.String(100))
    name = db.Column(db.String(200), nullable=False)
    track_patterns = db.Column(db.Text)  # JSON array of file patterns
    deadline = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade='all, delete-orphan')
    student_codes = db.relationship('StudentCode', backref='assignment', lazy=True, cascade='all, delete-orphan')


class StudentCode(db.Model):
    """Student access codes for assignments"""
    __tablename__ = 'student_codes'
    
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.String(50), db.ForeignKey('assignments.assignment_id'), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    code = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('assignment_id', 'email', name='_assignment_email_uc'),)


class Submission(db.Model):
    """Student submission - only events, no code"""
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False)
    assignment_id = db.Column(db.String(50), db.ForeignKey('assignments.assignment_id'), nullable=False)
    events_encrypted = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('assignment_id', 'email', name='_assignment_student_uc'),)
    
    analysis_result = db.relationship('AnalysisResult', backref='submission', uselist=False, cascade='all, delete-orphan')


class AnalysisResult(db.Model):
    """Analysis results for a submission"""
    __tablename__ = 'analysis_results'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    incremental_score = db.Column(db.Float)
    typing_variance = db.Column(db.Float)
    error_correction_ratio = db.Column(db.Float)
    paste_burst_count = db.Column(db.Integer)
    session_consistency = db.Column(db.Float)
    velocity_avg = db.Column(db.Float)
    velocity_max = db.Column(db.Float)
    overall_score = db.Column(db.Float)
    flags = db.Column(db.Text)  # JSON array of flag objects
    timeline_html = db.Column(db.Text)  # Plotly HTML visualization
    created_at = db.Column(db.DateTime, default=datetime.utcnow)