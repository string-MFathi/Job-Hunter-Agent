import os
import re
import csv
import io
from datetime import datetime
from typing import List, Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()

class JobSheetsClient:
    def __init__(self):
        raw_sheet = os.getenv("JOB_SHEET_URL", "").strip()
        self.sheet_id = self._extract_sheet_id(raw_sheet)
        self.webhook_url = os.getenv("JOB_SHEET_WEBHOOK_URL", "").strip()

    @staticmethod
    def _extract_sheet_id(val: str) -> str:
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", val)
        return match.group(1) if match else val

    @staticmethod
    def sanitize(val: Any) -> str:
        text = str(val or "").strip()
        return re.sub(r"^[\=\+\-\@\t\r\n]+", "", text).strip()

    def fetch_all_rows(self) -> List[Dict[str, str]]:
        if not self.sheet_id:
            return []
        csv_url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/export?format=csv"
        rows_list = []
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.get(csv_url)
                if resp.status_code == 200 and len(resp.text) > 10:
                    reader = csv.reader(io.StringIO(resp.text))
                    all_data = list(reader)
                    if len(all_data) <= 1:
                        return []
                    for r in all_data[1:]:
                        padded = (r + [""] * 8)[:8]
                        rows_list.append({
                            "timestamp": padded[0].strip(),
                            "company_name": padded[1].strip(),
                            "job_title": padded[2].strip(),
                            "platform": padded[3].strip(),
                            "official_email": padded[4].strip(),
                            "job_summary": padded[5].strip(),
                            "source_url": padded[6].strip(),
                            "status": padded[7].strip()
                        })
        except Exception:
            pass
        return rows_list

    def fetch_new_pending_leads(self) -> List[Dict[str, str]]:
        all_rows = self.fetch_all_rows()
        return [r for r in all_rows if r.get("status") == "جديد" and "@" in r.get("official_email", "")]

    def append_job_lead(self, company_name: str, job_title: str, platform: str, official_email: str, job_summary: str, source_url: str, status: str = "جديد") -> bool:
        if not self.webhook_url:
            return False
        payload = {
            "action": "append",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "company_name": self.sanitize(company_name),
            "job_title": self.sanitize(job_title),
            "platform": self.sanitize(platform),
            "official_email": self.sanitize(official_email),
            "job_summary": self.sanitize(job_summary),
            "source_url": self.sanitize(source_url),
            "status": status
        }
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.post(self.webhook_url, json=payload)
                return resp.status_code == 200
        except Exception:
            return False

    def update_lead_status(self, company_name: str, official_email: str, new_status: str) -> bool:
        if not self.webhook_url:
            return False
        payload = {
            "action": "update_status",
            "company_name": company_name,
            "official_email": official_email,
            "new_status": new_status
        }
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.post(self.webhook_url, json=payload)
                return resp.status_code == 200
        except Exception:
            return False