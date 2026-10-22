# TideCloak integration disclosure

**TeamLoveTheSun · RMIT_SGS · C2 · Plan C simulation**

The [official challenge page](https://tide.org/unlocked/#challenge) permits simulated sign-in, roles, and access flows under Plan C. This repository demonstrates the governance workflow locally. It does not connect to a live TideCloak identity provider or Tide distributed-authority network.

| Concern | Implemented here | Intended TideCloak role, not implemented |
| --- | --- | --- |
| Identity | Locally issued Ed25519 JWTs, `tidecloak-demo` issuer | TideCloak-managed identity and application authentication |
| Administrator roles | Fixed demo identities `admin1`, `admin2` | Managed governance permissions and lifecycle |
| Approval | Authenticated proposal plus a different administrator's Ed25519 signature over the approval payload | Policy-governed distributed authorization |
| Key custody | Local PEM files; signing key copied into browser localStorage | External distributed custody; no equivalent guarantees in this demo |
| Evidence | SQLite audit rows and policy version metadata | Integration with a hardened operational audit system |

## Raziel MCP

`.mcp.json` configures `npx -y @tideorg/mcp@1.9.33` as the development-time Raziel MCP server. It is optional for running the app. An MCP-capable development client can load this file and use the tools for Tide guidance. Installing or connecting MCP does **not** turn the local JWT implementation into a live TideCloak integration.

## Security scope

- Self-approval is rejected; the second administrator signs the backend-provided approval payload.
- The requester authenticates with a JWT; they do not create a separate operation signature. This is not threshold multisignature cryptography.
- Policy integrity uses a SHA-256 hash of canonical JSON. Some UI/internal labels say “Merkle root”; the implementation is a single digest, not a Merkle tree.
- Altering the policy file without its corresponding stored digest is detected. A host administrator who can modify both the database and file can bypass that comparison.
- Demo private keys exist on the server, and browser credentials are stored in localStorage. Do not use this deployment for production secrets or expose it publicly as a hardened service.
- Auditing covers implemented application events, not every possible system action, and is not tamper-proof storage.

The submission demonstrates the product interaction that TideCloak is intended to support, not a claim of completed production integration.
