"""Mocked contract tests for the site's two-stage signed-URL download flow."""

from unittest.mock import Mock

import requests

from backend.scraper_client import SevenDaysModsClient, API_BASE_URL


def test_download_endpoint_exchanges_a_file_request_for_r2_signed_url():
    session = requests.Session()
    client = SevenDaysModsClient(session=session)
    post = Mock(return_value=Mock(status_code=200, json=Mock(return_value={
        "token": "sample-token", "wait_ms": 0,
    })))
    signed = (
        "https://example.r2.cloudflarestorage.com/mods/file.zip"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=example"
    )
    get = Mock(return_value=Mock(status_code=200, json=Mock(return_value={"url": signed})))
    session.post = post
    session.get = get

    assert client.resolve_download_url("mod-id", "file-id") == signed
    assert post.call_args.args[0] == f"{API_BASE_URL}/v1/mods/mod-id/files/file-id/download"
    assert get.call_args.args[0] == f"{API_BASE_URL}/v1/mods/downloads/sample-token"
    assert post.call_args.kwargs["headers"]["Origin"] == "https://7daystodiemods.com"
    assert get.call_args.kwargs["headers"]["Referer"] == "https://7daystodiemods.com/"
