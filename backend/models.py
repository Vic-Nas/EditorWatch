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
    
    submissions = db.relationship('Submission', backref='assignment', lazy=True)


class Submission(db.Model):
    """Student submission"""
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), nullable=False)
    assignment_id = db.Column(db.String(50), db.ForeignKey('assignments.assignment_id'), nullable=False)
    events_encrypted = db.Column(db.Text, nullable=False)
    code_encrypted = db.Column(db.Text, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    analysis_result = db.relationship('AnalysisResult', backref='submission', uselist=False)


class AnalysisResult(db.Model):
    """Analysis results for a submission"""
    __tablename__ = 'analysis_results'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=False)
    incremental_score = db.Column(db.Float)
    typing_variance = db.Column(db.Float)
    error_correction_ratio = db.Column(db.Float)
    paste_burst_count = db.Column(db.Integer)
    timeline_html = db.Column(db.Text)  # Plotly HTML visualization
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
