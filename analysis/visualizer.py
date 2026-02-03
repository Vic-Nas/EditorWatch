"""
Plotly visualizations from compact event data.
Compact format: { base_time: int, events: [[delta_ms, type, filename, char_count], ...] }
Type codes: 'i' = insert, 'd' = delete, 's' = save
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_velocity_chart(event_data):
    """
    Typing speed over time in 30-second windows.
    Color-coded: Green = normal, Orange = fast, Red = suspicious.
    Returns: HTML string
    """
    base_time = event_data.get('base_time', 0)
    events = event_data.get('events', [])
    if not events:
        return ""

    inserts = [e for e in events if e[1] == 'i']
    if not inserts:
        return ""

    window_size = 30 * 1000  # 30 seconds
    start_time = base_time + events[0][0]
    end_time = base_time + events[-1][0]

    times, speeds, colors = [], [], []

    current_time = start_time
    while current_time < end_time:
        window_end = current_time + window_size
        chars = sum(e[3] for e in inserts if current_time <= (base_time + e[0]) < window_end)

        if chars:
            cpm = chars * 2  # 30-sec → per-minute
            times.append((current_time - start_time) / 1000 / 60)
            speeds.append(cpm)
            colors.append('red' if cpm > 200 else 'orange' if cpm > 100 else 'green')

        current_time += window_size

    fig = go.Figure()

    fig.add_hrect(y0=0, y1=80, fillcolor="green", opacity=0.1,
                  annotation_text="Normal Human Speed", annotation_position="top left")
    fig.add_hrect(y0=80, y1=150, fillcolor="yellow", opacity=0.1,
                  annotation_text="Fast", annotation_position="top left")
    fig.add_hrect(y0=150, y1=500, fillcolor="red", opacity=0.1,
                  annotation_text="SUSPICIOUSLY FAST (likely pasting)", annotation_position="top left")

    fig.add_trace(go.Scatter(
        x=times, y=speeds,
        mode='lines+markers',
        name='Typing Speed',
        line=dict(color='blue', width=2),
        marker=dict(size=8, color=colors),
        hovertemplate='<b>Time: %{x:.1f} min</b><br>Speed: %{y:.0f} chars/min<extra></extra>'
    ))

    fig.update_layout(
        title='<b>Typing Speed Over Time</b><br><sub>Human coders: 40-80 chars/min | Pasting: >200 chars/min</sub>',
        xaxis_title='Time (minutes since start)',
        yaxis_title='Characters per Minute',
        height=400, hovermode='closest', showlegend=False
    )

    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_activity_overview(event_data, file_risks):
    """
    4-panel dashboard: event type split, activity timeline, file risks, insert/delete balance.
    Returns: HTML string
    """
    base_time = event_data.get('base_time', 0)
    events = event_data.get('events', [])
    if not events:
        return ""

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Event Types', 'Activity Over Time', 'File Risk Levels', 'Insert vs Delete Balance'),
        specs=[[{'type': 'pie'}, {'type': 'bar'}],
               [{'type': 'bar'}, {'type': 'bar'}]]
    )

    # 1. Event-type pie
    type_labels = {'i': 'insert', 'd': 'delete', 's': 'save'}
    event_counts = {}
    for e in events:
        label = type_labels.get(e[1], e[1])
        event_counts[label] = event_counts.get(label, 0) + 1

    fig.add_trace(go.Pie(
        labels=list(event_counts.keys()),
        values=list(event_counts.values()),
        marker=dict(colors=['#2ecc71', '#e74c3c', '#3498db']),
        hovertemplate='<b>%{label}</b><br>%{value} events<br>%{percent}<extra></extra>'
    ), row=1, col=1)

    # 2. Activity over time (5-min bins keyed by delta)
    bin_size = 5 * 60 * 1000
    bins = {}
    for e in events:
        bin_index = int(e[0] / bin_size)
        bins[bin_index] = bins.get(bin_index, 0) + 1

    fig.add_trace(go.Bar(
        x=[f"{i * 5}" for i in sorted(bins)],
        y=[bins[i] for i in sorted(bins)],
        marker_color='#3498db',
        hovertemplate='<b>Minutes %{x}</b><br>%{y} events<extra></extra>'
    ), row=1, col=2)

    # 3. File risk levels
    if file_risks:
        risk_counts = {'high': 0, 'medium': 0, 'low': 0}
        for d in file_risks.values():
            risk_counts[d['risk']] = risk_counts.get(d['risk'], 0) + 1

        fig.add_trace(go.Bar(
            x=['High Risk', 'Medium Risk', 'Low Risk'],
            y=[risk_counts['high'], risk_counts['medium'], risk_counts['low']],
            marker_color=['#e74c3c', '#f39c12', '#2ecc71'],
            hovertemplate='<b>%{x}</b><br>%{y} files<extra></extra>'
        ), row=2, col=1)

    # 4. Insert vs delete balance
    insert_chars = sum(e[3] for e in events if e[1] == 'i')
    delete_chars = sum(e[3] for e in events if e[1] == 'd')

    fig.add_trace(go.Bar(
        x=['Characters Added', 'Characters Deleted'],
        y=[insert_chars, delete_chars],
        marker_color=['#2ecc71', '#e74c3c'],
        text=[f'{insert_chars:,}', f'{delete_chars:,}'],
        textposition='auto',
        hovertemplate='<b>%{x}</b><br>%{y:,} chars<extra></extra>'
    ), row=2, col=2)

    fig.update_layout(height=700, showlegend=False, title_text="<b>Activity Overview</b>")
    return fig.to_html(full_html=False, include_plotlyjs='cdn')


def create_file_risk_table(file_risks):
    """
    HTML table of per-file risk assessments, sorted high → low.
    Returns: HTML string
    """
    if not file_risks:
        return "<p>No files analyzed</p>"

    risk_order = {'high': 0, 'medium': 1, 'low': 2}
    sorted_files = sorted(file_risks.items(), key=lambda x: (risk_order[x[1]['risk']], x[0]))

    risk_colors = {'high': '#ffebee', 'medium': '#fff3e0', 'low': '#e8f5e9'}
    risk_badges = {'high': '🔴 HIGH', 'medium': '🟡 MEDIUM', 'low': '🟢 LOW'}

    rows = []
    for filename, data in sorted_files:
        rows.append(f'''
            <tr style="background: {risk_colors[data['risk']]};">
                <td style="padding: 12px; border: 1px solid #ddd;"><strong>{filename}</strong></td>
                <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">{risk_badges[data['risk']]}</td>
                <td style="padding: 12px; border: 1px solid #ddd;">{"; ".join(data['issues']) if data['issues'] else "No issues"}</td>
                <td style="padding: 12px; text-align: right; border: 1px solid #ddd;">{data['total_chars']:,}</td>
                <td style="padding: 12px; text-align: right; border: 1px solid #ddd;">{data['edit_ratio']:.2%}</td>
            </tr>''')

    return f'''<table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
        <tr style="background: #f8f9fa; font-weight: bold;">
            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">File</th>
            <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Risk</th>
            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Issues</th>
            <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Total Chars</th>
            <th style="padding: 12px; text-align: right; border: 1px solid #ddd;">Edit Ratio</th>
        </tr>
        {''.join(rows)}
    </table>'''