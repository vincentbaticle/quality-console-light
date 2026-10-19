"""What the Quality Console reads: databases, tables, columns, rows.

Every identifier a visitor sends (database, table, column) is checked against
what MySQL lists before it reaches a statement, since an identifier cannot be
bound as a parameter. Values are always bound.
"""

from dataclasses import dataclass, replace
from typing import Any

from company_db import DatabaseSettings, connect

SYSTEM_SCHEMAS = frozenset({"information_schema", "performance_schema", "mysql", "sys"})
"""Schemas MySQL keeps for itself, hidden from the console."""

ROWS_PER_PAGE = 50
"""Rows shown for a table or a search, enough for a table of a demo database."""


class UnknownObjectError(LookupError):
    """A database, table or column the account cannot see."""


@dataclass(frozen=True)
class TableSummary:
    """A table and how many rows it holds."""

    name: str
    rows: int


@dataclass(frozen=True)
class TableContent:
    """The columns of a table and the rows to show."""

    columns: list[str]
    rows: list[tuple[Any, ...]]


class DatabaseBrowser:
    """Reads the company database with the console's own account."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Point at the server.

        Args:
            settings: Coordinates and credentials of the console's account.
        """
        self._settings = settings

    @property
    def user(self) -> str:
        """The account the browser reads with."""
        return self._settings.user

    def databases(self) -> list[str]:
        """List the databases the account can read, system ones aside."""
        names = self._fetch("SHOW DATABASES", (), self._settings.name)
        return [row[0] for row in names if row[0] not in SYSTEM_SCHEMAS]

    def tables(self, database: str) -> list[TableSummary]:
        """List the tables of a database, each with its exact row count.

        Raises:
            UnknownObjectError: When the account cannot see that database.
        """
        return [
            TableSummary(name, self._count(database, name))
            for name in self._table_names(database)
        ]

    def _table_names(self, database: str) -> list[str]:
        """List the table names of a database the account can see.

        Raises:
            UnknownObjectError: When the account cannot see that database.
        """
        self._check(database, self.databases(), "database")
        return [
            row[0]
            for row in self._fetch(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = %s ORDER BY table_name",
                (database,),
                database,
            )
        ]

    def content(
        self,
        database: str,
        table: str,
        column: str = "",
        value: str = "",
        *,
        exact: bool = True,
    ) -> TableContent:
        """Read the first rows of a table, filtered on one column when asked.

        Args:
            database: Database holding the table.
            table: Table to read.
            column: Column to filter on, empty for no filter.
            value: Value to look for in that column.
            exact: True for an exact match, False for "contains".

        Returns:
            The columns of the table and at most ``ROWS_PER_PAGE`` rows.

        Raises:
            UnknownObjectError: When the database, table or column is unknown.
        """
        self._check(table, self._table_names(database), "table")
        columns = [
            row[0]
            for row in self._fetch(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = %s AND table_name = %s"
                " ORDER BY ordinal_position",
                (database, table),
                database,
            )
        ]
        statement = f"SELECT * FROM `{table}`"  # noqa: S608
        params: tuple[Any, ...] = ()
        if column:
            self._check(column, columns, "column")
            operator = "=" if exact else "LIKE"
            statement += f" WHERE `{column}` {operator} %s"
            params = (value if exact else f"%{value}%",)
        statement += f" LIMIT {ROWS_PER_PAGE}"
        return TableContent(columns, self._fetch(statement, params, database))

    def _count(self, database: str, table: str) -> int:
        """Count the rows of a table already checked to exist."""
        rows = self._fetch(f"SELECT COUNT(*) FROM `{table}`", (), database)  # noqa: S608
        return int(rows[0][0])

    def _fetch(
        self, statement: str, params: tuple[Any, ...], database: str
    ) -> list[tuple[Any, ...]]:
        """Run one read in a given database and return every row."""
        settings = replace(self._settings, name=database)
        with connect(settings) as connection, connection.cursor() as cursor:
            cursor.execute(statement, params)
            return list(cursor.fetchall())

    @staticmethod
    def _check(name: str, known: list[str], kind: str) -> None:
        """Refuse a name MySQL did not list.

        Raises:
            UnknownObjectError: When ``name`` is not in ``known``.
        """
        if name not in known:
            raise UnknownObjectError(f"Unknown {kind}: {name}")
