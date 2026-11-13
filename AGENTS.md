# Repository instructions

This repository provides Python bindings to vendored libsecp256k1 and
secp256k1-zkp. Follow [CONTRIBUTING.md](./CONTRIBUTING.md) for project
process, environment setup, and gates. Use [README.md](./README.md)
and [ARCHITECTURE.md](./ARCHITECTURE.md) for design and build details,
[SECURITY.md](./SECURITY.md) and [ASSURANCE_CASE.md](./ASSURANCE_CASE.md)
for security, [REPOSITORY.md](./REPOSITORY.md) for workflows and settings,
and [RELEASING.md](./RELEASING.md) for releases.

Keep the primary checkout clean and on `main`; use a separate worktree
for each task, following the setup and cleanup commands in
`CONTRIBUTING.md`.

Choose the least capable model that can reliably complete the task: use
a fast model for straightforward execution, a reasoning-focused model
for multi-step work, and the most capable available model for difficult
or ambiguous problems. Increase capability if progress stalls.

## Code Review Rules

Review against [REVIEWING.md](./REVIEWING.md). Its *The verdict* says
which review opens with a verdict line and what every other review
posts.

The heading is the one Codex's GitHub review asks for
([Customize what Codex reviews](https://learn.chatgpt.com/docs/third-party/github#customize-what-codex-reviews)).
