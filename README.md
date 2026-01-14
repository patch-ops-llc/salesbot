# LinkedIn Sales Robot

An automated LinkedIn outreach tool that finds executives at companies hiring for key roles, sends personalized connection requests, and logs leads to your CRM.

![LinkedIn Sales Robot](https://img.shields.io/badge/Python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

- 🔍 **Smart Job Search** - Find companies actively hiring for specific roles
- 👤 **Executive Discovery** - Automatically find decision-makers (CEOs, VPs, Directors)
- ✉️ **Personalized Outreach** - Generate custom connection messages using templates
- 🤖 **Browser Automation** - Uses Playwright for reliable, human-like interactions
- 📊 **Real-time Dashboard** - Monitor progress with live statistics
- 🎯 **CRM Integration** - Automatically log leads to work.patchops.io

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Run the Application

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

### 3. Open the UI

Navigate to [http://localhost:8000](http://localhost:8000) in your browser.

### 4. Configure & Run

1. **Job Titles**: Enter the job titles you want to search for (one per line)
2. **Message Template**: Create your connection message using placeholders:
   - `{name}` - Executive's first name
   - `{company}` - Company name
   - `{title}` - Executive's job title
   - `{job_title}` - The job they're hiring for
3. **CRM Stage ID**: Enter your pipeline stage UUID from PatchOps
4. Click **Start Robot**

## First-Time LinkedIn Login

The bot uses a persistent browser profile. On first run:

1. A Chromium browser window will open
2. Log in to LinkedIn manually
3. Complete any security challenges
4. Your session will be saved for future runs

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| Posted Within | How recent the job postings should be | Past week |
| Max Connections | Maximum connections per session | 20 |
| Delay | Seconds between connection requests | 30 |

## CRM Integration

The bot posts leads to `work.patchops.io/api/leads` with this payload:

```json
{
  "name": "Executive Name",
  "stageId": "your-stage-uuid",
  "company": "Company Name",
  "priority": "medium",
  "source": "LinkedIn Sales Robot",
  "nextSteps": "Follow up on LinkedIn connection acceptance",
  "notes": "LinkedIn profile, job details, and message sent"
}
```

## Project Structure

```
LinkedIn Sales Robot/
├── backend/
│   ├── main.py           # FastAPI server
│   ├── linkedin_bot.py   # LinkedIn automation
│   ├── crm_client.py     # CRM API client
│   └── models.py         # Data models
├── frontend/
│   ├── index.html        # Main UI
│   ├── style.css         # Cyberpunk styling
│   └── app.js            # Frontend logic
├── browser_data/         # Persistent browser session (auto-created)
├── requirements.txt      # Python dependencies
└── README.md
```

## Safety & Best Practices

⚠️ **Important**: Use this tool responsibly.

- **Rate Limiting**: Keep delay between connections at 30+ seconds
- **Daily Limits**: LinkedIn limits ~100 connections/week for new accounts
- **Personalization**: Write genuine, relevant messages
- **Compliance**: Ensure your outreach complies with LinkedIn's TOS

## Troubleshooting

### "Not logged in to LinkedIn"
- The browser window should have opened - log in manually
- Complete any security verification
- Restart the bot after logging in

### "Connect button not found"
- The person may already be connected or have a pending request
- Some profiles restrict connection requests

### WebSocket disconnected
- Refresh the page
- Check that the server is still running

## Tech Stack

- **Backend**: Python, FastAPI, Playwright
- **Frontend**: Vanilla HTML/CSS/JS
- **Real-time**: WebSocket
- **Browser**: Chromium (via Playwright)

## License

MIT License - Use at your own risk.

