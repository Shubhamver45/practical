# QR Attendance System

Run locally:

1. Create venv and install:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start server:

```
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Use endpoints from the homepage `/`.
