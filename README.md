# Backend Dev Helper GUI

Backend Dev Helper is a lightweight Tkinter application that makes it easy for backend engineers to craft and test HTTP requests without leaving the keyboard. It supports custom headers, request bodies, history management, and pretty-prints JSON responses so you can focus on iterating quickly on APIs.

## Features

- Compose requests with the standard HTTP verbs (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS).
- Enter request headers in an intuitive multi-line editor (`Header: Value` per line).
- Add raw request bodies and resend them with a single key stroke (`Ctrl+Enter` / `⌘+Enter`).
- View status code, elapsed time, response headers, and auto-formatted JSON body.
- Keep a persistent in-session history of the requests you made and reload them instantly.

## Getting started

### Prerequisites

- Python 3.9+
- Tkinter (bundled with the default CPython installers)

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the app

```bash
python app.py
```

The UI will open in a desktop window. Fill in the method, URL, headers, and body as needed, then press **Send** (or `Ctrl+Enter`/`⌘+Enter` inside the body editor). Responses are displayed with timing info and history entries are added automatically.

## Notes

- Requests are executed on a background thread so the UI stays responsive even for slow endpoints.
- Validation is minimal by design so the tool stays flexible—double check URLs before sending.
- History is kept in memory only. Clear entries you no longer need from the History panel.
