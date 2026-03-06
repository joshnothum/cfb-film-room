from pipeline.route_gold import build_route_gold_template_rows, infer_route_play_type


def test_infer_route_play_type_detects_kick():
    assert infer_route_play_type(play_slug="punt_safe", play_name="PUNT SAFE") == "kick"
    assert infer_route_play_type(play_slug="field_goal_left_hash", play_name="FIELD GOAL") == "kick"


def test_infer_route_play_type_detects_run():
    assert infer_route_play_type(play_slug="inside_zone", play_name="INSIDE ZONE") == "run"
    assert infer_route_play_type(play_slug="power_read", play_name="POWER READ") == "run"


def test_infer_route_play_type_detects_rpo():
    assert infer_route_play_type(play_slug="rpo_peek", play_name="RPO PEEK") == "rpo"


def test_build_route_gold_template_rows_sets_play_type():
    rows = [
        {
            "play_id": "georgia-off:26:gun:inside_zone",
            "play_slug": "inside_zone",
            "play_name": "INSIDE ZONE",
            "formation_slug": "gun",
            "play_art_path": "/tmp/p.jpg",
            "source_url": "https://example.com",
        }
    ]
    result = build_route_gold_template_rows(manifest_rows=rows)
    assert result[0]["play_type"] == "run"
    assert result[0]["assignment_labels_expected"] == ["X", "Y", "A", "B", "RB"]


def test_build_route_gold_template_rows_seeded_defaults_labels_when_missing():
    rows = [{"play_id": "p1"}]
    result = build_route_gold_template_rows(
        manifest_rows=rows,
        include_predicted_values=True,
        predicted_by_play_id={"p1": {"primary_route_family": "cross_or_over"}},
    )
    assert result[0]["assignment_labels_expected"] == ["X", "Y", "A", "B", "RB"]
