# Tips: short reminders, one tab per topic

**DevX**, **Tips** gathers short reminders, each with an example to copy: GitLab, Git, SQL, Docker, QA and front design. A first set, to be completed together.

> **TL;DR**
>
> - GitLab: `glab` for merge requests, pipelines and CI lint; suggestion blocks in reviews.
> - Git: branch fresh from `origin/main`, conventional commits, `--amend`, `bisect run`.
> - SQL: count first, `LEFT JOIN ... IS NULL`, try a write in a transaction then `ROLLBACK`, `EXPLAIN`.
> - Docker: logs of one service, a shell in a container, rebuild one service, free the disk.
> - QA: search before writing, never weaken a CI gate, local identical to CI, no magic value, no masking fallback, a test writes its own data.
> - Front design: a snow button, a bullet hole in SVG (interactive on a wooden target, and as a static image on a transparent background, `/static/bullet-hole.svg`), an entry card with its orange **Beta** ribbon.

## Adding a tip

One `<li>` in the tab of `src/quality_console/templates/_tips.html`: a title, one sentence, an example in a `<pre>`. Keep it short: a tip that needs a page belongs in its own page of `docs/`.
