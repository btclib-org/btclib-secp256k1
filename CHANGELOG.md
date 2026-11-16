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

- [v0.8.0.15](./changelog/v0.8.0.15.md)
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

## v0.8.0.16

### x86_64 macOS

- **No x86_64 macOS wheel is built or published, and the dynamic macOS
  wheel is arm64 alone** (issue btclib-org/.github#1982, #1409).

### iOS wheels

- **cibuildwheel builds them for the device and the arm64 simulator**
  (issue #1385, #1387) **and runs the suite in the simulator** (closes
  #1398, #1399); **a release builds and publishes them** (#1402).

### The illegal callback

- **A static extension compiles it as cffi's `extern "Python"`, so its
  modules import on iOS** (closes #1386, #1397).

### Android wheels

- **cibuildwheel's Android platform builds them, with Linux's branch
  protection** (issue #1385, #1392; closes #1390, #1395), but no workflow
  runs it; an x86_64 one is not asked for CET (closes #1394, #1405).

### A refused item of a list is named by its index

- **`keys.pubkey_sum`, `keys.pubkey_sort` and `silentpayments.scan_outputs`
  name it too** (closes #1356, #1375).

### Sourcery

- **Every rule is on but `dont-import-test-modules`, and the code takes
  its forms** (issue btclib-org/.github#2162, #1354); the workflow takes
  .github's concurrency comment (issue btclib-org/.github#2190, #1370).

### The bestpractices.dev answers

- **Brought to v0.8.0.15** (closes #1357, #1367), **answered by each
  criterion's text** (#1380, #1391) **and counting vulnerabilities as
  ruled** (issue btclib-org/.github#2318, #1401, #1406, #1407, #1408).

### `SECURITY.md`

- **What belongs here names a flaw that lets funds be stolen, lost or
  locked** (#1396).

### `REPOSITORY.md`

- **The maintainer holds `main-self-merge`'s bypass** (issue
  btclib-org/.github#2212, #1372), **and the merge is explicit, with
  auto-merge off** (issue btclib-org/.github#2272, #1379).

### `CONTRIBUTING.md`

- **The docs block stops on a failed build** (issue
  btclib-org/.github#2015, #1364), **and the checkout's layout is the
  contributor's** (issue btclib-org/.github#2263, #1377).

### Which pull requests the gates run on

- **Each sentence points to the job's `if:`** (#1378).

### `RELEASING.md`

- **A bestpractices.dev save nobody can make is recorded as owed**
  (issue btclib-org/.github#2205, #1368).

### The shared files of btclib-org/.github

- **The tree takes btclib-org/.github@7369e8a** (#1389) **and
  `AGENTS.md`'s Code Review Rules** (issue btclib-org/.github#2009,
  #1374).

### The documentation's links

- **The RootFileLinks transform is section 14's, verbatim** (issue
  btclib-org/.github#2166, #1365).

### The prettier hook

- **It leaves `.pre-commit-config.yaml` to pre-commit.ci** (issue
  btclib-org/.github#2038, #1376).

### The fuzz workflow

- **Its header names the branch dispatch, not a release** (issue
  btclib-org/.github#1927, #1369).

### Locks, actions and the clusterfuzzlite image

- **soupsieve, behind a furo marker** (closes #1371, #1373), coverage
  (#1360), ruff (#1384), actions (#1359, #1383) and the clusterfuzzlite
  image (#1382).
