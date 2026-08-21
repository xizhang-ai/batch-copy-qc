from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class QcFinding:
    category: str
    message: str
    level: str = "soft"
    evidence: str = ""
    suggestion: str = ""
    auto_fixable: bool = True
    rule_id: str | None = None
    source: str = "deterministic"
    matched_id: str | None = None


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def run_deterministic_qc(
    draft: Any,
    *,
    rules: list[Any] | None = None,
    must_include: list[str] | None = None,
    must_avoid: list[str] | None = None,
    title_min: int = 1,
    title_max: int = 40,
    body_min: int = 1,
    body_max: int = 1000,
) -> list[QcFinding]:
    title = str(_get(draft, "title", "")).strip()
    body = str(_get(draft, "body", "")).strip()
    tags = list(_get(draft, "tags", []) or [])
    combined = f"{title}\n{body}\n{' '.join(tags)}"
    findings: list[QcFinding] = []
    for field, text in (("title", title), ("body", body)):
        if not text:
            findings.append(
                QcFinding("required", f"{field} cannot be empty", "hard", auto_fixable=True)
            )
    if title and not title_min <= len(title) <= title_max:
        findings.append(
            QcFinding("length", f"Title length must be {title_min}-{title_max}", evidence=title)
        )
    if body and not body_min <= len(body) <= body_max:
        findings.append(
            QcFinding("length", f"Body length must be {body_min}-{body_max}", evidence=body[:80])
        )
    if not tags:
        findings.append(
            QcFinding(
                "tags",
                "至少需要一个话题标签",
                suggestion="输入标签文字即可，界面会自动显示 #。",
            )
        )
    invalid_tags = [
        str(tag).strip().lstrip("#")
        for tag in tags
        if not str(tag).strip().lstrip("#")
        or any(char.isspace() for char in str(tag).strip().lstrip("#"))
    ]
    if invalid_tags:
        findings.append(
            QcFinding(
                "tags",
                "话题标签不能包含空格",
                evidence="、".join(invalid_tags),
                suggestion="删除标签内部空格；无需手动输入 #，界面会自动补充。",
            )
        )
    for phrase in must_include or []:
        if phrase not in combined:
            findings.append(
                QcFinding("must_include", f"Missing required phrase: {phrase}", evidence=phrase)
            )
    for phrase in must_avoid or []:
        if phrase and phrase in combined:
            findings.append(
                QcFinding(
                    "must_avoid",
                    f"Forbidden phrase found: {phrase}",
                    "hard",
                    phrase,
                    auto_fixable=True,
                )
            )
    for rule in rules or []:
        if not _get(rule, "enabled", True):
            continue
        statement = str(_get(rule, "statement", ""))
        # First-version deterministic matching deliberately handles explicit phrase rules only.
        if (
            statement.startswith("必含：")
            and statement.removeprefix("必含：").strip() not in combined
        ):
            findings.append(
                QcFinding(
                    _get(rule, "category", "rule"),
                    statement,
                    _get(rule, "level", "soft"),
                    rule_id=_get(rule, "id"),
                )
            )
        if statement.startswith("禁用："):
            phrase = statement.removeprefix("禁用：").strip()
            if phrase in combined:
                findings.append(
                    QcFinding(
                        _get(rule, "category", "rule"),
                        statement,
                        _get(rule, "level", "hard"),
                        phrase,
                        rule_id=_get(rule, "id"),
                    )
                )
    return findings
