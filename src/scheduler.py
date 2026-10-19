import os
import time
from datetime import datetime
from filelock import FileLock, Timeout
from src.agent1_hunter import JobMarketHunterAgent
from src.agent2_drafter import SmartOutreachDrafterAgent

LOCK_FILE = "data/state/job_hunter.lock"

def run_full_daily_pipeline(max_queries_per_platform: int = 11):
    """تشغيل الوكيل الأول (صياد الوظائف) يليه مباشرة الوكيل الثاني (صانع مسودات الجيميل)"""
    lock = FileLock(LOCK_FILE, timeout=5)
    try:
        with lock:
            print(f"\n🌟 [Master Pipeline] Starting Daily Run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            agent1 = JobMarketHunterAgent()
            new_leads = agent1.run_session(max_queries_per_platform=max_queries_per_platform)

            print("\n🔄 [Master Pipeline] Handing over to Agent 2 (Smart Gmail Drafter)...")
            agent2 = SmartOutreachDrafterAgent()
            drafts_made = agent2.process_all_new_leads()

            print(f"\n🎉 [Pipeline Completed] New Leads: {new_leads} | Gmail Drafts Created: {drafts_made}")
    except Timeout:
        print("🔒 [Lock Active] Another pipeline instance is currently running.")

def start_daily_3pm_daemon():
    print("🕒 [Job Hunter Daemon] Active!")
    print("📌 Schedule Rule: Starts daily at 15:00 (3:00 PM) and runs freely until completion.")
    print("⏳ Monitoring clock in background...\n")

    last_executed_date = ""

    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # يبدأ الساعة 15:00 (3 عصراً) مرة واحدة كل يوم ويأخذ وقته بالكامل بلا قيود
            if now.hour == 15 and last_executed_date != today_str:
                last_executed_date = today_str
                run_full_daily_pipeline(max_queries_per_platform=11)

            # فحص إضافي كل ساعة للوكيل الثاني فقط (لو أضفت أنت أي شركة يدوياً في الشيت بحالة 'جديد')
            elif now.minute == 30:
                agent2 = SmartOutreachDrafterAgent()
                agent2.process_all_new_leads()
                time.sleep(60)

            time.sleep(30)
        except KeyboardInterrupt:
            print("\n🛑 [Daemon Stopped] By user.")
            break
        except Exception as e:
            print(f"⚠️ [Scheduler Warning]: {e}")
            time.sleep(60)

if __name__ == "__main__":
    start_daily_3pm_daemon()
