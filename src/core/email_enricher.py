import re
import urllib.parse
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup
import dns.resolver

class EmailEnrichmentLadder:
    """
    سلّم إثراء الإيميلات المطور (v2.0):
    1. استخراج الإيميل من نص الوظيفة.
    2. البحث المرن عن الموقع الرسمي للشركة عبر محركات البحث.
    3. التخمين الذكي للدومين (Domain Heuristics: .com, .io, .ai, .co, .net) مع فحص DNS MX الحقيقي.
    4. كشط صفحات الشركة (/careers, /contact, /about) لاستخراج الإيميل الفعلي قبل اللجوء لـ careers@domain.
    """
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        self.ignored_domains = {
            "wuzzuf.net", "bayt.com", "indeed.com", "indeed.ae", "indeed.sa", "indeed.eg",
            "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
            "google.com", "youtube.com", "glassdoor.com", "naukrigulf.com", "tanqeeb.com",
            "example.com", "sentry.io", "wixpress.com"
        }
        self.email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

    def extract_valid_emails_from_text(self, text: str) -> List[str]:
        if not text:
            return []
        found = self.email_regex.findall(text)
        clean_emails = []
        for email in found:
            email_low = email.lower().strip(".")
            domain = email_low.split("@")[-1]
            if any(ign in domain for ign in self.ignored_domains):
                continue
            if any(email_low.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".js", ".css"]):
                continue
            if email_low not in clean_emails:
                clean_emails.append(email_low)
        return clean_emails

    def verify_domain_mx(self, domain: str) -> bool:
        try:
            answers = dns.resolver.resolve(domain, "MX", lifetime=4.0)
            return len(answers) > 0
        except Exception:
            return False

    def _guess_domain_via_mx(self, company_name: str) -> Optional[str]:
        """توليد ذكي لدومين الشركة وفحص وجود الموقع + سجلات MX (ينقذ الشركات مثل Next Byte Lab)"""
        clean = re.sub(r"\b(llc|ltd|inc|corp|co|company|group|egypt|ksa|uae|for|and|the)\b", "", company_name.lower())
        slug = re.sub(r"[^a-z0-9]", "", clean)
        if len(slug) < 3 or len(slug) > 25:
            return None

        candidates = [f"{slug}.com", f"{slug}.io", f"{slug}.ai", f"{slug}.co", f"{slug}.net", f"{slug}.app"]
        with httpx.Client(timeout=5.0, headers=self.headers, follow_redirects=True) as client:
            for dom in candidates:
                if self.verify_domain_mx(dom):
                    try:
                        r = client.get(f"https://{dom}")
                        if r.status_code < 400:
                            return dom
                    except Exception:
                        continue
        return None

    def find_company_official_domain(self, company_name: str) -> Optional[str]:
        if not company_name or company_name.lower() in ["confidential", "unknown", "private company"]:
            return None

        # 1. بحث مرن عبر DuckDuckGo HTML
        query = f'{company_name} company website'
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        try:
            with httpx.Client(timeout=10.0, headers=self.headers, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.select("a.result__a, a.result__url"):
                        href = a.get("href", "").strip()
                        if "uddg=" in href:
                            parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                            href = parsed_qs.get("uddg", [href])[0]
                        if not href.startswith("http"):
                            href = "https://" + href.lstrip("/")
                        domain = urllib.parse.urlparse(href).netloc.lower().replace("www.", "")
                        if domain and "." in domain and not any(ign in domain for ign in self.ignored_domains):
                            if self.verify_domain_mx(domain):
                                return domain
        except Exception:
            pass

        # 2. إذا فشل محرك البحث، نستخدم التخمين الذكي الموثق بالـ MX والـ HTTP
        return self._guess_domain_via_mx(company_name)

    def scrape_domain_for_email(self, domain: str) -> Optional[str]:
        candidate_urls = [
            f"https://{domain}",
            f"https://{domain}/contact",
            f"https://{domain}/contact-us",
            f"https://{domain}/careers",
            f"https://{domain}/about"
        ]
        with httpx.Client(timeout=8.0, headers=self.headers, follow_redirects=True) as client:
            for url in candidate_urls:
                try:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        emails = self.extract_valid_emails_from_text(resp.text)
                        if emails:
                            for e in emails:
                                if any(k in e for k in ["career", "hr", "job", "talent", "recruit", "people", "info", "hello", "contact"]):
                                    return e
                            return emails[0]
                except Exception:
                    continue
        return None

    def enrich_company_email(self, company_name: str, job_text: str, explicit_domain: str = "") -> str:
        direct_emails = self.extract_valid_emails_from_text(job_text)
        if direct_emails:
            return direct_emails[0]

        domain = (explicit_domain or "").lower().replace("www.", "").strip()
        if not domain or any(ign in domain for ign in self.ignored_domains) or not self.verify_domain_mx(domain):
            domain = self.find_company_official_domain(company_name)

        if not domain:
            return ""

        scraped_email = self.scrape_domain_for_email(domain)
        if scraped_email:
            return scraped_email

        if self.verify_domain_mx(domain):
            return f"careers@{domain}"

        return ""
