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
