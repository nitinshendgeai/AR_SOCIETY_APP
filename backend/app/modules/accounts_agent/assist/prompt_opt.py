"""Turn what a person typed — in English, Hindi or Marathi, in Devanagari or Latin letters — into a short, clean query.

All of this runs locally and costs no API tokens. It does three things:

* drops greetings, politeness and filler ("namaste sir, kripya batayein ki…", "मला सांगा की…") and repeated punctuation,
  so neither the library search nor (when it is needed at all) the AI request carries them;
* maps the society words people use in Hindi and Marathi to the English words the bye-laws use ("थकबाकी", "bakaya" →
  arrears), so a Marathi question finds the English model bye-law clause without any translation call;
* notes the language, so a worded answer can come back in it from the same single request (no second "translate"
  call), and gives a stable key for reusing an earlier answer to the same question.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

# Filler that carries no meaning for the search or the answer. Matched as whole words / phrases, longest first.
_FILLER_PHRASES = [
    # English
    "can you please tell me", "could you please tell me", "can you tell me", "could you tell me", "please tell me",
    "i want to know", "i would like to know", "i wanted to know", "let me know", "kindly tell me", "tell me",
    "good morning", "good evening", "good afternoon", "thank you", "thanks", "please", "kindly", "hello", "hi", "hey",
    "dear", "sir", "madam", "maam", "ji",
    # Hindi / Marathi in Latin letters
    "kripya batayein", "kripya bataiye", "kripya bataye", "mujhe batao", "mujhe bataiye", "bataiye", "batao",
    "batayein", "mala sanga", "sanga na", "krupaya sanga", "krupaya", "kripya", "namaste", "namaskar", "dhanyavad",
    "dhanyawad", "shukriya", "sahab", "saheb", "bhai", "dada", "tai",
    # Devanagari
    "कृपया बताइए", "कृपया बताएं", "मुझे बताइए", "मुझे बताओ", "बताइए", "बताओ", "बताएं", "कृपया सांगा", "कृपया",
    "मला सांगा", "सांगा ना", "सांगा", "नमस्ते", "नमस्कार", "धन्यवाद", "शुक्रिया", "साहब", "साहेब", "जी",
]
_FILLER = re.compile(
    r"(?<![\wऀ-ॿ])(?:" + "|".join(re.escape(p) for p in sorted(_FILLER_PHRASES, key=len, reverse=True))
    + r")(?![\wऀ-ॿ])", re.IGNORECASE)

# Society words in Hindi / Marathi (Devanagari and common Latin spellings) → the words bye-laws and the books use.
GLOSSARY = {
    # meetings
    "सभा": ["meeting"], "बैठक": ["meeting"], "बैठकी": ["meeting"], "sabha": ["meeting"], "baithak": ["meeting"],
    "वार्षिक": ["annual"], "varshik": ["annual"], "सर्वसाधारण": ["general"], "आमसभा": ["general", "meeting"],
    "विशेष": ["special"], "vishesh": ["special"], "गणपूर्ति": ["quorum"], "कोरम": ["quorum"], "korum": ["quorum"],
    "सूचना": ["notice"], "नोटीस": ["notice"], "नोटिस": ["notice"], "notis": ["notice"], "suchna": ["notice"],
    "सूचनापत्र": ["notice"], "दिवस": ["days"], "दिन": ["days"], "din": ["days"], "divas": ["days"],
    "कार्यसूची": ["agenda"], "विषयसूची": ["agenda"], "agenda": ["agenda"],
    "समिती": ["committee"], "समिति": ["committee"], "samiti": ["committee"], "kamiti": ["committee"],
    "अध्यक्ष": ["chairman"], "सचिव": ["secretary"], "खजिनदार": ["treasurer"], "कोषाध्यक्ष": ["treasurer"],
    "निवडणूक": ["election"], "चुनाव": ["election"], "chunav": ["election"], "nivadnuk": ["election"],
    # money
    "थकबाकी": ["arrears", "dues"], "बकाया": ["arrears", "dues"], "bakaya": ["arrears", "dues"],
    "thakbaki": ["arrears", "dues"], "देय": ["dues"], "शुल्क": ["charges"], "shulk": ["charges"],
    "व्याज": ["interest"], "ब्याज": ["interest"], "byaj": ["interest"], "vyaj": ["interest"],
    "दंड": ["penalty", "fine"], "जुर्माना": ["penalty", "fine"], "jurmana": ["penalty", "fine"],
    "dand": ["penalty", "fine"], "मेंटेनन्स": ["maintenance"], "देखभाल": ["maintenance"], "dekhbhal": ["maintenance"],
    "देखरेख": ["maintenance"], "निधी": ["fund"], "निधि": ["fund"], "nidhi": ["fund"], "फंड": ["fund"],
    "दुरुस्ती": ["repairs"], "मरम्मत": ["repairs"], "marammat": ["repairs"], "durusti": ["repairs"],
    "खर्च": ["expenditure", "expense"], "kharch": ["expenditure", "expense"], "kharcha": ["expenditure", "expense"],
    "पावती": ["receipt"], "रसीद": ["receipt"], "rasid": ["receipt"], "pavti": ["receipt"],
    "बिल": ["bill"], "भुगतान": ["payment"], "bhugtan": ["payment"], "पेमेंट": ["payment"], "जमा": ["receipt"],
    "रोख": ["cash"], "नकद": ["cash"], "नगद": ["cash"], "rokh": ["cash"], "nakad": ["cash"], "nagad": ["cash"],
    "बँक": ["bank"], "बैंक": ["bank"],
    # property and people
    "भाडेकरू": ["tenant", "licensee"], "किरायेदार": ["tenant", "licensee"], "kirayedar": ["tenant", "licensee"],
    "bhadekaru": ["tenant", "licensee"], "भाडे": ["rent", "licence"], "किराया": ["rent", "licence"],
    "kiraya": ["rent", "licence"], "bhade": ["rent", "licence"],
    "सदनिका": ["flat"], "फ्लॅट": ["flat"], "फ्लैट": ["flat"], "सदस्य": ["member"], "सभासद": ["member"],
    "sabhasad": ["member"], "sadasya": ["member"],
    "हस्तांतरण": ["transfer"], "हस्तांतर": ["transfer"], "hastantaran": ["transfer"], "विक्री": ["transfer", "sale"],
    "बिक्री": ["transfer", "sale"], "नामनिर्देशन": ["nomination"], "नामांकन": ["nomination"], "वारस": ["nominee"],
    "पार्किंग": ["parking"], "वाहन": ["vehicle"], "गाडी": ["vehicle"], "गाड़ी": ["vehicle"], "gadi": ["vehicle"],
    "पाळीव": ["pets"], "पालतू": ["pets"], "जनावर": ["animals"], "लेखापरीक्षण": ["audit"], "ऑडिट": ["audit"],
    "अंदाजपत्रक": ["budget"], "बजेट": ["budget"], "गळती": ["leakage"], "लीकेज": ["leakage"],
}
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_MARATHI_MARKERS = ("आहे", "आहेत", "काय", "किती", "कसे", "कसा", "साठी", "मध्ये", "ची ", "चे ", "ला ", "नाही", "होते")
_HINDI_MARKERS = ("है", "हैं", "क्या", "कितने", "कितना", "कैसे", "के लिए", "में", "का ", "की ", "नहीं", "था")
_LATIN_MARATHI = ("ahe", "kay", "kiti", "kasa", "sathi", "madhe", "nahi ahe")
_LATIN_HINDI = ("hai", "kya", "kitne", "kitna", "kaise", "ke liye", "mein", "nahi hai")
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*|[ऀ-ॿ]+")
# Marathi / Hindi endings to strip before looking a word up ("सभेसाठी" → "सभे" → "सभा", "दिवसांची" → "दिवस").
_SUFFIXES = sorted(["साठी", "मध्ये", "मधील", "ांची", "ांचे", "ांचा", "ाची", "ाचे", "ाचा", "ची", "चे", "चा", "च्या",
                    "ला", "ना", "ने", "नी", "त", "ात", "ांत", "वर", "पर्यंत", "के", "की", "का", "को", "में", "से",
                    "ों", "ें", "ाँ", "ां"], key=len, reverse=True)


def lookup(word: str) -> List[str]:
    """The English words for one typed word (exact, then without an Indian-language ending, then by its stem)."""
    w = word.lower()
    if w in GLOSSARY:
        return GLOSSARY[w]
    if not _DEVANAGARI.search(w):
        return []
    stems = [w]
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) > len(suf) + 1:
            stems.append(w[: -len(suf)])
    for st in list(stems):
        if st.endswith("े"):
            stems.append(st[:-1] + "ा")                   # सभे → सभा
    for st in stems:
        if st in GLOSSARY:
            return GLOSSARY[st]
    for key in sorted(GLOSSARY, key=len, reverse=True):   # the longest known word the typed one starts with
        if len(key) >= 3 and _DEVANAGARI.search(key) and w.startswith(key):
            return GLOSSARY[key]
    return []


@dataclass
class OptimizedQuery:
    original: str
    text: str                       # the question without filler, trimmed — what an AI request would carry
    language: str                   # "en" | "hi" | "mr"
    keywords: List[str] = field(default_factory=list)   # English search words, including mapped local terms

    @property
    def search_text(self) -> str:
        """The text the library search runs on: the cleaned question plus the mapped English words."""
        extra = [k for k in self.keywords if k not in self.text.lower()]
        return (self.text + " " + " ".join(extra)).strip()

    @property
    def reply_language(self) -> str:
        return {"hi": "Hindi", "mr": "Marathi"}.get(self.language, "English")

    def key(self, *parts: Iterable[str]) -> str:
        """A stable key for 'the same question about the same sources' (word order and case do not matter)."""
        words = sorted(set(_WORD.findall(self.text.lower())) | set(self.keywords))
        blob = "|".join([" ".join(words)] + [",".join(sorted(map(str, p))) for p in parts])
        return hashlib.sha256(blob.encode()).hexdigest()


def detect_language(text: str) -> str:
    t = f" {text.lower()} "
    if _DEVANAGARI.search(text):
        mr = sum(m in t for m in _MARATHI_MARKERS)
        hi = sum(m in t for m in _HINDI_MARKERS)
        return "mr" if mr > hi else "hi"
    if any(f" {m} " in t for m in _LATIN_MARATHI):
        return "mr"
    if any(f" {m} " in t for m in _LATIN_HINDI):
        return "hi"
    return "en"


def normalize(text: str, max_chars: int = 400) -> OptimizedQuery:
    original = (text or "").strip()
    lang = detect_language(original)
    t = _FILLER.sub(" ", original)
    t = re.sub(r"([?!.,।])\1+", r"\1", t)                 # "??" → "?"
    t = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", " ", t)   # emoji
    t = re.sub(r"\s+", " ", t).strip(" ,.;:-–—")
    if not t:
        t = original
    if len(t) > max_chars:
        t = t[:max_chars].rsplit(" ", 1)[0]
    keywords: List[str] = []
    for w in _WORD.findall(t.lower()):
        for k in lookup(w):
            if k not in keywords:
                keywords.append(k)
    return OptimizedQuery(original=original, text=t, language=lang, keywords=keywords)


# ── Shrinking what an AI request carries ─────────────────────────────────────────────────────────────────────────────

_SENTENCE = re.compile(r"(?<=[.;:।])\s+|\n+")


def relevant_excerpt(text: str, words: Sequence[str], limit: int = 1200) -> str:
    """The sentences of a clause that mention the question's words (with their neighbours), at most [limit] chars.
    A short clause is sent whole; a long one is cut to what matters instead of the first 4,000 characters."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    sentences = [s for s in _SENTENCE.split(text) if s.strip()]
    wanted = {w.lower() for w in words if len(w) > 2}
    keep = set()
    for i, s in enumerate(sentences):
        low = s.lower()
        if any(w in low for w in wanted):
            keep.update({i - 1, i, i + 1})
    keep.add(0)                                          # the opening sentence says what the clause is about
    out, size = [], 0
    for i in sorted(k for k in keep if 0 <= k < len(sentences)):
        s = sentences[i].strip()
        if size + len(s) > limit:
            break
        out.append(s)
        size += len(s) + 1
    return " … ".join(out) if out else text[:limit]


def rank_names(items: Sequence[dict], text: str, k: int) -> List[dict]:
    """The [k] items whose names share most words with [text] (then the rest in their own order), so a request carries
    the likely ledgers and vendors instead of the whole chart."""
    words = set(_WORD.findall((text or "").lower()))
    for w in list(words):
        words.update(lookup(w))

    def score(x: dict) -> int:
        name = set(_WORD.findall(str(x.get("name", "")).lower()))
        return len(name & words)
    ranked = sorted(enumerate(items), key=lambda p: (-score(p[1]), p[0]))
    return [x for _, x in ranked[:k]]
