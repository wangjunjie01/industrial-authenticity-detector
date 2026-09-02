"""Ephemeral, privacy-preserving research support for local optimization.

Only user-approved search queries leave the computer. Downloaded documents are
bounded, reduced to short evidence cards, and never written to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import ipaddress
import json
import os
import re
import socket
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


BRAVE_PRIVACY_URL = "https://api-dashboard.search.brave.com/documentation/resources/privacy-notice"
SESSION_TTL_SECONDS = 30 * 60
MAX_DOCUMENT_BYTES = 2_000_000
MAX_PDF_PAGES = 20
MAX_QUERIES = 8
MAX_URLS = 12


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.date = ""
        self._in_title = False
        self._blocked = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._blocked += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            values = {key.lower(): (value or "") for key, value in attrs}
            name = (values.get("name") or values.get("property") or "").lower()
            if name in {"article:published_time", "date", "datepublished", "dc.date"}:
                self.date = values.get("content", "")[:80]

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"} and self._blocked:
            self._blocked -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._blocked or not data.strip():
            return
        if self._in_title:
            self.title += " " + data.strip()
        else:
            self.parts.append(data.strip())


def _public_https_url(url: str, resolver: Callable[..., Any] = socket.getaddrinfo) -> str:
    if not isinstance(url, str) or len(url) > 2_048:
        raise ValueError("Source URL must be HTTPS and no longer than 2,048 characters.")
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS source URLs are accepted.")
    if parsed.port not in {None, 443}:
        raise ValueError("Only the standard HTTPS port is accepted.")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local and private network sources are not accepted.")
    try:
        addresses = {item[4][0] for item in resolver(host, 443, type=socket.SOCK_STREAM)}
    except (OSError, socket.gaierror) as exc:
        raise ValueError("Source hostname could not be resolved safely.") from exc
    if not addresses:
        raise ValueError("Source hostname did not resolve.")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
        if not ip.is_global:
            raise ValueError("Local, private, reserved, or non-public source addresses are not accepted.")
    return parsed.geturl()


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, resolver: Callable[..., Any]) -> None:
        self.resolver = resolver
        super().__init__()

    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Request | None:
        target = _public_https_url(urljoin(req.full_url, newurl), self.resolver)
        return super().redirect_request(req, fp, code, msg, headers, target)


def _download_document(url: str, resolver: Callable[..., Any]) -> dict[str, Any]:
    safe_url = _public_https_url(url, resolver)
    opener = build_opener(_SafeRedirectHandler(resolver))
    request = Request(safe_url, headers={"User-Agent": "IndustrialAuthenticityDetector/0.4"})
    with opener.open(request, timeout=8) as response:
        final_url = _public_https_url(response.geturl(), resolver)
        content_type = response.headers.get_content_type().lower()
        if content_type not in {"text/html", "text/plain", "application/pdf"}:
            raise ValueError("Source content type is not supported.")
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > MAX_DOCUMENT_BYTES:
            raise ValueError("Source exceeds the 2 MB download limit.")
        body = response.read(MAX_DOCUMENT_BYTES + 1)
        if len(body) > MAX_DOCUMENT_BYTES:
            raise ValueError("Source exceeds the 2 MB download limit.")
    return {"url": final_url, "content_type": content_type, "body": body}


def _document_text(document: dict[str, Any]) -> tuple[str, str, str]:
    body = document["body"]
    content_type = document["content_type"]
    if content_type == "application/pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:
            raise ValueError("PDF extraction requires the optional research dependency.") from exc
        reader = PdfReader(BytesIO(body))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError("PDF exceeds the 20-page extraction limit.")
        text = " ".join((page.extract_text() or "") for page in reader.pages)
        return text, "", ""
    decoded = body.decode("utf-8", errors="replace")
    if content_type == "text/plain":
        return decoded, "", ""
    parser = _TextExtractor()
    parser.feed(decoded)
    return " ".join(parser.parts), parser.title.strip(), parser.date


def _source_type(url: str, text: str) -> tuple[str, str]:
    host = (urlsplit(url).hostname or "").lower()
    folded = (host + " " + text[:1_000]).lower()
    if host.endswith(".gov") or "standard" in folded or "标准" in folded:
        return "standard_or_government", "high"
    if any(token in folded for token in ("doi.org", "journal", "university", "研究", "论文")):
        return "peer_reviewed_or_research", "high"
    if any(token in folded for token in ("datasheet", "technical data", "specification", "技术数据")):
        return "official_technical_material", "medium_high"
    if any(token in folded for token in ("association", "institute", "协会", "学会")):
        return "industry_organization", "medium"
    return "other_web", "review_required"


def _candidate_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    sentences = [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+|(?<=[。！？])", normalized)]
    signals = re.compile(r"\d|\b(?:must|should|requires?|risk|test|temperature|load|material|standard)\b|(?:必须|应当|风险|测试|温度|载荷|材料|标准)", re.I)
    selected = [item for item in sentences if 35 <= len(item) <= 500 and signals.search(item)]
    if not selected:
        selected = [item for item in sentences if 35 <= len(item) <= 500]
    return selected[:3]


def _keywords(text: str) -> list[str]:
    acronyms = re.findall(r"\b[A-Z][A-Z0-9-]{1,}\b", text)
    english = re.findall(r"\b[A-Za-z][A-Za-z0-9-]{2,}\b", text)
    chinese = re.findall(r"[\u4e00-\u9fff]{2,10}", text)
    stop = {"the", "and", "for", "with", "this", "that", "from", "into", "before", "after", "product", "solution"}
    terms: list[str] = []
    for item in acronyms + chinese + english:
        if item.casefold() in stop or item.casefold() in {x.casefold() for x in terms}:
            continue
        terms.append(item)
    queries = []
    for index in range(0, min(len(terms), 15), 3):
        query = " ".join(terms[index:index + 3]).strip()
        if query:
            queries.append(query[:200])
    return queries[:5]


@dataclass
class _Session:
    created_at: float
    queries: list[str]
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)


class ResearchManager:
    """Keeps short-lived research metadata in memory only."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        clock: Callable[[], float] = time.time,
        search_request: Callable[[str, str], list[dict[str, Any]]] | None = None,
        document_request: Callable[[str], dict[str, Any]] | None = None,
        resolver: Callable[..., Any] = socket.getaddrinfo,
    ) -> None:
        self.api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "") if api_key is None else api_key
        self.clock = clock
        self.search_request = search_request or self._brave_search
        self.resolver = resolver
        self.document_request = document_request or (lambda url: _download_document(url, self.resolver))
        self.sessions: dict[str, _Session] = {}

    def _purge(self) -> None:
        now = self.clock()
        self.sessions = {key: value for key, value in self.sessions.items() if now - value.created_at <= SESSION_TTL_SECONDS}

    def prepare(self, text: Any) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Text must contain at least one non-whitespace character.")
        if len(text) > 50_000:
            raise ValueError("Text exceeds the 50,000-character research preparation limit.")
        self._purge()
        queries = _keywords(text)
        session_id = uuid4().hex
        self.sessions[session_id] = _Session(self.clock(), queries)
        warnings = []
        if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text):
            warnings.append("email_address_detected")
        if re.search(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)", text):
            warnings.append("phone_or_long_identifier_detected")
        return {
            "research_session_id": session_id,
            "expires_in_seconds": SESSION_TTL_SECONDS,
            "candidate_queries": queries,
            "outbound_preview": queries,
            "sensitive_information_warnings": warnings,
            "brave_search_available": bool(self.api_key),
            "manual_url_import_available": True,
            "privacy_notice_url": BRAVE_PRIVACY_URL,
            "privacy": "No draft was sent. Only queries explicitly approved in the next step can leave this computer.",
        }

    def _session(self, session_id: Any) -> _Session:
        self._purge()
        if not isinstance(session_id, str) or session_id not in self.sessions:
            raise ValueError("Research session is missing or expired. Prepare the research again.")
        return self.sessions[session_id]

    def _brave_search(self, query: str, api_key: str) -> list[dict[str, Any]]:
        from urllib.parse import urlencode
        url = "https://api.search.brave.com/res/v1/web/search?" + urlencode({"q": query, "count": 5})
        request = Request(url, headers={"Accept": "application/json", "X-Subscription-Token": api_key})
        with build_opener().open(request, timeout=8) as response:
            body = response.read(1_000_001)
            if len(body) > 1_000_000:
                raise ValueError("Search response exceeds the 1 MB limit.")
            payload = json.loads(body.decode("utf-8"))
        return payload.get("web", {}).get("results", [])[:5]

    def search(self, session_id: Any, queries: Any, manual_urls: Any, allow_network: Any) -> dict[str, Any]:
        session = self._session(session_id)
        if allow_network is not True:
            raise ValueError("Network research requires explicit user approval.")
        if not isinstance(queries, list) or not isinstance(manual_urls, list):
            raise ValueError("Queries and manual_urls must be arrays.")
        if len(queries) > MAX_QUERIES:
            raise ValueError(f"No more than {MAX_QUERIES} approved queries are accepted per request.")
        if len(manual_urls) > MAX_URLS:
            raise ValueError(f"No more than {MAX_URLS} manual URLs are accepted per request.")
        cleaned_queries = []
        for query in queries:
            if not isinstance(query, str) or not query.strip() or len(query) > 200:
                raise ValueError("Each approved query must be 1 to 200 characters.")
            cleaned_queries.append(query.strip())
        cleaned_urls = []
        for url in manual_urls:
            cleaned_urls.append(_public_https_url(url, self.resolver))
        # User-selected documents receive priority over search results so a
        # broad query cannot crowd an explicitly supplied technical source out.
        source_rows: list[dict[str, Any]] = [{"url": url, "title": ""} for url in cleaned_urls]
        errors: list[dict[str, str]] = []
        if cleaned_queries and self.api_key:
            for query in cleaned_queries:
                try:
                    source_rows.extend(self.search_request(query, self.api_key))
                except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
                    errors.append({"type": "search_unavailable", "detail": type(exc).__name__})
        elif cleaned_queries:
            errors.append({"type": "brave_api_key_missing", "detail": "Manual URL import remains available."})
        seen: set[str] = set()
        cards: list[dict[str, Any]] = []
        fetched_at = datetime.now(timezone.utc).isoformat()
        for row in source_rows[:MAX_URLS]:
            raw_url = row.get("url", "") if isinstance(row, dict) else ""
            try:
                safe_url = _public_https_url(raw_url, self.resolver)
                if safe_url in seen:
                    continue
                seen.add(safe_url)
                document = self.document_request(safe_url)
                final_url = _public_https_url(document.get("url", safe_url), self.resolver)
                text, extracted_title, published = _document_text(document)
                source_type, credibility = _source_type(final_url, text)
                title = (row.get("title") or extracted_title or urlsplit(final_url).hostname or "Source")[:300]
                publisher = (urlsplit(final_url).hostname or "")[:200]
                for fact in _candidate_sentences(text):
                    fingerprint = sha256((final_url + "\n" + fact).encode("utf-8")).hexdigest()
                    fact_id = fingerprint[:20]
                    card = {
                        "fact_id": fact_id,
                        "fact_summary": fact,
                        "applicability": "Confirm that product, material, test method, and operating conditions match your draft.",
                        "source_title": title,
                        "publisher": publisher,
                        "url": final_url,
                        "published_date": published or None,
                        "fetched_at": fetched_at,
                        "source_type": source_type,
                        "credibility": credibility,
                        "content_fingerprint": fingerprint,
                        "confirmed": False,
                    }
                    session.evidence[fact_id] = card
                    cards.append(card)
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                errors.append({"type": "source_unavailable", "detail": type(exc).__name__})
        return {
            "research_session_id": session_id,
            "evidence_cards": cards,
            "errors": errors,
            "brave_search_used": bool(cleaned_queries and self.api_key),
            "offline_fallback_available": True,
            "privacy": "Approved queries and selected public source URLs were used. Full pages were not retained.",
        }

    def confirmed_facts(self, session_id: Any, fact_ids: Any) -> list[dict[str, Any]]:
        session = self._session(session_id)
        if not isinstance(fact_ids, list):
            raise ValueError("confirmed_source_fact_ids must be an array.")
        selected = []
        for fact_id in fact_ids:
            if not isinstance(fact_id, str) or fact_id not in session.evidence:
                raise ValueError("A confirmed source fact is unknown or has expired.")
            card = dict(session.evidence[fact_id])
            card["confirmed"] = True
            selected.append(card)
        return selected
