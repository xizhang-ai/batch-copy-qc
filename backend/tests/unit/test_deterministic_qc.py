from backend.app.qc.deterministic import run_deterministic_qc


def test_required_and_forbidden_phrases_are_checked():
    findings = run_deterministic_qc(
        {"title": "气泡水", "body": "一喝就能治好疲劳", "tags": ["#气泡水"]},
        must_include=["通勤"],
        must_avoid=["治好"],
    )
    assert {finding.category for finding in findings} == {"must_include", "must_avoid"}
    assert next(f for f in findings if f.category == "must_avoid").level == "hard"


def test_tag_format_is_checked():
    findings = run_deterministic_qc({"title": "气泡水", "body": "通勤补水", "tags": ["气泡 水"]})
    assert findings[0].category == "tags"
    assert findings[0].message == "话题标签不能包含空格"


def test_tag_hash_is_a_presentation_detail_not_a_qc_requirement():
    findings = run_deterministic_qc(
        {"title": "气泡水", "body": "通勤补水", "tags": ["气泡水", "#通勤"]}
    )
    assert not [finding for finding in findings if finding.category == "tags"]
