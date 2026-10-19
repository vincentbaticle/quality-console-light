@tool-pytest
Feature: Every team bucket keeps its file contract
  Teams exchange files through buckets: finance exports its invoices every day,
  the catalog publishes its feeds. The same generic checks run on every bucket,
  each bucket bringing its own expectations as a row of examples: where the
  files are, how they are named, which format they hold, how fresh they must be.

  Scenario Outline: The files of a bucket follow its contract
    Goal: the files another team drops are where, named, shaped and as fresh
    as agreed, before our jobs read them.
    Given the files of bucket "<bucket>" under "<prefix>"
    Then there is at least one file
    And every file name matches "<pattern>"
    And no file is empty
    And every file reads as <format>
    And the newest file is less than <hours> hours old

    Examples:
      | bucket          | prefix  | pattern                                  | format | hours |
      | finance-exports | daily/  | ^daily/[0-9]{4}-[0-9]{2}-[0-9]{2}[.]csv$ | csv    | 720   |
      | catalog-feeds   | feeds/  | ^feeds/[a-z]+[.]json$                    | json   | 720   |

  Scenario Outline: The manifest of a bucket lists exactly its files
    Goal: the manifest and the files agree both ways: nothing listed is
    missing, nothing present is unlisted.
    Given the files of bucket "<bucket>" under "<prefix>"
    When the manifest "manifest.json" of the bucket is read
    Then every file it lists exists
    And every file under the prefix is listed

    Examples:
      | bucket          | prefix |
      | finance-exports | daily/ |
      | catalog-feeds   | feeds/ |
