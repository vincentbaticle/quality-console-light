# Release announcements: one message for a whole system

A system of the catalog (the Quality platform, Retail, Identity) is made of several components released on their own, each with its tags and its cocogitto changelog. Nobody reads them all, so nobody knows what changed in the system as a whole. The `/announce-release` skill (team skills, `team-skills/announce-release/`) drafts that one message; the console shows the drafts in Tools, **Release announcements**.

## What the skill does

`/announce-release quality #platform-releases`:

1. resolves the components of the system and their repositories from the catalog, so no list is kept by hand;
2. finds where to start in the `Versions:` line of the previous announcement in the channel (or asks, or takes `--since <date>`);
3. reads the changelog of each dedicated repository, and the commits of the component's folder, bounded by tags, for a component living in a shared repository;
4. drops the noise (bots, CI, chores, refactors nobody sees) and adds the context of the tickets, their epics and the merge requests;
5. drafts 10 to 15 lines following `references/wording-guide.md`: title with the version, one context sentence, 1 to 3 headline features, fixes as symptoms that disappear, actions users must take, then `Tickets:` and `Versions:`;
6. shows the draft and its sources, then saves a **Slack draft**. It never posts: the developer reads it and sends it.

## The example in the console

`announcements/` holds the two announcements of the Quality platform, drafted from the real tags of this repository: 1.1.0 (from v1.0.2) and 1.2.0 (from v1.1.0). The page draws them as Slack would, newest first, and reads their footer back:

- **Where the next run starts**: the `Versions:` line of the newest announcement of each system, here `quality-console v1.2.0`. The next `/announce-release quality` only covers the commits after that tag.
- Each announcement: the title, the blocks, `Tickets:` (`none` here: the commits of this repository carry no ticket key) and `Versions:`.

A file is named `<YYYY-MM-DD>-<system>-<version>.md` and holds the Slack text exactly as drafted (`quality_console/announcements.py` reads it). The page only reads: to add one, run the skill and save its draft there.
