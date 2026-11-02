"""Authenticated call to a fixed, private Cloud Run ADK worker."""

import os
from urllib.parse import urlsplit

import httpx

from heritagelink.campaign_contract import CampaignInput


def run_campaign(body: CampaignInput) -> dict:
    url = os.getenv("ADK_WORKER_URL", "").rstrip("/")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not (parsed.hostname or "").endswith(".run.app")
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise RuntimeError("Campaign worker is not configured")
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import fetch_id_token

    token = fetch_id_token(Request(), url)
    response = httpx.post(
        url + "/campaign",
        json=body.model_dump(),
        timeout=45,
        headers={"Authorization": "Bearer " + token},
        follow_redirects=False,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("requires_human_review") is not True or result.get("published") is not False:
        raise ValueError("Unexpected campaign response")
    return result
