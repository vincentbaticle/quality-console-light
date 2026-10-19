@recorded @tool-playwright
Feature: Greet yourself on the storefront page
  The journey a customer clicks, recorded and written in the template of a
  recorded scenario: who plays, from which data, what is seen. Playwright
  drives a real Chromium on the storefront of the running stack.

  Scenario: A customer greets themselves and sees their balance
    Goal: what the customer really sees, not only what the API answers: the
    page greets them by first name and shows the balance the bank holds.
    Given "ada", a customer of the company who can see their bank balance
    And the partner bank holds an account for "ada"
    When "ada" greets themselves on the storefront page
    Then the page greets "Ada" with a balance in EUR
