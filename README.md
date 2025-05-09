# Cookie Monitor Project

This project monitors cookies using Playwright and provides a web interface for management.

## Modules

- `server/`: FastAPI backend server.
- `browser_manager/`: Playwright browser automation logic.
- `sites.json`: Configuration files (e.g., `sites.json`).
- `user_data/`: Persistent data for browser contexts.
- `server/static/`: Static assets for the frontend.

## Requirements

- Python 3.x
- Playwright
- FastAPI
- Uvicorn

See `requirements.txt` for specific versions.

## Setup

1.  Clone the repository.
2.  Install dependencies: `pip install -r requirements.txt`
3.  Install Playwright browsers: `playwright install`

## Running the project

```bash
python main.py
```

This will start the FastAPI server (typically on `http://127.0.0.1:8000`) and the browser manager. 