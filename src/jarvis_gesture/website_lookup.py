from __future__ import annotations

import json
import re
from typing import List, Tuple
from urllib import parse, request


class WebsiteLookupService:
    def __init__(self, enabled: bool = True, timeout_seconds: float = 4.0, allowlist_csv: str = "") -> None:
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.allowlist = [x.strip().lower() for x in allowlist_csv.split(",") if x.strip()]

    def lookup(self, text: str) -> Tuple[bool, str]:
        if not self.enabled:
            return False, "Website lookup is disabled."

        url = self._extract_url(text)
        if url:
            if not self._is_url_allowed(url):
                return False, "URL is not in allowlist."
            return self._fetch_url_summary(url)

        return self._duckduckgo_instant_answer(text)

    def _extract_url(self, text: str) -> str:
        match = re.search(r"https?://[^\s]+", text)
        if not match:
            return ""
        return match.group(0)

    def _is_url_allowed(self, url: str) -> bool:
        if not self.allowlist:
            return True
        domain = parse.urlparse(url).netloc.lower()
        return any(domain.endswith(allowed) for allowed in self.allowlist)

    def _fetch_url_summary(self, url: str) -> Tuple[bool, str]:
        req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            return False, f"Failed to read URL: {exc}"

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        title = ""
        if title_match:
            title = self._clean_text(title_match.group(1))

        body_text = self._clean_text(re.sub(r"<[^>]+>", " ", html))
        summary = body_text[:260]
        if title:
            return True, f"{title}. {summary}"
        return True, summary

    def _duckduckgo_instant_answer(self, query: str) -> Tuple[bool, str]:
        q = query.strip()
        if not q:
            return False, "No lookup query provided."

        url = "https://api.duckduckgo.com/?" + parse.urlencode({"q": q, "format": "json", "no_html": 1})
        req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as exc:
            return False, f"Lookup failed: {exc}"

        abstract = self._clean_text(str(data.get("AbstractText", "")))
        heading = self._clean_text(str(data.get("Heading", "")))
        if abstract:
            if heading:
                return True, f"{heading}. {abstract[:260]}"
            return True, abstract[:260]

        return False, "No instant answer found. Try providing a specific URL."

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
