import pytest
from unittest.mock import Mock

import requests

from scraper import cfbfan


def test_get_formations_empty_slug_raises():
    with pytest.raises(ValueError):
        cfbfan.get_formations("")


def test_get_plays_empty_url_raises():
    with pytest.raises(ValueError):
        cfbfan.get_plays("")


def test_get_play_art_url_empty_url_raises():
    with pytest.raises(ValueError):
        cfbfan.get_play_art_url("")


def test_get_play_art_url_invalid_side_raises():
    with pytest.raises(ValueError):
        cfbfan.get_play_art_url("/26/play/does-not-matter", playbook_side="bad-side")


def test_get_play_art_url_raises_on_403():
    mock_session = Mock(spec=requests.Session)
    mock_resp = Mock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("403 Client Error")
    mock_session.get.return_value = mock_resp

    with pytest.raises(requests.HTTPError):
        cfbfan.get_play_art_url("/26/play/does-not-matter", session=mock_session)


def test_get_formations_raises_on_403():
    mock_session = Mock(spec=requests.Session)
    mock_resp = Mock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("403 Client Error")
    mock_session.get.return_value = mock_resp

    with pytest.raises(requests.HTTPError):
        cfbfan.get_formations("georgia-off", session=mock_session)


def test_get_plays_raises_on_403():
    mock_session = Mock(spec=requests.Session)
    mock_resp = Mock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("403 Client Error")
    mock_session.get.return_value = mock_resp

    with pytest.raises(requests.HTTPError):
        cfbfan.get_plays("/26/playbook/formation", session=mock_session)


def test_get_play_art_url_uses_explicit_defense_side():
    mock_session = Mock(spec=requests.Session)
    mock_resp = Mock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = """
    <html>
      <h1><div class="text-lightest-gray">Nickel Over</div></h1>
      <li class="breadcrumbs__item"><a class="breadcrumbs__link" href="/26/playbooks/georgia-def/nickel-over">Nickel Over</a></li>
      <img src="https://s3.us-east-2.amazonaws.com/media.cfb.fan/26/playbookdb/defense/nickel/over/cover_3_sky.jpg"/>
    </html>
    """
    mock_session.get.return_value = mock_resp

    url = cfbfan.get_play_art_url(
        "/26/playbooks/georgia-def/nickel-over/cover-3-sky",
        playbook_side="defense",
        session=mock_session,
    )
    assert (
        url
        == "https://s3.us-east-2.amazonaws.com/media.cfb.fan/26/playbookdb/defense/nickel/over/cover_3_sky.jpg"
    )


def test_get_play_art_url_auto_infers_defense_from_team_slug():
    mock_session = Mock(spec=requests.Session)
    mock_resp = Mock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = """
    <html>
      <h1><div class="text-lightest-gray">Nickel Over</div></h1>
      <li class="breadcrumbs__item"><a class="breadcrumbs__link" href="/26/playbooks/georgia-def/nickel-over">Nickel Over</a></li>
      <img src="https://s3.us-east-2.amazonaws.com/media.cfb.fan/26/playbookdb/defense/nickel/over/cover_3_sky.jpg"/>
    </html>
    """
    mock_session.get.return_value = mock_resp

    url = cfbfan.get_play_art_url(
        "/26/playbooks/georgia-def/nickel-over/cover-3-sky",
        session=mock_session,
    )
    assert "/playbookdb/defense/" in url


def test_extract_play_art_url_from_html_matches_hyphen_play_slug():
    html = """
    <img src="https://s3.us-east-2.amazonaws.com/media.cfb.fan/26/playbookdb/defense/3-4/tite/cover_1_hole.jpg"/>
    """
    url = cfbfan._extract_play_art_url_from_html(
        html=html,
        play_slug="cover-1-hole",
        playbook_side="defense",
        year="26",
    )
    assert url is not None
    assert url.endswith("cover_1_hole.jpg")


def test_normalize_formation_name_for_slug_strips_group_prefix():
    normalized = cfbfan._normalize_formation_name_for_slug(
        "Nickel 2-4 Load Mug",
        "nickel-2-4-load-mug",
    )
    assert normalized == "2-4_load_mug"
