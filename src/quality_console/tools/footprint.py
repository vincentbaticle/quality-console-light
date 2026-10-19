"""retro-footprint: which APIs and tables one test touches, found by running it.

One click starts an experiment on the real stack: five real runs of the
chosen test (API calls, SQL of its own, or both) while colleagues query the
same database, a pause of 20 seconds, five more runs; the database side counted
by ``performance_schema``, the trace of each API call read in Tempo. The page
follows it with a progress bar, the path of the test, one tab per run.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from quality_console.footprint import (
    COLLEAGUE_TABLES,
    LOOPING_TABLES,
    PAUSE_SECONDS,
    RUNS,
    RUNS_PER_BATCH,
    TARGETS,
)
from quality_console.footprint_lab import FootprintLab
from quality_console.table_kinds import LIVE_TABLES
from quality_console.tools import NotFoundError

EXPERIMENT_PATH = "/devx/retro-footprint/experiments/{experiment_id}"
"""Where the page polls the state of an experiment."""


def footprint_router(lab: FootprintLab, templates: Jinja2Templates) -> APIRouter:
    """Build the routes of retro-footprint tool.

    Args:
        lab: Runs the experiments.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/devx/retro-footprint")

    @router.get("", response_class=HTMLResponse)
    def footprint(
        request: Request,
        target: str = "hello",
        experiment: str | None = None,
        busy: bool = False,
    ) -> HTMLResponse:
        """The chosen target, and the experiment followed live once started."""
        if target not in TARGETS:
            raise NotFoundError(f"Unknown target: {target}")
        if experiment is not None and lab.get(experiment) is None:
            raise NotFoundError(f"Unknown or expired experiment: {experiment}")
        return templates.TemplateResponse(
            request,
            "footprint.html",
            {
                "section": "devx",
                "targets": TARGETS,
                "target": target,
                "runs_count": RUNS,
                "runs_per_batch": RUNS_PER_BATCH,
                "pause_seconds": PAUSE_SECONDS,
                "colleagues": COLLEAGUE_TABLES,
                "looping_tables": LOOPING_TABLES,
                "live_tables": sorted(LIVE_TABLES["mycompany"] or ()),
                "experiment": experiment,
                "busy": busy,
            },
        )

    @router.post("/run")
    def run(target: str) -> RedirectResponse:
        """Start an experiment and open the page that follows it.

        While a real experiment runs, another real one is not started: the
        page of the running one opens instead, saying so.
        """
        if target not in TARGETS:
            raise NotFoundError(f"Unknown target: {target}")
        running = lab.running()
        if running is not None and TARGETS[target].demo is None:
            return RedirectResponse(
                f"/devx/retro-footprint?target={running.target.key}"
                f"&experiment={running.id}&busy=true",
                status_code=303,
            )
        started = lab.start(TARGETS[target])
        return RedirectResponse(
            f"/devx/retro-footprint?target={target}&experiment={started.id}",
            status_code=303,
        )

    @router.get("/experiments/{experiment_id}")
    def experiment_state(experiment_id: str) -> JSONResponse:
        """Where the experiment stands, as JSON."""
        found = lab.get(experiment_id)
        if found is None:
            raise NotFoundError(f"Unknown or expired experiment: {experiment_id}")
        return JSONResponse(found.to_json())

    return router
