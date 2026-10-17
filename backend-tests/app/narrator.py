"""The AI narrator: the Torn Scroll's chat and Wukong's taunts (design doc section 10).

The Scroll is the game's storyteller (review 2): every Scroll line, AI or
written by the team, is 2 or 3 short sentences in a calm, relaxed, quietly
amused voice. The browser speaks these lines aloud (static/app.js, Voice).

The AI only writes words. It never decides anything (design rule 1), and it
never writes hints: hints are shown exactly as the team wrote them in the
hints table (review fix: the AI must not be able to make a hint stronger).

Every AI reply passes safety.reply_problem() before a child sees it. If the
AI is off, fails, takes longer than 6 seconds, or writes something unsafe,
a pre-written line is used instead, so the game always works.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Protocol

from app import safety

log = logging.getLogger("monkey_king.narrator")

TEMPERATURE = 0.3      # section 10: low, so the Scroll stays calm and on-script
MAX_TOKENS = 120       # section 10: short answers
WUKONG_MAX_WORDS = 20  # section 10: "ONE line (under 20 words)"

# ---- Prompts -------------------------------------------------------------
# The Scroll prompt starts from design doc section 10 and adds the storyteller
# voice (review 2): exactly 2 or 3 short sentences; calm, relaxed, quietly
# amused, understated. Rule 5 is new too: never tell the child what to pick.
# The doc's "HINT:" slot is gone: hints never go through the AI (they are shown
# exactly as the team wrote them), so it was always "none".
MIN_SENTENCES, MAX_SENTENCES = 2, 3

SCROLL_SYSTEM_PROMPT = """You are the Torn Scroll, the storyteller of a mystery game for children aged 8 to 13.
You tell the story in a calm, relaxed, quietly amused voice. You are understated: never excited, never scary.
Many of your pages are torn. You only know the facts in KNOWN PAGES and SCENE below.

RULES
1. Write exactly 2 or 3 short sentences. Use simple words. No lists, no emojis, no sound effects.
2. Use only facts from KNOWN PAGES and SCENE. Never add new facts, people, or events.
3. If the child asks about something not in KNOWN PAGES, say that page is torn, then ask what they could look at to find out.
4. Never say who broke the hourglass, the order of the pearls, or if a claim is true.
5. Never tell the child which answer to select, choose, or pick. Never guess the answer to a question for them.
6. End with one short question that makes the child think.
7. Be kind. Never call an answer stupid. Never use scary words.

YOUR VOICE, for example: "The forest has gone quiet. Someone has misplaced an hour. Let's see where it went."

SCENE: {realm_name} - {scene_text}
KNOWN PAGES: {opened_pearl_texts}"""

WUKONG_SYSTEM_PROMPT = """You are Sun Wukong, the playful Monkey King, in a children's game.
Write ONE line (under 20 words) to the child, the Seeker.
EVENT: {event}
FORM: {form_name}
RULES: Be funny and proud, never mean. Do not reveal any answer.
Do not mention the claim's truth. No scary words."""


class ChatModel(Protocol):
    """Anything that can answer one system + user message. Real: OCIChatModel. Tests: a fake."""

    def chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str: ...


@dataclass
class Line:
    text: str
    source: str  # "ai" (model wrote it), "table" (hint table text), "fallback" (pre-written line)


class OCIChatModel:
    """OCI Generative AI chat. Cohere models use CohereChatRequest; others use the generic API."""

    def __init__(self, config_file: str, profile: str, compartment_id: str, endpoint: str,
                 model_id: str, timeout_s: float):
        import oci  # imported here so the game still starts if the SDK is missing

        self._oci = oci
        config = oci.config.from_file(config_file, profile)
        self._client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            config=config,
            service_endpoint=endpoint,
            retry_strategy=oci.retry.NoneRetryStrategy(),  # no silent retries past our 6 s budget
            timeout=(min(3.0, timeout_s), timeout_s),
        )
        self._compartment_id = compartment_id
        self._model_id = model_id

    def chat(self, system: str, user: str, temperature: float, max_tokens: int) -> str:
        m = self._oci.generative_ai_inference.models
        if self._model_id.startswith("cohere."):
            request = m.CohereChatRequest(
                preamble_override=system, message=user,
                temperature=temperature, max_tokens=max_tokens,
            )
        else:
            request = m.GenericChatRequest(
                api_format=m.BaseChatRequest.API_FORMAT_GENERIC,
                messages=[
                    m.SystemMessage(content=[m.TextContent(text=system)]),
                    m.UserMessage(content=[m.TextContent(text=user)]),
                ],
                temperature=temperature, max_tokens=max_tokens,
            )
        details = m.ChatDetails(
            compartment_id=self._compartment_id,
            serving_mode=m.OnDemandServingMode(model_id=self._model_id),
            chat_request=request,
        )
        response = self._client.chat(details).data.chat_response
        if self._model_id.startswith("cohere."):
            return response.text
        return response.choices[0].message.content[0].text


class Narrator:
    def __init__(self, model: ChatModel | None, fallbacks: dict[str, str], timeout_s: float = 6.0):
        self.model = model
        self.fallbacks = fallbacks
        self.timeout_s = timeout_s
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="genai")
        self._lock = threading.Lock()
        # What really happened on the last AI call. /api/health reports this, so
        # "AI configured" is never mistaken for "AI working" (review fix).
        self.last_call: dict = {"ok": None, "error": None, "at": None}

    @property
    def ai_enabled(self) -> bool:
        """True only means the AI is CONFIGURED. Use last_call or ping() to know if it WORKS."""
        return self.model is not None

    def _record(self, ok: bool, error: str | None) -> None:
        with self._lock:
            self.last_call = {"ok": ok, "error": error, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def _call(self, system: str, user: str) -> str | None:
        """Ask the model, but give up after timeout_s. Returns None on any problem."""
        if self.model is None:
            return None
        future = self._pool.submit(self.model.chat, system, user, TEMPERATURE, MAX_TOKENS)
        try:
            text = future.result(timeout=self.timeout_s)
        except FutureTimeout:
            # (Python's TimeoutError is the same class, so also check whether the call really ran long.)
            if future.done():
                log.warning("GenAI call failed (TimeoutError from the service); using fallback line")
                self._record(False, "TimeoutError")
            else:
                log.warning("GenAI call took longer than %.1fs; using fallback line", self.timeout_s)
                self._record(False, "timeout")
            return None
        except Exception as e:  # network, auth, quota... the game must keep going
            log.warning("GenAI call failed (%s); using fallback line", type(e).__name__)
            self._record(False, type(e).__name__)
            return None
        self._record(True, None)
        text = safety.clean_model_line(text or "")
        return text or None

    def ping(self) -> dict:
        """Make one REAL, tiny AI call and report whether it worked (used by /api/health?check_ai=1)."""
        if self.model is None:
            return {"ok": False, "error": "not_configured"}
        started = time.monotonic()
        reply = self._call("Reply with exactly one word: ready", "Are you ready?")
        return {"ok": reply is not None, "error": None if reply is not None else self.last_call["error"],
                "seconds": round(time.monotonic() - started, 2)}

    # ------------------------------------------------------------- Scroll
    def scroll(self, *, scene_name: str, scene_text: str, known_pages: list[str],
               question: str, culprit_words: list[str], answer_phrases: list[str] = ()) -> Line:
        """One Torn Scroll chat reply to the child's question.

        known_pages must contain ONLY pearls this player has opened; the
        engine guarantees that. The hidden truth is never a parameter here.
        Hints never come through here: the engine shows hint-table text as is.
        answer_phrases: the choices of puzzles not answered yet; a reply that repeats one is blocked.
        """
        system = SCROLL_SYSTEM_PROMPT.format(
            realm_name=scene_name,
            scene_text=scene_text or "Nothing seen yet.",
            opened_pearl_texts=" | ".join(known_pages) if known_pages else "none yet",
        )
        reply = self._call(system, question)
        if reply is not None:
            reply = safety.limit_sentences(reply, MAX_SENTENCES)
            problem = safety.reply_problem(reply, culprit_words, answer_phrases)
            if problem is None and safety.count_sentences(reply) < MIN_SENTENCES:
                problem = "too_short"   # the storyteller always speaks 2 or 3 sentences
            if problem is None:
                return Line(reply, "ai")
            log.info("Scroll reply blocked (%s); replaced with a pre-written line", problem)
        return Line(self.fallbacks["scroll_no_hint"], "fallback")

    # ------------------------------------------------------------- Wukong
    def wukong(self, *, event: str, form_name: str) -> Line:
        """One taunt. event is 'correct' or 'wrong'. The model never sees the claim or the answer."""
        assert event in ("correct", "wrong")
        system = WUKONG_SYSTEM_PROMPT.format(event=event, form_name=form_name)
        reply = self._call(system, "Say your one line to the Seeker now.")
        if reply:
            reply = reply.splitlines()[0].strip()
            # The form name is already on screen, so it is not a leak; accusations,
            # truth talk, order talk and rudeness are.
            if 0 < len(reply.split()) <= WUKONG_MAX_WORDS and safety.reply_problem(reply, []) is None:
                return Line(reply, "ai")
        key = "wukong_correct" if event == "correct" else "wukong_wrong"
        return Line(self.fallbacks[key], "fallback")
