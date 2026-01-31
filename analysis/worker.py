import os
import sys
import json
import logging

# Make package imports work when run as a worker
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Submission, AnalysisResult
from analysis.metrics import calculate_all_metrics
from analysis.visualizer import create_velocity_chart, create_activity_overview, create_file_risk_table
from utils import get_events_from_submission

# Worker logger (avoid dumping sensitive payloads)
logger = logging.getLogger('editorwatch.worker')


def _mask_email(email):
    try:
        local, domain = email.split('@', 1)
        return f"{local[:1]}***@{domain}"
    except Exception:
        return '***'


def analyze_submission(submission_id):
    """
    Background worker to analyze a submission.
    Called by RQ queue.
    """
    from app import app
    
    with app.app_context():
        submission = Submission.query.get(submission_id)
        if not submission:
            logger.warning('Submission not found: %s', submission_id)
            return

        masked = _mask_email(submission.email or '')
        logger.info('Analyzing submission %s (student=%s)', submission_id, masked)

        # Get events (utils handles decryption safely)
        events = get_events_from_submission(submission)
        logger.info('Events to analyze: %d', len(events))

        # Calculate comprehensive metrics
        result = calculate_all_metrics(events)
        logger.info('Metrics calculated for submission %s', submission_id)

        # Generate visualizations (do not log their content)
        logger.info('Creating visualizations for submission %s', submission_id)
        velocity_html = create_velocity_chart(events)
        overview_html = create_activity_overview(events, result['file_risks'])
        file_risk_table = create_file_risk_table(result['file_risks'])
        
        # Combine visualizations
        combined_html = f"""
        <div class="visualizations">
            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin-top: 0;">📊 Activity Overview</h3>
                {overview_html}
            </div>
            
            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin-top: 0;">⚡ Typing Speed Analysis</h3>
                <p style="color: #666; margin-bottom: 15px;">
                    Human coders typically type 40-80 characters/minute. 
                    Speeds consistently above 200 chars/min indicate pasting.
                </p>
                {velocity_html}
            </div>
            
            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin-top: 0;">📁 File-Level Risk Analysis</h3>
                <p style="color: #666; margin-bottom: 15px;">
                    Each file is analyzed for suspicious patterns like large pastes and minimal editing.
                </p>
                {file_risk_table}
            </div>
        </div>
        """
        
        logger.info('Visualizations created for submission %s', submission_id)
        
        # Save or update results in database
        analysis = AnalysisResult.query.filter_by(submission_id=submission_id).first()
        
        if analysis:
            # Update existing
            analysis.incremental_score = result['incremental_score']
            analysis.typing_variance = result['typing_variance']
            analysis.error_correction_ratio = result['error_correction_ratio']
            analysis.paste_burst_count = result['paste_burst_count']
            analysis.session_consistency = result.get('session_consistency', 0)
            analysis.velocity_avg = result['velocity'].get('average_cpm', 0)
            analysis.velocity_max = result['velocity'].get('max_cpm', 0)
            analysis.overall_score = result.get('overall_score', 0)
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
                session_consistency=result.get('session_consistency', 0),
                velocity_avg=result['velocity'].get('average_cpm', 0),
                velocity_max=result['velocity'].get('max_cpm', 0),
                overall_score=result.get('overall_score', 0),
                flags=json.dumps(result['flags']),
                timeline_html=combined_html
            )
            db.session.add(analysis)
        
        db.session.commit()

        logger.info('Analysis complete for submission %s: overall_score=%.1f', submission_id, result.get('overall_score', 0))
        logger.info('Metrics summary for %s: incremental=%.1f variance=%.1f errors=%.1f',
                submission_id,
                result.get('incremental_score', 0),
                result.get('typing_variance', 0),
                result.get('error_correction_ratio', 0))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        submission_id = int(sys.argv[1])
        analyze_submission(submission_id)