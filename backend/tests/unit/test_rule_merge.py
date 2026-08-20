from dataclasses import dataclass

from backend.app.qc.merge_rules import merge_rules


@dataclass
class Rule:
    category: str
    statement: str
    level: str = "soft"
    enabled: bool = True


def test_type_soft_rule_overrides_project_soft_rule():
    merged = merge_rules([Rule("tone", "克制")], [Rule("tone", "活泼")])
    assert merged.effective[0].statement == "活泼"


def test_type_soft_cannot_override_project_hard_and_creates_conflict():
    merged = merge_rules([Rule("claim", "不得宣称治疗", "hard")], [Rule("claim", "突出治疗效果")])
    assert merged.effective[0].statement == "不得宣称治疗"
    assert [rule.statement for rule in merged.effective] == ["不得宣称治疗", "突出治疗效果"]
    assert merged.conflicts[0].category == "claim"
    assert merged.conflicts[0].project_statement == "不得宣称治疗"
    assert merged.conflicts[0].type_statement == "突出治疗效果"


def test_all_hard_rules_are_kept_while_type_soft_only_replaces_project_soft():
    project = [
        Rule("claim", "不得宣称治疗", "hard"),
        Rule("claim", "不得承诺见效", "hard"),
        Rule("tone", "克制"),
        Rule("tone", "真实"),
    ]
    type_rules = [Rule("tone", "轻松"), Rule("claim", "不得虚构资质", "hard")]

    merged = merge_rules(project, type_rules)

    assert [rule.statement for rule in merged.effective] == [
        "不得宣称治疗",
        "不得承诺见效",
        "不得虚构资质",
        "轻松",
    ]
    assert merged.conflicts == []
