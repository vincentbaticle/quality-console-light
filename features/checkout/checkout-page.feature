@recorded @tool-playwright
Feature: Order on the storefront page and follow it
  The checkout journey a customer clicks, recorded and written in the template
  of a recorded scenario. Playwright fills the order form of the storefront and
  watches the workflow steps the page draws as the worker runs them.

  Scenario: A customer orders and watches the order until paid
    Goal: the page follows the asynchronous workflow to the end on its own,
    the customer never reloads: three steps turn done, the order reads paid.
    Given "ada", a customer of the company who can order
    And the stock of "BK-0004" holds at least 1 item
    When "ada" orders 1 "BK-0004" on the storefront page
    Then the page shows every step done and the order paid
