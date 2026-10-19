"""Credentials a service reads from a file a Vault Agent keeps up to date.

The services never talk to Vault. A Vault Agent beside them logs in, asks
Vault for each service's credentials, renews them and, when a short-lived one
reaches the end of its life, asks for new ones and rewrites the file. A
service reads its file each time it opens a connection, so it moves to the new
credentials without a restart. Without a file (tests, a laptop without
Vault), the environment variables still say everything.
"""

from pathlib import Path


def read_env_file(path: str) -> dict[str, str]:
    """Read ``KEY=value`` lines, the way the agent renders them.

    Args:
        path: The file the agent writes.

    Returns:
        Each key and its value, blank lines and comments skipped.
    """
    values = {}
    for line in Path(path).read_text().splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            values[key.strip()] = value.strip()
    return values
