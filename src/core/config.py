import os
from dotenv import load_dotenv

load_dotenv()

# 1. مسميات الوظائف المستهدفة (مقسمة حسب المسار لتوجيه الـ CV المناسب حتمياً بدون استهلاك Tokens)
AI_ROLES = [
    "AI Agent Developer",
    "AI Automation Engineer",
    "Agentic AI Engineer"
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

# 4. الكلمات المفتاحية للعمل عن بعد (شرط صارم)
REMOTE_POSITIVE_KEYWORDS = [
    "remote", "work from home", "wfh", "anywhere", "distributed", "عن بعد", "عن بُعد"
]

# الكلمات التي تستبعد الوظيفة إذا كانت إجبارية (On-site / Hybrid)
NON_REMOTE_NEGATIVE_KEYWORDS = [
    "on-site only", "onsite only", "in-office only", "hybrid only", "must relocate"
]

# 5. مسارات ملفات السيرة الذاتية
CV_AI_PATH = os.path.join("data", "cvs", "CV_AI.pdf")
CV_PM_PATH = os.path.join("data", "cvs", "CV_PM.pdf")

# 6. الروابط الشخصية الثابتة
LINKEDIN_URL = "https://www.linkedin.com/in/mohamed-fathi-pm/"
GITHUB_URL = "https://github.com/string-MFathi"

# 7. قوالب الإيميل المعتمدة
AI_EMAIL_TEMPLATE = """Hi {hiring_name},

{opening_hook}

Most "AI agent" portfolios stop at a working demo. Mine had to survive production: I built an autonomous outbound lead-discovery engine — a fail-closed pipeline that recovers from API failures via SQLite idempotency locks and automated state reconciliation, with LLM output constrained to schema-validated JSON specifically to eliminate hallucinated claims before they reach production.

That's the gap I'd close for {company_name}: {bridge_sentence}

Repo with the actual architecture: {github_url}

Worth a 15-minute call to see if this maps to what you're building remotely?

Mohamed Fathi
LinkedIn: {linkedin_url}
GitHub: {github_url}"""

PM_EMAIL_TEMPLATE = """Hi {hiring_name},

{opening_hook}

Most PMs hand bugs to engineering and wait. In my previous product roles, I tested API endpoints myself via Postman, monitored cloud infrastructure directly, and cut average ticket resolution time by 16% — because I could diagnose the technical root cause before escalating, not after.

I also built end-to-end workflow automations (Zapier/Make & custom Python agents) that cut payment and operational processing cycles from 5 days to 24 hours, while maintaining 97% CSAT.

{bridge_sentence}

Happy to walk through the specifics on a short remote call.

Mohamed Fathi
LinkedIn: {linkedin_url}
Portfolio & GitHub: {github_url}"""

def get_role_track(job_title: str) -> str:
    """توجيه حتمي (Deterministic Routing) لتحديد المسار والـ CV بدون استهلاك Tokens"""
    title_low = (job_title or "").lower()
    for pm_role in PM_ROLES:
        if pm_role.lower() in title_low or "product manager" in title_low:
            return "PM"
    return "AI"
