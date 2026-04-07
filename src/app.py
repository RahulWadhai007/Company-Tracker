import os
from datetime import datetime, timezone

from flask import Flask, jsonify, send_file

from . import database
from .ingestion import run_ingestion

PORT = 5000
HTML_FILE = 'job_application_command_center.html'
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
HTML_PATH = os.path.join(PROJECT_ROOT, 'frontend', HTML_FILE)

app = Flask(__name__)


def _status_to_column(status):
    if status == 'Applied':
        return 'Applied'
    if status == 'Assessment':
        return 'Assessment'
    return 'Interview'


def get_apps_payload():
    """Fetches data from SQLite and structures it for the frontend."""
    database.init_db()
    apps_data = database.get_all_applications()

    formatted_apps = []
    for application in apps_data:
        comms = database.get_communications(application['id'])

        status = application.get('status') or 'Applied'
        col = _status_to_column(status)

        formatted_comms = []
        for comm in comms:
            sender = comm.get('sender') or 'Unknown Sender'
            subject = comm.get('subject') or 'No Subject'
            body = str(comm.get('body') or '')
            received_at = comm.get('received_at')
            msg_type = 'linkedin' if 'linkedin' in sender.lower() else 'gmail'

            try:
                date_time = datetime.fromisoformat(received_at) if received_at else None
                time_label = date_time.strftime("%b %d, %H:%M") if date_time else 'Unknown time'
            except ValueError:
                time_label = str(received_at) if received_at else 'Unknown time'

            formatted_comms.append({
                'type': msg_type,
                'from': sender,
                'msg': f"{subject} - {body[:100]}...",
                'time': time_label
            })

        formatted_apps.append({
            'id': application['id'],
            'company': application.get('company') or 'Unknown Company',
            'role': application.get('role') or 'Unknown Role',
            'status': status,
            'deadline': application.get('deadline') or 'No deadline',
            'col': col,
            'action_required': bool(application.get('action_required')),
            'link': application.get('link'),
            'comms': formatted_comms
        })

    return formatted_apps


@app.get('/')
def index():
    return send_file(HTML_PATH)


@app.get('/job_application_command_center.html')
def index_alias():
    return send_file(HTML_PATH)


@app.get('/api/applications')
def api_applications():
    warnings = []

    try:
        run_ingestion()
    except Exception as exc:
        warnings.append(f"Ingestion failed: {exc}")

    try:
        data = get_apps_payload()
    except Exception as exc:
        generated_at = datetime.now(timezone.utc).isoformat()
        return jsonify({
            'meta': {
                'total': 0,
                'generated_at': generated_at,
                'warnings': warnings + [f"Database read failed: {exc}"]
            },
            'data': []
        }), 500

    generated_at = datetime.now(timezone.utc).isoformat()
    return jsonify({
        'meta': {
            'total': len(data),
            'generated_at': generated_at,
            'warnings': warnings
        },
        'data': data
    })


def start_server():
    database.init_db()
    print(f"Serving your Agentic Command Center at http://localhost:{PORT}")
    app.run(host='127.0.0.1', port=PORT, debug=False)

if __name__ == "__main__":
    start_server()
