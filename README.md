# Company Tracker 🏢📈

A localized, AI-powered system designed to automatically ingest, track, and manage job applications directly from your inbox. It acts as an **Agentic Command Center**, displaying all your application statuses, communications, and upcoming deadlines in a streamlined web dashboard.

## Features
- **Automated Email Ingestion:** Securely reads your emails (e.g., from Gmail) to find job application updates or communications.
- **AI Processing:** Processes incoming communications using Google's Gemini Models (via LangChain) to extract meaningful data such as companies, roles, and current statuses (Applied, Assessment, Interview).
- **Web Dashboard:** A local Flask server that provides a unified view of all tracked applications and recent communications.
- **Local Database:** All data is safely stored in a local SQLite database, keeping your tracking private.
- **Alerting System:** Optional notifications via Telegram whenever an important job update occurs.

## Prerequisites
- **Python 3.8+**
- A **Google Gemini API Key** (for processing email text)
- An **App Password** for your email account (e.g., Gmail App Password if 2FA is enabled)
- (Optional) A **Telegram Bot Token** and **Chat ID** for notifications

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/RahulWadhai007/Company-Tracker.git
   cd Company-Tracker
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables Config:**
   Create a `.env` file in the root of the project to store your secret keys and configurations:
   ```env
   # Email configuration
   EMAIL_ACCOUNT="your_email@gmail.com"
   EMAIL_PASS="your_16_character_app_password"
   
   # Optional: limit the number of emails to parse per run
   EMAIL_MAX_UNREAD_FETCH="75"

   # AI configuration 
   GOOGLE_API_KEY="your_google_api_key_here"

   # Telegram configuration (optional - for alerts)
   TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
   TELEGRAM_CHAT_ID="your_telegram_chat_id"
   ```

## Usage

1. Start the Flask server / Command Center:
   ```bash
   python src/app.py
   ```
   *(Or just `python app.py` if running from the root wrappers)*

2. Open your browser and navigate to the provided local URL:
   ```
   http://127.0.0.1:5000/
   ```

The application will automatically initialize the local SQLite database on the first run, trigger the ingestion script to read unread emails, process those emails using AI, and render the results in the web dashboard.

## Project Structure
- `src/app.py`: Main Flask application and API backend.
- `src/email_reader.py`: Connects to IMAP server to fetch unread emails.
- `src/ai_processor.py`: Interfaces with the Google GenAI API to parse email subjects and bodies.
- `src/ingestion.py`: Orchestrates fetching emails and saving processed data into the database.
- `src/database.py`: Handles SQLite schema creations and queries.
- `frontend/`: Contains the localized HTML dashboard user interface.
- `data/`: Used for storing SQLite databases.

## License
MIT
