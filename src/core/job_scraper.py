import re
import time
import random
import urllib.parse
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

class MultiPlatformJobScraper:
    """
    محرك الكشط التاريخي واليومي العميق (v5.0):
    - في وضع BACKFILL (أول 3 أيام): يمسح حتى 8 صفحات لكل مسمى وظيفي + يبحث في أرشيف محركات البحث لعام 2026 بالكامل.
    - في وضع DAILY_DELTA (بعد اليوم الثالث): يركز على أحدث الصفحات المعلنة خلال آخر 24 ساعة.
    """
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0"
        ]

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"
        }

    def build_queries_for_platform(self, platform: str, roles: List[str], time_filter: str) -> List[str]:
        """تغطية شاملة لمساري AI Engineering و Product Management"""
        return [
            "AI Agent",
            "AI Engineer",
            "LLM Engineer",
            "Generative AI",
            "AI Automation",
            "Machine Learning Engineer",
            "Technical Product Manager",
            "Product Manager SaaS",
            "AI Product Manager",
            "Senior Product Manager",
            "Product Owner Tech"
        ]

    def _scrape_wuzzuf_paginated(self, keyword: str, max_pages: int = 8) -> List[Dict[str, str]]:
        results = []
        seen_urls = set()
        encoded_kw = urllib.parse.quote(keyword)

        with httpx.Client(timeout=15.0, headers=self._get_headers(), follow_redirects=True) as client:
            for page_idx in range(max_pages):
                url = f"https://wuzzuf.net/search/jobs/?q={encoded_kw}&start={page_idx}"
                try:
                    resp = client.get(url)
                    if resp.status_code != 200:
                        break
                    soup = BeautifulSoup(resp.text, "html.parser")
                    page_links = 0
                    for a_tag in soup.select("a[href*='/jobs/p/']"):
                        href = a_tag.get("href", "").strip().split("?")[0]
                        if href.startswith("/"):
                            href = "https://wuzzuf.net" + href
                        title = a_tag.get_text(strip=True)
                        if href.startswith("http") and href not in seen_urls and len(title) > 3:
                            seen_urls.add(href)
                            results.append({
                                "title": title,
                                "url": href,
                                "snippet": f"Wuzzuf job listing for {title} ({keyword})"
                            })
                            page_links += 1
                    if page_links == 0:
                        break
                    time.sleep(0.7)
                except Exception:
                    break
        return results

    def _scrape_bayt_paginated(self, keyword: str, max_pages: int = 8) -> List[Dict[str, str]]:
        results = []
        seen_urls = set()
        slug = keyword.lower().strip().replace(" ", "-")
        job_id_pattern = re.compile(r"-\d{5,}/?$")

        with httpx.Client(timeout=15.0, headers=self._get_headers(), follow_redirects=True) as client:
            for page_num in range(1, max_pages + 1):
                url = f"https://www.bayt.com/en/international/jobs/{slug}-jobs/?page={page_num}"
                try:
                    resp = client.get(url)
                    if resp.status_code != 200:
                        break
                    soup = BeautifulSoup(resp.text, "html.parser")
                    page_links = 0
                    for a_tag in soup.select("a[href*='/jobs/']"):
                        href = a_tag.get("href", "").strip().split("?")[0]
                        if href.startswith("/"):
                            href = "https://www.bayt.com" + href
                        if not job_id_pattern.search(href) and not a_tag.get("data-js-aid") == "jobID":
                            continue
                        title = a_tag.get_text(strip=True)
                        if href not in seen_urls and len(title) > 4:
                            seen_urls.add(href)
                            results.append({
                                "title": title,
                                "url": href,
                                "snippet": f"Bayt MENA job listing for {title} ({keyword})"
                            })
                            page_links += 1
                    if page_links == 0:
                        break
                    time.sleep(0.7)
                except Exception:
                    break
        return results

    def search_jobs_batch(self, platform: str, keyword: str, time_filter: str = "SINCE_JAN_2026", max_results: int = 45) -> List[Dict[str, str]]:
        results = []
        plat_low = platform.lower()
        pages_to_scan = 8 if time_filter == "SINCE_JAN_2026" else 2

        if plat_low == "wuzzuf":
            results = self._scrape_wuzzuf_paginated(keyword, max_pages=pages_to_scan)
        elif plat_low == "bayt":
            results = self._scrape_bayt_paginated(keyword, max_pages=pages_to_scan)

        if time_filter == "SINCE_JAN_2026" or plat_low in ["indeed", "ats_direct"] or len(results) < 10:
            if plat_low == "wuzzuf":
                ddg_queries = [
                    f'site:wuzzuf.net/jobs/p "{keyword}" 2026',
                    f'site:wuzzuf.net/jobs/careers "{keyword}"'
                ]
            elif plat_low == "bayt":
                ddg_queries = [
                    f'site:bayt.com/en/ "{keyword}" jobs 2026',
                    f'site:bayt.com "{keyword}" Remote'
                ]
            elif plat_low == "ats_direct":
                # صيد الشركات التي تعين عبر ATS خارج وظف وبيت
                ddg_queries = [
                    f'site:boards.greenhouse.io "{keyword}" (Remote OR MENA)',
                    f'site:jobs.lever.co "{keyword}" (Remote OR MENA)'
                ]
            else:
                ddg_queries = [
                    f'(site:ae.indeed.com OR site:sa.indeed.com OR site:eg.indeed.com) "{keyword}" 2026',
                    f'(site:ae.indeed.com OR site:sa.indeed.com OR site:eg.indeed.com) "{keyword}" Remote'
                ]

            seen = {r["url"] for r in results}
            for dq in ddg_queries:
                try:
                    with DDGS() as ddgs:
                        ddg_items = list(ddgs.text(dq, max_results=20))
                        for item in ddg_items:
                            href = item.get("href", "").split("?")[0]
                            if href.startswith("http") and href not in seen:
                                seen.add(href)
                                results.append({
                                    "title": item.get("title", ""),
                                    "url": href,
                                    "snippet": item.get("body", "")
                                })
                except Exception:
                    pass

        print(f"   ↳ Found {len(results)} job ads for [{platform} -> '{keyword}']")
        return results[:max_results]
    
    def fetch_job_page_content(self, url: str, fallback_title: str = "", fallback_snippet: str = "") -> str:
        extracted_parts = [f"URL: {url}", f"Search Title: {fallback_title}", f"Search Snippet: {fallback_snippet}"]

        try:
            with httpx.Client(timeout=12.0, headers=self._get_headers(), follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200 and len(resp.text) > 300:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    if soup.title and soup.title.string:
                        extracted_parts.append(f"Page Meta Title: {soup.title.string.strip()}")
                    for meta in soup.find_all("meta", attrs={"name": ["description", "og:title", "og:description"], "property": ["og:title", "og:description"]}):
                        content = meta.get("content", "").strip()
                        if content:
                            extracted_parts.append(f"Meta Info: {content}")

                    for script in soup.find_all("script", type="application/ld+json"):
                        if script.string and ("hiringOrganization" in script.string or "JobPosting" in script.string):
                            extracted_parts.append(f"Structured Job JSON: {script.string.strip()[:2000]}")

                    next_data = soup.find("script", id="__NEXT_DATA__")
                    if next_data and next_data.string:
                        extracted_parts.append(f"NextJS Data Snippet: {next_data.string.strip()[:2500]}")

                    for tag in soup(["script", "style", "noscript", "footer", "nav"]):
                        tag.decompose()
                    visible_text = " ".join(soup.get_text(separator=" ").split())
                    if visible_text:
                        extracted_parts.append(f"Visible Page Text: {visible_text[:2500]}")
        except Exception:
            pass

        full_text = "\n".join(extracted_parts)
        if len(full_text) < 400 or "just a moment" in full_text.lower():
            try:
                with httpx.Client(timeout=15.0, headers=self._get_headers(), follow_redirects=True) as client:
                    j_resp = client.get(f"https://r.jina.ai/{url}")
                    if j_resp.status_code == 200:
                        full_text += f"\nJina Content: {j_resp.text[:3000]}"
            except Exception:
                pass

        return full_text[:5000]
