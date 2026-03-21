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
┌───────────────────────────────────────────┐
│  Celery worker — process_security_alert() │
│                                           │
│  1. VirusTotal IP enrichment              │
│  2. Firewall block if malicious_votes ≥ 3 │
│  3. Slack notification with full context  │
└───────────────────────────────────────────┘
```

---

### Running locally

The fastest path is Docker — Redis, API, and worker in one command:

```bash
cp .env.example .env   # add your API keys
docker-compose up
```

Or manually:

```bash
# 1. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 2. Python env
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Config
cp .env.example .env
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
    "source_ip":   "185.156.73.53",
    "alert_type":  "SSH Brute Force",
    "severity":    "high",
    "description": "50+ failed SSH logins in 60 seconds from this IP"
  }'
```

Watch the Celery terminal — you'll see the task pick up, hit VirusTotal, and fire the Slack alert.

---

### Config (`.env`)

```ini
REDIS_URL=redis://localhost:6379/0
VIRUSTOTAL_API_KEY=     # free tier (500 req/day). Leave blank to use mock responses.
SLACK_WEBHOOK_URL=      # https://hooks.slack.com/services/...
```

Both keys are optional for local testing — the playbook degrades gracefully if they're missing.

---

### Adding a playbook

`tasks.py` → `process_security_alert()` dispatches on `alert_data["alert_type"]`. Add a branch:

```python
if alert_type == "dns_exfil":
    block_ip_on_firewall(source_ip)
    send_slack_alert(f"DNS exfiltration detected from {source_ip}")
```

Celery handles retries, concurrency, and failure logging.

---

### Health check

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

---

### License

MIT
