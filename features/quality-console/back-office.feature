@tool-pytest
Feature: The Quality Console shows the platform, read-only
  The back office lists what the company runs and lets anyone browse its data
  without the right to change it. A name nobody listed never reaches a query.

  Scenario: The catalog lists every system of the company
    Goal: the catalog the tests' metadata relies on is the one the console
    shows.
    When I open the console page "/catalog"
    Then the page shows "Storefront"
    And the page shows "Quality platform"

  Scenario: The company database can be browsed
    Goal: anyone can read the company data without a database client.
    When I open the console page "/databases/mycompany"
    Then the page shows "30 tables"

  Scenario: A table nobody listed is refused
    Goal: a name from the URL never reaches a SQL statement unless MySQL
    listed it.
    When I open the console page "/databases/mycompany/tables/salaries"
    Then the console answers 404
