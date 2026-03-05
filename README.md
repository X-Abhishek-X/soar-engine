# soar-engine

A lightweight async SOAR engine that automates incident response. When an IDS alert fires, you don't want a human manually querying VirusTotal and copy-pasting IPs into Slack at 3am — this handles that.

The core design decision: the webhook receiver never blocks. It takes the alert, drops it into a Redis queue, and immediately returns `202 Accepted`. Background Celery workers pick up the job asynchronously — so even if VirusTotal is slow or Slack is having issues, you don't miss alerts during traffic spikes.

```
IDS / SIEM
    │
    ▼ POST /api/v1/webhook/alert
┌─────────────┐
│  FastAPI    │  →  202 Accepted (immediate)
│  receiver   │
└──────┬──────┘
       │ enqueue
       ▼
┌─────────────┐
│    Redis    │  (job queue, survives restarts)
└──────┬──────┘
       │ dequeue
       ▼
┌─────────────────────────────────────┐
│  Celery worker — run_playbook()     │
│                                     │
│  malware  →  VirusTotal lookup      │
│  brute    →  Slack alert + block    │
│  default  →  log + Slack notify     │
└─────────────────────────────────────┘
```

---

### Running locally

The fastest path is Docker — Redis + API + worker in one command:

```bash
docker-compose up
```

Or manually if you prefer:

```bash
# 1. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 2. Python env
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Config
cp .env.example .env
# edit .env — add VT key and Slack webhook
```

Start the worker and API in separate terminals:

```bash
# Terminal 1
celery -A tasks worker --loglevel=info

# Terminal 2
uvicorn main:app --reload --port 8000
```

---

### Fire a test alert

```bash
curl -X POST http://localhost:8000/api/v1/webhook/alert \
  -H "Content-Type: application/json" \
  -d '{
    "type": "malware",
    "source": "crowdstrike",
    "severity": "high",
    "ip": "185.156.73.53",
    "description": "Cobalt Strike beacon detected on host DESKTOP-4F9A"
  }'
```

Watch the Celery terminal — you'll see the task pick up, hit VirusTotal, and fire the Slack message.

---

### Config (`.env`)

```ini
REDIS_URL=redis://localhost:6379/0
VIRUSTOTAL_API_KEY=     # free tier works (500 req/day)
SLACK_WEBHOOK_URL=      # https://hooks.slack.com/services/...
```

Both keys are optional for local testing — the playbooks degrade gracefully if they're missing.

---

### Adding a playbook

`tasks.py` has a `run_playbook` function with a simple dispatch on `alert.type`. Add a branch:

```python
elif alert.type == "dns_exfil":
    block_domain(alert.description)
    send_slack(f":warning: DNS exfiltration detected: {alert.description}")
```

Celery handles retries, concurrency, and failure logging — you just write the response logic.

---

### Health check

```bash
curl http://localhost:8000/health
# {"status": "ok", "worker": "connected"}
```

---

### License

MIT
