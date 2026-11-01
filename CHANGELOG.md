# Changelog

Every change of a release, in full: what changed, why, and what it cost.
[RELEASE_NOTES.md](./RELEASE_NOTES.md) has the release notes, which say
what a user has to act on; this file is the record behind them, and is
where a claim in those notes can be checked.

A release's own pull request writes the release's section, from the
squash subjects since the previous tag, and no other pull request adds
an entry.

This file carries the most recent release. Every release before it has
a file of its own under `changelog/`, holding that release's section
and nothing of any other. Past a size ceiling GitHub's contents API
answers a file with an empty `content` at HTTP 200, which reads as an
empty file rather than as an error, and one file per release keeps each
of them under it.

- [v0.8.0.13](./changelog/v0.8.0.13.md)
- [v0.8.0.12](./changelog/v0.8.0.12.md)
- [v0.8.0.11](./changelog/v0.8.0.11.md)
- [v0.8.0.10](./changelog/v0.8.0.10.md)
- [v0.8.0.9](./changelog/v0.8.0.9.md)
- [v0.8.0.8](./changelog/v0.8.0.8.md)
- [v0.8.0.7](./changelog/v0.8.0.7.md)
- [v0.8.0.6](./changelog/v0.8.0.6.md)
- [v0.8.0.5](./changelog/v0.8.0.5.md)
- [v0.8.0.4](./changelog/v0.8.0.4.md)
- [v0.8.0.3](./changelog/v0.8.0.3.md)
- [v0.8.0.2](./changelog/v0.8.0.2.md)
- [v0.8.0.1](./changelog/v0.8.0.1.md)
- [v0.8.0](./changelog/v0.8.0.md)
- [v0.7.1.3](./changelog/v0.7.1.3.md)
- [v0.7.1.2](./changelog/v0.7.1.2.md)

The changelog starts at v0.7.1.2. The releases before it were documented
at release-notes length in the first place, and are still in
[RELEASE_NOTES.md](./RELEASE_NOTES.md) rather than duplicated here.

## v0.8.0.14

### An ECDSA signature scalar is in [1, n-1]

- **`dsa` and `recovery` refuse a zero r or s in every form, and a DER r
  or s that is negative or not below n** (closes #1272).

### Invalid arguments never reach the illegal callback

- **A test drives every public function with each invalid scalar and
  point**, outside `zkp` (closes #1264) and in it (closes #1283).

### Fuzzing

- **The key and x-only parse targets are seeded at the edges of the
  field** (closes #1268).

### libsecp256k1's own tests

- **They run with the static Linux wheels' compiler and flags** (closes
  #1249, closes #1269).

### Verifying a release

- **The sdist and the bill of materials are verified by repository id,
  which a rename keeps** (closes #1256).

### The changelog

- **Every release but the newest has its own file under `changelog/`**
  (closes #1267).

### The workflows

- **CI moves off the compromised emSign roots** (issue
  btclib-org/.github#1844).

### The calls of btclib-org/.github

- **They are pinned to a tagged commit** (issue btclib-org/.github#1870,
  #1273, #1274).

### The Windows cross build

- **It installs only its compiler** (closes #1252).

### cibuildwheel 4.3.5, pytest and hatchling

- **The Linux image pins move with cibuildwheel** (closes #1261, closes
  #1295).

### Dependencies

- **mypy 2.4.1** (closes #1296); **setuptools and filelock past their
  advisories** (issue btclib-org/.github#1849).

### Locks, hooks and actions

- **pre-commit and ruff** (#1258), the hook revisions (#1286), actions
  and the clusterfuzzlite image (#1277, #1293, #1294).

### Contributing

- **Development is LLM-based, and a contribution must be read** (issue
  btclib-org/.github#1846); **`CONTRIBUTING.md` says how to check a
  `.pyc`** (closes #1287, closes #1288).

### `REVIEWING.md`

- **It takes the shared part** (issue btclib-org/.github#1846,
  btclib-org/.github#1904, btclib-org/.github#1919).

### `SECURITY.md` and the badges

- **`SECURITY.md` links what changed since the security review** (issue
  btclib-org/.github#1795); the version badges are blue (closes #1270).
