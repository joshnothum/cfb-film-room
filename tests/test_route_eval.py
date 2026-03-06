from pipeline.route_eval import build_prediction_row, evaluate_predictions, normalize_route_family


def test_normalize_route_family_aliases():
    assert normalize_route_family("go") == "fade_or_go"
    assert normalize_route_family("hitch") == "flat_or_hitch"
    assert normalize_route_family("screen") == "screen_or_swing"
    assert normalize_route_family("swing") == "screen_or_swing"
    assert normalize_route_family("cross") == "cross_or_over"
    assert normalize_route_family("in") == "in_or_out_break"
    assert normalize_route_family("post") == "post_or_corner"
    assert normalize_route_family("corner") == "post_or_corner"


def test_build_prediction_row_chooses_top_two_unique_families():
    parse_result = {
        "route_candidates": [
            {"route_type_candidate": "flat_or_hitch", "confidence": 0.62},
            {"route_type_candidate": "fade_or_go", "confidence": 0.81},
            {"route_type_candidate": "fade_or_go", "confidence": 0.74},
        ],
        "assignment_labels": ["X", "Y"],
        "quality_flags": [],
    }
    row = {"play_id": "georgia-off:26:gun:basic"}
    predicted = build_prediction_row(row=row, parse_result=parse_result)

    assert predicted["play_id"] == "georgia-off:26:gun:basic"
    assert predicted["primary_route_family"] == "fade_or_go"
    assert predicted["secondary_route_family"] == "flat_or_hitch"
    assert predicted["assignment_labels_predicted"] == ["X", "Y"]


def test_evaluate_predictions_reports_accuracy_and_coverage():
    gold_rows = [
        {
            "play_id": "p1",
            "primary_route_family": "fade_or_go",
            "secondary_route_family": "flat_or_hitch",
        },
        {
            "play_id": "p2",
            "primary_route_family": "cross_or_over",
            "secondary_route_family": "in_or_out_break",
        },
    ]
    predicted_rows = [
        {
            "play_id": "p1",
            "primary_route_family": "go",
            "secondary_route_family": "hitch",
        },
        {
            "play_id": "p2",
            "primary_route_family": "unknown",
            "secondary_route_family": "out",
        },
    ]

    metrics = evaluate_predictions(gold_rows=gold_rows, predicted_rows=predicted_rows)
    primary = metrics["fields"]["primary_route_family"]
    secondary = metrics["fields"]["secondary_route_family"]

    assert primary["compared_rows"] == 2
    assert primary["correct_rows"] == 1
    assert primary["coverage"] == 0.5
    assert primary["accuracy"] == 0.5
    assert secondary["correct_rows"] == 2
    assert secondary["accuracy"] == 1.0
