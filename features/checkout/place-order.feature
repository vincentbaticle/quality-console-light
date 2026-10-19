@tool-pytest
Feature: Place an order and follow it until paid
  An order is accepted at once, then a worker reserves the stock, issues the
  invoice and captures the payment, one event per step. An order the stock
  cannot serve is cancelled before any payment. Each run of the first
  scenario takes one item of the stock of the running stack.

  Scenario: An order in stock is paid step by step
    Goal: the asynchronous workflow runs to the end: accepted at once with a
    202, then stock, invoice and payment each done by the worker, in order.
    When "ada" orders 1 "BK-0004"
    Then the order is accepted at once
    And the workflow ends "completed" with the order "paid"
    And the step "capture_payment" is "done"

  Scenario: An order out of stock is cancelled before any payment
    Goal: a failing step stops the workflow: the order is cancelled and the
    customer is never charged.
    When "grace" orders 1 "EL-0001"
    Then the order is accepted at once
    And the workflow ends "failed" with the order "cancelled"
    And the step "capture_payment" is "skipped"

  Scenario: A closed customer cannot order
    Goal: the API refuses a closed customer itself, before any event reaches
    the queue.
    When "dennis" orders 1 "BK-0004"
    Then the storefront answers 404
