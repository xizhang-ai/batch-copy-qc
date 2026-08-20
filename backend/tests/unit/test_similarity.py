from backend.app.qc.similarity import (
    compare_items,
    compare_with_references,
    normalize_for_similarity,
)


def test_normalization_handles_full_width_and_whitespace():
    assert normalize_for_similarity("Ａ  气泡水\n") == "a 气泡水"


def test_near_duplicate_chinese_copy_is_flagged():
    result = compare_items(
        {"id": "a", "body": "通勤喝气泡水"}, [{"id": "b", "body": "通勤路上喝气泡水"}], 70
    )
    assert result[0].matched_id == "b"


def test_item_is_never_compared_with_itself():
    assert compare_items({"id": "a", "body": "同一篇"}, [{"id": "a", "body": "同一篇"}], 80) == []


def test_generated_copy_too_close_to_reference_is_flagged():
    result = compare_with_references(
        {"id": "a", "body": "午后第一口气泡水"}, [{"id": "r1", "body": "午后第一口气泡水"}], 80
    )
    assert result[0].source_kind == "reference_example"
