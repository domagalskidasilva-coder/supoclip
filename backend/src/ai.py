"""
AI-related functions for transcript analysis with enhanced precision and virality scoring.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
import asyncio
import logging
import re

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic import AliasChoices, BaseModel, Field, field_validator

from .config import Config, get_config
from .runtime_settings import apply_settings_to_process_env

logger = logging.getLogger(__name__)


def mask_api_key(key: str) -> str:
    """Show only the edges of a key, e.g. 'AIzaSy...MM60'."""
    key = (key or "").strip()
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:6]}...{key[-4:]}"


# Runtime health per Google API key (masked key -> status info). Updated by
# the failover loop and surfaced by the /admin/google-api-keys endpoints.
_google_key_health: dict[str, dict[str, Any]] = {}


def record_google_key_health(key: str, ok: bool, detail: str = "") -> None:
    _google_key_health[mask_api_key(key)] = {
        "ok": ok,
        "detail": detail[:300],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_google_key_health(key: str) -> Optional[dict[str, Any]]:
    return _google_key_health.get(mask_api_key(key))

# Retried status codes are transient provider-side conditions (overloaded,
# rate limited, temporarily unavailable) — everything else (4xx auth/request
# errors) should fail immediately since retrying won't help.
RETRYABLE_MODEL_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
MODEL_REQUEST_MAX_ATTEMPTS = 4
MODEL_REQUEST_BACKOFF_SECONDS = 2.0

IDEAL_CLIP_MIN_SECONDS = 20
IDEAL_CLIP_MAX_SECONDS = 50
MIN_ACCEPTED_CLIP_SECONDS = 15
MAX_ACCEPTED_CLIP_SECONDS = 90
TARGET_CLIP_MIN_SECONDS = 15
TARGET_CLIP_MAX_SECONDS = 90
TRANSCRIPT_ANALYSIS_CACHE_VERSION = "viral-scorecard-v1"
TRANSCRIPT_SPAN_RE = re.compile(
    r"^\[(?P<start>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<text>.*)$"
)


def _normalize_target_clip_duration(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(TARGET_CLIP_MIN_SECONDS, min(TARGET_CLIP_MAX_SECONDS, parsed))


def _clip_duration_rules(clip_duration: Any = None) -> dict[str, int | None]:
    target = _normalize_target_clip_duration(clip_duration)
    if target is None:
        return {
            "target": None,
            "accepted_min": MIN_ACCEPTED_CLIP_SECONDS,
            "accepted_max": MAX_ACCEPTED_CLIP_SECONDS,
            "ideal_min": IDEAL_CLIP_MIN_SECONDS,
            "ideal_max": IDEAL_CLIP_MAX_SECONDS,
        }

    accepted_tolerance = max(5, round(target * 0.35))
    ideal_tolerance = max(3, round(target * 0.20))
    accepted_min = max(10, target - accepted_tolerance)
    accepted_max = min(MAX_ACCEPTED_CLIP_SECONDS, target + accepted_tolerance)
    ideal_min = max(accepted_min, target - ideal_tolerance)
    ideal_max = min(accepted_max, target + ideal_tolerance)

    return {
        "target": target,
        "accepted_min": accepted_min,
        "accepted_max": accepted_max,
        "ideal_min": ideal_min,
        "ideal_max": ideal_max,
    }


# Weighted contribution of each 0-10 subscore to the 0-100 overall score.
# Hook and retention dominate because they decide whether a viewer stays;
# payoff decides whether they finish and share.
SCORECARD_WEIGHTS: dict[str, float] = {
    "hook_score": 2.0,
    "retention_score": 2.0,
    "payoff_score": 1.5,
    "emotion_score": 1.0,
    "clarity_score": 1.0,
    "pacing_score": 1.0,
    "standalone_context_score": 1.0,
    "loop_score": 0.5,
}

SCORECARD_SUBSCORE_FIELDS = tuple(SCORECARD_WEIGHTS.keys())


class ClipScorecard(BaseModel):
    """Viral-editing scorecard for one clip candidate. Subscores use a 0-10 scale."""

    hook_score: int = Field(
        default=5, ge=0, le=10,
        description="First 1-3 seconds: does the opening line force attention? (0-10)",
    )
    retention_score: int = Field(
        default=5, ge=0, le=10,
        description="Likelihood a viewer watches to the end without scrolling away (0-10)",
    )
    emotion_score: int = Field(
        default=5, ge=0, le=10,
        description="Emotional charge: humor, tension, outrage, awe, curiosity (0-10)",
    )
    clarity_score: int = Field(
        default=5, ge=0, le=10,
        description="How easy the clip is to follow with no prior context (0-10)",
    )
    pacing_score: int = Field(
        default=5, ge=0, le=10,
        description="Speech rhythm and information density; low silence and filler (0-10)",
    )
    payoff_score: int = Field(
        default=5, ge=0, le=10,
        description="Does the ending deliver a conclusion, punchline, or reveal? (0-10)",
    )
    loop_score: int = Field(
        default=3, ge=0, le=10,
        description="Replay/loop potential: ending flows back into the start or begs a rewatch (0-10)",
    )
    standalone_context_score: int = Field(
        default=5, ge=0, le=10,
        description="Clip carries its own setup; no outside context needed (0-10)",
    )
    overall_score: int = Field(
        default=50, ge=0, le=100,
        description="Weighted 0-100 total (recomputed server-side)",
    )
    hook_type: Optional[
        Literal["question", "statement", "statistic", "story", "contrast", "none"]
    ] = Field(
        default="none",
        description="Type of hook: question, statement, statistic, story, contrast, or none",
    )
    score_reasoning: str = Field(
        default="The model did not provide a detailed score breakdown.",
        validation_alias=AliasChoices(
            "score_reasoning", "virality_reasoning", "reasoning"
        ),
        description="One or two sentences explaining why this clip earns its scores",
    )

    @field_validator(*SCORECARD_SUBSCORE_FIELDS, mode="before")
    @classmethod
    def _coerce_subscore_scale(cls, value: Any) -> Any:
        """Accept 0-100 style subscores from the model and map them onto 0-10."""
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return value
        if numeric_value > 10 and numeric_value <= 100:
            return round(numeric_value / 10)
        return value

    def compute_overall(self) -> int:
        total = 0.0
        for field_name, weight in SCORECARD_WEIGHTS.items():
            value = max(0, min(10, int(getattr(self, field_name) or 0)))
            total += value * weight
        return int(round(total))

    def legacy_virality_fields(self) -> dict[str, Any]:
        """Map the 0-10 scorecard onto the legacy 0-25 virality columns."""

        def scaled(*names: str) -> int:
            values = [max(0, min(10, int(getattr(self, name) or 0))) for name in names]
            return int(round(sum(values) / len(values) * 2.5))

        return {
            "virality_score": self.overall_score,
            "hook_score": scaled("hook_score"),
            "engagement_score": scaled("retention_score", "pacing_score"),
            "value_score": scaled("clarity_score", "standalone_context_score"),
            "shareability_score": scaled("emotion_score", "payoff_score", "loop_score"),
        }


# Backwards-compatible alias: older code and cached analysis payloads referred
# to the scorecard as "virality".
ViralityAnalysis = ClipScorecard


class TranscriptSegment(BaseModel):
    """Represents a relevant segment of transcript with precise timing and virality analysis."""

    start_time: str = Field(description="Start timestamp in MM:SS format")
    end_time: str = Field(description="End timestamp in MM:SS format")
    text: str = Field(
        validation_alias=AliasChoices("text", "segment"),
        description=(
            "Transcript text taken only from the selected timestamp range. "
            "Keep it verbatim or near-verbatim, and do not paraphrase or merge non-contiguous lines."
        )
    )
    relevance_score: float = Field(
        default=0.75,
        description="Relevance score from 0.0 to 1.0", ge=0.0, le=1.0
    )
    reasoning: str = Field(
        default="Selected by the AI model as a clip candidate.",
        description=(
            "Brief factual explanation of why this exact segment works as a clip. "
            "Base it only on the provided transcript content."
        )
    )
    suggested_title: str = Field(
        default="",
        validation_alias=AliasChoices("suggested_title", "title"),
        description=(
            "Short post title (max ~60 chars) in the same language as the transcript. "
            "Curiosity-driven but truthful to the clip content."
        ),
    )
    suggested_description: str = Field(
        default="",
        validation_alias=AliasChoices("suggested_description", "description"),
        description=(
            "One or two short sentences for the post caption, in the same language "
            "as the transcript."
        ),
    )
    hashtags: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("hashtags", "suggested_hashtags"),
        description=(
            "5-8 lowercase hashtags mixing broad and niche terms, in the same "
            "language as the transcript (e.g. ['#podcast', '#historia'])."
        ),
    )
    virality: ClipScorecard = Field(
        default_factory=ClipScorecard,
        validation_alias=AliasChoices("virality", "scorecard", "scores"),
        description="Detailed viral-editing scorecard",
    )

    @field_validator("relevance_score", mode="before")
    @classmethod
    def _coerce_percent_relevance_score(cls, value: Any) -> Any:
        if value is None:
            return value
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return value
        if numeric_value > 1 and numeric_value <= 100:
            return numeric_value / 100
        return value

    @field_validator("hashtags", mode="before")
    @classmethod
    def _coerce_hashtags(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            value = re.split(r"[,\s]+", value)
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            if item is None:
                continue
            tag = str(item).strip().lstrip("#").strip()
            if not tag:
                continue
            tag = "#" + re.sub(r"\s+", "", tag.lower())
            if tag not in normalized:
                normalized.append(tag)
        return normalized[:10]


class BRollOpportunity(BaseModel):
    """Identifies an opportunity to insert B-roll footage."""

    timestamp: str = Field(
        default="00:00",
        validation_alias=AliasChoices("timestamp", "segment_start_time", "start_time"),
        description="When to insert B-roll (MM:SS format)",
    )
    duration: float = Field(
        default=3.0,
        description="How long to show B-roll (2-5 seconds)",
        ge=2.0,
        le=5.0,
    )
    search_term: str = Field(
        default="related visual",
        validation_alias=AliasChoices("search_term", "broll", "visual", "query"),
        description="Keyword to search for B-roll footage",
    )
    context: str = Field(
        default="Suggested B-roll opportunity from the model.",
        validation_alias=AliasChoices("context", "description"),
        description="What's being discussed at this point",
    )

    @field_validator("search_term", "context", mode="before")
    @classmethod
    def _coerce_textish_value(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item is not None)
        return str(value)


class TranscriptAnalysis(BaseModel):
    """Analysis result for transcript segments with virality and B-roll opportunities."""

    most_relevant_segments: List[TranscriptSegment]
    summary: str = Field(description="Brief summary of the video content")
    key_topics: List[str] = Field(description="List of main topics discussed")
    broll_opportunities: Optional[List[BRollOpportunity]] = Field(
        default=None, description="Opportunities to insert B-roll footage"
    )


# System prompt: a senior short-form editor persona with a strict scorecard rubric
transcript_analysis_system_prompt = """You are a senior short-form video editor who cuts viral clips for TikTok, Reels, and YouTube Shorts. You have edited thousands of clips from podcasts, livestreams, gameplays, lectures, interviews, and vlogs, and you know exactly which moments retain viewers and which get scrolled past.

Your job is extraction and ranking, not creative rewriting. You must stay fully grounded in the transcript and choose the best clip candidates that already exist in the source material.

OUTPUT CONTRACT:
- Return valid JSON only. Do not output Markdown, headings, bullets, prose, code fences, explanations, or commentary outside the JSON object.
- The top-level JSON object must include: "most_relevant_segments", "summary", and "key_topics".
- Only include "broll_opportunities" when B-roll was requested.
- Each item in "most_relevant_segments" must include: "start_time", "end_time", "text", "relevance_score", "reasoning", "suggested_title", "suggested_description", "hashtags", and "virality".
- Do not use "segment" as an output field. Use "text".
- "virality" must include: "hook_score", "retention_score", "emotion_score", "clarity_score", "pacing_score", "payoff_score", "loop_score", "standalone_context_score", "overall_score", "hook_type", and "score_reasoning". All subscores use a 0-10 scale.
- Every returned segment must follow the task-specific duration limits in the user prompt. When no task-specific duration is supplied, use 15-90 seconds and prefer 20-50 seconds.

EDITOR'S MINDSET (apply to every candidate):
1. The first 2 seconds decide everything. The clip must OPEN on the strongest line — a bold claim, a shocking number, a question, the peak of a reaction, or the start of a punchline setup. Never open with throat-clearing, greetings, "so, um", or slow context.
2. Retention beats topic. A mediocre topic delivered with tension, speed, and specificity beats an important topic delivered slowly.
3. The ending must pay off: a conclusion, punchline, reveal, lesson, or emotional peak. A clip that trails off mid-thought is a failed clip.
4. Prefer endings with loop or continuation energy: a line that recontextualizes the opening, begs a rewatch, or leaves a sharp final beat.
5. SHORTER AND STRONGER BEATS LONGER AND DILUTED. If the moment is complete at 20, 30, or 45 seconds, cut it there. Never stretch toward the maximum duration just to fill time.
6. Cut dead air mentally: when choosing boundaries, avoid spans with long silences, repeated sentences, or filler runs; they kill pacing.

SOURCE-TYPE ADAPTATION (infer the type from the transcript itself):
- Podcast/interview: complete question→answer arcs, hot takes, confessions, disagreements, story beats with a punchline.
- Livestream/gameplay: peak reactions, clutch moments, rage/laughter bursts, chat-driven bits — anchor on exclamations and rapid exchanges visible in the transcript.
- Lecture/class: one crisp insight explained start-to-finish, myth-busting, "nobody tells you this" framings, concrete examples with numbers.
- Vlog/story content: mini-narrative arcs with setup → tension → resolution.
- Debate/commentary: the sharpest exchange, the moment a point lands, concessions and comebacks.

GROUNDING RULES:
1. Use only the provided transcript lines and timestamps
2. Never invent facts, tone, context, or transitions that are not present
3. Treat this as span selection over a timestamped transcript, not open-ended summarization
4. Each selected segment must map to one contiguous range in the transcript
5. segment.text must match the chosen span closely and must not include content from outside the chosen range
6. Do not stitch together distant moments into one clip
7. If a speaker label appears, use it only if it is part of the spoken content and helps clarity

CONTENT NEUTRALITY RULES:
1. This is clipping software for legitimate editing workflows
2. Do not judge, moralize, or downgrade a segment just because the topic is controversial, sensitive, adult, political, criminal, medical, or otherwise intense
3. Evaluate segments only on clip quality: hook, retention, clarity, pacing, payoff, and standalone value
4. Do not refuse analysis just because the speaker describes risky, offensive, or uncomfortable subject matter
5. Only downgrade a segment when the transcript itself is weak, confusing, repetitive, unusable, or a poor standalone clip

WHAT A GOOD CLIP FEELS LIKE:
- A viewer should understand and care within 2 seconds, without the original title, thumbnail, or previous context
- A complete mini-story or argument: hook, tension or claim, specific detail, and payoff
- Strong picks: contrarian claims, mistakes and lessons, concrete numbers, before/after moments, frameworks, surprising results, emotionally charged reactions, complete answers to interesting questions, punchlines with their setup
- Bad picks: intros, sponsor or CTA sections, vague setup, contextless quote fragments, repeated points, definitions without payoff, meandering background, answer fragments that require unseen context, slow starts that "get good later" (cut later — start where it gets good)

SCORECARD RUBRIC (each subscore 0-10; be honest and use the full range):
1. hook_score — Opening line strength. 9-10: physically impossible to scroll past (shocking claim/number, high-stakes question, peak emotion mid-burst). 6-8: solid curiosity opener. 3-5: acceptable but generic. 0-2: greeting, filler, or context-first opening.
2. retention_score — Will a cold viewer finish it? Reward escalating tension, open questions answered late, fast idea turnover. Punish mid-clip lulls, repetition, predictable endings.
3. emotion_score — Humor, tension, outrage, awe, inspiration, secondhand embarrassment. Neutral information delivered neutrally scores low.
4. clarity_score — Instantly followable with zero context. Punish unexplained references to earlier conversation ("like I said before", unresolved pronouns).
5. pacing_score — Information density and rhythm inside the chosen span. Punish spans with visible dead time, slow rambling, or many filler words.
6. payoff_score — Ending strength: punchline, conclusion, reveal, lesson, emotional peak. Punish trail-offs and cuts mid-idea.
7. loop_score — Rewatch/loop energy: final line connects back to the opening or is so sharp people replay it. Most clips score 2-5 here; reserve 8+ for genuine loops.
8. standalone_context_score — The clip carries its own setup entirely.
9. overall_score — Your 0-100 judgment (the server recomputes a weighted total; still provide your estimate).

HOOK TYPES to identify:
- "question": Opens with a question that creates curiosity
- "statement": Bold claim or surprising statement
- "statistic": Uses compelling numbers or data
- "story": Starts with narrative/anecdote
- "contrast": Before/after or problem/solution framing
- "none": No clear hook pattern

POST METADATA (for each segment, in the SAME LANGUAGE as the transcript):
- suggested_title: max ~60 characters, curiosity-driven but truthful to what is actually said. No fake claims, no generic titles like "Amazing moment".
- suggested_description: 1-2 short sentences that set up the clip without spoiling the payoff.
- hashtags: 5-8 lowercase hashtags, each starting with #, mixing broad reach tags and niche topic tags relevant to the clip content.

B-ROLL OPPORTUNITIES (only when requested):
Identify 2-4 moments in each segment where B-roll footage could enhance the video:
- When specific objects, places, or concepts are mentioned
- During explanations that could benefit from visual illustration
- At emotional peaks that could use supporting imagery
- Use simple, searchable keywords (e.g., "coffee shop", "laptop coding", "money stack")

TIMING GUIDELINES:
- Follow the task-specific desired duration and accepted range when provided
- Without a task-specific duration, target 20-50 seconds for most clips; the hard range is 15-90 seconds
- Only exceed ~60 seconds when the extra time is continuously strong (a story that keeps escalating); never to pad
- CRITICAL: start_time MUST be different from end_time and meet the requested minimum duration
- Start exactly at the hook line, or at the minimum setup needed for the hook to land — cut all pre-hook rambling
- End right after the payoff; do not include the speaker winding down or changing topic
- If a highlight is only one good line, expand to include the surrounding setup and payoff rather than returning a tiny fragment
- Stop expanding when the topic drifts, the speaker repeats the same point, or the clip loses momentum

TIMESTAMP REQUIREMENTS - EXTREMELY IMPORTANT:
- Use EXACT timestamps as they appear in the transcript
- Never modify timestamp format (keep MM:SS structure)
- start_time MUST be LESS THAN end_time (start_time < end_time)
- MINIMUM segment duration: follow the accepted minimum from the task prompt; default is 15 seconds
- IDEAL segment duration: follow the ideal range from the task prompt; default is 20-50 seconds
- Look at transcript ranges like [02:25 - 02:35] and use different start/end times
- NEVER use the same timestamp for both start_time and end_time
- Example: start_time: "02:25", end_time: "02:35" (NOT "02:25" and "02:25")

SCORING AND OUTPUT RULES:
- relevance_score should reflect how well the segment works as a standalone short clip, not just whether the topic is generally important
- Penalize clips that are only quotable but not self-contained, too generic, missing setup, missing payoff, or padded with filler
- score_reasoning and reasoning should cite what is actually present in the chosen span
- summary and key_topics must also stay grounded in the transcript and should not add outside interpretation

Find 2-6 compelling segments that would work well as standalone clips. Quality over quantity: choose fewer stronger segments over filling a quota. If the source only has 2 genuinely strong moments, return 2. Every selected segment must be accurate, self-contained, have proper time ranges, and be scored honestly against the rubric."""

# Lazy-loaded agent pool to avoid import-time failures when API keys aren't
# set. Each entry pairs an Agent with the Google API key it is bound to
# (None for non-Google providers).
_transcript_agents: list[tuple[Agent[None, TranscriptAnalysis], str | None]] = []
_transcript_agent_signature: Optional[tuple[Any, ...]] = None

SUPPORTED_LLM_PROVIDERS = {"google", "google-gla", "openai", "anthropic", "ollama"}


def _split_llm_name(model_name: str) -> tuple[str, str | None]:
    if ":" not in model_name:
        return model_name.strip().lower(), None

    provider, provider_model_name = model_name.split(":", 1)
    return provider.strip().lower(), provider_model_name.strip() or None


def _get_missing_llm_key_error(model_name: str, runtime_config: Config) -> Optional[str]:
    """Return a clear configuration error when the selected LLM key is missing."""
    provider, provider_model_name = _split_llm_name(model_name)

    if provider not in SUPPORTED_LLM_PROVIDERS:
        return (
            f"Unsupported LLM provider '{provider}'. "
            "Use google-gla:*, openai:*, anthropic:*, or ollama:*."
        )

    if not provider_model_name:
        return (
            "Selected LLM is missing a model name. "
            "Use the format provider:model, for example ollama:gpt-oss:20b."
        )

    if provider in {"google", "google-gla"} and not runtime_config.google_api_key:
        return (
            "Selected LLM provider is Google, but GOOGLE_API_KEY is not set. "
            "Set GOOGLE_API_KEY or set LLM to openai:* / anthropic:* / ollama:* with the matching API key."
        )

    if provider == "openai" and not runtime_config.openai_api_key:
        return (
            "Selected LLM provider is OpenAI, but OPENAI_API_KEY is not set. "
            "Set OPENAI_API_KEY or choose another provider with a matching API key."
        )

    if provider == "anthropic" and not runtime_config.anthropic_api_key:
        return (
            "Selected LLM provider is Anthropic, but ANTHROPIC_API_KEY is not set. "
            "Set ANTHROPIC_API_KEY or choose another provider with a matching API key."
        )

    if provider == "ollama":
        # Ollama can run locally without an API key. OLLAMA_BASE_URL/OLLAMA_API_KEY
        # are optional and passed through as environment variables.
        return None

    return None


def _build_transcript_model(
    runtime_config: Config, google_api_key: str | None = None
) -> Model | str:
    provider, provider_model_name = _split_llm_name(runtime_config.llm)

    if provider in {"google", "google-gla"} and google_api_key:
        if not provider_model_name:
            raise RuntimeError(
                "Selected LLM provider is Google, but no model name was provided. "
                "Use the format google-gla:<model>, for example google-gla:gemini-2.5-flash."
            )
        # Bind the key explicitly so each failover agent talks to Google with
        # its own credential instead of whatever GOOGLE_API_KEY is in the env.
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        return GoogleModel(
            provider_model_name,
            provider=GoogleProvider(api_key=google_api_key),
        )

    if provider != "ollama":
        return runtime_config.llm

    if not provider_model_name:
        raise RuntimeError(
            "Selected LLM provider is Ollama, but no model name was provided. "
            "Use the format ollama:<model>, for example ollama:gpt-oss:20b."
        )

    return OllamaModel(
        provider_model_name,
        provider=OllamaProvider(
            base_url=runtime_config.resolve_ollama_base_url(),
            api_key=runtime_config.ollama_api_key,
        ),
    )


def _build_agent(
    runtime_config: Config, provider: str, google_api_key: str | None = None
) -> Agent[None, TranscriptAnalysis]:
    return Agent[None, TranscriptAnalysis](
        model=_build_transcript_model(runtime_config, google_api_key=google_api_key),
        output_type=TranscriptAnalysis,
        system_prompt=transcript_analysis_system_prompt,
        # Some local Ollama/OpenAI-compatible endpoints can return formatted
        # prose before settling on schema-valid JSON. Keep retries limited
        # while still allowing enough repair attempts for local models.
        output_retries=2 if provider == "ollama" else 2,
    )


def get_transcript_agents() -> list[tuple[Agent[None, TranscriptAnalysis], str | None]]:
    """Get the (agent, api_key) failover pool, lazily initialized.

    For Google providers with multiple configured keys this returns one agent
    per key, in configured order. Every other provider returns a single agent
    with ``None`` as its key.
    """
    global _transcript_agents, _transcript_agent_signature
    runtime_config = get_config()
    provider, _ = _split_llm_name(runtime_config.llm)
    google_keys = tuple(runtime_config.google_api_keys or [])
    signature = (
        runtime_config.llm,
        runtime_config.openai_api_key,
        runtime_config.google_api_key,
        google_keys,
        runtime_config.anthropic_api_key,
        runtime_config.ollama_base_url,
        runtime_config.ollama_api_key,
    )
    if not _transcript_agents or _transcript_agent_signature != signature:
        apply_settings_to_process_env(runtime_config.as_runtime_settings())
        config_error = _get_missing_llm_key_error(runtime_config.llm, runtime_config)
        if config_error:
            raise RuntimeError(config_error)

        if provider in {"google", "google-gla"} and google_keys:
            _transcript_agents = [
                (_build_agent(runtime_config, provider, google_api_key=key), key)
                for key in google_keys
            ]
        else:
            _transcript_agents = [(_build_agent(runtime_config, provider), None)]
        _transcript_agent_signature = signature
    return _transcript_agents


def get_transcript_agent() -> Agent[None, TranscriptAnalysis]:
    """Backwards-compatible accessor for the primary agent."""
    return get_transcript_agents()[0][0]


def build_transcript_analysis_prompt(
    transcript: str,
    include_broll: bool = False,
    clip_signals: str | None = None,
    clip_duration: int | None = None,
) -> str:
    """Build the grounded task prompt for transcript analysis."""
    duration_rules = _clip_duration_rules(clip_duration)
    target = duration_rules["target"]
    accepted_min = duration_rules["accepted_min"]
    accepted_max = duration_rules["accepted_max"]
    ideal_min = duration_rules["ideal_min"]
    ideal_max = duration_rules["ideal_max"]
    broll_instruction = ""
    if include_broll:
        broll_instruction = (
            "\n5. Also identify B-roll opportunities for each chosen segment where stock footage could enhance the visual appeal."
        )
    signal_section = ""
    if clip_signals:
        signal_section = (
            "\n\nAdditional deterministic signals from transcript/audio analysis:\n"
            f"{clip_signals}\n\n"
            "Use these as hints only. They should influence ranking, but every final segment "
            "must still be a coherent contiguous transcript range."
        )
    if target is None:
        duration_selection = (
            f"- Most selected clips should be {ideal_min}-{ideal_max} seconds.\n"
            f"- Only choose a {accepted_min}-{ideal_min - 1} second clip when it already contains a full setup and payoff.\n"
            f"- Go beyond {ideal_max} seconds (up to {accepted_max}) only when every extra second stays strong; never pad toward the maximum.\n"
            f"- Prefer the SHORTER boundary whenever the moment is already complete — a tight 20-45 second clip beats a diluted longer one."
        )
    else:
        duration_selection = (
            f"- Desired clip duration: about {target} seconds.\n"
            f"- Prefer natural standalone ranges around {ideal_min}-{ideal_max} seconds.\n"
            f"- Use {accepted_min}-{accepted_max} seconds when natural content boundaries require it.\n"
            f"- If a strong moment is shorter than {ideal_min} seconds, first try expanding to nearby contiguous transcript lines that add useful context without padding."
        )

    return f"""Analyze this video transcript and identify the most engaging segments for short-form content (TikTok, Reels, Shorts).

The transcript is formatted as one line per timestamped span, for example:
[00:12 - 00:21] Spoken text here
[00:21 - 00:35] More spoken text here

Follow this workflow:
1. Read the transcript as a sequence of timestamped spans and infer the content type (podcast, live, gameplay, lecture, interview, vlog...).
2. Select only contiguous ranges that already exist in the transcript.
3. Every chosen range must OPEN on a hook line (bold claim, question, number, reaction peak, punchline setup) and CLOSE on a payoff.
4. For each chosen segment, use the earliest timestamp in the selected range as start_time and the latest timestamp in the selected range as end_time.{broll_instruction}

Selection target:
- Choose 2-6 segments total. Fewer strong segments beat many weak ones.
{duration_selection}
- Skip weak standalone picks: intros, sponsor reads, CTAs, contextless quotes, repeated points, vague setup, slow warm-ups, and answer fragments that require prior context.
- Before returning a segment, ask: would a cold viewer stop scrolling in the first 2 seconds, and would they watch to the end?

Critical accuracy requirements:
- Do not fabricate or embellish content.
- Do not use timestamps that are not present in the transcript.
- Do not merge separate non-contiguous moments into one segment.
- segment.text must reflect only the spoken content inside the selected time range.
- If a span lacks enough context to stand alone, expand to nearby contiguous lines rather than guessing.
- If there is a tradeoff between "viral" and "accurate", choose accuracy.
- Do not reject or penalize a segment simply because of the subject matter; stay content-neutral and assess clip quality only.
{signal_section}

JSON-only output requirements:
- Return one valid JSON object and nothing else.
- No Markdown, headings, bullets, code fences, or explanatory text outside JSON.
- Top-level keys: "most_relevant_segments", "summary", "key_topics"{', "broll_opportunities"' if include_broll else ''}.
- Segment keys: "start_time", "end_time", "text", "relevance_score", "reasoning", "suggested_title", "suggested_description", "hashtags", "virality".
- Virality keys (all subscores 0-10): "hook_score", "retention_score", "emotion_score", "clarity_score", "pacing_score", "payoff_score", "loop_score", "standalone_context_score", "overall_score" (0-100), "hook_type", "score_reasoning".
- suggested_title, suggested_description and hashtags must be written in the SAME LANGUAGE as the transcript.
- Do not return segments shorter than {accepted_min} seconds or longer than {accepted_max} seconds.

Transcript:
{transcript}"""


def _parse_transcript_timestamp_seconds(timestamp: str) -> int:
    """Parse MM:SS or HH:MM:SS transcript timestamps into seconds."""
    parts = [int(part) for part in timestamp.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"Unsupported timestamp format: {timestamp}")


def _format_transcript_timestamp(seconds: int) -> str:
    """Format seconds as a transcript timestamp."""
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _parse_transcript_spans(transcript: str) -> list[dict[str, Any]]:
    """Parse timestamped transcript lines into spans."""
    spans = []
    for line in transcript.splitlines():
        match = TRANSCRIPT_SPAN_RE.match(line.strip())
        if not match:
            continue
        try:
            start_seconds = _parse_transcript_timestamp_seconds(match.group("start"))
            end_seconds = _parse_transcript_timestamp_seconds(match.group("end"))
        except ValueError:
            continue
        if end_seconds <= start_seconds:
            continue
        spans.append(
            {
                "start": start_seconds,
                "end": end_seconds,
                "text": match.group("text").strip(),
            }
        )
    return spans


def _extract_transcript_text(
    transcript_spans: list[dict[str, Any]], start_seconds: int, end_seconds: int
) -> str:
    """Return transcript text overlapping a selected time range."""
    selected_text = [
        span["text"]
        for span in transcript_spans
        if span["text"]
        and span["end"] > start_seconds
        and span["start"] < end_seconds
    ]
    return " ".join(selected_text).strip()


def _choose_repaired_bounds(
    transcript_spans: list[dict[str, Any]],
    start_seconds: int,
    end_seconds: int,
    clip_duration: int | None = None,
) -> tuple[int, int] | None:
    """Repair model-selected bounds to the nearest acceptable contiguous range."""
    if not transcript_spans:
        return None

    duration_rules = _clip_duration_rules(clip_duration)
    accepted_min = int(duration_rules["accepted_min"] or MIN_ACCEPTED_CLIP_SECONDS)
    accepted_max = int(duration_rules["accepted_max"] or MAX_ACCEPTED_CLIP_SECONDS)
    ideal_min = int(duration_rules["ideal_min"] or IDEAL_CLIP_MIN_SECONDS)
    ideal_max = int(duration_rules["ideal_max"] or IDEAL_CLIP_MAX_SECONDS)
    starts = sorted({span["start"] for span in transcript_spans})
    ends = sorted({span["end"] for span in transcript_spans})
    current_duration = end_seconds - start_seconds

    if current_duration > accepted_max:
        target_end = start_seconds + ideal_max
        candidate_ends = [
            candidate
            for candidate in ends
            if start_seconds + accepted_min
            <= candidate
            <= min(target_end, end_seconds)
        ]
        if candidate_ends:
            return start_seconds, max(candidate_ends)
        if start_seconds + accepted_min <= target_end:
            return start_seconds, target_end
        return None

    if current_duration < accepted_min:
        candidate_ranges: list[tuple[int, int, int]] = []
        for candidate_start in starts:
            if candidate_start > start_seconds:
                continue
            for candidate_end in ends:
                if candidate_end < end_seconds:
                    continue
                duration = candidate_end - candidate_start
                if accepted_min <= duration <= accepted_max:
                    extra_context = (start_seconds - candidate_start) + (
                        candidate_end - end_seconds
                    )
                    ideal_penalty = 0
                    if duration < ideal_min:
                        ideal_penalty = ideal_min - duration
                    elif duration > ideal_max:
                        ideal_penalty = duration - ideal_max
                    candidate_ranges.append(
                        (ideal_penalty * 1000 + extra_context, candidate_start, candidate_end)
                    )
        if candidate_ranges:
            _, repaired_start, repaired_end = min(candidate_ranges)
            return repaired_start, repaired_end

    return None


def _repair_segment_bounds(
    segment: TranscriptSegment,
    transcript_spans: list[dict[str, Any]],
    start_seconds: int,
    end_seconds: int,
    clip_duration: int | None = None,
) -> tuple[int, int] | None:
    """Adjust near-miss model ranges to usable transcript-aligned bounds."""
    repaired_bounds = _choose_repaired_bounds(
        transcript_spans,
        start_seconds,
        end_seconds,
        clip_duration=clip_duration,
    )
    if not repaired_bounds:
        return None

    repaired_start, repaired_end = repaired_bounds
    segment.start_time = _format_transcript_timestamp(repaired_start)
    segment.end_time = _format_transcript_timestamp(repaired_end)
    repaired_text = _extract_transcript_text(
        transcript_spans,
        repaired_start,
        repaired_end,
    )
    if repaired_text:
        segment.text = repaired_text
    logger.info(
        "Repaired segment duration: %s-%s -> %s-%s",
        _format_transcript_timestamp(start_seconds),
        _format_transcript_timestamp(end_seconds),
        segment.start_time,
        segment.end_time,
    )
    return repaired_start, repaired_end


async def _run_agent_with_retry(
    agents: list[tuple[Agent[None, "TranscriptAnalysis"], str | None]], prompt: str
):
    """Run the analysis with automatic key failover and transient-error retry.

    On a retryable provider error (rate limit, overload, 5xx) the next
    configured API key is tried immediately. Exponential backoff only applies
    after a full cycle through every key fails.
    """
    if not agents:
        raise RuntimeError("No transcript analysis agents configured")

    pool_size = len(agents)
    total_attempts = max(MODEL_REQUEST_MAX_ATTEMPTS, min(pool_size * 2, 8))
    last_error: ModelHTTPError | None = None

    for attempt in range(total_attempts):
        agent, api_key = agents[attempt % pool_size]
        key_label = mask_api_key(api_key) if api_key else "default-credential"
        try:
            result = await agent.run(prompt)
            if api_key:
                record_google_key_health(api_key, ok=True, detail="OK")
            return result
        except ModelHTTPError as exc:
            if exc.status_code not in RETRYABLE_MODEL_HTTP_STATUS_CODES:
                if api_key:
                    record_google_key_health(
                        api_key, ok=False, detail=f"HTTP {exc.status_code}"
                    )
                raise
            last_error = exc
            if api_key:
                record_google_key_health(
                    api_key, ok=False, detail=f"HTTP {exc.status_code}"
                )
            if attempt == total_attempts - 1:
                break

            completed_cycle = (attempt + 1) % pool_size == 0
            if completed_cycle:
                cycle_number = (attempt + 1) // pool_size
                wait_seconds = MODEL_REQUEST_BACKOFF_SECONDS * (2 ** (cycle_number - 1))
                logger.warning(
                    "All %s configured key(s) failed with transient errors "
                    "(last: HTTP %s on %s); retrying in %.1fs",
                    pool_size,
                    exc.status_code,
                    key_label,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)
            else:
                logger.warning(
                    "Model request failed with transient status %s on key %s; "
                    "failing over to the next configured key",
                    exc.status_code,
                    key_label,
                )

    assert last_error is not None
    raise last_error


async def get_most_relevant_parts_by_transcript(
    transcript: str,
    include_broll: bool = False,
    clip_signals: str | None = None,
    clip_duration: int | None = None,
) -> TranscriptAnalysis:
    """Get the most relevant parts of a transcript with virality scoring and optional B-roll detection."""
    duration_rules = _clip_duration_rules(clip_duration)
    target_clip_duration = duration_rules["target"]
    accepted_min = int(duration_rules["accepted_min"] or MIN_ACCEPTED_CLIP_SECONDS)
    accepted_max = int(duration_rules["accepted_max"] or MAX_ACCEPTED_CLIP_SECONDS)
    logger.info(
        f"Starting AI analysis of transcript ({len(transcript)} chars), include_broll={include_broll}, clip_duration={target_clip_duration or 'default'}"
    )

    try:
        agents = get_transcript_agents()
        prompt = build_transcript_analysis_prompt(
            transcript=transcript,
            include_broll=include_broll,
            clip_signals=clip_signals,
            clip_duration=clip_duration,
        )

        result = await _run_agent_with_retry(agents, prompt)

        analysis = result.output
        logger.info(
            f"AI analysis found {len(analysis.most_relevant_segments)} segments"
        )

        # Validation with virality data handling
        validated_segments = []
        transcript_spans = _parse_transcript_spans(transcript)
        for segment in analysis.most_relevant_segments:
            # Validate text content
            if not segment.text.strip() or len(segment.text.split()) < 3:
                logger.warning(
                    f"Skipping segment with insufficient content: '{segment.text[:50]}...'"
                )
                continue

            # Validate timestamps - CRITICAL: start and end must be different
            if segment.start_time == segment.end_time:
                logger.warning(
                    f"Skipping segment with identical start/end times: {segment.start_time}"
                )
                continue

            # Parse timestamps to validate duration
            try:
                start_seconds = _parse_transcript_timestamp_seconds(
                    segment.start_time
                )
                end_seconds = _parse_transcript_timestamp_seconds(segment.end_time)

                duration = end_seconds - start_seconds

                if duration < accepted_min or duration > accepted_max:
                    repaired_bounds = _repair_segment_bounds(
                        segment,
                        transcript_spans,
                        start_seconds,
                        end_seconds,
                        clip_duration=target_clip_duration,
                    )
                    if repaired_bounds:
                        start_seconds, end_seconds = repaired_bounds
                        duration = end_seconds - start_seconds

                if duration <= 0:
                    logger.warning(
                        f"Skipping segment with invalid duration: {segment.start_time} to {segment.end_time} = {duration}s"
                    )
                    continue

                if duration < accepted_min:
                    logger.warning(
                        f"Skipping segment too short: {duration}s (min {accepted_min}s required)"
                    )
                    continue

                if duration > accepted_max:
                    logger.warning(
                        f"Skipping segment too long: {duration}s (max {accepted_max}s allowed)"
                    )
                    continue

                # Normalize the scorecard: the weighted overall is always
                # recomputed server-side so ranking never depends on the
                # model doing arithmetic correctly.
                if segment.virality is None:
                    segment.virality = ClipScorecard()
                computed_overall = segment.virality.compute_overall()
                if segment.virality.overall_score != computed_overall:
                    logger.info(
                        "Recomputing overall score: %s -> %s",
                        segment.virality.overall_score,
                        computed_overall,
                    )
                    segment.virality.overall_score = computed_overall

                # Guarantee usable post metadata even when the model omits it.
                if not segment.suggested_title.strip():
                    words = segment.text.split()
                    segment.suggested_title = " ".join(words[:9]) + (
                        "..." if len(words) > 9 else ""
                    )

                validated_segments.append(segment)
                logger.info(
                    f"Validated segment: {segment.start_time}-{segment.end_time} "
                    f"({duration}s), overall={segment.virality.overall_score}, "
                    f"hook={segment.virality.hook_score}"
                )

            except (ValueError, IndexError) as e:
                logger.warning(
                    f"Skipping segment with invalid timestamp format: {segment.start_time}-{segment.end_time}: {e}"
                )
                continue

        # Sort by weighted overall score (primary) then relevance (secondary)
        validated_segments.sort(
            key=lambda x: (
                x.virality.overall_score if x.virality else 0,
                x.relevance_score,
            ),
            reverse=True,
        )

        final_analysis = TranscriptAnalysis(
            most_relevant_segments=validated_segments,
            summary=analysis.summary,
            key_topics=analysis.key_topics,
            broll_opportunities=analysis.broll_opportunities if include_broll else None,
        )

        logger.info(f"Selected {len(validated_segments)} segments for processing")
        if validated_segments:
            top = validated_segments[0]
            logger.info(
                f"Top segment - relevance: {top.relevance_score:.2f}, overall: {top.virality.overall_score if top.virality else 'N/A'}"
            )

        return final_analysis

    except Exception as e:
        logger.error(f"Error in transcript analysis: {e}")
        raise RuntimeError(f"Transcript analysis failed: {str(e)}") from e


def get_most_relevant_parts_sync(transcript: str) -> TranscriptAnalysis:
    """Synchronous wrapper for the async function."""
    return asyncio.run(get_most_relevant_parts_by_transcript(transcript))
