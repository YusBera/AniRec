# AniRec accounts: design (D-021)

Status: phase 1 in progress; early design review applied (13 findings). This file is the design and the phase plan; D-021
in `DECISIONS.md` records the choices, and `ACCOUNT_SCOPE_INVENTORY.md`
records what the code scoped to before accounts existed.

## The problem it solves

Before accounts, one `config/profile_state.json` held one active profile for
the whole installation. Every web request read and wrote that profile's saved
decisions (Watch Later, Not interested, votes, activity). Anyone who could
reach the service could import any public MyAnimeList username and then see
and change the saved decisions of whoever had imported it before. MyAnimeList
itself is never written to; the exposure is AniRec's own saved data.

## The rule

A signed-in **AniRec account**, identified by an ID the server assigns, owns
everything a reader saves. A MyAnimeList username only names a public list to
read *into that account*. Two accounts that import the same username get two
separate imports, each with its own saved decisions. Nothing is ever keyed or
looked up across accounts by a MyAnimeList name or ID.

No route accepts an account ID, a profile ID or a username as authority. The
session cookie names the account; the account names its active import; a
`profile_id` in a request is only checked against that.

## The user's choices (2026-09-24)

- Sign-in: **email and password**; **Google** as an optional quick way to
  register; **passkeys**, added after registering, as extra security.
- **Try first, then register.** A visitor can import a list and use Watch
  Later before registering. A gentle prompt says "Create an account so you
  don't lose your Watch Later", and registering keeps everything.
- **The same accounts everywhere,** in the local app as well as a hosted one.
  This settles D-014's open local-mode question: local mode runs the same
  account schema as a hosted deployment with one or more accounts.

## How "try first" works: guest accounts

A visitor who does something worth keeping (imports a list) gets a **guest
account**: a real server-side account with no email or password, and a
session cookie. Their import and decisions live under it exactly as a
registered reader's do. Registering *upgrades the same account* by adding an
email and password, so nothing has to be copied or merged and nothing can be
lost in between.

Looking at the sample library needs no account at all, and creates none.

If a guest signs in to an existing account instead of registering, the guest's
imports move to that account (ownership changes; files stay where they are),
and become its active import only when it has none. The guest account is then
deleted. Nothing is silently discarded.

A guest session that is never registered expires. Its data is kept, unreachable,
until a later phase prunes it; nothing is deleted in phase 1. **Pruning is a
launch gate for any hosted deployment** (phase 2).

## Per-visitor limits (`AniRec/api/limits.py`)

Limits are kept per visitor, so one visitor exhausting theirs blocks nobody
else. Past a limit the reason is `busy` (or `too-many-attempts`, or HTTP 429
for a route without a reason field).

| Limit | Per visitor | Counts |
| --- | --- | --- |
| New accounts | 10 an hour | a guest created by an import, a registration that is not a guest upgrade |
| Sign-in failures | 20 a minute | wrong passwords, across every email (password spraying) |
| MyAnimeList budget | 60 an hour | imports, `profile-lookup`, live Compare, Library title look-ups: each spends the installation's Client ID |

The per-email lockout below stays in the account service. At most 10,000
visitors are tracked; the least recently seen is forgotten first.

**Who the visitor is.** AniRec binds to loopback, so a hosted deployment sits
behind a reverse proxy and every request would come from the proxy's address.
`ANIREC_TRUSTED_PROXIES` (comma-separated addresses) names the proxies whose
`X-Forwarded-For` and `X-Forwarded-Proto` are believed. The visitor is the
right-most `X-Forwarded-For` address that is not a trusted proxy (anything to
its left was written by the client), and the cookie is `Secure` when the
trusted proxy reports `https`. From any other peer those headers are
ignored.

## Storage

One SQLite database, `config/accounts.sqlite3`, using the standard library
(`sqlite3`, WAL mode, one short transaction per change). The activity store
already uses SQLite the same way.

| Table | Columns | Notes |
| --- | --- | --- |
| `accounts` | `account_id` PK, `kind` (`guest`/`registered`), `email` UNIQUE NULL, `password_hash` NULL, `active_profile_id` NULL, `created_at`, `updated_at` | `account_id` is `acc_` + 128 random bits. Email is stored trimmed and case-folded. |
| `sessions` | `token_hash` PK, `account_id` FK, `created_at`, `expires_at`, `last_seen_at` | Only SHA-256 of the cookie value is stored. |
| `profile_owners` | `profile_id` PK, `account_id` FK, `created_at` | One owner per import directory. |
| `login_failures` | `email` PK, `count`, `last_failed_at` | Throttling; cleared on success. |
| `installation` | `key` PK, `value` | `owner_account_id`: the installation owner (see below). |

Import directories stay `profiles/<profile_id>/` with the existing files. New
imports get `profile_id = "imp_" + 32 hex characters`, never a MAL-derived ID.

## Passwords

- `hashlib.scrypt` from the standard library (no new dependency), N=2^15,
  r=8, p=1, `maxmem` 64 MiB, 16-byte salt, 32-byte key, stored as
  `scrypt$15$8$1$<salt b64>$<hash b64>`. Compared with `hmac.compare_digest`.
  The parameters live in the string, so they can be raised later and old
  hashes rehashed at the next sign-in.
- Length 8 to 256 characters, enforced by the request model before any
  hashing, and NFKC-normalised before hashing. No composition rules (NIST SP
  800-63B).
- At most two hashes run at once (each needs 32 MiB); a request that finds
  both slots busy is refused with `busy` rather than queued.
- Sign-in with an unknown email still runs one scrypt against a fixed dummy
  hash, so response time does not reveal which emails exist.
- Each attempt is counted *before* the password is checked, in one
  `BEGIN IMMEDIATE` transaction, so parallel guesses cannot all see a low
  count; success clears the count. After 5 failures for one email (known or
  not, so the lockout reveals nothing), attempts are refused for 15 minutes
  with `too-many-attempts`. Across all emails, one visitor's failures are
  limited per minute (see "Per-visitor limits").
- Registration with an email that already has an account says so ("An
  account with this email already exists. Sign in instead."). This reveals
  that the email is registered; avoiding that needs email verification, which
  needs an email sender (phase 5). Recorded as a known limit.
- Passwords, hashes and session tokens are never logged or returned. The
  redaction set in `logging_config.py` gains `password` and the session
  cookie name.

## Sessions

- Cookie `anirec_session`: 32 random bytes, URL-safe; `HttpOnly`,
  `SameSite=Lax`, `Path=/`, `Secure` when the request arrived over HTTPS.
  The session and the cookie both expire 30 days after sign-in.
- **Every sign-in, registration and sign-out issues a new token and deletes
  every other session of the account it leaves** (a guest's included), so a
  cookie planted before the reader signed in never reaches their account.
  Cookies ignore ports, so another page on `127.0.0.1` could plant one.
- Registering while signed in as a registered account is refused
  (`already-signed-in`); sign out first.
- Signing out deletes the session row and clears the cookie. Changing the
  password (phase 2) deletes every other session.
- A session whose account no longer exists is treated as no session.

## Cross-site requests

The cookie is sent by the browser automatically, so a page on another origin
could make a signed-in reader's browser act. `SameSite=Lax` does not cover
another port on the same host (`127.0.0.1:5173` and `127.0.0.1:8770` are the
same *site*). One middleware therefore checks every `/api/` request:

- **Host:** the `Host` header's name must be loopback (`127.0.0.1`,
  `localhost`, `::1`) or listed in `ANIREC_ALLOWED_HOSTS`. This stops DNS
  rebinding, where a page on `evil.test` resolves to `127.0.0.1` and becomes
  same-origin with the API.
- **Origin, on `POST`, `PUT`, `PATCH` and `DELETE`:** an `Origin` header must
  be in the configured list (`_default_origins()` plus
  `ANIREC_ALLOWED_ORIGIN`); it is never derived from `Host`. `Origin: null`
  is refused. A request with no `Origin` is accepted only when
  `Sec-Fetch-Site` is absent or `same-origin`/`none`: browsers send `Origin`
  on every cross-origin write, and non-browser clients cannot hold a
  reader's cookie. Vite's proxy (`changeOrigin`) rewrites `Host`, not
  `Origin`, so the dev server's origin reaches the check unchanged.

Reads stay protected by CORS. This middleware also fulfils the `AGENTS.md`
rule that every state-mutating route is origin-checked, which the code did
not previously enforce. The default dev origins trust whatever runs on port
5173 of this machine; that is a known local limit.

## Scope resolution

A FastAPI dependency, `reader_scope`, resolves on every account-scoped route:

1. the session from the cookie (or none);
2. the account (or none);
3. the account's active import, *only if the account owns it* (or none).

Routes then use `scope.profile` where they used
`services.profiles.active_profile()`, and pass it explicitly to anything they
call internally. With no account or no import, a route behaves as the
no-profile case does today (the sample feed, or 409 for writes).

Every call site that read the machine-wide profile changes:

| Call site | Phase 1 |
| --- | --- |
| `system_state`, `discover_feed`, activity, feedback, operations (`app.py`) | `scope.profile`; `activity_event` and feedback pass the scope into `discover_feed` |
| `workspace.py` `active()`, library, resolve, compare | the `profile_id` must equal `scope.profile` |
| `workspace.py` settings `username` | `scope.profile`'s username |
| `ProfileStatisticsService.profile_payload` (Profile page) | takes the profile as an argument |
| `OnboardingService.needs_setup` | per account: no import yet |
| `_build_handler` | always passes `profile_override`, and an `access_token_provider` bound to the scope's profile, for every kind (`more-recommendations` passed none and fell back to the machine-wide profile's token) |
| `container.access_token_provider`, `PipelineOrchestrator.resolve_profile` | never reached from the API: every API call passes an explicit profile |

A test fails if the API reads or writes `profile_state.json`, and a
two-accounts-one-username test covers every route and operation kind.

- **Operations** are authorised through ownership at access time: listing,
  reading, following (the event stream) and cancelling an operation require
  that the session's account owns the operation's `profile_id` *now*. So an
  operation a guest started stays visible after the guest signs in and their
  import moves. Another account's operation is "Unknown operation" (404).
- **`profile_state.json`** is no longer read or written by the API. The
  desktop tool (deprecated) keeps using it for its own single operator.

## The installation owner

`config/settings.json` holds installation-wide settings: the MyAnimeList
Client ID and the ranking preferences (adventurousness, batch size, minimum
score, NSFW). In phase 1 they stay installation-wide, so changing them would
change every account's ranking. Only the **installation owner** may save
them; every other account sees them read-only with a line saying so.

The owner is named by the operator from the machine's console, never through
the web, because registration is open and "the first to register" can be
anyone:

```
python -m AniRec.api.accounts owner reader@example.com
```

The same command gives the owner every import that belongs to no account:
the profiles saved before accounts existed, and any the desktop tool made
since. Those include `tokens/*.json` MyAnimeList sign-ins, which is why only
someone with the machine's console can hand them out. A fresh hosted
deployment has none. Splitting reader preferences out of the installation
settings is phase 2, and **a hosted deployment must not launch before it.**

## API (phase 1)

| Route | Does |
| --- | --- |
| `GET /api/account` | The session's account: `kind`, `email` (registered only), whether an import exists, whether it owns the installation. `null` when signed out. |
| `POST /api/account/register` | Email and password. Upgrades the current guest account, or creates a new registered account. Sets the cookie. |
| `POST /api/account/sign-in` | Email and password. Moves a guest's imports to the account (see above). Sets the cookie. |
| `POST /api/account/sign-out` | Deletes the session. |
| `GET /api/account/imports` | The account's own lists and which one is shown. |
| `POST /api/account/imports/active` | `{profile_id}`: show another of the account's lists; any other is `not-owner`. |
| `POST /api/system/shutdown` | Only the launcher (per-launch token) or the installation owner; anyone else 403. |
| `POST /api/onboarding/mal-profile` | As before, but the import belongs to the session's account; a guest account is created when there is none. The known-username reuse applies only within the same account. |

Failures return a `reason` string, as the onboarding route does, never a
server error.

## Frontend (phase 1)

- The account menu: "Create account" and "Sign in" for a guest or a signed-out
  visitor; the email and "Sign out" for a registered reader.
- One dialog with two modes, Create account and Sign in: email, password
  (with a show/hide control), and the reason in words on failure.
- The gentle prompt: for a guest with something saved, a dismissible line on
  Discover and My Library, "Create an account so you don't lose your Watch
  Later." Dismissing it hides it for the session.
- The first-run pop-up gains "Already have an account? Sign in".
- Settings: read-only, with the reason, for anyone but the owner.
- 375px, keyboard and screen reader, as every surface.

## Known limits

- Any other process on this machine receives cookies for `127.0.0.1`,
  because cookies ignore the port.
- A page on another local port can plant a guest cookie before the reader
  has one, and share that guest account until the reader registers or signs
  in (which then ends every other session).
- Registering reveals whether an email already has an account.
- Limits are per visitor address. Many visitors behind one address (a
  school, a carrier NAT) share one allowance; an attacker with many
  addresses gets many. The MyAnimeList budget has no installation-wide
  ceiling yet.
- The limit tables live in the process: a restart clears them, and several
  worker processes would each keep their own.
- The desktop shell (Tauri) does not exist yet. Its webview origin is
  cross-site to the API, so a `SameSite=Lax` cookie would not reach it; it
  will need the session in a header, decided when that shell is built.

## Later phases

2. **Account management.** Done (2026-09-24): switching between an
   account's lists, per-visitor limits, trusted proxy headers, an owner-only
   shutdown route, the MyAnimeList budget on lookup, Compare and title
   look-ups. Still required before any hosted launch: change password
   (revokes other sessions), delete account (and its imports), export,
   reader preferences split from installation settings, pruning of expired
   guest accounts' data.
3. **Google:** OpenID Connect authorization code flow with PKCE and `state`
   and `nonce`; the ID token is verified against Google's published keys. It
   needs a Google Cloud OAuth client that the owner creates; the code reads
   its ID and secret from the environment, and the button is hidden when
   they are unset. A Google sign-in whose email matches an existing account
   links to it only if Google marks the email verified.
4. **Passkeys:** WebAuthn registration from the account menu once signed in,
   and passkey sign-in. Browsers allow passkeys only for a domain name, never
   an IP address: locally the app must be served at `localhost`, not
   `127.0.0.1`. This likely needs a WebAuthn library (a new dependency, to be
   agreed).
5. **Email:** verification and password reset. It needs an email-sending
   service, which does not exist. Until then a forgotten local password
   cannot be reset from the web.
