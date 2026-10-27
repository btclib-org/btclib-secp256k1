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

## v0.8.0.13

### One value where a list is wanted is refused

- **The list parameters of `create_outputs`, `pubkey_tweak_mul_sum` and
  the `pedersen_blind_*` sums raise `TypeError`** for a bare value
  (closes #1228, closes #1229, closes #1231).

### `silentpayments.scan_outputs`

- **The label lookup is C built into the library**, and a label tweak
  outside [1, n-1] raises `ValueError` (closes #1247, closes #1248).

### The compiled wheels

- **They are built with hardening flags, which `check-dist` reads back**
  (closes #1194).

### cibuildwheel 4.3.1

- **The Linux image pins move with it** (closes #1233).

### x86_64 macOS

- **It does not build on a pull request or a push to `main`** (closes
  #1201).

### The secp256k1-zkp pin

- **It moves to `335dc1d2`, and `zkp-pin.yml` trusts the maintainer's
  current key** (#1251).

### The suite

- **It runs under pytest-xdist** (closes #1180).

### Secret-free tests

- **`assert_secret_free` checks the refusals of secret inputs** (closes
  #1177), and takes the shared helper's grouped-secret check (issue
  btclib-org/.github#1697).

### Dependencies

- **aiohttp, virtualenv, GitPython and the CA bundle** (closes #1235; issue
  btclib-org/.github#1824, btclib-org/.github#1835; #1240); hooks, actions
  and the clusterfuzzlite image (#1237, #1245, #1244).

### The organization's shared files

- **`CONTRIBUTING.md` takes the shared half** (issue
  btclib-org/.github#1740); **`SECURITY.md` says a report easy to
  rediscover is fixed as soon as possible** (issue btclib-org/.github#1771).

### Repository guidance

- **`AGENTS.md` replaces `CLAUDE.md`** (issue btclib-org/.github#1808,
  #1239).

### `RELEASING.md` and stale comments

- **The next-version step has a four-part example** (closes #1224); stale
  comments are corrected (closes #1225, closes #1213).

### The hooks and workflows

- **The pyroma hook builds no dependency from source** (issue
  btclib-org/.github#1763); **`claude-review.yml` declines zizmor's
  dangerous-triggers on `issue_comment`** (issue btclib-org/.github#1813).
