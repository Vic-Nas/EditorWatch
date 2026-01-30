import os
import sys
import json
from cryptography.fernet import Fernet

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Submission, AnalysisResult
from analysis.metrics import calculate_all_metrics
from analysis.visualizer import create_timeline, create_activity_heatmap

# Initialize encryption (same as app.py but without importing app)
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())
if isinstance(ENCRYPTION_KEY, str):
    ENCRYPTION_KEY = ENCRYPTION_KEY.encode()
cipher = Fernet(ENCRYPTION_KEY)


def decrypt_data(encrypted_data):
    """Decrypt data from storage (duplicated here to avoid circular import)"""
    decrypted = cipher.decrypt(encrypted_data.encode())
    return json.loads(decrypted.decode())


def analyze_submission(submission_id):
    """
    Background worker to analyze a submission.
    Called by RQ queue.
    """
    # Import app here to get context, after other imports are done
    from app import app
    
    with app.app_context():
        submission = Submission.query.get(submission_id)
        if not submission:
            print(f"Submission {submission_id} not found")
            return
        
        # Decrypt events
        events = decrypt_data(submission.events_encrypted)
        
        # Calculate metrics and flags
        result = calculate_all_metrics(events)
        
        # Generate visualizations
        timeline_html = create_timeline(events)
        activity_html = create_activity_heatmap(events)
        
        # Combine visualizations
        combined_html = f"""
        <div class="visualizations">
            {timeline_html}
            <br>
            {activity_html}
        </div>
        """
        
        # Save or update results
        analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
        
        if analysis:
            # Update existing
            analysis.incremental_score = result['incremental_score']
            analysis.typing_variance = result['typing_variance']
            analysis.error_correction_ratio = result['error_correction_ratio']
            analysis.paste_burst_count = result['paste_burst_count']
            analysis.flags = json.dumps(result['flags'])
            analysis.timeline_html = combined_html
        else:
            # Create new
            analysis = AnalysisResult(
                submission_id=submission_id,
                incremental_score=result['incremental_score'],
                typing_variance=result['typing_variance'],
                error_correction_ratio=result['error_correction_ratio'],
                paste_burst_count=result['paste_burst_count'],
                flags=json.dumps(result['flags']),
                timeline_html=combined_html
            )
            db.session.add(analysis)
        
        db.session.commit()
        
        print(f"✅ Analysis complete for submission {submission_id}")
        print(f"Metrics: incremental={result['incremental_score']}, variance={result['typing_variance']}")
        print(f"Flags: {len(result['flags'])} generated")


if __name__ == '__main__':
    # For testing: run analysis on a specific submission
    if len(sys.argv) > 1:
        submission_id = int(sys.argv[1])
        analyze_submission(submission_id)