"""Bank Partner: a fake core banking API giving the balance of an account.

It plays the external service the hello API depends on but does not own, the way
a payment provider or a core banking system would in a real product. It reads
the ``bank_accounts`` table of the company database, the way many services share
one legacy database. It only runs by hand (``mise run partner:up``), to be
captured; the tests never call it, they call Microcks replaying what it answered.
"""

import os
import secrets

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import pymysql

FIND_PRIMARY_BALANCE = (
    "SELECT c.username, a.balance_cents, a.currency_code"
    " FROM bank_accounts a JOIN customers c ON c.id = a.customer_id"
    " WHERE c.username = %s AND a.is_primary"
)
"""Balance of the primary account of a username, the one the bank exposes."""

NO_ACCOUNT = "No account for this username"
"""Detail of the ``404`` answered when the bank holds no account."""

API_KEY_VARIABLE = "BANK_PARTNER_API_KEY"
"""The key the bank issued its client; unset, the bank asks for none."""

BAD_KEY = "Missing or unknown API key"
"""Detail of the ``401`` answered to a caller without the right key."""


class Balance(BaseModel):
    """What the partner answers for an account."""

    username: str
    balance_cents: int
    currency: str


app = FastAPI(title="Bank Partner")


@app.get("/balance")
def get_balance(username: str, x_api_key: str = Header(default="")) -> Balance:
    """Give the balance of the primary account held for a username.

    A long-lived key, issued once to each client of the bank, is checked on
    every call when the bank has one configured.
    """
    expected = os.environ.get(API_KEY_VARIABLE, "")
    if expected and not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail=BAD_KEY)
    with (
        pymysql.connect(
            host=os.environ["DB_HOST"],
            port=int(os.environ["DB_PORT"]),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
        ) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(FIND_PRIMARY_BALANCE, (username.strip().lower(),))
        row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=NO_ACCOUNT)
    return Balance(username=row[0], balance_cents=row[1], currency=row[2])
