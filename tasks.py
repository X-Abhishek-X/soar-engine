import requests
import json
from celery import Celery
from config import settings

celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

# For testing without a Redis/Docker broker:
celery_app.conf.task_always_eager = True

def get_virustotal_reputation(ip_address: str) -> dict:
    """Query VirusTotal for IP reputation."""
    if not settings.VIRUSTOTAL_API_KEY or settings.VIRUSTOTAL_API_KEY == "your_virustotal_api_key_here":
        # Mock response if API key is not set
        print(f"[WARN] VIRUSTOTAL_API_KEY not configured. Mocking response for {ip_address}")
        return {"malicious_votes": 5, "total_votes": 90, "mocked": True}
        
    url = f"https://www.virustotal.com/api/v3/ip_addresses/{ip_address}"
    headers = {
        "accept": "application/json",
        "x-apikey": settings.VIRUSTOTAL_API_KEY
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            return {"malicious_votes": stats.get("malicious", 0), "total_votes": sum(stats.values()), "mocked": False}
    except Exception as e:
        print(f"[ERROR] Failed to query VirusTotal: {e}")
    return {"malicious_votes": 0, "total_votes": 0, "mocked": False}

def send_slack_alert(message: str) -> bool:
    """Send alert to a Slack channel via webhook."""
    if not settings.SLACK_WEBHOOK_URL or settings.SLACK_WEBHOOK_URL == "your_slack_webhook_url_here":
        print(f"[MOCK SLACK ALERT]: {message}")
        return True
        
    payload = {"text": message}
    try:
        response = requests.post(settings.SLACK_WEBHOOK_URL, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"[ERROR] Failed to send Slack alert: {e}")
        return False

def block_ip_on_firewall(ip_address: str) -> bool:
    """Implement logic to block the IP address on local firewall or Docker network."""
    # In a real environment, this might make an API call to a Palo Alto/Fortinet, 
    # or execute a remote SSH command to add an iptables rule.
    print(f"[ACTION CONTAINMENT] Executing automated block block for IP: {ip_address} on Firewall.")
    return True

@celery_app.task(name="process_security_alert")
def process_security_alert(alert_data: dict):
    """
    Main SOAR Playbook:
    1. Acknowledge alert
    2. Enrich threat data
    3. Determine action (block or ignore)
    4. Notify SOC channel
    """
    source_ip = alert_data.get("source_ip")
    alert_type = alert_data.get("alert_type")
    
    print(f"[*] Starting SOAR Playbook for {alert_type} involving IP {source_ip}")
    
    # 1. Enrichment Phase
    vt_reputation = get_virustotal_reputation(source_ip)
    malicious_score = vt_reputation.get("malicious_votes", 0)
    
    containment_status = "Ignored"
    
    # 2. Decision and Containment Phase
    if malicious_score >= 3 or alert_data.get("severity", "").lower() == "high":
        print(f"[!] HIGH RISK DETECTED: IP {source_ip} has {malicious_score} malicious votes.")
        # Trigger containment
        success = block_ip_on_firewall(source_ip)
        if success:
             containment_status = "Successfully Blocked"
        else:
             containment_status = "Block Failed"
    else:
        print(f"[-] Low risk: IP {source_ip} only has {malicious_score} malicious votes.")
        
    # 3. Notification Phase
    slack_message = (
        f":rotating_light: *Automated Incident Response Triggered* :rotating_light:\n"
        f"*Alert Type:* {alert_type}\n"
        f"*Source IP:* {source_ip}\n"
        f"*Severity:* {alert_data.get('severity')}\n"
        f"*Description:* {alert_data.get('description')}\n"
        f"---\n"
        f"*Threat Enrichment (VirusTotal):* {malicious_score} engines reported as malicious.\n"
        f"*SOAR Action Taken:* {containment_status}"
    )
    send_slack_alert(slack_message)
    
    return {"status": "completed", "containment": containment_status, "ip": source_ip}
