from src.server import app

if __name__ == "__main__":
    print("Starting lightweight Flask API server on http://localhost:5000/api/applications")
    app.run(port=5000, debug=True)
