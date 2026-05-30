"""Cloudflare R2 client helper.

Returns None when credentials are missing so callers can short-circuit
without raising — useful so a dev environment without R2 still runs.
"""
from typing import Optional

import boto3
from botocore.client import Config as BotoConfig

from wikiseed.config import CONFIG


def client() -> Optional[object]:
    if not (CONFIG.r2_account_id and CONFIG.r2_access_key_id and CONFIG.r2_secret_access_key):
        return None
    return boto3.client(
        "s3",
        endpoint_url=f"https://{CONFIG.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=CONFIG.r2_access_key_id,
        aws_secret_access_key=CONFIG.r2_secret_access_key,
        region_name="auto",
        config=BotoConfig(signature_version="s3v4"),
    )
