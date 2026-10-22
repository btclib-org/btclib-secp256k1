# Repository instructions

This repository provides Python bindings to vendored libsecp256k1 and
secp256k1-zkp. Follow [CONTRIBUTING.md](./CONTRIBUTING.md) for project
process, environment setup, and gates; read [REVIEWING.md](./REVIEWING.md)
before reviewing or opening a pull request. Use [README.md](./README.md)
and [ARCHITECTURE.md](./ARCHITECTURE.md) for design and build details,
[SECURITY.md](./SECURITY.md) and [ASSURANCE_CASE.md](./ASSURANCE_CASE.md)
for security, [REPOSITORY.md](./REPOSITORY.md) for workflows and settings,
and [RELEASING.md](./RELEASING.md) for releases.

For concurrent tasks, use separate worktrees and keep the primary checkout
clean and on `main`; see CONTRIBUTING.md for setup and cleanup.

Choose the least capable model that reliably completes the task: a fast
model for straightforward execution, a reasoning-focused model for
multi-step work, and the most capable available model for difficult or
ambiguous problems. Increase capability if progress stalls.
