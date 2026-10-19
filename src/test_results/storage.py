"""Opening the results bucket, the real one or a local emulator."""

import os

from google.api_core.exceptions import GoogleAPIError
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from requests.exceptions import RequestException

EMULATOR_VARIABLE = "STORAGE_EMULATOR_HOST"
"""Standard variable of the Cloud Storage client: set, it talks to an emulator."""

EMULATOR_PROJECT = "local"
"""Project name an emulator accepts; it checks nothing."""


def open_client() -> storage.Client:
    """Return a Cloud Storage client, without any network call yet.

    With ``STORAGE_EMULATOR_HOST`` set, the client talks to that emulator
    without credentials, as a local stack or a CI sidecar needs. Without it,
    the client uses Application Default Credentials against Google Cloud.

    Returns:
        The client.
    """
    if os.environ.get(EMULATOR_VARIABLE):
        return storage.Client(
            project=EMULATOR_PROJECT, credentials=AnonymousCredentials()
        )
    return storage.Client()


def open_bucket(name: str) -> storage.Bucket:
    """Return a handle on the bucket, without any network call yet.

    Args:
        name: Bucket name.

    Returns:
        The bucket handle, see ``open_client`` for where it lives.
    """
    return open_client().bucket(name)


REACHABILITY_TIMEOUT_SECONDS = 3
"""Budget for telling whether the bucket answers, before any upload."""


def is_reachable(bucket: storage.Bucket) -> bool:
    """Say whether the bucket answers, in seconds rather than after retries.

    Args:
        bucket: Bucket handle from ``open_bucket``.

    Returns:
        True when the bucket exists and answered.
    """
    try:
        return bool(bucket.exists(timeout=REACHABILITY_TIMEOUT_SECONDS, retry=None))
    except GoogleAPIError, RequestException:
        return False
