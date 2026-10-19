@recorded @tool-playwright
Feature: Sign in on the storefront page
  The sign-in a customer clicks, recorded and written in the template of a
  recorded scenario. The account is test data like any other: the scenario
  creates its own, with a password, so it never depends on the account of
  whoever recorded it.

  Scenario: A new customer signs in through the form of the storefront
    Goal: a customer with a password reaches their account from the page,
    the form sending what the tenant expects and showing who is signed in.
    Given "a new customer", a customer account who can sign in with a password
    And a new account of the QA mailbox whose password is "Foundation-2026"
    When the customer signs in on the storefront page with "Foundation-2026"
    Then the page says the customer is signed in
