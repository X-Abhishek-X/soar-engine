from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional
from tasks import process_security_alert

app = FastAPI(title="Serverless SOAR Engine", version="1.0.0")

class AlertPayload(BaseModel):
    source_ip: str
    destination_ip: Optional[str] = None
    alert_type: str
    severity: str
    description: str

@app.post("/api/v1/webhook/alert")
async def receive_alert(alert: AlertPayload):
    """
    Webhook endpoint to receive security alerts from IDS (like Suricata/Snort) or SIEM.
    """
    # Send the task to Celery asynchronously
    task = process_security_alert.delay(alert.dict())
    
    return {
        "status": "success",
        "message": "Alert received and queued for automated response.",
        "task_id": task.id
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}
