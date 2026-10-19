@tool-pytest
Feature: Sign in to a customer account
  The simulated Auth0 tenant signs a customer in with their email and
  password. It never says whether an account exists, tells a blocked customer
  to check their email, asks a new customer to set a password first, and
  asks a customer with a second factor for the code of their authenticator app.

  Scenario: A customer signs in with their password
    Goal: the plain sign-in works for a customer with an email and a password.
    When "qa-mailbox+ada@mycompany.test" signs in with "Foundation-2026"
    Then the sign-in is accepted

  Scenario: An unknown email gets the same answer as a wrong password
    Goal: the tenant never tells an attacker which emails have an account.
    When "qa-mailbox+nobody@mycompany.test" signs in with "Foundation-2026"
    Then the tenant answers 401 "Wrong email or password"

  Scenario: A blocked customer is told to check their email
    Goal: a blocked account says why and where to go next, with its own status
    code.
    When "qa-mailbox+grace@mycompany.test" signs in with "Ultrabook-2026"
    Then the tenant answers 423 "Account blocked, check your email"

  Scenario: A customer without a password yet is sent back to their email
    Goal: an account created without a password cannot be entered until its
    link is used.
    When "qa-mailbox+zoe@mycompany.test" signs in with "Anything-2026"
    Then the tenant answers 403 "No password yet, open the link of your email"

  Scenario: A customer with a second factor signs in with the code of their app
    Goal: the password alone is not enough with a second factor: the tenant
    asks for the code, then accepts it.
    When "qa-mailbox+lin@mycompany.test" signs in with "Authenticator-2026"
    Then the tenant answers 403 "mfa_required"
    When the customer sends the code of their authenticator app
    Then the sign-in is accepted
