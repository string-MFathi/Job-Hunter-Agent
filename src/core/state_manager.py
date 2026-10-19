import os
import json
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, Any, Tuple, List
from src.core.config import PLATFORMS, ALL_TARGET_ROLES

class JobHunterStateManager:
    """
    يدير آلة الزمن (Two-Phase State Machine) وقاعدة بيانات SQLite لمنع تكرار الشركات أو الروابط.
    - المرحلة 1 (Backfill): أول 3 جلسات/أيام، كل جلسة تمسح منصة واحدة بالكامل منذ يناير 2026.
    - المرحلة 2 (Daily Delta): بعد إنهاء المنصات الثلاث، يفحص آخر 24 ساعة في الـ 3 منصات يومياً.
    """
    def __init__(self):
        os.makedirs("data/state", exist_ok=True)
        self.state_file = "data/state/hunter_phase_state.json"
        self.db_path = "data/state/processed_jobs.sqlite"
        self._init_sqlite()
        self.state = self._load_state()

    def _init_sqlite(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_urls (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT,
                    platform TEXT,
                    discovered_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_companies (
                    company_norm TEXT PRIMARY KEY,
                    official_email TEXT,
                    platform TEXT,
                    discovered_at TEXT
                )
            """)
            conn.commit()

    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        default_state = {
            "mode": "BACKFILL",  # BACKFILL or DAILY_DELTA
            "backfill_platform_index": 0,  # 0: Wuzzuf, 1: Bayt, 2: Indeed
            "completed_backfill_platforms": [],
            "total_sessions_completed": 0,
            "last_run_date": ""
        }
        self._save_state(default_state)
        return default_state

    def _save_state(self, state_data: Dict[str, Any]):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)

    def get_current_session_plan(self) -> Dict[str, Any]:
        """يحدد خطة الجلسة الحالية: هل نحن في مرحلة الكشط التاريخي أم المراقبة اليومية؟"""
        mode = self.state.get("mode", "BACKFILL")
        idx = self.state.get("backfill_platform_index", 0)

        if mode == "BACKFILL" and idx < len(PLATFORMS):
            target_platform = PLATFORMS[idx]
            return {
                "mode": "BACKFILL",
                "day_number": idx + 1,
                "platforms_to_scan": [target_platform],
                "time_filter": "SINCE_JAN_2026",
                "roles": ALL_TARGET_ROLES,
                "description": f"المرحلة التاريخية (اليوم {idx + 1}/3) — مسح شامل لمنصة {target_platform} منذ يناير 2026"
            }
        else:
            return {
                "mode": "DAILY_DELTA",
                "day_number": self.state.get("total_sessions_completed", 3) + 1,
                "platforms_to_scan": PLATFORMS,
                "time_filter": "LAST_24_HOURS",
                "roles": ALL_TARGET_ROLES,
                "description": "مرحلة الفلتر اليومي الذكي — فحص وظائف آخر 24 ساعة في المنصات الثلاث (Wuzzuf, Bayt, Indeed)"
            }

    def mark_session_completed(self):
        """تحديث آلة الزمن بعد انتهاء جلسة اليوم بنجاح"""
        mode = self.state.get("mode", "BACKFILL")
        idx = self.state.get("backfill_platform_index", 0)

        if mode == "BACKFILL":
            if idx < len(PLATFORMS):
                plat = PLATFORMS[idx]
                if plat not in self.state["completed_backfill_platforms"]:
                    self.state["completed_backfill_platforms"].append(plat)
            idx += 1
            self.state["backfill_platform_index"] = idx
            if idx >= len(PLATFORMS):
                self.state["mode"] = "DAILY_DELTA"
                print("🎉 [State Machine] Completed all 3 historical backfill days! Switching to DAILY_DELTA mode from tomorrow.")

        self.state["total_sessions_completed"] = self.state.get("total_sessions_completed", 0) + 1
        self.state["last_run_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_state(self.state)

    @staticmethod
    def _hash_url(url: str) -> str:
        clean = (url or "").strip().lower().split("?")[0]
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    @staticmethod
    def normalize_company(name: str) -> str:
        return " ".join((name or "").strip().lower().split())

    def is_url_seen(self, url: str) -> bool:
        h = self._hash_url(url)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT 1 FROM seen_urls WHERE url_hash = ?", (h,))
            return cur.fetchone() is not None

    def mark_url_seen(self, url: str, platform: str):
        h = self._hash_url(url)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO seen_urls (url_hash, url, platform, discovered_at) VALUES (?, ?, ?, ?)",
                (h, url, platform, datetime.now().isoformat())
            )
            conn.commit()

    def is_company_seen(self, company_name: str) -> bool:
        norm = self.normalize_company(company_name)
        if not norm or norm in ["confidential", "unknown", "private company", "شركة خاصة"]:
            return False
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT 1 FROM seen_companies WHERE company_norm = ?", (norm,))
            return cur.fetchone() is not None

    def mark_company_seen(self, company_name: str, email: str, platform: str):
        norm = self.normalize_company(company_name)
        if not norm:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO seen_companies (company_norm, official_email, platform, discovered_at) VALUES (?, ?, ?, ?)",
                (norm, email, platform, datetime.now().isoformat())
            )
            conn.commit()
