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

- [v0.8.0.14](./changelog/v0.8.0.14.md)
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

## v0.8.0.15

### x86_64 macOS

- **`os-macos` runs on the arm64 image alone** (issue
  btclib-org/.github#1982, #1308). The release notes announce that the
  next release publishes no x86_64 macOS wheel.

### Constant time under Valgrind

- **`upstream-tests` runs secp256k1-zkp's own `ctime_tests`, and checks
  the secret-taking secp256k1-zkp calls they do not make** (closes #1302,
  closes #1315).

### `REVIEWING.md`

- **It asks whether a CI step reads an overloaded exit code as one
  outcome** (closes #1333).

### Secrets in refusals

- **The refusal of a label tweak at the order is checked for the
  secret** (closes #1310); the `secret_free` helper is
  btclib-org/.github's (issue btclib-org/.github#1950, #1351).

### Coverage

- **A run that leaves a source directory unmeasured is refused** (closes
  #1345).

### The BIP352 vectors

- **They are refreshed from bitcoin/bips** (closes #1309, closes #1338);
  `check_vendored_vectors.py` takes only an issue titled exactly as
  searched (issue btclib-org/.github#2152).

### The package metadata

- **The homepage is the project's page on btclib.org**, and the links
  to functional-tests and benchmarks follow their renames (closes #1301,
  closes #1303, closes #1307).

### The README

- **The status badges are in a Status section at its end** (issue
  btclib-org/.github#1856, #1336, #1337).

### The README's links

- **The README links its own files absolutely, kept local in the docs**
  (issue btclib-org/.github#1851, #1313, #1335).

### Sourcery

- **Sourcery runs on every pull request, and its findings are cleared**
  (issue btclib-org/.github#2005).

### The bestpractices.dev answers

- **`.bestpractices.json` holds them** (issue btclib-org/.github#2153),
  **corrected** (issue btclib-org/.github#2159).

### The calls of btclib-org/.github

- **They follow its tags** (issue btclib-org/.github#1988, #1314, #1323,
  #1340).

### `CONTRIBUTING.md` and `REVIEWING.md`

- **They take the shared part** (#1306; issue btclib-org/.github#2004,
  btclib-org/.github#2022, btclib-org/.github#2054,
  btclib-org/.github#2088, btclib-org/.github#2145).

### `.coderabbit.yaml`

- **It is the shared copy** (issue btclib-org/.github#1998).

### The citations of the standard

- **The standard is cited by its name** (#1339; issue
  btclib-org/.github#2137).

### `RELEASING.md`

- **The rehearsal's install refreshes the package, `deps-latest` is read
  by the declared ranges, and a release does not wait for its
  dependents** (issue btclib-org/.github#2107).

### Recreating a skipped GitHub release

- **The by-hand recovery stops where the tag's notes are missing or
  empty** (closes btclib-org/.github#2059, #1361).

### Locks, hooks and actions

- **coverage and ruff** (#1322), the hook revisions (#1311, #1343),
  actions (#1324, #1340) and the clusterfuzzlite image (#1320).
