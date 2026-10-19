"""Reading the catalog back from MySQL, the way a tool linked to it does."""

from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Any

from catalog.sql import DATABASE
from company_db import DatabaseSettings, connect


@dataclass(frozen=True)
class TeamRow:
    """A team and its Jira project."""

    name: str
    title: str
    description: str
    jira_project: str


@dataclass(frozen=True)
class ProductRow:
    """A product of a system."""

    name: str
    title: str
    capability: str
    description: str


@dataclass(frozen=True)
class EntityRow:
    """An API or a resource of a system."""

    name: str
    title: str
    type: str
    owner: str
    description: str
    target: str


@dataclass
class ComponentRow:
    """A component, with the APIs and resources it is linked to."""

    name: str
    title: str
    type: str
    lifecycle: str
    owner: str
    source: str
    description: str
    apis: dict[str, list[str]] = field(default_factory=dict)
    resources: list[str] = field(default_factory=list)


@dataclass
class SystemView:
    """A system and everything it is made of."""

    name: str
    title: str
    domain: str
    owner: str
    description: str
    products: list[ProductRow] = field(default_factory=list)
    components: list[ComponentRow] = field(default_factory=list)
    apis: list[EntityRow] = field(default_factory=list)
    resources: list[EntityRow] = field(default_factory=list)


class CatalogReader:
    """Reads the ``catalog`` database with the console's read-only account."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Point at the server; the database name is the catalog's own.

        Args:
            settings: Coordinates and credentials of the console's account.
        """
        self._settings = replace(settings, name=DATABASE)

    def teams(self) -> list[TeamRow]:
        """Every team, by name."""
        return [
            TeamRow(*row)
            for row in self._fetch(
                "SELECT name, title, description, jira_project FROM teams ORDER BY name"
            )
        ]

    def systems(self) -> list[SystemView]:
        """Every system with its products, components, APIs and resources."""
        systems = {
            row[0]: SystemView(*row)
            for row in self._fetch(
                "SELECT s.name, s.title, d.title, s.owner, s.description"
                " FROM systems s JOIN domains d ON d.name = s.domain"
                " ORDER BY d.title, s.title"
            )
        }
        for system, *product in self._fetch(
            "SELECT system_name, name, title, capability, description"
            " FROM products ORDER BY title"
        ):
            systems[system].products.append(ProductRow(*product))
        links: dict[str, dict[str, list[str]]] = defaultdict(dict)
        for component, api, relation in self._fetch(
            "SELECT component, api, relation FROM component_apis ORDER BY api"
        ):
            links[component].setdefault(relation, []).append(api)
        resources: dict[str, list[str]] = defaultdict(list)
        for component, resource in self._fetch(
            "SELECT component, resource FROM component_resources ORDER BY resource"
        ):
            resources[component].append(resource)
        for system, *component in self._fetch(
            "SELECT system_name, name, title, type, lifecycle, owner, source,"
            " description FROM components ORDER BY title"
        ):
            row = ComponentRow(*component)
            row.apis = links[row.name]
            row.resources = resources[row.name]
            systems[system].components.append(row)
        for system, *api in self._fetch(
            "SELECT system_name, name, title, type, owner, description, definition"
            " FROM apis ORDER BY title"
        ):
            systems[system].apis.append(EntityRow(*api))
        for system, *resource in self._fetch(
            "SELECT system_name, name, title, type, owner, description, database_name"
            " FROM resources ORDER BY title"
        ):
            systems[system].resources.append(EntityRow(*resource))
        return list(systems.values())

    def products(self) -> dict[str, ProductRow]:
        """Every product, by name."""
        return {
            row[0]: ProductRow(*row)
            for row in self._fetch(
                "SELECT name, title, capability, description FROM products"
            )
        }

    def apis(self) -> list[EntityRow]:
        """Every API, by title, its definition path as target."""
        return [
            EntityRow(*row)
            for row in self._fetch(
                "SELECT name, title, type, owner, description, definition"
                " FROM apis ORDER BY title"
            )
        ]

    def _fetch(self, statement: str) -> list[tuple[Any, ...]]:
        """Run one read and return every row."""
        with connect(self._settings) as connection, connection.cursor() as cursor:
            cursor.execute(statement)
            return [tuple(row) for row in cursor.fetchall()]
