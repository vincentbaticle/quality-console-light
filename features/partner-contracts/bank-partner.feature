@tool-schemathesis
Feature: The Bank Partner keeps the contract we copied
  The bank is not ours. We copied its contract, Microcks replays it to our
  tests and the greeting trusts it: if the bank changes what it answers, every
  test stays green on the replay while the real greeting breaks. Schemathesis
  reads the copy, generates requests from it and checks each answer of the
  real partner against it. Red here means our copy is no longer true.

  Scenario: Any username generated from the contract gets a documented answer
    Goal: usernames of every shape the contract allows (empty, accented,
    very long) never crash the bank, and every answer is one the contract
    describes, the "no account" 404 included.
    Given the contract of the Bank Partner
    When schemathesis sends 50 requests generated from it
    Then no answer is a server error
    And every status code is documented by the contract
    And every body matches the schema of its status code

  Scenario Outline: A customer of the bank gets a balance shaped as the contract says
    Goal: the answers the greeting really uses, a known customer's balance,
    keep the fields and types of the contract, the amount in integer cents.
    Given the contract of the Bank Partner
    When schemathesis asks the balance of "<username>"
    Then the partner answers 200
    And every body matches the schema of its status code

    Examples:
      | username |
      | ada      |
      | grace    |

  Scenario: A caller without the key the bank issued is refused
    Goal: the bank only answers its clients: without the long-lived key it
    issued us (kept in Vault), the answer is a 401, documented by the contract.
    Given the contract of the Bank Partner
    When schemathesis asks the balance of "ada" without the key
    Then the partner answers 401
    And every body matches the schema of its status code
