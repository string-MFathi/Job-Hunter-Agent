import os
import json
import time
import imaplib
from email.message import EmailMessage
from typing import Dict, Any
import httpx
from dotenv import load_dotenv
from groq import Groq
from langsmith import traceable

from src.core.config import (
    get_role_track,
    CV_AI_PATH,
    CV_PM_PATH,
    AI_EMAIL_TEMPLATE,
    PM_EMAIL_TEMPLATE,
    LINKEDIN_URL,
    GITHUB_URL
)
from src.core.sheets_client import JobSheetsClient

load_dotenv()

class SmartOutreachDrafterAgent:
    """
    الوكيل الثاني (صانع الفرص):
    - يقرأ الشركات ذات الحالة 'جديد' من الشيت.
    - يوجه الوظيفة حتمياً إلى مسار AI أو PM ويختار الـ CV والقالب المناسبين.
    - يملأ المتغيرات فقط عبر Groq، ثم يحفظ الإيميل بالمرفقات في Gmail Drafts ويحدث الشيت ذرياً.
    """
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not self.api_key or "ضع_" in self.api_key:
            raise ValueError("⚠️ Please set a valid GROQ_API_KEY in .env file!")
        self.groq_client = Groq(api_key=self.api_key)
        self.models = [
            "openai/gpt-oss-120b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ]
        self.sheets = JobSheetsClient()
        self.gmail_user = os.getenv("GMAIL_USER_EMAIL", "").strip()
        self.gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()

        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    def send_telegram(self, message: str):
        if not self.telegram_token or "ضع_" in self.telegram_token:
            print(f"\n📱 [Telegram Notification]:\n{message}\n" + "-" * 45)
            return
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(url, json={"chat_id": self.telegram_chat_id, "text": message})
        except Exception as e:
            print(f"⚠️ [Telegram Error]: {e}")

    @traceable(name="Agent2_Groq_Email_Personalizer", run_type="chain")
    def generate_dynamic_email_slots(self, company_name: str, job_title: str, job_summary: str, track: str) -> Dict[str, str]:
        """توليد الأسطر المتغيرة فقط (Subject, Opening Hook, Bridge Sentence) لمنع أي هلوسة في الإنجازات"""
        system_prompt = f"""You are an Elite Technical Executive Copywriter crafting high-conversion B2B cold outreach variables for Mohamed Fathi.
Track: {track} ({job_title})
Company: {company_name}
Job Summary / Need: {job_summary}

Generate ONLY the 3 dynamic slots in JSON format:
1. "subject_problem": A sharp 4-7 word phrase naming the core technical/product challenge from the job summary.
2. "opening_hook": Exactly 1 natural, specific sentence referencing their remote {job_title} need or technical challenge from the job summary (proving this is NOT a generic copy-paste).
3. "bridge_sentence": Exactly 1 strong sentence connecting Mohamed's proven production architecture (if AI track) or technical root-cause ownership & automation (if PM track) directly to {company_name}'s goal.

Return ONLY valid JSON:
{{
  "subject_problem": "string",
  "opening_hook": "string",
  "bridge_sentence": "string"
}}"""

        for model_name in self.models:
            try:
                resp = self.groq_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Generate slots for {company_name} ({job_title})"}
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                return json.loads(resp.choices[0].message.content)
            except Exception as e:
                print(f"⚠️ [Groq Drafter Warning on {model_name}]: {e}")
                time.sleep(1.5)

        return {
            "subject_problem": f"Scaling {job_title} operations",
            "opening_hook": f"Noticed {company_name} is expanding its remote engineering/product capabilities around {job_title}.",
            "bridge_sentence": f"I'd bring that same production-first execution directly to {company_name}'s remote roadmap."
        }

    def build_full_email(self, lead: Dict[str, str]) -> Dict[str, str]:
        company = lead.get("company_name", "your team").strip()
        job_title = lead.get("job_title", "AI Agent Developer").strip()
        job_summary = lead.get("job_summary", "").strip()

        track = get_role_track(job_title)
        slots = self.generate_dynamic_email_slots(company, job_title, job_summary, track)

        prob = slots.get("subject_problem", f"{job_title} execution").strip()
        hook = slots.get("opening_hook", "").strip()
        bridge = slots.get("bridge_sentence", "").strip()

        if track == "PM":
            subject = f"{prob} — PM who reads the API logs, not just the ticket"
            body = PM_EMAIL_TEMPLATE.format(
                hiring_name=f"{company} Hiring Team",
                opening_hook=hook,
                bridge_sentence=bridge,
                linkedin_url=LINKEDIN_URL,
                github_url=GITHUB_URL
            )
            cv_path = CV_PM_PATH
        else:
            subject = f"{prob} — Production-grade AI agent reliability, not just a prototype"
            body = AI_EMAIL_TEMPLATE.format(
                hiring_name=f"{company} Hiring Team",
                company_name=company,
                opening_hook=hook,
                bridge_sentence=bridge,
                linkedin_url=LINKEDIN_URL,
                github_url=GITHUB_URL
            )
            cv_path = CV_AI_PATH

        return {
            "track": track,
            "subject": subject,
            "body": body,
            "cv_path": cv_path
        }

    def save_to_gmail_drafts(self, to_email: str, subject: str, body: str, cv_path: str) -> bool:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.gmail_user
        msg["To"] = to_email
        msg.set_content(body)

        # إرفاق ملف السيرة الذاتية المناسب تلقائياً إن وجد
        if cv_path and os.path.exists(cv_path):
            with open(cv_path, "rb") as f:
                pdf_data = f.read()
            filename = os.path.basename(cv_path)
            msg.add_attachment(
                pdf_data,
                maintype="application",
                subtype="pdf",
                filename=filename
            )
        else:
            print(f"⚠️ [CV Warning] File not found at '{cv_path}'. Creating draft without PDF attachment.")

        try:
            with imaplib.IMAP4_SSL("imap.gmail.com", 993) as imap:
                imap.login(self.gmail_user, self.gmail_pass)
                status, _ = imap.append('"[Gmail]/Drafts"', "", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
                return status == "OK"
        except Exception as e:
            print(f"❌ [Gmail Draft Save Error for {to_email}]: {e}")
            return False

    @traceable(name="Agent2_Process_Pending_Sheet_Leads", run_type="chain")
    def process_all_new_leads(self) -> int:
        pending_leads = self.sheets.fetch_new_pending_leads()
        print(f"\n✉️ [Agent 2: Smart Drafter] Found {len(pending_leads)} leads with status 'جديد' in Sheet.")

        if not pending_leads:
            return 0

        drafts_created = 0
        for lead in pending_leads:
            company = lead["company_name"]
            email = lead["official_email"]
            role = lead["job_title"]

            print(f"✍️ [Drafting] Preparing personalized outreach for '{company}' ({role} -> {email})...")
            email_pkg = self.build_full_email(lead)

            saved = self.save_to_gmail_drafts(
                to_email=email,
                subject=email_pkg["subject"],
                body=email_pkg["body"],
                cv_path=email_pkg["cv_path"]
            )

            if saved:
                # تحديث ذري فوري للحالة في الشيت بعد كل مسودة ناجحة
                self.sheets.update_lead_status(company, email, new_status="تم تجهيز المسودة")
                drafts_created += 1
                print(f"✅ [Draft Ready] Saved in Gmail Drafts ({email_pkg['track']} Track) & Updated Sheet for: {company}")
                time.sleep(1.5)

        if drafts_created > 0:
            self.send_telegram(
                f"📬 *تقرير الوكيل الثاني (صانع الفرص)*\n\n"
                f"✅ تم تجهيز *{drafts_created}* مسودة إيميل مخصصة مع الـ CV المناسب داخل حسابك في Gmail Drafts.\n"
                f"📊 تم تحديث حالتها في الشيت إلى: *تم تجهيز المسودة*."
            )

        return drafts_created

if __name__ == "__main__":
    agent2 = SmartOutreachDrafterAgent()
    agent2.process_all_new_leads()
