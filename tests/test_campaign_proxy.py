"""The public service mints an audience-bound token only for its configured worker."""

from types import SimpleNamespace

import pytest

from heritagelink.campaign_contract import CampaignInput
from heritagelink.web.campaign import run_campaign


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://private.run.app",
        "https://private.run.app.evil.test",
        "https://private.run.app/campaign",
        "https://user@private.run.app",
    ],
)
def test_proxy_rejects_invalid_destinations(monkeypatch, url):
    monkeypatch.setenv("ADK_WORKER_URL", url)
    with pytest.raises(RuntimeError):
        run_campaign(CampaignInput(product_id="p", goal="Introduce this concept"))


def test_proxy_uses_worker_audience_and_does_not_follow_redirects(monkeypatch):
    from google.oauth2 import id_token

    from heritagelink.web import campaign

    url = "https://haha-adk.run.app"
    monkeypatch.setenv("ADK_WORKER_URL", url)

    def token(request, audience):
        assert audience == url
        return "test-id-token"

    def post(destination, **kwargs):
        assert destination == url + "/campaign"
        assert kwargs["headers"] == {"Authorization": "Bearer test-id-token"}
        assert kwargs["follow_redirects"] is False
        assert kwargs["timeout"] == 45
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"requires_human_review": True, "published": False},
        )

    monkeypatch.setattr(id_token, "fetch_id_token", token)
    monkeypatch.setattr(campaign.httpx, "post", post)
    assert (
        run_campaign(CampaignInput(product_id="p", goal="Introduce this concept"))["published"]
        is False
    )
