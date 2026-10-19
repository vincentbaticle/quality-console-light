@tool-k6
Feature: The greeting keeps its service level under load
  Ten customers greet themselves for half a minute, each call going through
  the storefront, the API, the database, the partner bank and Redis. k6 plays
  the load, the scenario reads its summary: the same numbers a load test job
  files in Test results.

  Scenario: Ten customers greeted for half a minute keep the service level
    Goal: the greeting stays fast and reliable with several customers at
    once, not only for one tester clicking: under 1% of failed calls, 95% of
    the greetings in less than 500 ms.
    When k6 plays "customer-welcome-baseline.js" against the storefront
    Then less than 1 percent of the calls fail
    And 95 percent of the greetings answer within 500 ms
