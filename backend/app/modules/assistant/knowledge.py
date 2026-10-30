"""Deterministic knowledge index over an allowlist of approved help documents.

Only the files named in APPROVED_DOCUMENTS are ever read, and only from inside the docs directory. Nothing else in the
repository (env files, fixtures, code, RBAC_MATRIX.md, developer rules) can reach the index. Text is split into chunks
along headings, scored with a small TF-IDF ranking (no vector store, no extra dependency), and a fixed number of the
best chunks is returned. Retrieved text is DATA: a chunk that looks like an instruction to the assistant is quarantined
at indexing time, and the provider prompt never treats chunk text as instructions (see service.py).
"""
import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CHUNKER_VERSION = "1"
MAX_FILE_BYTES = 2_000_000
MAX_CHUNK_CHARS = 1400
TOP_K = 4
MAX_CONTEXT_CHARS = 6000

DOCS_ROOT = Path(__file__).resolve().parents[4] / "docs"


@dataclass(frozen=True)
class ApprovedDocument:
    path: str          # relative to the docs directory
    title: str
    kind: str          # "md" | "html"


# Adding a document here is a reviewed change (see docs/HELP_ASSISTANT.md, "Knowledge sources").
# Deliberately absent: RBAC_MATRIX.md (stale role coverage, not a permissions source), AI_DEVELOPMENT_RULES.md and
# ARCHITECTURE.md (developer documents), KNOWN_ISSUES.md, audit reports, anything outside docs/.
APPROVED_DOCUMENTS: Tuple[ApprovedDocument, ...] = (
    ApprovedDocument("user-guide/DUX_OS_Help_Guide.html", "DUX OS Help Guide", "html"),
    ApprovedDocument("GUIDES/MAINTENANCE_BILLING_COMPLETE_GUIDE.md", "Maintenance Billing — Complete Guide", "md"),
    ApprovedDocument("GUIDES/MAINTENANCE_ELEMENT_WISE_MANUAL.md", "Maintenance Billing — Element-wise Help Manual", "md"),
    ApprovedDocument("GUIDES/VENDOR_MASTERS_COMPLETE_GUIDE.md", "Vendors, Work Orders and Contracts — Complete Guide", "md"),
    ApprovedDocument("MODULES/ACCOUNTS.md", "Accounts Module", "md"),
    ApprovedDocument("ACCOUNTING_PROCEDURE.md", "Accounting Procedure", "md"),
)

# Text that tries to instruct the assistant. A chunk matching any of these is never indexed.
_INJECTION = re.compile(
    r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier|system|security)\b"
    r"|you\s+are\s+now\b|system\s+prompt|developer\s+message|jailbreak"
    r"|(reveal|print|show|send)\s+[^.\n]{0,40}(secret|api[\s_-]?key|password|token)"
    r"|act\s+as\s+(an?\s+)?(admin|root|superuser)",
    re.IGNORECASE,
)


def looks_like_injection(text: str) -> bool:
    return bool(_INJECTION.search(text or ""))


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document: str
    title: str
    section: str
    roles: Tuple[str, ...]
    text: str
    order: int = 0


@dataclass
class KnowledgeIndex:
    version: str
    chunks: List[Chunk] = field(default_factory=list)
    documents: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    quarantined: int = 0
    _idf: Dict[str, float] = field(default_factory=dict, repr=False)
    _tf: List[Counter] = field(default_factory=list, repr=False)
    _head_tf: List[Counter] = field(default_factory=list, repr=False)
    _pairs: List[set] = field(default_factory=list, repr=False)

    def search(self, query: str, audience_roles: Tuple[str, ...] = (), top_k: int = TOP_K) -> List[Tuple[Chunk, float]]:
        q = [t for t in dict.fromkeys(tokenize(query))]
        if not q or not self.chunks:
            return []
        scored = []
        for i, chunk in enumerate(self.chunks):
            tf, head = self._tf[i], self._head_tf[i]
            matched = [t for t in q if tf.get(t) or head.get(t)]
            if not matched:
                continue
            score = sum(self._idf.get(t, 0.0) * ((1 + math.log(tf[t])) if tf.get(t) else 0.0)
                        + 4.0 * self._idf.get(t, 0.0) * (1 if head.get(t) else 0) for t in matched)
            score *= len(matched) / len(q)                       # reward covering more of the question
            score *= 1 + 0.25 * sum(1 for a, b in zip(q, q[1:]) if (a + " " + b) in self._pairs[i])   # neighbouring words together
            if audience_roles and any(r in chunk.roles for r in audience_roles):
                score *= 1.15                                    # prefer the part written for this person's role
            scored.append((score, len(matched), chunk))
        need = 1 if len(q) == 1 else 2
        scored = [s for s in scored if s[1] >= need]
        scored.sort(key=lambda s: (-s[0], s[2].order))
        picked, used = [], 0
        for score, _, chunk in scored:
            if len(picked) >= top_k or used + len(chunk.text) > MAX_CONTEXT_CHARS:
                continue
            picked.append((chunk, round(score, 4)))
            used += len(chunk.text)
        return picked


_STOP = frozenset("""a an and are as at be but by can do does did for from has have how i if in into is it its me my of on
or our so that the their then there these this to us was we what when where which who why will with would you your should
could please tell about need want get make""".split())


def _stem(t: str) -> str:
    if len(t) > 4 and t.endswith("ies"):
        t = t[:-3] + "y"
    elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    if len(t) > 5 and t.endswith("ing"):
        t = t[:-3]
    elif len(t) > 4 and t.endswith("ed"):
        t = t[:-2]
    if len(t) > 4 and t.endswith("e"):
        t = t[:-1]                              # generate / generating / generated all become "generat"
    return t


def tokenize(text: str) -> List[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in _STOP and len(t) >= 2]


# ── Document → sections ──────────────────────────────────────────────────────

Section = Tuple[str, Tuple[str, ...], str]           # (heading path, roles, text)


def _split_long(text: str) -> List[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n|\n(?=\d+\.\s|[-*]\s|\|)", text):
        if cur and len(cur) + len(para) + 1 > MAX_CHUNK_CHARS:
            parts.append(cur.strip())
            cur = ""
        while len(para) > MAX_CHUNK_CHARS:
            parts.append(para[:MAX_CHUNK_CHARS].strip())
            para = para[MAX_CHUNK_CHARS:]
        cur += para + "\n"
    if cur.strip():
        parts.append(cur.strip())
    return parts


def markdown_sections(text: str) -> List[Section]:
    stack: List[Tuple[int, str]] = []
    buf: List[str] = []
    out: List[Section] = []
    in_fence = False

    def flush():
        body = "\n".join(buf).strip()
        if body:
            heads = [h for lvl, h in stack if lvl > 1] or [h for _, h in stack]     # the document title is not a section
            out.append((" › ".join(heads) or "Introduction", (), body))
        buf.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"^(#{1,4})\s+(.*\S)\s*$", line)
        if m:
            flush()
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, re.sub(r"[*_`]", "", m.group(2)).strip()))
        else:
            buf.append(line)
    flush()
    return out


class _GuideParser(HTMLParser):
    """The help guide: <section data-roles data-title> blocks with h2/h3 headings, p, li and table rows."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections: List[Section] = []
        self.title = ""
        self._roles: Tuple[str, ...] = ()
        self._sec_title = ""
        self._sub = ""
        self._lines: List[str] = []
        self._text: List[str] = []
        self._skip = 0
        self._cap: Optional[str] = None
        self._ol: List[int] = []
        self._in_li = False
        self._in_section = False

    def _flush_text(self, prefix=""):
        t = re.sub(r"\s+", " ", "".join(self._text)).strip()
        self._text = []
        if t:
            self._lines.append(prefix + t)

    def _flush_section(self):
        body = "\n".join(self._lines).strip()
        if body:
            path = " › ".join(x for x in (self._sec_title, self._sub) if x)
            self.sections.append((path or "Introduction", self._roles, body))
        self._lines = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "svg", "nav", "head"):
            self._skip += 1
            return
        if tag == "section" and a.get("data-title"):
            self._flush_section()
            self._in_section = True
            self._sec_title = a.get("data-title", "")
            self._sub = ""
            self._roles = tuple((a.get("data-roles") or "all").split())
        elif tag in ("h2", "h3", "h4", "p", "li", "tr", "td", "th", "div", "br"):
            if not (self._in_li and tag in ("p", "div", "br", "td", "th", "tr")):     # a step keeps its inner blocks
                self._flush_text()
            if tag in ("h3", "h4") and self._in_section:
                self._flush_section()
            self._cap = tag if tag in ("h2", "h3", "h4", "li") else self._cap
        if tag == "ol":
            self._ol.append(0)
        elif tag == "li" and self._ol:
            self._ol[-1] += 1
        if tag == "li":
            self._in_li = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg", "nav", "head"):
            self._skip = max(0, self._skip - 1)
            return
        if tag == "title":
            return
        if tag == "ol" and self._ol:
            self._ol.pop()
        if tag in ("h2", "h3", "h4"):
            t = re.sub(r"\s+", " ", "".join(self._text)).strip()
            self._text = []
            if self._in_section and t:
                if tag == "h2":
                    self._sec_title = t
                else:
                    self._sub = t
        elif tag == "li":
            self._in_li = False
            prefix = f"{self._ol[-1]}. " if self._ol else "- "
            self._flush_text(prefix)
        elif tag in ("p", "tr", "div") and not self._in_li:
            self._flush_text()
        elif tag == "section":
            self._flush_text()
            self._flush_section()
            self._in_section = False

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def close(self):
        super().close()
        self._flush_text()
        self._flush_section()


def html_sections(text: str) -> List[Section]:
    p = _GuideParser()
    p.feed(text)
    p.close()
    return p.sections


# ── Index construction ───────────────────────────────────────────────────────

def _read_allowed(root: Path, rel: str) -> Optional[bytes]:
    path = (root / rel)
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())            # refuses symlinks / paths that leave the docs directory
        if not resolved.is_file() or resolved.stat().st_size > MAX_FILE_BYTES:
            return None
        return resolved.read_bytes()
    except (OSError, ValueError):
        return None


def build_index(docs_root: Optional[Path] = None, documents: Tuple[ApprovedDocument, ...] = APPROVED_DOCUMENTS) -> KnowledgeIndex:
    root = Path(docs_root) if docs_root is not None else DOCS_ROOT
    digest = hashlib.sha256(CHUNKER_VERSION.encode())
    chunks: List[Chunk] = []
    index = KnowledgeIndex(version="")
    order = 0
    for doc in sorted(documents, key=lambda d: d.path):
        raw = _read_allowed(root, doc.path)
        if raw is None:
            index.missing.append(doc.path)
            continue
        digest.update(doc.path.encode() + b"\0" + hashlib.sha256(raw).digest())
        text = raw.decode("utf-8", errors="replace")
        sections = html_sections(text) if doc.kind == "html" else markdown_sections(text)
        index.documents.append(doc.path)
        n = 0
        for path, roles, body in sections:
            for part in _split_long(body):
                if len(part) < 40:
                    continue
                if looks_like_injection(part) or looks_like_injection(path):
                    index.quarantined += 1
                    continue
                n += 1
                chunks.append(Chunk(f"{doc.path}#{n}", doc.path, doc.title, path, roles or ("all",), part, order))
                order += 1
    index.version = digest.hexdigest()[:12]
    index.chunks = chunks
    df: Counter = Counter()
    for c in chunks:
        tf = Counter(tokenize(c.text))
        head = Counter(tokenize(f"{c.title} {c.section}"))
        index._tf.append(tf)
        index._head_tf.append(head)
        toks = tokenize(c.text)
        index._pairs.append({a + " " + b for a, b in zip(toks, toks[1:])})
        df.update(set(tf) | set(head))
    total = max(len(chunks), 1)
    index._idf = {t: math.log(1 + total / n) for t, n in df.items()}
    return index


_cache: Dict[str, KnowledgeIndex] = {}


def get_index(docs_root: Optional[Path] = None) -> KnowledgeIndex:
    key = str(docs_root or DOCS_ROOT)
    if key not in _cache:
        _cache[key] = build_index(docs_root)
    return _cache[key]


def reset_index_cache() -> None:
    _cache.clear()


# ── Extractive helpers (used for steps and the no-provider answer) ───────────

def extract_steps(chunk_text: str, limit: int = 8) -> List[str]:
    steps = []
    for line in chunk_text.splitlines():
        s = line.strip()
        m = re.match(r"^(\d+)[.)]\s+(.*\S)$", s)
        if m:
            steps.append(m.group(2))
        elif s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 2 and cells[0].isdigit() and not set(cells[1]) <= set("-: "):
                steps.append(": ".join(c for c in cells[1:3] if c))
        if len(steps) >= limit:
            break
    return [re.sub(r"[*_`]", "", s)[:300] for s in steps]


def lead_text(chunk_text: str, limit: int = 500) -> str:
    """The start of a chunk as readable text: bullets and numbered table rows on their own lines, markdown marks
    removed, cut at a line or sentence end."""
    src = [l.strip() for l in chunk_text.splitlines()]
    lines = []
    for n, s in enumerate(src):
        if not s or re.fullmatch(r"\|[-: |]+\|", s):
            continue
        if s.startswith("|"):
            if n + 1 < len(src) and re.fullmatch(r"\|[-: |]+\|", src[n + 1]):
                continue                                          # the table's header row
            cells = [c.strip() for c in s.strip("|").split("|") if c.strip()]
            s = (f"{cells[0]}. " + " — ".join(cells[1:])) if cells and cells[0].isdigit() else "• " + " — ".join(cells)
        else:
            s = re.sub(r"^[-*]\s+", "• ", s)
        lines.append(re.sub(r"[*`#>]|(?<!\w)_|_(?!\w)", "", s))
    out = "\n".join(lines)
    if len(out) <= limit:
        return out
    cut = out[:limit]
    boundary = max(cut.rfind("\n"), cut.rfind(". "))
    return (cut[:boundary + 1] if boundary > limit // 2 else cut.rsplit(" ", 1)[0]).rstrip() + " …"
