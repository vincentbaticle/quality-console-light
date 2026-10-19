"""The entities of the software catalog, as ``catalog/catalog.yaml`` declares them."""

from pathlib import Path

from pydantic import BaseModel, Field
import yaml


class Domain(BaseModel):
    """A business area grouping systems."""

    name: str
    title: str
    description: str


class Capability(BaseModel):
    """What the business does, the ``business_capability`` of a test."""

    name: str
    title: str
    description: str


class Team(BaseModel):
    """A team owning entities, and the Jira project it tracks its work in."""

    name: str
    title: str
    description: str
    jira_project: str


class System(BaseModel):
    """A set of components delivering one business function."""

    name: str
    title: str
    domain: str
    owner: str
    description: str


class Product(BaseModel):
    """What a user sees of a system, the ``product`` of a test."""

    name: str
    title: str
    system: str
    capability: str
    description: str


class Component(BaseModel):
    """A piece of software: a service, a website, a worker, a library."""

    name: str
    title: str
    type: str
    lifecycle: str
    system: str
    owner: str
    source: str
    description: str
    provides: list[str] = Field(default_factory=list)
    consumes: list[str] = Field(default_factory=list)
    publishes: list[str] = Field(default_factory=list)
    subscribes: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class Api(BaseModel):
    """An interface a component provides, with its definition when we hold one."""

    name: str
    title: str
    type: str
    system: str
    owner: str
    description: str
    definition: str = ""


class Resource(BaseModel):
    """Infrastructure a component depends on: a database, a queue, a bucket."""

    name: str
    title: str
    type: str
    system: str
    owner: str
    description: str
    database: str = ""


class Catalog(BaseModel):
    """The whole catalog."""

    about: str
    domains: list[Domain]
    business_capabilities: list[Capability]
    teams: list[Team]
    systems: list[System]
    products: list[Product]
    components: list[Component]
    apis: list[Api]
    resources: list[Resource]


def load_catalog(path: Path) -> Catalog:
    """Read the catalog file.

    Args:
        path: The YAML file, ``catalog/catalog.yaml`` in the repository.

    Returns:
        The validated catalog.
    """
    return Catalog.model_validate(yaml.safe_load(path.read_text()))


def dangling_references(catalog: Catalog) -> list[str]:
    """List every reference to an entity the catalog does not declare.

    Args:
        catalog: The catalog to check.

    Returns:
        One line per broken reference, empty when the catalog holds together.
    """
    known = {
        "domain": {d.name for d in catalog.domains},
        "capability": {c.name for c in catalog.business_capabilities},
        "team": {t.name for t in catalog.teams},
        "system": {s.name for s in catalog.systems},
        "api": {a.name for a in catalog.apis},
        "resource": {r.name for r in catalog.resources},
    }
    references: list[tuple[str, str, str]] = []
    for system in catalog.systems:
        references += [
            (system.name, "domain", system.domain),
            (system.name, "team", system.owner),
        ]
    for product in catalog.products:
        references += [
            (product.name, "system", product.system),
            (product.name, "capability", product.capability),
        ]
    for component in catalog.components:
        references += [
            (component.name, "system", component.system),
            (component.name, "team", component.owner),
        ]
        for api in (
            component.provides
            + component.consumes
            + component.publishes
            + component.subscribes
        ):
            references.append((component.name, "api", api))
        references += [(component.name, "resource", r) for r in component.depends_on]
    owned: list[Api | Resource] = [*catalog.apis, *catalog.resources]
    for entity in owned:
        references += [
            (entity.name, "system", entity.system),
            (entity.name, "team", entity.owner),
        ]
    return [
        f"{owner} names an unknown {kind}: {name}"
        for owner, kind, name in references
        if name not in known[kind]
    ]
