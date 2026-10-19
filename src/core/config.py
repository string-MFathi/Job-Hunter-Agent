import os
from dotenv import load_dotenv

load_dotenv()

# 1. مسميات الوظائف المستهدفة (مقسمة حسب المسار لتوجيه الـ CV المناسب حتمياً بدون استهلاك Tokens)
AI_ROLES = [
    "Software Engineer",
    "Mobile App Developer",
]

PM_ROLES = [
    "Technical Product Manager",
    "B2B SaaS Product Manager"
]

ALL_TARGET_ROLES = AI_ROLES + PM_ROLES

# 2. المنصات المستهدفة بالترتيب (أول 3 أيام: منصة كاملة كل يوم من يناير 2026)
PLATFORMS = ["Wuzzuf", "Bayt", "Indeed", "ATS_Direct"]

# 3. النطاق الجغرافي (دول الوطن العربي + Remote)
ARAB_COUNTRIES_KEYWORDS = [
    "saudi", "ksa", "riyadh", "jeddah", "uae", "dubai", "abu dhabi",
    "egypt", "cairo", "alexandria", "qatar", "doha", "kuwait", "bahrain",
    "oman", "jordan", "amman", "morocco", "tunisia", "algeria", "lebanon",
    "mena", "middle east", "arab", "السعودية", "الرياض", "جدة", "الإمارات",
    "دبي", "مصر", "القاهرة", "قطر", "الكويت", "البحرين", "عمان", "الأردن"
]


# 5. مسارات ملفات السيرة الذاتية
CV_AI_PATH = os.path.join("data", "cvs", "CV_1.pdf")
CV_PM_PATH = os.path.join("data", "cvs", "CV_2.pdf")

# 5. Public Links Placeholders
LINKEDIN_URL = "https://www.linkedin.com/in/your-profile/"
GITHUB_URL = "https://github.com/your-username"

# 6. Generic Outreach Email Templates
AI_EMAIL_TEMPLATE = """Hi {hiring_name},

{opening_hook}

I built an autonomous outbound lead-discovery engine — a fail-closed pipeline featuring SQLite idempotency locks, automated state reconciliation, and schema-validated LLM extraction to eliminate hallucinations in production.

That's the technical rigor I'd bring to {company_name}: {bridge_sentence}

Repo: {github_url}

Worth a 15-minute remote call?

[Your Name]
LinkedIn: {linkedin_url}"""

PM_EMAIL_TEMPLATE = """Hi {hiring_name},

{opening_hook}

In my previous product roles, I monitored cloud infrastructure directly and cut average ticket resolution time by diagnosing technical root causes before escalating. I also engineered end-to-end workflow automations that reduced processing cycles significantly.

{bridge_sentence}

Happy to discuss on a short remote call.

[Your Name]
LinkedIn: {linkedin_url}"""

def get_role_track(job_title: str) -> str:
    title_low = (job_title or "").lower()
    for pm_role in PM_ROLES:
        if pm_role.lower() in title_low or "product manager" in title_low:
            return "PM"
    return "AI"


