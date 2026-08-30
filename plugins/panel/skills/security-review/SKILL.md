---
name: security-review
description: Independent, change-scoped security review. Use for every code/config/dependency change after implementation, and never let the implementer perform this review.
---

# Independent security review

Review the exact base..head diff in a fresh context. Read the repository's security,
architecture, authentication, authorization, data-handling, and deployment conventions
before judging the change.

## Required lenses

1. Map changed trust boundaries, inputs, identities, secrets, data stores, and outbound calls.
2. Trace untrusted data from source to sensitive sink. Check validation at the boundary,
   authorization at the operation, and safe encoding at the sink.
3. Check authentication/session handling, permission changes, tenant isolation, secret
   exposure, injection, SSRF, path traversal, unsafe deserialization, cryptography,
   dependency/supply-chain changes, logging/privacy, and denial-of-service/resource bounds.
4. Distinguish exploitable change-introduced defects from inherited debt. Only the former
   block this change; track real inherited debt separately.
5. Demand a concrete attack path and affected asset for every finding. Reject speculative
   checklist noise.
6. Confirm security tests exercise failure/abuse paths, not only happy paths.

## Output

For each finding: severity, changed file/line, attacker precondition, exploit path, impact,
and smallest remediation. End with exactly one verdict: `PASS`, `PASS WITH FOLLOW-UPS`, or
`BLOCK`.

This reviewer is independent evidence. It does not replace deterministic scanners or the
repository's CI, and its prose is not itself a delivery attestation.
