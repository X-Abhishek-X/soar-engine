# soar-engine

i threw this together to automate a few incident response tasks. dealing with raw IDS alerts manually gets old fast, so this basically just listens for webhooks, parses out the bad IPs, and runs an automated playbook on them. 

the main goal was to make sure it doesn't drop alerts if there's a spike in traffic. so instead of blocking the main thread while querying external APIs, the webhook receiver just throws the payload into a redis queue and immediately returns a 200 OK. then, background celery workers pick up the jobs asynchronously.

right now, the playbook just checks the offending IP against virustotal and throws an alert into a slack channel. easy to expand though.

## stack

- **fastapi**: for the webhook receiver endpoint
- **celery & redis**: handles the asynchronous background queues
- **python**: for the playbook logic 

## running it locally

1. **get redis running**
   i included a compose file if you just want to run it in docker:
   ```bash
   docker-compose up -d
   ```

2. **set up the python env**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **api keys**
   create a `.env` file in the root. you can skip this if you just want to test it (it'll mock the responses), but to actually use it you'll need:
   ```text
   REDIS_URL=redis://localhost:6379/0
   VIRUSTOTAL_API_KEY=your_vt_key
   SLACK_WEBHOOK_URL=your_slack_webhook
   ```

## firing it up

you'll need to run the worker and the api server separately.

**terminal 1 (the worker):**
```bash
celery -A tasks worker --loglevel=info
```

**terminal 2 (the api):**
```bash
uvicorn main:app --reload --port 8000
```

## testing it

you can just throw a fake alert at the webhook using curl to see the playbook run:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/webhook/alert \
-H "Content-Type: application/json" \
-d '{
    "source_ip": "185.156.73.53",
    "alert_type": "Suspected SSH Brute Force",
    "severity": "high",
    "description": "More than 50 failed login attempts in 1 minute."
}'
```

watch the celery logs to see it pick up the task and run the vt enrichment.
