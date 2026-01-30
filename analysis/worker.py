import os
import sys
import json
from cryptography.fernet import Fernet

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import db, Submission, AnalysisResult
from analysis.metrics import calculate_all_metrics
from analysis.visualizer import (create_timeline, create_activity_heatmap, 
                                 create_velocity_chart, create_activity_overview,
                                 create_file_risk_table)
from analysis.data_export import export_for_llm_analysis, generate_llm_prompt

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
        
        print(f"🔍 Analyzing submission {submission_id} for {submission.email}")
        
        # Decrypt events
        events = decrypt_data(submission.events_encrypted)
        print(f"   {len(events)} events to analyze")
        
        # Calculate comprehensive metrics
        result = calculate_all_metrics(events)
        print(f"   ✓ Metrics calculated")
        
        # Generate visualizations
        print(f"   Creating visualizations...")
        timeline_html = create_timeline(events)
        activity_html = create_activity_heatmap(events)
        velocity_html = create_velocity_chart(events)
        overview_html = create_activity_overview(events, result['file_risks'])
        file_risk_table = create_file_risk_table(result['file_risks'])
        
        # Combine visualizations in a logical order
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
            
            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin-top: 0;">📈 Event Timeline</h3>
                {timeline_html}
            </div>
            
            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin-top: 0;">📊 Activity Distribution</h3>
                {activity_html}
            </div>
        </div>
        """
        
        print(f"   ✓ Visualizations created")
        
        # Create temporary analysis object for export
        temp_analysis = type('obj', (object,), {
            'incremental_score': result['incremental_score'],
            'typing_variance': result['typing_variance'],
            'error_correction_ratio': result['error_correction_ratio'],
            'paste_burst_count': result['paste_burst_count'],
            'flags': json.dumps(result['flags'])
        })()
        
        # Generate LLM exports (stored in database, not filesystem)
        print(f"   Generating LLM exports...")
        try:
            llm_json = export_for_llm_analysis(submission, temp_analysis, events, result['file_risks'])
            llm_prompt = generate_llm_prompt(submission, temp_analysis, events, result['file_risks'])
            print(f"   ✓ LLM exports generated")
        except Exception as e:
            print(f"   ⚠️  Could not generate LLM data: {e}")
            llm_json = {}
            llm_prompt = ""
        
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
            analysis.flags = json.dumps(result['flags'])
            analysis.timeline_html = combined_html
            # Store LLM exports in database
            analysis.llm_export_json = json.dumps(llm_json)
            analysis.llm_export_prompt = llm_prompt
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
                flags=json.dumps(result['flags']),
                timeline_html=combined_html,
                # Store LLM exports in database
                llm_export_json=json.dumps(llm_json),
                llm_export_prompt=llm_prompt
            )
            db.session.add(analysis)
        
        db.session.commit()
        
        print(f"✅ Analysis complete for submission {submission_id}")
        print(f"   Metrics: incremental={result['incremental_score']:.2f}, " +
              f"variance={result['typing_variance']:.2f}, " +
              f"errors={result['error_correction_ratio']:.2f}, " +
              f"bursts={result['paste_burst_count']}")
        print(f"   Session consistency: {result.get('session_consistency', 0):.2f}")
        print(f"   Velocity: avg={result['velocity']['average_cpm']:.0f} chars/min, " +
              f"max={result['velocity']['max_cpm']:.0f} chars/min")
        print(f"   Flags: {len(result['flags'])} generated")
        print(f"   LLM exports stored in database")
        
        # Print flag summary
        high_flags = [f for f in result['flags'] if f['severity'] == 'high']
        if high_flags:
            print(f"   ⚠️  HIGH RISK: {len(high_flags)} critical flags")
            for flag in high_flags[:3]:  # Show first 3
                print(f"      - {flag['category']}: {flag['message'][:80]}...")


if __name__ == '__main__':
    # For testing: run analysis on a specific submission
    if len(sys.argv) > 1:
        submission_id = int(sys.argv[1])
        analyze_submission(submission_id)