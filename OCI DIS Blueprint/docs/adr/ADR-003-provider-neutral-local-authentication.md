# ADR-003 — Provider-neutral local authentication and read-only API tokens

**Status:** Accepted
**Date:** 2026-08-14

## Context

The App previously accepted caller-supplied actor headers. That was useful for
local development but could not establish a user identity or isolate project
data. The product also needs external, non-interactive API queries today and OCI
IAM Identity Domains later. OCI IAM is an additional sign-in method, not a
replacement for local accounts.

## Decision

Use one provider-neutral `AppUser` as the authorization subject. A user may have
one or more `AuthIdentity` records:

- `local`, backed by an Argon2id password credential;
- `oci_iam`, reserved for a future verified OIDC subject.

Browser access uses an opaque, hashed, revocable database session in an
HttpOnly, SameSite cookie. Projects are visible only through explicit
`ProjectMembership` records. The API overwrites legacy actor headers with the
authenticated principal before existing role checks execute, so clients cannot
select their own actor or role.

External integrations use high-entropy bearer tokens whose secret is shown
once and stored only as a SHA-256 digest. Tokens have explicit read-only domain
scopes, expiry and revocation state, inherit the user's live project
memberships, and may be narrowed to a selected project subset. Scope resolution
is fail-closed and the legacy `api:read` value remains only as a compatibility
umbrella for tokens created before granular scopes existed. A token can never
expand access or perform a mutation. Codex may use such a token; the web App
continues using the browser session.

There is no public self-registration. A one-shot, idempotent installation Job
creates only the first Admin from a mounted secret or generates one-time
credentials into an exclusive mode-`0600` artifact. It fails closed when an
unexpected user already exists and never rotates credentials on retry. Admins
then create users, edit usernames, assign App roles and memberships, and disable
accounts in User Management; the repository-owned CLI is a recovery path. OCI
IAM identity linking will require a
verified issuer and subject; identities must never be auto-linked from an
unverified email claim.

## Consequences

- Local authentication is functional without coupling authorization to one IdP.
- A project-membership change immediately affects sessions and API tokens.
- Revocation, expiry, password lockout, and token lifecycle are persisted and
  auditable.
- The account menu lives in the authenticated initials control at the top-right;
  the desktop sidebar is reserved for workspace navigation.
- First-install secret generation has an explicit operator handoff and must not
  be run independently by every application replica.
- Production must set secure-cookie and trusted-origin configuration.
- OCI IAM integration still requires OIDC/JWT validation, account-linking rules,
  group-to-role mapping, and an operational break-glass policy.

## Validation

- Bad and successful login tests, including committed lockout state.
- Cross-user project access returns `404`.
- Spoofed actor headers do not change ownership.
- A project- and capability-scoped bearer token reads only its selected evidence
  and receives `403` for missing scopes and mutations.
- User Management tests cover Admin-only access, username change, role and
  membership changes, deactivation safety, and cross-project isolation.
- Bootstrap tests cover first creation, audit, idempotent retry, one-time token,
  and fail-closed behavior on an initialized database.
- Browser QA covers login, the top-right user menu, User Management, account
  scopes, token one-time reveal/revocation, and zero console warnings/errors.
