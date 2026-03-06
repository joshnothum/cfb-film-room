from scripts.review_server import ReviewHandler


def test_validate_payload_route_play_type():
    payload = {
        "play_id": "x",
        "play_type": "rpo",
        "primary_route_family": "unknown",
        "secondary_route_family": None,
        "assignment_labels_expected": ["X", "RB"],
        "labeler_notes": None,
        "review_state": "pending",
        "review_disposition": "keep",
    }
    errors = ReviewHandler._validate_payload(payload, schema="route")
    assert errors == []


def test_validate_payload_route_accepts_screen_or_swing_family():
    payload = {
        "play_id": "x",
        "play_type": "pass",
        "primary_route_family": "screen_or_swing",
        "secondary_route_family": None,
        "assignment_labels_expected": ["RB"],
        "labeler_notes": None,
        "review_state": "pending",
        "review_disposition": "keep",
    }
    errors = ReviewHandler._validate_payload(payload, schema="route")
    assert errors == []


def test_validate_payload_route_rejects_bad_play_type():
    payload = {
        "play_id": "x",
        "play_type": "trick",
        "review_state": "pending",
        "review_disposition": "keep",
    }
    errors = ReviewHandler._validate_payload(payload, schema="route")
    assert any(err["field"] == "play_type" for err in errors)
