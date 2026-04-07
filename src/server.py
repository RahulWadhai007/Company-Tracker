import sqlite3
import os
from flask import Flask, jsonify
from flask_cors import CORS

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
DB_FILE = os.path.join(PROJECT_ROOT, 'data', 'jobs.db')

app = Flask(__name__)
# Enable Cross-Origin Resource Sharing so external HTML/JS can fetch the API
CORS(app)

def get_db_connection():
    """
    Helper function to connect to the SQLite database.
    Setting row_factory=sqlite3.Row allows us to access columns by name.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/applications', methods=['GET'])
def get_applications():
    # Connect to the SQLite database
    conn = get_db_connection()
    
    # Query all records from the applications table
    rows = conn.execute('SELECT * FROM applications').fetchall()
    
    # Close the database connection defensively since we have all the data
    conn.close()

    formatted_applications = []
    
    # Iterate through the SQLite rows to parse them into dictionaries
    for row in rows:
        app_dict = dict(row)
        
        # Explicitly cast the action_required SQLite INTEGER back into a Python Boolean
        app_dict['action_required'] = bool(app_dict['action_required'])
        
        formatted_applications.append(app_dict)

    # Return the clean, formatted dictionary list as a JSON payload
    return jsonify(formatted_applications)

if __name__ == '__main__':
    print("Starting lightweight Flask API server on http://localhost:5000/api/applications")
    app.run(port=5000, debug=True)