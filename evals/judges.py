"""
Quality judges for generated research reports.

Three metrics per report:

  grounding  — LLM judge: are the report's claims supported by the cited
               source snippets? (samples up to N claims, temperature 0)
  coverage   — LLM judge: how completely does the report cover the topics
               the prompt asked for?
  structure  — deterministic checks (no LLM): required parts present,
               sane word counts, citations attached.

All LLM calls go through the existing LLMService at temperature 0.
"""

import re

from app.models.schemas import ResearchReport
from app.services.llm_service import get_llm_service

MAX_CLAIMS_JUDGED = 8


def extract_claims(report: ResearchReport, max_claims: int = MAX_CLAIMS_JUDGED) -> list[str]:
    """Sample declarative sentences from the report body to grounding-check."""
    body = " ".join(report.sections.values())
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body)]
    # Prefer substantive sentences: long enough to contain a checkable fact.
    claims = [s for s in sentences if 60 <= len(s) <= 400 and not s.startswith("#")]
    # Spread samples across the report instead of only the beginning.
    if len(claims) > max_claims:
        step = len(claims) / max_claims
        claims = [claims[int(i * step)] for i in range(max_claims)]
    return claims


async def judge_grounding(report: ResearchReport) -> dict:
    """
    Fraction of sampled claims supported by the report's cited snippets.

    Returns {"score": float 0-1, "supported": int, "partial": int,
             "unsupported": int, "claims_judged": int}
    """
    claims = extract_claims(report)
    if not claims:
        return {"score": 0.0, "supported": 0, "partial": 0, "unsupported": 0, "claims_judged": 0}

    snippets = "\n".join(
        f"[{i + 1}] {c.title}: {c.snippet}" for i, c in enumerate(report.citations[:20])
    )
    if not snippets:
        return {"score": 0.0, "supported": 0, "partial": 0, "unsupported": len(claims), "claims_judged": len(claims)}

    claims_block = "\n".join(f"{i + 1}. {claim}" for i, claim in enumerate(claims))

    llm = get_llm_service()
    parsed = await llm.call_llm_json(
        system_prompt=(
            "You are a strict fact-checking judge. For each numbered claim, decide whether it is "
            "supported by the provided source snippets.\n"
            'Return JSON: {"verdicts": [{"claim": <number>, "verdict": "supported" | "partial" | "unsupported"}]}\n'
            "- supported: a snippet directly backs the claim\n"
            "- partial: snippets back part of the claim or a weaker version\n"
            "- unsupported: no snippet relates to the claim"
        ),
        user_prompt=f"Source snippets:\n{snippets}\n\nClaims to check:\n{claims_block}",
        temperature=0.0,
    )

    verdicts = parsed.get("verdicts", [])
    supported = sum(1 for v in verdicts if v.get("verdict") == "supported")
    partial = sum(1 for v in verdicts if v.get("verdict") == "partial")
    unsupported = sum(1 for v in verdicts if v.get("verdict") == "unsupported")
    judged = max(supported + partial + unsupported, 1)
    score = (supported + 0.5 * partial) / judged
    return {
        "score": round(score, 3),
        "supported": supported,
        "partial": partial,
        "unsupported": unsupported,
        "claims_judged": judged,
    }


async def judge_coverage(prompt: str, report: ResearchReport) -> dict:
    """
    LLM-judged completeness of the report against the original prompt.

    Returns {"score": float 0-1, "missing": [str]}
    """
    body_preview = "\n".join(
        f"## {topic}\n{text[:600]}" for topic, text in report.sections.items()
    )

    llm = get_llm_service()
    parsed = await llm.call_llm_json(
        system_prompt=(
            "You are a research editor judging whether a report fully answers a research request.\n"
            'Return JSON: {"score": <0 to 1>, "missing": [<short strings naming missing aspects>]}\n'
            "score 1.0 = every topic in the request is covered with substance; "
            "0.5 = major aspects missing; 0 = report is off-topic."
        ),
        user_prompt=(
            f"Research request: {prompt}\n\n"
            f"Report title: {report.title}\n"
            f"Report sections:\n{body_preview}\n\n"
            f"Conclusion: {report.conclusion[:400]}"
        ),
        temperature=0.0,
    )

    score = min(max(float(parsed.get("score", 0.0)), 0.0), 1.0)
    missing = [str(m) for m in parsed.get("missing", [])][:5]
    return {"score": round(score, 3), "missing": missing}


def check_structure(report: ResearchReport, expected_topics: int) -> dict:
    """
    Deterministic structural checks — no LLM involved.

    Returns {"score": float 0-1, "checks": {name: bool}}
    """
    checks = {
        "has_introduction": len(report.introduction.split()) >= 40,
        "has_conclusion": len(report.conclusion.split()) >= 30,
        "has_all_topic_sections": len(report.sections) >= expected_topics,
        "sections_have_content": all(len(text.split()) >= 40 for text in report.sections.values()),
        "has_citations": len(report.citations) >= 3,
        "word_count_sane": 400 <= report.total_words <= 8000,
        "comparative_analysis_when_multi_topic": (
            expected_topics < 2 or bool((report.comparative_analysis or "").strip())
        ),
    }
    score = sum(checks.values()) / len(checks)
    return {"score": round(score, 3), "checks": checks}
