"""The company database: where it is, and how a service opens a connection to it."""

from dataclasses import dataclass
import os

import pymysql

from company_secrets import read_env_file

CONNECT_TIMEOUT_SECONDS = 5
"""Budget for opening one database connection, after which the caller fails."""

ENVIRONMENT_VARIABLES = {
    "host": "DB_HOST",
    "port": "DB_PORT",
    "user": "DB_USER",
    "password": "DB_PASSWORD",
    "name": "DB_NAME",
}
"""Environment variable holding each setting, the same for every service."""

CREDENTIALS_FILE_VARIABLE = "DB_CREDENTIALS_FILE"
"""File holding ``DB_USER`` and ``DB_PASSWORD``, kept fresh by a Vault Agent."""


@dataclass(frozen=True)
class DatabaseSettings:
    """Where the company database lives, and who connects to it."""

    host: str
    port: int
    user: str
    password: str
    name: str
    credentials_file: str = ""

    def credentials(self) -> tuple[str, str]:
        """The user and password to connect with, read again on every call.

        Returns:
            Those of the credentials file when there is one (short-lived,
            rewritten by the Vault Agent), the settings' own otherwise.
        """
        if not self.credentials_file:
            return self.user, self.password
        values = read_env_file(self.credentials_file)
        return values["DB_USER"], values["DB_PASSWORD"]


def settings_from_environment() -> DatabaseSettings:
    """Read the settings a deployment gives through ``DB_*`` variables.

    Returns:
        The settings of the company database.
    """
    credentials_file = os.environ.get(CREDENTIALS_FILE_VARIABLE, "")
    required = not credentials_file
    return DatabaseSettings(
        host=os.environ[ENVIRONMENT_VARIABLES["host"]],
        port=int(os.environ[ENVIRONMENT_VARIABLES["port"]]),
        user=_variable(ENVIRONMENT_VARIABLES["user"], required),
        password=_variable(ENVIRONMENT_VARIABLES["password"], required),
        name=os.environ[ENVIRONMENT_VARIABLES["name"]],
        credentials_file=credentials_file,
    )


def _variable(name: str, required: bool) -> str:
    """A variable that must be set unless a credentials file replaces it."""
    return os.environ[name] if required else os.environ.get(name, "")


def connect(settings: DatabaseSettings) -> pymysql.connections.Connection:
    """Open a connection to the company database.

    Args:
        settings: Coordinates and credentials of the database.

    Returns:
        An open connection, to be used as a context manager.
    """
    user, password = settings.credentials()
    return pymysql.connect(
        host=settings.host,
        port=settings.port,
        user=user,
        password=password,
        database=settings.name,
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
    )
