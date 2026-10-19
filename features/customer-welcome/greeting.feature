@tool-pytest
Feature: Greet a returning customer
  A customer typing their username is greeted by first name, told which visit
  this is, and shown the balance the partner bank holds for them. The greeting
  must never invent a balance nor greet someone the company does not serve.

  Scenario: A known customer is greeted with their balance
    Goal: the happy path through the three neighbours at once: the database
    gives the first name, the partner bank the balance, formatted in euros
    from integer cents.
    When "ada" asks for a greeting
    Then the greeting starts with "Hello Ada!"
    And the greeting shows a balance in EUR

  Scenario: Every visit is counted
    Goal: the visit counter in Redis really grows by one per greeting, so a
    returning customer is recognised.
    When "grace" asks for a greeting
    And "grace" asks for a greeting again
    Then the second visit number is one more than the first

  Scenario: A customer without bank account is greeted without a balance
    Goal: a 404 of the partner bank means no account, not an error: the
    greeting goes on and invents no amount.
    When "zoe" asks for a greeting
    Then the greeting starts with "Hello Zoe!"
    And the greeting shows no balance

  Scenario: A closed customer is refused
    Goal: a customer the company no longer serves gets a 404, before any call
    to the bank or any visit counted.
    When "dennis" asks for a greeting
    Then the storefront answers 404
