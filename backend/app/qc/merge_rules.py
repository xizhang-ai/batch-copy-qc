from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _value(rule: Any, name: str) -> Any:
    return rule.get(name) if isinstance(rule, dict) else getattr(rule, name)


@dataclass(frozen=True, slots=True)
class RuleConflict:
    category: str
    project_statement: str
    type_statement: str


@dataclass(frozen=True, slots=True)
class MergedRules:
    effective: list[Any]
    conflicts: list[RuleConflict]


def merge_rules(project_rules: list[Any], type_rules: list[Any]) -> MergedRules:
    effective: list[Any] = []
    conflicts: list[RuleConflict] = []
    projects = [rule for rule in project_rules if _value(rule, "enabled")]
    types = [rule for rule in type_rules if _value(rule, "enabled")]
    categories = dict.fromkeys([_value(rule, "category") for rule in [*projects, *types]])
    for category in categories:
        project_group = [rule for rule in projects if _value(rule, "category") == category]
        type_group = [rule for rule in types if _value(rule, "category") == category]
        project_hard = [rule for rule in project_group if _value(rule, "level") == "hard"]
        project_soft = [rule for rule in project_group if _value(rule, "level") != "hard"]
        type_hard = [rule for rule in type_group if _value(rule, "level") == "hard"]
        type_soft = [rule for rule in type_group if _value(rule, "level") != "hard"]

        effective.extend(project_hard)
        effective.extend(type_hard)
        effective.extend(type_soft or project_soft)
        # A type soft rule cannot override a project hard rule. Hard rules remain
        # additive because their different text does not itself imply a conflict.
        for project_rule in project_hard:
            for type_rule in type_soft:
                if _value(type_rule, "statement") != _value(project_rule, "statement"):
                    conflicts.append(
                        RuleConflict(
                            category,
                            _value(project_rule, "statement"),
                            _value(type_rule, "statement"),
                        )
                    )
    return MergedRules(effective, conflicts)
