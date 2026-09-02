"""Explainable writing-pattern analysis for industrial B2B copy.

The analyzer evaluates observable features in a draft. It does not infer who or
what authored the text and does not attempt to bypass third-party detectors.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import re
from statistics import mean, pstdev
from typing import Iterable


SCOPE_NOTE = (
    "Writing-pattern diagnosis only; this is not an AI-authorship or "
    "AI-probability determination."
)

GENERIC_VERBS = {
    "ensure", "enhance", "optimize", "facilitate", "improve", "support",
    "provide", "help", "赋能", "确保", "提升", "优化", "助力", "支持",
}
MARKETING_WORDS = {
    "innovative", "cutting-edge", "high-quality", "premium", "advanced",
    "revolutionary", "seamless", "robust", "game-changing", "sustainable",
    "创新", "领先", "高品质", "优质", "先进", "革命性", "无缝", "卓越", "可持续",
}
TRANSITIONS = {
    "firstly", "moreover", "consequently", "in addition", "furthermore",
    "finally", "overall", "it is worth noting", "首先", "其次", "然后", "此外",
    "最后", "总的来说", "值得注意的是", "与此同时",
}
DECISION_MARKERS = {
    "choose", "select", "prefer", "avoid", "recommend", "unless", "when",
    "if", "because", "instead", "取决于", "选择", "优先", "避免", "建议", "除非",
    "当", "如果", "因为", "而不是",
}
TRADEOFF_MARKERS = {
    "trade-off", "tradeoff", "versus", "vs", "however", "but", "while",
    "at the cost of", "权衡", "取舍", "相比", "但是", "然而", "代价", "同时",
}
ENGINEERING_TERMS = {
    "thickness", "tolerance", "load", "stiffness", "weight", "geometry",
    "orientation", "cycle", "compression", "impact", "density", "temperature",
    "humidity", "divider", "flute", "gsm", "mm", "kg", "mpa", "厚度", "公差",
    "载荷", "刚度", "重量", "结构", "方向", "循环", "压缩", "冲击", "密度",
    "温度", "湿度", "隔板", "克重", "周转",
}
PLATFORMS = {"linkedin", "facebook", "blog", "b2b", "general"}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    sentence_index: int | None
    snippet: str
    observation: str
    action: str


def _sentences(text: str) -> list[str]:
    chunks = re.split(
        r"(?<=[.!?。！？])(?:\s+|(?=[A-Za-z0-9\u4e00-\u9fff]))|\n+(?=\S)",
        text.strip(),
    )
    return [item.strip() for item in chunks if item.strip()]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*|[\u4e00-\u9fff]", text.lower())


def _contains(sentence: str, terms: Iterable[str]) -> list[str]:
    matches = set()
    for term in terms:
        if re.fullmatch(r"[A-Za-z][A-Za-z -]*", term):
            pattern = rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])"
            if re.search(pattern, sentence, re.IGNORECASE):
                matches.add(term)
        elif term.lower() in sentence.lower():
            matches.add(term)
    return sorted(matches)


def _snippet(sentence: str, limit: int = 110) -> str:
    sentence = re.sub(r"\s+", " ", sentence).strip()
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def _statistical_layer(sentences: list[str], tokens: list[str]) -> dict:
    lengths = [len(_tokens(sentence)) for sentence in sentences if _tokens(sentence)]
    avg_length = mean(lengths) if lengths else 0.0
    variation = (pstdev(lengths) / avg_length) if len(lengths) > 1 and avg_length else 0.0
    counts = Counter(tokens)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    lexical_diversity = len(counts) / len(tokens) if tokens else 0.0
    repetition_ratio = repeated / len(tokens) if tokens else 0.0
    # A transparent predictability proxy, not language-model perplexity.
    predictability_proxy = _clamp(100 * (0.62 * repetition_ratio + 0.38 * (1 - variation)))
    return {
        "word_count": len(tokens),
        "sentence_count": len(sentences),
        "average_sentence_words": round(avg_length, 1),
        "sentence_length_cv": round(variation, 3),
        "burstiness_score": _clamp(variation * 120),
        "lexical_diversity": round(lexical_diversity, 3),
        "repetition_ratio": round(repetition_ratio, 3),
        "predictability_proxy": predictability_proxy,
        "method_note": "Predictability is a lexical/rhythm proxy; no hidden model or perplexity claim is used.",
    }


def _findings(sentences: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    starts: list[str] = []
    for index, sentence in enumerate(sentences):
        words = _tokens(sentence)
        if words:
            starts.append(" ".join(words[:2]))
        generic = _contains(sentence, GENERIC_VERBS)
        if generic and len(_contains(sentence, ENGINEERING_TERMS)) == 0:
            findings.append(Finding(
                "generic_language", "medium", index, _snippet(sentence),
                f"Low-information wording ({', '.join(generic[:4])}) is not tied to a mechanism or check.",
                "Replace the claim with an observable action, constraint, or consequence.",
            ))
        marketing = _contains(sentence, MARKETING_WORDS)
        if marketing:
            findings.append(Finding(
                "unsupported_marketing", "high", index, _snippet(sentence),
                f"Marketing claim ({', '.join(marketing[:4])}) lacks a stated criterion or evidence source.",
                "Substantiate the term, qualify it, or remove it.",
            ))
        transitions = _contains(sentence, TRANSITIONS)
        if transitions:
            findings.append(Finding(
                "templated_transition", "low", index, _snippet(sentence),
                f"Formulaic transition detected ({', '.join(transitions[:3])}).",
                "Use logical adjacency or name the concrete subject instead.",
            ))
        if len(words) > 34:
            findings.append(Finding(
                "long_sentence", "medium", index, _snippet(sentence),
                f"The sentence contains {len(words)} tokens and carries several ideas.",
                "Split at the decision, condition, or consequence.",
            ))

    repeated_starts = {start for start, count in Counter(starts).items() if start and count >= 3}
    for start in sorted(repeated_starts):
        findings.append(Finding(
            "repeated_opening", "medium", None, start,
            "Three or more sentences use the same opening pattern.",
            "Combine related claims or lead with the variable that changes the decision.",
        ))
    return findings


def _platform_fit(platform: str, stats: dict, text: str) -> tuple[int, str]:
    words = stats["word_count"]
    paragraphs = len([p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()])
    if platform == "linkedin":
        score = 92 - max(0, words - 300) // 4 - (12 if paragraphs < 2 and words > 100 else 0)
        note = "LinkedIn favors a scannable decision-led structure and a concrete, low-friction CTA."
    elif platform == "facebook":
        score = 90 - max(0, words - 220) // 3
        note = "Facebook favors direct context, readable spacing, and a simple audience-relevant takeaway."
    elif platform == "blog":
        score = 88 - (18 if words < 180 else 0)
        note = "Blog content needs enough depth, evidence structure, and useful headings for the reader's decision."
    elif platform == "b2b":
        score = 88
        note = "B2B copy should connect claims to a buying, engineering, or operating decision."
    else:
        score = 85
        note = "General assessment; choose a platform for channel-specific guidance."
    return _clamp(score), note


def analyze_text(text: str, platform: str = "general") -> dict:
    """Analyze *text* and return a JSON-serializable explainable report."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text must contain at least one non-whitespace character.")
    if len(text) > 50_000:
        raise ValueError("Text exceeds the 50,000-character local analysis limit.")
    platform = platform.lower().strip()
    if platform not in PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")

    sentences = _sentences(text)
    tokens = _tokens(text)
    stats = _statistical_layer(sentences, tokens)
    findings = _findings(sentences)
    generic_count = sum(1 for item in findings if item.rule == "generic_language")
    marketing_count = sum(1 for item in findings if item.rule == "unsupported_marketing")
    transition_count = sum(1 for item in findings if item.rule == "templated_transition")

    decision_hits = len(_contains(text, DECISION_MARKERS))
    tradeoff_hits = len(_contains(text, TRADEOFF_MARKERS))
    engineering_hits = len(_contains(text, ENGINEERING_TERMS))
    numeric_hits = len(re.findall(r"\b\d+(?:\.\d+)?\s?(?:mm|cm|m|kg|g|%|mpa|gsm|°c|cycles?)?\b", text.lower()))

    rhythm = _clamp(52 + stats["sentence_length_cv"] * 90 - (16 if len(sentences) < 2 else 0))
    ai_smell = _clamp(
        92 - generic_count * 8 - marketing_count * 13 - transition_count * 5
        - max(0, stats["predictability_proxy"] - 45) * 0.45
    )
    engineering = _clamp(38 + engineering_hits * 8 + numeric_hits * 3 + tradeoff_hits * 5)
    decision = _clamp(35 + decision_hits * 9 + tradeoff_hits * 6)
    specificity = _clamp(35 + engineering_hits * 6 + numeric_hits * 5)
    human_voice = _clamp((ai_smell * 0.55) + (rhythm * 0.45))
    platform_score, platform_note = _platform_fit(platform, stats, text)

    dimensions = {
        "ai_smell_quality": ai_smell,
        "engineering_credibility": engineering,
        "decision_density": decision,
        "specificity": specificity,
        "human_voice": human_voice,
        "platform_fit": platform_score,
    }
    authenticity = _clamp(
        engineering * 0.24 + decision * 0.20 + specificity * 0.18
        + human_voice * 0.18 + platform_score * 0.12 + ai_smell * 0.08
    )
    risk = _clamp(100 - (ai_smell * 0.68 + human_voice * 0.20 + rhythm * 0.12))
    if risk >= 65:
        tendency, risk_band = "formulaic_ai_like", "high"
    elif risk >= 35:
        tendency, risk_band = "mixed", "medium"
    else:
        tendency, risk_band = "natural_low_formulaicity", "low"

    per_sentence = []
    for index, sentence in enumerate(sentences):
        sentence_findings = [item for item in findings if item.sentence_index == index]
        technical = len(_contains(sentence, ENGINEERING_TERMS))
        choices = len(_contains(sentence, DECISION_MARKERS | TRADEOFF_MARKERS))
        sentence_risk = _clamp(18 + sum({"high": 28, "medium": 17, "low": 8}[f.severity] for f in sentence_findings) - technical * 5 - choices * 5)
        per_sentence.append({
            "index": index,
            "text": sentence,
            "risk": sentence_risk,
            "level": "high" if sentence_risk >= 60 else "medium" if sentence_risk >= 35 else "low",
            "rules": [item.rule for item in sentence_findings],
        })

    ordered_findings = sorted(
        findings,
        key=lambda item: ({"high": 0, "medium": 1, "low": 2}[item.severity], item.sentence_index or -1),
    )
    suggestions = [item.action for item in ordered_findings]
    if decision < 70:
        suggestions.append("State what should be chosen, under which condition, and why.")
    if engineering < 70:
        suggestions.append("Add only verified constraints, mechanisms, failure modes, or check methods.")
    if tradeoff_hits == 0:
        suggestions.append("Name the relevant trade-off instead of presenting benefits without limits.")
    suggestions = list(dict.fromkeys(suggestions))[:6]

    return {
        "scope_note": SCOPE_NOTE,
        "platform": platform,
        "classifier": {
            "style_tendency": tendency,
            "ai_like_writing_risk": risk,
            "risk_band": risk_band,
            "confidence_note": "Explainable heuristic classification of the writing, not the author's identity.",
            "signals": {
                "formulaic_findings": len(findings),
                "decision_markers": decision_hits,
                "tradeoff_markers": tradeoff_hits,
                "engineering_terms": engineering_hits,
            },
        },
        "statistical_layer": stats,
        "rule_layer": {
            "finding_count": len(ordered_findings),
            "findings": [asdict(item) for item in ordered_findings],
        },
        "industrial_authenticity_engine": {
            "score": authenticity,
            "dimensions": dimensions,
            "platform_note": platform_note,
            "fact_boundary_note": "Specificity is rewarded only when present; the tool never invents missing facts.",
        },
        "sentences": per_sentence,
        "revision_plan": suggestions,
    }
