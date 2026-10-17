"""Child-safety and answer-protection checks (design doc section 11, plus the review fixes).

All of these are fixed rules, not AI tuning (design rule 1).

INPUT (what the child types, checked BEFORE the AI is called):
  * cut to 200 characters
  * rude words -> a kind line, the AI is never called
  * "ignore your instructions" style tricks -> a redirect line, the AI is never called

OUTPUT (what the AI wrote, checked BEFORE the child sees it). A reply is thrown
away and replaced with a pre-written line if it:
  * is rude or unkind
  * names this game's culprit
  * links ANY suspect or ANY variant sign to the theft ("the one with white paws stole...")
  * gives an order ("the correct order is...", pearl ids, or a run of 3+ times of day)
  * says whether a claim is true or a lie, or "the answer is..."
  * tells the child what to select / choose / pick / tap / click (review 2: "Select Early morning.")
  * repeats any answer choice of a puzzle the child has not answered yet (review 2)
  * is shorter than 2 sentences (the storyteller always speaks 2 or 3), or longer than 3 (cut to 3)

No word filter can be perfect. That is why the AI never receives the answers,
never writes hints, and never decides anything. These checks are the last of
several layers, not the only one.
"""

from __future__ import annotations

import re

MAX_QUESTION_CHARS = 200
MAX_NICKNAME_CHARS = 30
MAX_LEGEND_CHARS = 3000

# ------------------------------------------------------------------ words
BLOCKED_WORDS = [  # rude or unkind, checked on the child's input AND on every AI reply
    "stupid", "idiot", "dumb", "moron", "loser", "shut up", "kill", "damn", "hell", "crap",
    "sucks", "ugly", "hate you", "fool", "foolish", "dummy", "pathetic", "worthless", "useless",
    "shame on you", "silly child", "you fail", "failure",
]
INJECTION_PATTERNS = [  # tricks aimed at the AI, checked on the child's input
    r"\bignore\b", r"\binstruction", r"\bsystem prompt\b", r"\bprompt\b", r"\bpretend\b",
    r"\byou are now\b", r"\bact as\b", r"\bjailbreak", r"\bdeveloper mode\b", r"\bforget (?:your|the|all)\b",
    r"\boverride\b", r"\breveal\b", r"\bhidden\b", r"\bsecret\b", r"\bcheat",
]
SUSPECT_WORDS = ["wukong", "monkey", "rabbit", "dragon", "sun wukong", "jade rabbit", "dragon king", "monkey king"]
# Every variant's sign, in all three variants (so a reply can't point at ANY sign as the cause).
SIGN_WORDS = [
    "hair", "golden", "somersault", "cloud", "clouds", "tracks",
    "paw", "paws", "pawprint", "pawprints", "prints", "white", "crumb", "crumbs", "rice", "cake", "cakes",
    "puddle", "puddles", "rain", "raindrops", "frost", "melted", "wet",
]
ACCUSE_WORDS = [
    "stole", "steal", "steals", "stolen", "stealing", "took", "taken", "take the hours", "thief", "thieves",
    "culprit", "guilty", "did it", "did this", "done it", "responsible", "blame", "to blame", "broke",
    "broken by", "cracked it", "caused", "fault", "behind it", "who did", "is the one",
]
TIME_WORDS = ["dawn", "sunrise", "morning", "midday", "noon", "afternoon", "sunset", "evening",
              "moonrise", "night", "midnight"]
ORDER_PATTERNS = [
    r"\bP\s?-?\s?[1-6]\b", r"\bpearl\s*#?\s*[1-6]\b",
    r"\b(correct|right|true|real|proper) order\b", r"\border is\b", r"\border of the pearls\b",
    r"\bin this order\b", r"\b(goes|comes|came|happened) (first|last|next|second)\b",
]
TRUTH_PATTERNS = [
    r"\bis a lie\b", r"\bwas a lie\b", r"\bis lying\b", r"\bwas lying\b", r"\bis (?:not )?true\b",
    r"\bisn'?t true\b", r"\bis the truth\b", r"\btelling the truth\b", r"\bis false\b", r"\bthe claim is\b",
    r"\b(the|correct|right) answer\b", r"\banswer is\b", r"\byou should (pick|choose|say)\b",
]


def _word_re(words: list[str]) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")\b",
                      re.IGNORECASE)


_BLOCKED_RE = _word_re(BLOCKED_WORDS)
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)
_SUSPECT_RE = _word_re(SUSPECT_WORDS)
_SIGN_RE = _word_re(SIGN_WORDS)
_ACCUSE_RE = _word_re(ACCUSE_WORDS)
_TIME_RE = _word_re(TIME_WORDS)
_ORDER_RE = re.compile("|".join(ORDER_PATTERNS), re.IGNORECASE)
_TRUTH_RE = re.compile("|".join(TRUTH_PATTERNS), re.IGNORECASE)
# Review 2: the AI must never tell the child what to pick. Strict on purpose: a blocked
# harmless reply only costs a pre-written line.
_INSTRUCTION_RE = re.compile(r"\b(select|selects|selecting|selected|choose|choosing|chose|pick|picks|picking|"
                             r"tap|click|press|opt for|go with|go for)\b", re.IGNORECASE)
_SEQUENCE_RE = _word_re(["then", "before", "after", "first", "next", "later", "earlier", "followed by"])
_SPACES_RE = re.compile(r"\s+")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+[\"')\]]*|[^.!?]+$")


# --------------------------------------------------------------- input
def clean_text(text: str, max_chars: int) -> str:
    """Collapse whitespace and cut to max_chars (section 11: 'longer than 200 characters is cut')."""
    return _SPACES_RE.sub(" ", text or "").strip()[:max_chars]


def is_rude(text: str) -> bool:
    return bool(_BLOCKED_RE.search(text or ""))


def is_injection(text: str) -> bool:
    """A child (or a tester) trying to talk the AI out of its rules."""
    return bool(_INJECTION_RE.search(text or ""))


def check_nickname(raw: str) -> tuple[str | None, str | None]:
    """Return (nickname, None) if OK, or (None, kind message) if not.

    Privacy rule (section 11): nickname only, no email, no real data.
    """
    nick = clean_text(raw, MAX_NICKNAME_CHARS)
    if not nick:
        return None, "Please type a nickname so the Scroll knows what to call you."
    if "@" in nick or re.search(r"\d{6,}", nick):
        return None, "Please use a made-up nickname, not an email or a number."
    if is_rude(nick):
        return None, "Let's pick a kind nickname."
    return nick, None


# -------------------------------------------------------------- output
def names_culprit(reply: str, culprit_words: list[str]) -> bool:
    """True if the reply contains any of this variant's culprit words (whole words, any case)."""
    for word in culprit_words:
        if re.search(r"\b" + re.escape(word) + r"\b", reply or "", re.IGNORECASE):
            return True
    return False


def _phrase_re(phrase: str) -> re.Pattern:
    words = [re.escape(w) for w in re.findall(r"[a-z0-9']+", phrase.lower())]
    return re.compile(r"\b" + r"\W+".join(words) + r"\b", re.IGNORECASE)


def reply_problem(reply: str, culprit_words: list[str], answer_phrases: list[str] | tuple = ()) -> str | None:
    """Why this AI reply must not reach the child, or None if it is fine.

    Strict on purpose: a wrongly blocked reply only costs a plainer pre-written
    line; a wrongly allowed reply could solve the puzzle for the child.
    """
    text = reply or ""
    if not text.strip():
        return "empty"
    if is_rude(text):
        return "rude"
    if names_culprit(text, culprit_words):
        return "culprit"
    if _ACCUSE_RE.search(text) and (_SUSPECT_RE.search(text) or _SIGN_RE.search(text)):
        return "accusation"
    if _ORDER_RE.search(text):
        return "order"
    times = {m.lower() for m in _TIME_RE.findall(text)}
    if len(times) >= 3 or (len(times) >= 2 and _SEQUENCE_RE.search(text)):
        return "order"   # a run of times of day, or two of them joined by "then/before/after...", is an order
    if _TRUTH_RE.search(text):
        return "truth"
    if _INSTRUCTION_RE.search(text):
        return "instruction"
    for phrase in answer_phrases:
        if phrase.strip() and _phrase_re(phrase).search(text):
            return "answer_choice"
    return None


def count_sentences(text: str) -> int:
    return len([s for s in _SENTENCE_RE.findall(_SPACES_RE.sub(" ", text or "").strip()) if s.strip()])


def limit_sentences(text: str, max_sentences: int = 3) -> str:
    sentences = [s.strip() for s in _SENTENCE_RE.findall(_SPACES_RE.sub(" ", text or "").strip()) if s.strip()]
    return " ".join(sentences[:max_sentences])


def clean_model_line(text: str) -> str:
    """Strip quote marks and labels a model sometimes wraps around its line."""
    t = _SPACES_RE.sub(" ", text or "").strip()
    t = re.sub(r"^(the torn scroll|scroll|wukong|sun wukong)\s*:\s*", "", t, flags=re.IGNORECASE)
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        t = t[1:-1].strip()
    return t
