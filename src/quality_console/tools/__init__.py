"""The tools of the Quality Console, one router module each."""

from dataclasses import dataclass


class NotFoundError(LookupError):
    """An API, feature, bucket or object the tool does not hold."""


@dataclass(frozen=True)
class Tool:
    """A tool of the console, as the home and tools pages list it."""

    name: str
    path: str
    icon: str
    purpose: str
    section: str = "cockpit"
    kind: str = "static"
    kind_note: str = "Reads data loaded once; nothing changes it."
    doc: str = ""


TOOLS = (
    Tool(
        "Software catalog",
        "/catalog",
        "🗺️",
        "Systems, components, APIs and databases, who owns them, how they are tested.",
        doc="catalog-and-metadata",
    ),
    Tool(
        "Test results",
        "/test-results",
        "🧪",
        "Every CI run uploaded to the results bucket, its details and its trends.",
        kind="live",
        kind_note="Grows with every test run, CI or local, and every Gherkin run.",
        doc="test-results",
    ),
    Tool(
        "Jobs",
        "/test-results/trends",
        "📊",
        "Every job at a glance, last runs first.",
        kind="live",
        kind_note="Grows with every test run.",
        doc="test-results",
    ),
    Tool(
        "Gherkin scenarios",
        "/tools/gherkin",
        "🥒",
        "The acceptance scenarios by product; click one to run it on the stack.",
        kind="mixed",
        kind_note="Some features write for real (orders, accounts), others only read.",
        doc="gherkin",
    ),
    Tool(
        "Scenario design",
        "/tools/designs",
        "🧭",
        "Each journey drawn as a graph, the paths its scenarios walk, the gaps.",
        doc="scenario-design",
    ),
    Tool(
        "Leaving SonarQube (sonar-decom)",
        "/tools/docs?page=sonar-decom",
        "🎯",
        "A quality gate on new code without a server: the analysers each language"
        " has, scoped to the lines a merge request adds.",
        kind_note="A guide, versioned with the code.",
        doc="sonar-decom",
    ),
    Tool(
        "API docs",
        "/tools/apis",
        "📘",
        "The contracts of the catalog: Swagger for HTTP APIs, a page for events.",
        doc="api-contracts",
    ),
    Tool(
        "Recorded examples",
        "/tools/recordings",
        "⏺️",
        "Real partner answers and real events, recorded into contracts/, replayed"
        " by the tests (Microcks for HTTP).",
        doc="recordings",
    ),
    Tool(
        "Release announcements",
        "/tools/announcements",
        "📣",
        "Each system's release announcement as /announce-release drafts it for Slack.",
        doc="release-announcements",
    ),
    Tool(
        "Bucket browser",
        "/tools/bucket",
        "🪣",
        "Folders and files of the Cloud Storage buckets, opened in place.",
        kind="mixed",
        kind_note="test-results grows with each run; the team buckets are loaded once.",
        doc="bucket-browser",
    ),
    Tool(
        "Documentation",
        "/tools/docs",
        "📖",
        "Every page of docs/: the testing guide, one page per tool and product.",
        kind_note="The pages of docs/, versioned with the code.",
    ),
    Tool(
        "Databases",
        "/databases",
        "🗄️",
        "Every database the console's read-only account can see, row by row.",
        kind="mixed",
        kind_note="The storefront writes orders, workflows and accounts; the rest"
        " is loaded once.",
        doc="databases",
    ),
    Tool(
        "Tips",
        "/devx/tips",
        "💡",
        "GitLab, Git, SQL, Docker, QA and front design, in short examples.",
        "devx",
        kind="static",
        kind_note="Written in the page.",
        doc="tips",
    ),
    Tool(
        "retro-footprint",
        "/devx/retro-footprint",
        "🔎",
        "Which fronts, APIs and tables a test touches: 5 real runs, a pause,"
        " 5 more, then its trace in Tempo.",
        "devx",
        kind="live",
        kind_note="Opens the fronts and calls the storefront API for real: places"
        " orders, counts visits.",
        doc="retro-footprint",
    ),
    Tool(
        "Vault",
        "/devx/vault",
        "🔐",
        "Which credentials the services hold now, for how long: short-lived ones"
        " for MySQL and RabbitMQ, a long-lived key for the bank.",
        "devx",
        kind="live",
        kind_note="Leases come and go every few minutes as the Vault Agent renews"
        " and replaces them.",
        doc="vault",
    ),
    Tool(
        "Quality Console MCP",
        "/tools/docs?page=mcp",
        "🔌",
        "Let Claude Code run scenarios, read test runs and measure footprints,"
        " with three examples.",
        "devx",
        kind="live",
        kind_note="Runs scenarios and retro-footprint on the local Docker stack.",
        doc="mcp",
    ),
    Tool(
        "Audio asset generator",
        "/utility/audio-assets",
        "🎵",
        "Placeholder tracks on demand: duration, WAV or FLAC, bit depth, rate,"
        " channels.",
        "utility",
        kind="live",
        kind_note="Writes audio files into audio-assets/ of the repository, never"
        " committed.",
        doc="audio-assets",
    ),
)
"""Every tool, in the order the pages list them; ``section`` says where."""

DOCS_PAGE = "/tools/docs?page={}"
"""The page of the documentation tool showing one page."""


def doc_of(path: str) -> str | None:
    """The documentation page of the tool a console path belongs to.

    Args:
        path: The path of the page shown, without its query.

    Returns:
        The link to its documentation, ``None`` outside a tool.
    """
    owners = [
        tool
        for tool in TOOLS
        if tool.doc and (path == tool.path or path.startswith(f"{tool.path}/"))
    ]
    if not owners:
        return None
    return DOCS_PAGE.format(max(owners, key=lambda tool: len(tool.path)).doc)
