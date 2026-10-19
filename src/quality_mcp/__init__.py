"""An MCP server over the running stack: scenarios, test results, retro-footprint.

It lets Claude Code (or any MCP client) ask the local Quality Console what a
tester would click: run a Gherkin scenario, read the last test runs, measure
which tables a test touches. Everything stays on the Docker stack of
``mise run up``.
"""
