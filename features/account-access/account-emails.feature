@tool-pytest
Feature: Account emails reach the QA mailbox
  Every email of the tenant lands in the QA mailbox, each test account being
  a plus tag of one address. A scenario reads the email of its own address,
  opens the link it carries and goes on, as a customer would.

  Background:
    Given a new address of the QA mailbox

  Scenario: A new account receives the email to choose a password
    Goal: creating an account really sends an email, readable by a test like a
    customer reads an inbox.
    When the customer creates an account with it
    Then the mailbox receives "choose your password" for that address
    And the email holds a password link

  Scenario: A customer sets the password from the email, then signs in
    Goal: the whole onboarding, from the email link to the first sign-in.
    When the customer creates an account with it
    And the customer sets "Foundation-2026" from the link of "choose your password"
    Then the customer signs in with "Foundation-2026"

  Scenario: The password link works only once
    Goal: a leaked or replayed link cannot change the password again.
    When the customer creates an account with it
    And the customer sets "Foundation-2026" from the link of "choose your password"
    Then setting "Another-2026" from the same link is refused

  Scenario: A forgotten password gets a reset link
    Goal: a customer who forgot the password can get back in through the
    mailbox.
    When the customer creates an account with it
    And the customer sets "Foundation-2026" from the link of "choose your password"
    And the customer asks to reset the password
    Then the mailbox receives "Reset your" for that address

  Scenario: Ten wrong passwords block the account and send an unblock email
    Goal: brute force is stopped at ten tries, and the real owner is told by
    email.
    When the customer creates an account with it
    And the customer sets "Foundation-2026" from the link of "choose your password"
    And the customer signs in 10 times with "Wrong-password-1"
    Then the mailbox receives "blocked" for that address
    And the customer cannot sign in with "Foundation-2026"
