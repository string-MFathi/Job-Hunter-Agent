import os
import json
import time
import random
from typing import List, Dict, Any
import httpx
from dotenv import load_dotenv
from groq import Groq
from langsmith import traceable

from src.core.config import ALL_TARGET_ROLES
from src.core.state_manager import JobHunterStateManager
from src.core.sheets_client import JobSheetsClient
from src.core.job_scraper import MultiPlatformJobScraper
from src.core.email_enricher import EmailEnrichmentLadder

load_dotenv()

class JobMarketHunterAgent:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not self.api_key or "ضع_" in self.api_key:
            raise ValueError("⚠️ Please set a valid GROQ_API_KEY in .env file!")
        self.groq_client = Groq(api_key=self.api_key)
        
        # الاعتماد على الموديلات الأقوى والأحدث فعلياً لتفادي هلوسات الفلترة
        self.models = [
            "llama-3.3-70b-versatile",
            "mixtral-8x7b-32768",
            "llama-3.1-8b-instant"
        ]
        self.state_manager = JobHunterStateManager()
        self.sheets = JobSheetsClient()
        self.scraper = MultiPlatformJobScraper()
        self.enricher = EmailEnrichmentLadder()

        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        self.excluded_non_tech_words = [
            "hotel", "sheraton", "marriott", "hilton", "resort", "fertilizer", "chemical",
            "cement", "construction", "hospital", "clinic", "pharmacy", "supermarket",
            "restaurant", "cafe", "textile", "factory"
        ]

    def send_telegram(self, message: str):
        if not self.telegram_token or "ضع_" in self.telegram_token:
            print(f"\n📱 [Telegram Notification]:\n{message}\n" + "-" * 45)
            return
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(url, json={"chat_id": self.telegram_chat_id, "text": message})
        except Exception:
            pass

    @traceable(name="Agent1_Groq_Batch_Job_Filter", run_type="chain")
    def analyze_jobs_batch_with_llm(self, batch_items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        if not batch_items:
            return []

        system_prompt = """You are an Elite B2B Tech & AI Job Market Analyst.
Analyze the provided batch of scraped job listings from Arab/MENA job boards.
Extract ONLY real Technology, Software, SaaS, AI, FinTech, EdTech, or Tech-enabled companies hiring for AI/Automation or Product Management roles.

STRICT FILTERING RULES:
1. TECH & DIGITAL COMPANIES ONLY: REJECT traditional non-tech industries unless they are building a software/AI product.
2. ROLE ALIGNMENT: Must genuinely relate to one of the 5 target tracks (AI Developer, Agentic AI, AI Automation, Tech PM, SaaS PM).
3. VALID COMPANY NAME: Extract the exact hiring company name. Never output "Confidential" or "Unknown".

Return ONLY valid JSON:
{
  "qualified_jobs": [
    {
      "source_url": "string",
      "company_name": "string",
      "matched_role": "string",
      "is_qualified": true,
      "company_domain_hint": "string",
      "job_summary": "2 concise sentences in English summarizing the role"
    }
  ]
}"""

        user_payload = json.dumps(batch_items, ensure_ascii=False)

        for model_name in self.models:
            try:
                resp = self.groq_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Job Listings Batch:\n{user_payload}"}
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                data = json.loads(resp.choices[0].message.content)
                jobs = data.get("qualified_jobs", [])
                print(f"   ✅ [Groq Tech Filter]: Qualified {len(jobs)} tech roles using {model_name}.")
                return jobs
            except Exception as e:
                print(f"⚠️ [Groq Warning on {model_name}]: {e}")
                time.sleep(2)
        return []

    @traceable(name="Agent1_Run_Session", run_type="chain")
    def run_session(self, max_queries_per_platform: int = 11, is_test_run: bool = False) -> int:
        plan = self.state_manager.get_current_session_plan()
        print(f"\n🚀 [Agent 1: Job Hunter] Starting Session: {plan['description']}")

        existing_rows = self.sheets.fetch_all_rows()
        for r in existing_rows:
            if r.get("company_name"):
                self.state_manager.mark_company_seen(r["company_name"], r.get("official_email", ""), r.get("platform", ""))

        new_companies_saved = 0
        total_urls_scraped = 0

        for platform in plan["platforms_to_scan"]:
            queries = self.scraper.build_queries_for_platform(platform, plan["roles"], plan["time_filter"])
            queries = queries[:max_queries_per_platform]
            print(f"🔎 [{platform}] Executing {len(queries)} deep multi-page & archive search queries...")

            raw_candidates = []
            for q in queries:
                results = self.scraper.search_jobs_batch(platform, q, time_filter=plan["time_filter"], max_results=40)
                for item in results:
                    url = item["url"]
                    if self.state_manager.is_url_seen(url):
                        continue
                    self.state_manager.mark_url_seen(url, platform)

                    page_text = self.scraper.fetch_job_page_content(url, item["title"], item["snippet"])
                    raw_candidates.append({
                        "source_url": url,
                        "platform": platform,
                        "title": item["title"],
                        "content": page_text[:3000]
                    })
                    total_urls_scraped += 1
                    time.sleep(random.uniform(0.5, 1.0))

                    if len(raw_candidates) >= 5:
                        new_companies_saved += self._process_batch(raw_candidates, platform)
                        raw_candidates = []

            if raw_candidates:
                new_companies_saved += self._process_batch(raw_candidates, platform)

        if total_urls_scraped > 0 and not is_test_run and max_queries_per_platform >= 10:
            self.state_manager.mark_session_completed()

        summary_msg = (
            f"🎯 *تقرير الوكيل الأول (صياد الوظائف)*\n\n"
            f"📋 *الخطة المنفذة:* {plan['description']}\n"
            f"🔍 *إجمالي الإعلانات المفحوصة:* {total_urls_scraped}\n"
            f"🏢 *شركات تقنية تم تسجيلها بالشيت:* {new_companies_saved}\n"
            f"🔄 *الحالة:* جاهزة للوكيل الثاني."
        )
        self.send_telegram(summary_msg)
        return new_companies_saved

    def _process_batch(self, batch: List[Dict[str, str]], platform: str) -> int:
        qualified = self.analyze_jobs_batch_with_llm(batch)
        saved_count = 0
        content_map = {item["source_url"]: item["content"] for item in batch}

        for job in qualified:
            company = (job.get("company_name") or "").strip()
            comp_low = company.lower()
            if not company or len(company) < 2 or comp_low in ["confidential", "unknown", "wuzzuf", "bayt", "indeed"]:
                continue
            if any(bad in comp_low for bad in self.excluded_non_tech_words):
                continue
            if not job.get("is_qualified", True):
                continue
            if self.state_manager.is_company_seen(company):
                continue

            source_url = job.get("source_url", "")
            domain_hint = job.get("company_domain_hint", "")
            
            print(f"   🕵️‍♂️ [Enrichment Ladder] Hunting official email for '{company}'...")
            official_email = self.enricher.enrich_company_email(company, content_map.get(source_url, ""), explicit_domain=domain_hint)
            
            role_title = job.get("matched_role", "AI Agent Developer")
            job_summary = job.get("job_summary", "Seeking technical talent for AI/Product operations.")

            # التعديل الأهم: عدم ضياع الفرصة إن لم نجد الإيميل
            if not official_email:
                official_email = "LinkedIn DM"
                status = "بدون إيميل - تواصل لينكدإن"
                print(f"   ⚠️ [No Email] Saved '{company}' for Manual LinkedIn Outreach.")
            else:
                status = "جديد"
                print(f"   💎 [NEW TECH LEAD SAVED] {company} | {role_title} | {official_email}")

            ok = self.sheets.append_job_lead(
                company_name=company,
                job_title=role_title,
                platform=platform,
                official_email=official_email,
                job_summary=job_summary,
                source_url=source_url,
                status=status
            )
            if ok:
                self.state_manager.mark_company_seen(company, official_email, platform)
                saved_count += 1

        return saved_count

if __name__ == "__main__":
    agent1 = JobMarketHunterAgent()
    agent1.run_session(max_queries_per_platform=11)