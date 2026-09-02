"""Offline, fact-preserving optimization for industrial B2B copy.

The optimizer improves observable editorial quality. It never targets the
lightweight model probability and never treats that probability as authorship.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .analyzer import ENGINEERING_TERMS, MARKETING_WORDS, TRANSITIONS, analyze_text
from .model import LightweightModel


OPTIMIZER_VERSION = "iad-research-optimizer-0.4.0"
MAX_TEXT_LENGTH = 50_000
FACT_FIELDS = {
    "audience_decision": ("目标读者及决策", "Audience and decision"),
    "application": ("应用场景或用途", "Application or use case"),
    "specifications_constraints": ("规格、材料及约束", "Specifications, materials, and constraints"),
    "failure_risk_check": ("失效风险和检查方法", "Failure risk and check method"),
    "evidence": ("已核实测试或证据", "Verified test or evidence"),
    "tradeoff_preference": ("取舍及推荐选择", "Trade-off and preferred choice"),
    "cta": ("期望行动", "Desired action"),
}


def _clean_fact_values(values: Any) -> dict[str, str]:
    if values is None:
        return {}
    if not isinstance(values, dict):
        raise ValueError("verified_facts must be an object.")
    unknown = set(values) - set(FACT_FIELDS)
    if unknown:
        raise ValueError(f"Unsupported verified fact field: {sorted(unknown)[0]}")
    cleaned: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(value, str):
            raise ValueError(f"Verified fact field {key} must be text.")
        value = value.strip()
        if len(value) > 2_000:
            raise ValueError(f"Verified fact field {key} exceeds 2,000 characters.")
        if value:
            cleaned[key] = value
    return cleaned


def _clean_source_facts(values: Any) -> list[dict[str, str]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("source_facts must be an array.")
    cleaned = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("Each source fact must be an object.")
        summary = value.get("fact_summary", "")
        url = value.get("url", "")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 500:
            raise ValueError("Each source fact summary must be 1 to 500 characters.")
        if not isinstance(url, str) or not url.startswith("https://") or len(url) > 2_048:
            raise ValueError("Each source fact must retain a traceable HTTPS source.")
        cleaned.append({
            "fact_id": str(value.get("fact_id", ""))[:80],
            "fact_summary": summary.strip(),
            "applicability": str(value.get("applicability", ""))[:500],
            "source_title": str(value.get("source_title", ""))[:300],
            "publisher": str(value.get("publisher", ""))[:200],
            "url": url,
            "published_date": str(value.get("published_date") or "")[:80],
            "fetched_at": str(value.get("fetched_at") or "")[:80],
            "source_type": str(value.get("source_type", "other_web"))[:80],
            "credibility": str(value.get("credibility", "review_required"))[:80],
            "content_fingerprint": str(value.get("content_fingerprint", ""))[:128],
        })
    return cleaned


def _language(text: str) -> str:
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return "zh" if chinese >= latin * 0.35 else "en"


def _remove_formulaic_language(text: str) -> tuple[str, list[dict[str, str]]]:
    changes: list[dict[str, str]] = []
    result = text
    transition_pattern = "|".join(sorted((re.escape(x) for x in TRANSITIONS), key=len, reverse=True))
    result, transition_count = re.subn(
        rf"(?im)(^|(?<=[.!?。！？])\s+)\s*(?:{transition_pattern})\s*[,，:：]?\s*",
        lambda match: match.group(1),
        result,
    )
    if transition_count:
        changes.append({
            "type": "formulaic_transition",
            "reason_zh": "移除不承载工程逻辑的程式化过渡词。",
            "reason_en": "Removed formulaic transitions that did not carry engineering logic.",
        })

    marketing_pattern = "|".join(sorted((re.escape(x) for x in MARKETING_WORDS), key=len, reverse=True))
    result, marketing_count = re.subn(
        rf"(?i)(?<![A-Za-z])(?:{marketing_pattern})(?![A-Za-z])\s*",
        "",
        result,
    )
    if marketing_count:
        changes.append({
            "type": "unsupported_marketing",
            "reason_zh": "删除缺少标准或证据支撑的营销形容词。",
            "reason_en": "Removed marketing adjectives without a stated criterion or evidence source.",
        })

    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r"\s+([,.;:!?，。；：！？])", r"\1", result)
    result = re.sub(r"([,，])\s*([.!?。！？])", r"\2", result)
    result = re.sub(
        r"(^|(?<=[.!?])\s+)([a-z])",
        lambda match: match.group(1) + match.group(2).upper(),
        result,
    )
    return result.strip(), changes


def _split_long_sentences(text: str) -> tuple[str, list[dict[str, str]]]:
    changed = False
    paragraphs: list[str] = []
    for paragraph in re.split(r"(\n\s*\n)", text):
        if not paragraph.strip() or re.fullmatch(r"\n\s*\n", paragraph):
            paragraphs.append(paragraph)
            continue
        if _language(paragraph) == "zh" and len(paragraph) > 90:
            revised, count = re.subn(r"；|，(?=(?:但|如果|当|因为|因此|同时))", "。", paragraph)
        elif len(re.findall(r"[A-Za-z]+", paragraph)) > 44:
            revised, count = re.subn(r";\s+|,\s+(?=(?:but|while|if|when|because|so)\b)", ". ", paragraph, flags=re.I)
        else:
            revised, count = paragraph, 0
        changed = changed or bool(count)
        paragraphs.append(revised)
    changes = []
    if changed:
        changes.append({
            "type": "sentence_rhythm",
            "reason_zh": "在条件、取舍或结果边界拆分过长句子。",
            "reason_en": "Split long sentences at condition, trade-off, or consequence boundaries.",
        })
    return "".join(paragraphs).strip(), changes


def _adapt_platform_structure(text: str, platform: str) -> tuple[str, list[dict[str, str]]]:
    """Create a channel-readable candidate without adding or rewriting facts."""
    if platform not in {"linkedin", "facebook", "blog"} or "\n\n" in text:
        return text, []
    sentences = [
        item.strip()
        for item in re.split(
            r"(?<=[.!?。！？])(?:\s+|(?=[A-Za-z0-9\u4e00-\u9fff]))",
            text.strip(),
        )
        if item.strip()
    ]
    if len(sentences) < 3:
        return text, []
    group_size = 1 if platform in {"linkedin", "facebook"} else 2
    paragraphs = [" ".join(sentences[index:index + group_size]) for index in range(0, len(sentences), group_size)]
    adapted = "\n\n".join(paragraphs)
    if adapted == text:
        return text, []
    return adapted, [{
        "type": "platform_structure",
        "reason_zh": f"仅调整 {platform.title()} 的段落与扫读结构，未新增事实。",
        "reason_en": f"Adjusted paragraphing for {platform.title()} scanning without adding facts.",
    }]


def _verified_block(facts: dict[str, str], language: str) -> str:
    if not facts:
        return ""
    labels = {
        "audience_decision": ("决策", "Decision"),
        "application": ("适用条件", "Application condition"),
        "specifications_constraints": ("已核实规格与约束", "Verified specifications and constraints"),
        "failure_risk_check": ("失效风险与检查方法", "Failure risk and check method"),
        "evidence": ("已核实证据", "Verified evidence"),
        "tradeoff_preference": ("取舍与建议选择", "Trade-off and recommended choice"),
        "cta": ("下一步", "Next action"),
    }
    rows = []
    for key in FACT_FIELDS:
        if key in facts:
            label = labels[key][0 if language == "zh" else 1]
            rows.append(f"{label}：{facts[key]}" if language == "zh" else f"{label}: {facts[key]}")
    heading = "已核实的决策信息" if language == "zh" else "Verified decision inputs"
    return heading + ("：\n" if language == "zh" else ":\n") + "\n".join(rows)


def _source_block(facts: list[dict[str, str]], language: str, citation_mode: str, platform: str) -> str:
    if not facts:
        return ""
    heading = "用户确认的来源事实" if language == "zh" else "User-confirmed source facts"
    rows = [f"- {fact['fact_summary']}" for fact in facts]
    if citation_mode == "body" and platform == "blog":
        source_heading = "来源" if language == "zh" else "Sources"
        rows.extend(["", source_heading, *[f"- {fact['source_title'] or fact['publisher']}: {fact['url']}" for fact in facts]])
    return heading + ("：\n" if language == "zh" else ":\n") + "\n".join(rows)


def _numeric_source_conflicts(text: str, facts: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Conservatively reject sourced numbers that contradict the same-unit draft value."""
    pattern = re.compile(r"(?i)(\d+(?:[.,]\d+)?)\s*(mm|cm|m|kg|g|%|mpa|gsm|°c|cycles?)\b")
    original_by_unit: dict[str, set[str]] = {}
    for number, unit in pattern.findall(text):
        original_by_unit.setdefault(unit.casefold(), set()).add(number.replace(",", "."))
    accepted, conflicts = [], []
    for fact in facts:
        source_by_unit: dict[str, set[str]] = {}
        for number, unit in pattern.findall(fact["fact_summary"]):
            source_by_unit.setdefault(unit.casefold(), set()).add(number.replace(",", "."))
        conflicting_units = [
            unit for unit, values in source_by_unit.items()
            if unit in original_by_unit and values.isdisjoint(original_by_unit[unit])
        ]
        if conflicting_units:
            conflicts.append({
                "fact_id": fact["fact_id"],
                "reason": "numeric_unit_conflict",
                "units": ", ".join(conflicting_units),
                "fact_summary": fact["fact_summary"],
                "url": fact["url"],
            })
        else:
            accepted.append(fact)
    return accepted, conflicts


def _protected_items(text: str) -> dict[str, list[str]]:
    numbers = re.findall(r"(?i)(?<!\w)\d+(?:[.,]\d+)?\s*(?:mm|cm|m|kg|g|%|mpa|gsm|°c|cycles?)?", text)
    negatives = re.findall(r"(?i)(?<![A-Za-z])(?:not|no|never|without|cannot|can't|mustn't)(?![A-Za-z])|不得|不能|不应|没有|未|无", text)
    acronyms = re.findall(r"(?<![A-Za-z])[A-Z][A-Z0-9-]{1,}(?![A-Za-z])", text)
    engineering = [term for term in ENGINEERING_TERMS if term.lower() in text.lower()]
    return {"numbers_units": numbers, "negations": negatives, "product_terms": acronyms, "technical_terms": engineering}


def _contains_multiset(candidate: str, items: list[str]) -> bool:
    source = Counter(item.casefold().strip() for item in items)
    folded = candidate.casefold()
    return all(folded.count(item) >= count for item, count in source.items())


def _safety_check(original: str, candidate: str, verified: dict[str, str], source_facts: list[dict[str, str]] | None = None) -> dict:
    protected = _protected_items(original)
    checks = {
        name: _contains_multiset(candidate, items)
        for name, items in protected.items()
    }
    # Claims with a high fabrication cost may only appear when already present
    # in the source or in user-confirmed facts.
    allowed = (original + "\n" + "\n".join(verified.values()) + "\n" + "\n".join(
        fact["fact_summary"] for fact in (source_facts or [])
    )).casefold()
    risky_patterns = [
        r"\b(?:certified|certification|customer achieved|saved \$|roi of)\b",
        r"(?:认证|客户实现|节省金额|投资回报率)",
    ]
    unsupported = []
    for pattern in risky_patterns:
        for match in re.findall(pattern, candidate, flags=re.I):
            if str(match).casefold() not in allowed:
                unsupported.append(str(match))
    checks["no_unverified_high_stakes_claims"] = not unsupported
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "protected_items": protected,
        "unsupported_additions": unsupported,
        "note": "Numbers, units, negation, product identifiers, technical terms, and unsupported high-stakes claims were checked locally.",
    }


def _missing_fact_requests(original: dict, verified: dict[str, str]) -> list[dict[str, str]]:
    dims = original["industrial_authenticity_engine"]["dimensions"]
    requests = []
    mappings = (
        ("engineering_credibility", "failure_risk_check", "补充已核实的工况、失效风险和检查方法。", "Add verified operating conditions, failure risks, and check methods."),
        ("specificity", "specifications_constraints", "补充已核实的尺寸、材料、规格和约束。", "Add verified dimensions, materials, specifications, and constraints."),
        ("decision_density", "tradeoff_preference", "补充目标读者需要作出的决策、取舍和推荐选择。", "Add the reader's decision, trade-off, and preferred choice."),
    )
    for dimension, field, zh, en in mappings:
        if dims[dimension] < 70 and field not in verified:
            requests.append({"dimension": dimension, "field": field, "message_zh": zh, "message_en": en})
    return requests


def _score_changes(before: dict, after: dict) -> dict:
    before_dims = before["industrial_authenticity_engine"]["dimensions"]
    after_dims = after["industrial_authenticity_engine"]["dimensions"]
    quality = {
        "industrial_authenticity": {
            "before": before["industrial_authenticity_engine"]["score"],
            "after": after["industrial_authenticity_engine"]["score"],
        }
    }
    for key, value in before_dims.items():
        quality[key] = {"before": value, "after": after_dims[key]}
    for item in quality.values():
        item["delta"] = item["after"] - item["before"]
        item["direction"] = "higher_is_better"
    risks = {
        "writing_style_risk": {
            "before": before["writing_style_risk"]["ai_like_writing_risk"],
            "after": after["writing_style_risk"]["ai_like_writing_risk"],
            "direction": "lower_is_better",
        },
        "predictability_proxy": {
            "before": before["statistical_layer"]["predictability_proxy"],
            "after": after["statistical_layer"]["predictability_proxy"],
            "direction": "lower_is_better",
        },
    }
    for item in risks.values():
        item["delta"] = item["after"] - item["before"]
    model = {
        "before": before["model_detection"].get("probability_percent"),
        "after": after["model_detection"].get("probability_percent"),
        "direction": "reference_only",
        "used_for_selection": False,
    }
    model["delta"] = None if model["before"] is None or model["after"] is None else round(model["after"] - model["before"], 1)
    return {"quality": quality, "risks": risks, "model_detection": model}


def optimize_text(
    text: str,
    platform: str = "general",
    verified_facts: Any = None,
    confirmed_verified: bool = False,
    model: LightweightModel | None = None,
    source_facts: Any = None,
    citation_mode: str = "panel",
) -> dict:
    """Return the best safe offline candidate and its transparent evaluation."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Text must contain at least one non-whitespace character.")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError("Text exceeds the 50,000-character local optimization limit.")
    facts = _clean_fact_values(verified_facts)
    if citation_mode not in {"panel", "body", "none"}:
        raise ValueError("citation_mode must be panel, body, or none.")
    cleaned_source_facts = _clean_source_facts(source_facts)
    usable_source_facts, fact_conflicts = _numeric_source_conflicts(text, cleaned_source_facts)
    confirmed = confirmed_verified is True
    usable_facts = facts if confirmed else {}
    original = analyze_text(text, platform, model)
    language = _language(text)

    cleaned, clean_changes = _remove_formulaic_language(text)
    split, split_changes = _split_long_sentences(cleaned)
    adapted, platform_changes = _adapt_platform_structure(split, platform)
    candidates: list[tuple[str, list[dict[str, str]]]] = [
        (cleaned, clean_changes),
        (split, clean_changes + split_changes),
        (adapted, clean_changes + split_changes + platform_changes),
    ]
    block = _verified_block(usable_facts, language)
    source_block = _source_block(usable_source_facts, language, citation_mode, platform)
    if source_block:
        block = (block + "\n\n" + source_block).strip()
    if block:
        candidates.extend([
            (text.rstrip() + "\n\n" + block, [{
                "type": "verified_decision_inputs",
                "reason_zh": "仅加入用户确认已核实的决策与工程信息。",
                "reason_en": "Added only decision and engineering facts confirmed by the user.",
            }]),
            (split.rstrip() + "\n\n" + block, clean_changes + split_changes + [{
                "type": "verified_decision_inputs",
                "reason_zh": "仅加入用户确认已核实的决策与工程信息。",
                "reason_en": "Added only decision and engineering facts confirmed by the user.",
            }]),
            (adapted.rstrip() + "\n\n" + block, clean_changes + split_changes + platform_changes + [{
                "type": "verified_decision_inputs",
                "reason_zh": "仅加入用户确认已核实的决策与工程信息。",
                "reason_en": "Added only decision and engineering facts confirmed by the user.",
            }]),
        ])

    original_dims = original["industrial_authenticity_engine"]["dimensions"]
    target_dimensions = [key for key, value in original_dims.items() if value < 70]
    evaluated = []
    for candidate, changes in candidates:
        if not candidate or candidate == text:
            continue
        safety = _safety_check(text, candidate, usable_facts, usable_source_facts)
        if not safety["passed"]:
            continue
        analysis = analyze_text(candidate, platform, model)
        dims = analysis["industrial_authenticity_engine"]["dimensions"]
        regressions = [key for key, value in original_dims.items() if value >= 70 and dims[key] < value - 2]
        improved_targets = [key for key in target_dimensions if dims[key] > original_dims[key]]
        if (
            analysis["industrial_authenticity_engine"]["score"] <= original["industrial_authenticity_engine"]["score"]
            or regressions
            or not improved_targets
        ):
            continue
        selection_score = (
            analysis["industrial_authenticity_engine"]["score"] * 10
            + sum(dims[key] - original_dims[key] for key in improved_targets)
        )
        evaluated.append((selection_score, candidate, changes, analysis, safety, improved_targets))

    if evaluated:
        _, optimized, changes, optimized_analysis, safety, improved_targets = max(evaluated, key=lambda item: item[0])
        status = "improved"
    else:
        optimized, changes, optimized_analysis = text, [], original
        safety = _safety_check(text, text, usable_facts, usable_source_facts)
        improved_targets = []
        status = "blocked_by_missing_facts" if _missing_fact_requests(original, usable_facts) else "no_safe_improvement"

    missing = _missing_fact_requests(original, usable_facts)
    blocked_dimensions = [
        item["dimension"] for item in missing
        if item["dimension"] in target_dimensions and item["dimension"] not in improved_targets
    ]
    provided_items = _protected_items(text)
    return {
        "optimizer_version": OPTIMIZER_VERSION,
        "status": status,
        "platform": platform,
        "original_analysis": original,
        "optimized_text": optimized,
        "optimized_analysis": optimized_analysis,
        "score_changes": _score_changes(original, optimized_analysis),
        "change_log": changes,
        "fact_ledger": {
            "provided": provided_items,
            "safely_derived": ["Structural and editorial changes only; no new performance conclusion was inferred."],
            "verified": [
                {"field": key, "label_zh": FACT_FIELDS[key][0], "label_en": FACT_FIELDS[key][1], "value": value}
                for key, value in usable_facts.items()
            ],
            "unconfirmed": [
                {"field": key, "label_zh": FACT_FIELDS[key][0], "label_en": FACT_FIELDS[key][1], "value": value}
                for key, value in facts.items() if not confirmed
            ],
            "confirmed_source_facts": usable_source_facts,
            # Retained as a response alias for early v0.4.0 preview clients.
            "verified_source_facts": usable_source_facts,
            "source_fact_conflicts": fact_conflicts,
            "missing_or_unverified": missing,
        },
        "citations": [
            {key: fact[key] for key in ("fact_id", "fact_summary", "source_title", "publisher", "url", "published_date", "source_type", "credibility")}
            for fact in usable_source_facts
        ],
        "citation_mode": citation_mode,
        "unresolved_fact_requests": missing,
        "blocked_dimensions": blocked_dimensions,
        "safety": safety,
        "model_detection_note": {
            "zh": "AI 类模式概率仅作独立参考，不参与候选选择，也不用于判定作者身份。",
            "en": "AI-like pattern probability is shown independently, is not used to select a candidate, and is not proof of authorship.",
        },
        "privacy": "Optimization ran locally; source text, supplied facts, and the candidate were not persisted.",
    }
