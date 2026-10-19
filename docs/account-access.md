# Account access: a simulated Auth0 and the QA mailbox

The third product of the storefront signs customers in through a simulated Auth0 tenant, and every email it sends lands in a QA mailbox the tests read. It reproduces, locally, the setup a team needs to test sign-in and password emails for real.

> **TL;DR**
>
> - Identity service (`src/identity/`, port behind `/api/identity/`): sign-up, sign-in, a second factor (TOTP, the codes of an authenticator app), password reset, set password from a link, and a Management API that gives a link without any email.
> - Users in the `identity` database (`db/06-identity.sql`), emails stored in lowercase, passwords hashed (PBKDF2).
> - Mailpit plays the QA mailbox: SMTP for the service, a web UI on <http://localhost:8025> (also in the console's tools), an API for the tests.
> - One mailbox, one plus tag per test account: `qa-mailbox+ada@mycompany.test`.
> - A test signs in through the second factor on its own: it keeps the TOTP secret beside the password and computes the code (`tests/authenticator.py`).
- Tested at three levels: rules (unit), service against MySQL and Mailpit (integration), the whole journey through the storefront (acceptance and browser).

## The rules it simulates

They are the ones a real Auth0 tenant applies and that tests stumble on:

- **Lowercase emails.** A sign-up as `QA-Mailbox+Ada@MyCompany.test` stores `qa-mailbox+ada@mycompany.test`; the email still reaches the mailbox, which ignores the case.
- **No password at sign-up.** A new account gets a "choose your password" email; signing in before that answers `403`.
- **Single-use links, five days.** A link sets one password, the second use answers `400`; after five days it is expired.
- **No account probing.** A wrong password and an unknown email get the same `401`; a reset request always answers `202` with the same text.
- **Blocking.** The tenth wrong password in a row blocks the account (`423`) and sends an unblock email; setting a new password from it unblocks.
- **Second factor (TOTP).** An account with an authenticator app answers its right password with `403` `mfa_required` and an `mfa_token`; the six-digit code of the app, sent with that token to `/api/identity/mfa/verify`, signs it in. A code lives 30 seconds (the step before and after are accepted, for clocks a little apart) and **works once per account**: a second sign-in with the same code is refused, with the same `401` as a wrong code.
- **Management API.** `POST /api/identity/management/tickets/password-change` with the bearer token gives the password link without sending anything, the way a test can get a link without a mailbox.

## Seeded accounts

| Email | Password | State |
| --- | --- | --- |
| `qa-mailbox+ada@mycompany.test` | `Foundation-2026` | signs in |
| `qa-mailbox+grace@mycompany.test` | `Ultrabook-2026` | blocked after ten wrong passwords |
| `qa-mailbox+zoe@mycompany.test` | none | invited, never opened the email |
| `qa-mailbox+lin@mycompany.test` | `Authenticator-2026` | second factor, TOTP secret `OF2WC3DJOR4S2Y3PNZZW63DFFV2G65DQ` |

The console's read-only account sees the users through two views, `identity.accounts` (with `has_totp`) and `identity.password_links`, which carry neither the password hash, the TOTP secret nor the link secret.

## Try it

1. `mise run up`, open <http://localhost:8080#account>.
2. **Sign in** with the example `ada`: signed in. `grace`: blocked, told to check her email. `zoe`: sent back to her email.
3. **Create account**, click the example to get a new plus tag, create it. Open the QA mailbox (<http://localhost:8025>): the welcome email is there. Click its link: the storefront opens on **Set password**. Set one, then sign in.
4. Open the link a second time: refused.
5. **Sign in** as `lin`: the password is right, the page asks for the **Authenticator code**. Add the secret above to an authenticator app on your phone, or click **compute the code** (the page computes it the way a test does), then **Verify**: signed in. Sign in again and verify the same code within its 30 seconds: refused.

## Signing in through a second factor, automatically

A test has no phone: it does what the authenticator app does. RFC 6238 is public, so the code only needs the secret and the clock.

1. **The secret is a credential.** At enrolment (`POST /api/identity/mfa/enroll` with the email and password) the tenant shows the secret once, as `secret` and as the `otpauth://` link a QR code carries. A team keeps it beside the account's password, in its vault or a masked CI variable, never in the code; the seeded `lin` keeps it in `tests/authenticator.py` because it is a demo account.
2. **The code is computed.** `pyotp.TOTP(secret).now()`, the same six digits as the app. Python: `pyotp`; TypeScript: `otpauth` or `otplib`; k6: an HMAC-SHA1 over the step, a dozen lines.
3. **Never a code about to expire.** `fresh_code` waits for the next step when fewer than five seconds remain, or the code can expire between typing it and the tenant checking it.
4. **One retry, with the next code.** A code works once per account: a rerun inside the same 30 seconds, or another job signed in with the same account, may have spent it. `codes(secret)` gives a fresh code, then the next one; the test tries the second only if the first is refused. Refused twice means the secret is wrong (the account was enrolled again), and the test fails.
5. **One account per parallel job.** Two jobs sharing one TOTP account spend each other's codes and wait 30 seconds for the next one, again and again. Each API test enrols its own plus tag (`enrolled` in `test_identity_mailpit.py`); only the browser and Gherkin tests use the seeded `lin`, once per run.
6. **Skip the factor when it is not what you test.** Most tests need a signed-in customer, not the second factor: sign them in through an account without one, or through an API path the tenant does not challenge. Test the factor itself in a handful of tests, like the ones below.

```python
from tests.authenticator import codes

for code in codes(secret):
    response = identity.post("/api/identity/mfa/verify", json={"mfa_token": token, "code": code})
    if response.status_code == 200:
        break
```

## How the tests read the mailbox

`tests/mailbox.py` does what a test against a real mailbox does: wait for the email of one address whose subject contains a text, then extract the link and its ticket. Each test signs up its own plus tag, so tests never share an account and never block a seeded one.

- `tests/unit/test_identity_rules.py`: the rules, pure, the TOTP codes checked against the vectors of RFC 6238 and against `pyotp`.
- `tests/integration/test_identity_mailpit.py`: the service in process against a real MySQL and a real Mailpit (container locally, sidecar in CI); the second factor on accounts each test enrols.
- `features/account-access/`: the same journeys in Gherkin, against the running stack, runnable from the console.
- `tests/integration/test_hello_page_browser.py`: a customer signs in through the page, and `lin` through the page and the code of the authenticator, computed by the test.

The whole journey, and the transitions no scenario walks yet (an account migrated from a legacy login, the Management API link, a weak password), is drawn in the console: **Tools**, **Scenario design**, "Account access" ([Scenario design](scenario-design.md)).
