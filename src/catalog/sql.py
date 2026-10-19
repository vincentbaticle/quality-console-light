"""Render the catalog as the SQL script that loads it into MySQL.

The script is generated, never written by hand: ``mise run catalog:sql``
rewrites ``db/05-catalog.sql`` from ``catalog/catalog.yaml``, and a unit test
fails when the two drift.
"""

from collections.abc import Iterable, Sequence

from catalog.model import Catalog

DATABASE = "catalog"
"""Database the catalog is loaded into, beside the company one."""

READER_ACCOUNT = "'console_reader'@'%'"
"""Read-only account of the Quality Console, created by ``db/03-console-reader.sql``."""

SCHEMA = f"""DROP DATABASE IF EXISTS {DATABASE};
CREATE DATABASE {DATABASE};

CREATE TABLE {DATABASE}.domains (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL
);

CREATE TABLE {DATABASE}.business_capabilities (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL
);

CREATE TABLE {DATABASE}.teams (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL,
  jira_project VARCHAR(20) NOT NULL
);

CREATE TABLE {DATABASE}.systems (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  domain VARCHAR(60) NOT NULL,
  owner VARCHAR(60) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_systems_domain
    FOREIGN KEY (domain) REFERENCES {DATABASE}.domains (name),
  CONSTRAINT fk_systems_owner
    FOREIGN KEY (owner) REFERENCES {DATABASE}.teams (name)
);

CREATE TABLE {DATABASE}.products (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  system_name VARCHAR(60) NOT NULL,
  capability VARCHAR(60) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_products_system
    FOREIGN KEY (system_name) REFERENCES {DATABASE}.systems (name),
  CONSTRAINT fk_products_capability
    FOREIGN KEY (capability) REFERENCES {DATABASE}.business_capabilities (name)
);

CREATE TABLE {DATABASE}.components (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  type VARCHAR(30) NOT NULL,
  lifecycle VARCHAR(30) NOT NULL,
  system_name VARCHAR(60) NOT NULL,
  owner VARCHAR(60) NOT NULL,
  source VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_components_system
    FOREIGN KEY (system_name) REFERENCES {DATABASE}.systems (name),
  CONSTRAINT fk_components_owner
    FOREIGN KEY (owner) REFERENCES {DATABASE}.teams (name)
);

CREATE TABLE {DATABASE}.apis (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  type VARCHAR(30) NOT NULL,
  system_name VARCHAR(60) NOT NULL,
  owner VARCHAR(60) NOT NULL,
  definition VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_apis_system
    FOREIGN KEY (system_name) REFERENCES {DATABASE}.systems (name),
  CONSTRAINT fk_apis_owner
    FOREIGN KEY (owner) REFERENCES {DATABASE}.teams (name)
);

CREATE TABLE {DATABASE}.resources (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  type VARCHAR(30) NOT NULL,
  system_name VARCHAR(60) NOT NULL,
  owner VARCHAR(60) NOT NULL,
  database_name VARCHAR(60) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_resources_system
    FOREIGN KEY (system_name) REFERENCES {DATABASE}.systems (name),
  CONSTRAINT fk_resources_owner
    FOREIGN KEY (owner) REFERENCES {DATABASE}.teams (name)
);

CREATE TABLE {DATABASE}.component_apis (
  component VARCHAR(60) NOT NULL,
  api VARCHAR(60) NOT NULL,
  relation ENUM('provides', 'consumes', 'publishes', 'subscribes')
    NOT NULL,
  PRIMARY KEY (component, api, relation),
  CONSTRAINT fk_component_apis_component
    FOREIGN KEY (component) REFERENCES {DATABASE}.components (name),
  CONSTRAINT fk_component_apis_api
    FOREIGN KEY (api) REFERENCES {DATABASE}.apis (name)
);

CREATE TABLE {DATABASE}.component_resources (
  component VARCHAR(60) NOT NULL,
  resource VARCHAR(60) NOT NULL,
  PRIMARY KEY (component, resource),
  CONSTRAINT fk_component_resources_component
    FOREIGN KEY (component) REFERENCES {DATABASE}.components (name),
  CONSTRAINT fk_component_resources_resource
    FOREIGN KEY (resource) REFERENCES {DATABASE}.resources (name)
);
"""
"""Tables of the catalog, with the foreign keys that keep it consistent."""

API_RELATIONS = ("provides", "consumes", "publishes", "subscribes")
"""How a component relates to an API, the fields of a component that list them."""


def quote(value: str) -> str:
    """Write a string as a MySQL literal, quotes and backslashes escaped."""
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def _insert(table: str, columns: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """One multi-row ``INSERT`` of string values, empty when there is no row."""
    values = [f"  ({', '.join(quote(v) for v in row)})" for row in rows]
    if not values:
        return ""
    joined = ",\n".join(values)
    return f"INSERT INTO {DATABASE}.{table} ({', '.join(columns)}) VALUES\n{joined};\n"


def render_sql(catalog: Catalog) -> str:
    """Render the script creating the catalog database and filling it.

    Args:
        catalog: The catalog as ``catalog/catalog.yaml`` declares it.

    Returns:
        The SQL script, deterministic for a given catalog.
    """
    statements = [
        _insert(
            "domains",
            ("name", "title", "description"),
            ((d.name, d.title, d.description) for d in catalog.domains),
        ),
        _insert(
            "business_capabilities",
            ("name", "title", "description"),
            ((c.name, c.title, c.description) for c in catalog.business_capabilities),
        ),
        _insert(
            "teams",
            ("name", "title", "description", "jira_project"),
            ((t.name, t.title, t.description, t.jira_project) for t in catalog.teams),
        ),
        _insert(
            "systems",
            ("name", "title", "domain", "owner", "description"),
            (
                (s.name, s.title, s.domain, s.owner, s.description)
                for s in catalog.systems
            ),
        ),
        _insert(
            "products",
            ("name", "title", "system_name", "capability", "description"),
            (
                (p.name, p.title, p.system, p.capability, p.description)
                for p in catalog.products
            ),
        ),
        _insert(
            "components",
            (
                "name",
                "title",
                "type",
                "lifecycle",
                "system_name",
                "owner",
                "source",
                "description",
            ),
            (
                (
                    c.name,
                    c.title,
                    c.type,
                    c.lifecycle,
                    c.system,
                    c.owner,
                    c.source,
                    c.description,
                )
                for c in catalog.components
            ),
        ),
        _insert(
            "apis",
            (
                "name",
                "title",
                "type",
                "system_name",
                "owner",
                "definition",
                "description",
            ),
            (
                (
                    a.name,
                    a.title,
                    a.type,
                    a.system,
                    a.owner,
                    a.definition,
                    a.description,
                )
                for a in catalog.apis
            ),
        ),
        _insert(
            "resources",
            (
                "name",
                "title",
                "type",
                "system_name",
                "owner",
                "database_name",
                "description",
            ),
            (
                (r.name, r.title, r.type, r.system, r.owner, r.database, r.description)
                for r in catalog.resources
            ),
        ),
        _insert(
            "component_apis",
            ("component", "api", "relation"),
            (
                (c.name, api, relation)
                for c in catalog.components
                for relation in API_RELATIONS
                for api in getattr(c, relation)
            ),
        ),
        _insert(
            "component_resources",
            ("component", "resource"),
            ((c.name, r) for c in catalog.components for r in c.depends_on),
        ),
        f"GRANT SELECT, SHOW VIEW ON {DATABASE}.* TO {READER_ACCOUNT};\n",
    ]
    return SCHEMA + "\n" + "\n".join(s for s in statements if s)
