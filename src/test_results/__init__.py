"""Test results in a bucket: how a run is uploaded, indexed and read back.

The same contract a CI test runner and a results dashboard share: one folder per
run under ``test-runner/reports/``, a ``metadata.json`` describing it, the JUnit
XML, HTML report or k6 summary beside it, and a run index the dashboard reads
instead of crawling the bucket on every page.
"""
