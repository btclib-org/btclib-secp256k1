# Changelog

<!-- markdownlint-configure-file
  {
    // MD024/no-duplicate-heading - a group heading repeats under every
    // release with an entry in that group ("Packaging metadata", "The
    // gate", "CI"), which is what keeps the page readable scrolling down
    // it; only a duplicate under the same release heading would be the
    // accident this rule looks for
    "MD024": { "siblings_only": true }
  }
-->

Every change of a release, in full: what changed, why, and what it cost.
[RELEASE_NOTES.md](./RELEASE_NOTES.md) has the release notes, which say
what a user has to act on; this file is the record behind them, and is
where a claim in those notes can be checked.

This file starts at v0.7.1.2. The releases before it were documented at
release-notes length in the first place, and are still in
[RELEASE_NOTES.md](./RELEASE_NOTES.md) rather than duplicated here.

## v0.8.0.5 (work in progress, not released yet)

### `ruff` selects every rule family

- **`[tool.ruff.lint]`'s `select` reads `["ALL"]`, replacing the
  hand-picked list of families this file named individually** (issue
  #387, btclib-org/.github#334). Section 5 of the organization standard
  gives the reason: a hand-picked list is a list that rots, since
  nothing forces a second edit here the day ruff ships a family nobody
  has looked at yet, where `ALL` takes a new family in on the pull
  request that bumps ruff's own pinned revision instead. `ignore` now
  carries every family this tree declines, each entry naming the rule
  and arguing the decline beside it: the formatter conflict
  (`missing-trailing-comma`), families this codebase's own shape
  declines on their own merits -- flake8-errmsg beside the existing
  `raise-vanilla-args` reasoning, flake8-boolean-trap against the
  wrapping layer's own booleans, some mirroring libsecp256k1's C
  signature and the rest named and explained at that same signature,
  flake8-self against the three shapes this tree actually
  reaches a private attribute through, flake8-annotations' `any-type`
  against the cffi boundary and the third-party signatures a few
  functions override, and flake8-type-checking's import-deferral rules,
  which measurably break `sphinx.ext.autodoc`'s resolution of a
  module's other annotations the moment one import moves behind
  `TYPE_CHECKING` -- and the families genuinely zero-finding because the
  construct is absent from this codebase. The sites the family sweep
  still flags beyond those -- `context.py`'s and `silentpayments.py`'s
  cffi callback signatures, `docs/source/conf.py`'s
  `SphinxPostTransform` override, and the pytest parametrize IDs
  `tests/bytes_like_test.py` and `tests/parsed_keys_test.py` keep for
  the test name -- answer with a targeted `# noqa` at each site instead
  of a blanket exemption.

### The documentation build is `furo`, and `-n` is on

- **The `docs` group declares `furo` and `docs/source/conf.py` names it as
  `html_theme`, replacing `sphinx_rtd_theme`, and the build adds `-n` to
  `-W`** (issue #387, btclib-org/.github#329, btclib-org/.github#324).
  Section 2 of the organization standard gives both: `furo` over the
  theme a Read the Docs project starts with by default, and `-n` because
  `-W` alone never sees a cross-reference that resolves to nothing -- a
  renamed class or a moved function in a `:class:` role builds green and
  the link goes nowhere. `docs.yml`, `.readthedocs.yaml`,
  `docs/README.rst` and `CONTRIBUTING.md`'s own copy of the command all
  carry the flag, so what CI checks, what gets published and what a
  contributor runs by hand stay one command.
- **`sphinx.ext.intersphinx` comes first in `extensions`, with a mapping
  for python**, ahead of turning `-n` on: without an inventory, a name
  from outside this tree -- `collections.abc.Sequence`,
  `collections.abc.Mapping`, `collections.abc.Callable`,
  `types.TracebackType`, the stdlib names this package's own annotations
  reach -- resolves to nothing and reads as this tree's own broken link.
  No `nitpick_ignore` entry was needed: every name the public API's
  annotations reach is either a builtin sphinx's own domain answers for,
  or stdlib the mapping now resolves.
- **Every `Returns:` section whose first line carried a colon, in
  `dsa.py`, `keys.py`, `musig.py`, `silentpayments.py` and `xonly.py`,
  loses it.** `-n` turned each into a broken cross-reference of its own
  making rather than a genuine one: Napoleon's Google-style parser reads
  a `Returns:` section's first line as `type: description` wherever a
  colon appears in it, so a colon inside the description's own prose was
  read as a bogus return type, which sphinx's python domain then split
  again on every `,` and ` of ` it contained and tried to resolve each
  fragment as a class of its own -- `xonly.from_prvkey`'s
  `"The 32-byte x coordinate of kG, and the parity of its y"` is the
  case with the most fragments to split into. The wording is unchanged;
  the colon that was never meant as a type separator is an em dash
  instead.

### The uv floor is raised to the Dependabot ceiling

- **`[tool.uv]`'s `required-version` moves from `>=0.12.0` to
  `>=0.12.1`, the uv Dependabot's own uv-ecosystem updater bundles, and
  the comment beside it now points at the organization standard's
  section 1 and section 15 rather than restating their argument**
  (closes #380).

### The package sits under `src/`

- **`btclib_secp256k1/` sits under `src/`, matching section 2 of the
  organization standard** (#382, btclib-org/.github#313). Hatchling
  finds it there by its own second file-selection heuristic,
  `src/<name>/__init__.py`, needing no `[tool.hatch.build.targets.wheel]`
  table to say so. The vendored `secp256k1/` submodule stays at the
  repository root: it is not this package. `scripts/cffi_build.py`'s
  `clean_patterns` entry for the copied shared library moves with the
  package to `src/btclib_secp256k1/libsecp256k1.*`, and the line
  reaching the submodule, `Path(__file__).parent.parent / "secp256k1"`,
  does not. A wheel built from the tree is unaffected: `btclib_secp256k1/`
  and the compiled extension still sit at the wheel's own root, only the
  source tree moved.

### Every fixable hook fixes, and `CHANGELOG.md`'s derogation is gone

- **`codespell` gains `--write-changes`, and `.pre-commit-config.yaml`
  now states that `typos` already fixes in place through its own
  upstream default, so an `args:` added there later cannot silently
  drop it** (closes #379). `markdownlint-cli2` already fixes;
  `yamllint` is noted where it has no fix mode to turn on.
- **With every markdown-fixing hook running in place, the two-comment
  directive at `CHANGELOG.md`'s head has nothing left to guard against:
  a rebase-dropped blank line is repaired on the next hook run instead
  of failing a gate with nothing behind it to fix.** The directive is
  gone, and MD022 and MD032 apply to this file again.

### Every module declares `__all__`

- **The public surface is a declared list, not everything a module
  happens not to underscore** (#357, btclib-org/.github#79). A module
  with no `__all__` answers `import *` with every name it does not
  underscore, the ones it imported included: `ffi` and `lib` came out of
  `btclib_secp256k1.dsa` alongside its own entry points. Every module
  under `btclib_secp256k1/` now declares one, `_scalar`, `_secret` and
  `_cdata` excepted by their own leading underscore, and `context.ctx`
  kept public beside `check` for the caller reaching `lib` directly that
  SECURITY.md and the README already document. `tests/all_test.py` is
  the census section 7 asks for: it walks the package rather than
  listing it, so a new public name fails until it is exported or
  recorded in `UNEXPORTED`, and a module re-exporting a name it only
  imported is caught the same way. `tests/README.md`'s convention table
  moves the public surface out of "Not tested here" and into the table;
  input validation stays absent, section 7's own escape for it now
  missing only the connection nothing here makes.

### Documentation

- **`REVIEWING.md`'s shared half is the organization standard's own
  text** (closes #407). Everything above *This repository in particular*
  matches `btclib-org/.github`'s copy byte for byte, and *The verdict* is
  the section that differed. It names three verdict lines -- `ACK <sha>`,
  `CHANGES REQUESTED <sha>` and `NACK <sha>` -- and says the ack of
  record is posted as a review of type COMMENT, `gh pr review
  --comment`, never as a forge approval or a forge request for changes,
  which is what this repository's own `claude-review.yml` prompt already
  instructs. It also separates a `NACK` from a review that ends without
  a verdict: both leave the pull request unacked, and only the first
  concludes anything.

- **`SECURITY.md` stops claiming what it cannot check** (#356,
  btclib-org/.github#109). "as for every btclib project" was an
  enumeration this file has no way to verify, and it was already
  false when measured: `btclib-benchmarks` gave a different address,
  `devs@btclib.org`, until it dropped `SECURITY.md` entirely. The
  reporting address is unchanged -- *security at btclib dot org* -- and
  the sentence now points at where it actually lives, section 2 of
  the organization standard, rather than restating a claim about
  repositories this file does not read.

- **`RELEASING.md` and `REPOSITORY.md` stop naming `btclib` to justify
  this package's own choices** (btclib-org/.github#81). The first pass
  held both files out of scope, reading a maintainer's runbook as prose
  the rule does not reach; `bitcoin-core-rpc`'s later half
  (bitcoin-core-rpc#245) read the same rule as reaching a new maintainer
  who may not have `btclib` at all, and that reading is what lands here
  too. `RELEASING.md`'s CycloneDX paragraph — the case this round turns
  on — now states its own reasoning instead of sending that reader to
  `btclib`'s `RELEASING.md` for it: a generator that read only
  `Requires-Dist` could not describe a vendored submodule's pin, that
  limit is fixed upstream (btclib-org/btclib#1280), and what remains is
  adoption here, tracked at `btclib-org/.github#24`. Every other
  comparison against `btclib`'s own settings or history, in both files,
  now states the same fact without the name.

- **`CONTRIBUTING.md`'s repository-specific section stops comparing
  against `btclib` by name** (#365, btclib-org/.github#81). The same
  census finds four more instances below `## This repository in
  particular`, each the same shape: a fact about this repository's own
  build or gates, explained by contrast with `btclib`'s rather than
  stated on its own -- the documentation build needing the submodule
  checked out, the organization's shared concurrent-jobs ceiling, and
  the benchmarks' own dependency list. Each now states the fact without
  the name, or names it as "the library downstream of these bindings"
  where the relationship itself is what the sentence is about. Left
  unchanged, and read against the standard's own "positioning in the
  family" carve-out rather than assumed a violation: the routing
  sentence telling a contributor that a wallet, a transaction or a
  signing session belongs in `btclib`'s own tracker, which is what
  these bindings are for -- the same shape section 9 of the standard
  names allowed, where a package stands on the organization that
  publishes it and where it sits in the family.

- **`CONTRIBUTING.md`'s shared half is the organization's copy again**
  (#375). Section 14's own `verbatim_test.py` compares everything above
  `## This repository in particular` against `btclib-org/.github`'s
  copy, and this tree's had drifted from it: a `### The landing queue`
  subsection the shared half has gained since, and a rewritten paragraph
  on what a commit message becomes once it lands on `main`, were both
  missing here. Replaced with the organization's copy of the same text
  byte for byte -- the same hash the issue's own measurement checks
  for -- leaving everything from that heading down untouched.

- **`.gitattributes` is the organization's file byte for byte**
  (btclib-org/.github#192). Section 14 of the standard makes the two
  `merge=union` entries and the reasoning beside them the standard's
  text rather than each tree's, and the paragraph missing from this copy
  is the one saying both lines belong in every repository's copy, a tree
  carrying no `RELEASE_NOTES.md` included: an attribute on a path the
  tree does not hold matches nothing. This tree has no attribute of its
  own, so it carries no `## This repository in particular` heading and
  the whole file is the shared half. `shasum -a256` agrees with the raw
  file the API serves for `btclib-org/.github`, and
  `git check-attr merge` still answers `union` for `CHANGELOG.md` and
  `RELEASE_NOTES.md`.

- **`REVIEWING.md`'s *The gates are the evidence* excepts no gate from
  the run a reviewer may rely on, the test suite included.** The
  organization's copy, shared half byte for byte (section 14): a run is
  whole whoever makes it — never a module on its own, a `-k`, a `--lf`,
  a deselect or a marker in its place — and one that was narrowed or cut
  short is reported as no run (btclib-org/.github#168).

- **`REVIEWING.md` is the organization's copy.** A review reads the prose
  that stays in the tree, treats a commit message or a pull request's
  body as a finding only where it decides something, and asks a stated
  count, a measurement nothing re-derives, or the history of the code
  told in a comment to go — section 14 of the standard, the shared half
  byte for byte.

- **`REVIEWING.md`'s *The verdict* posts the summary to the forge as a
  review and says which verdict is the ack of record.** The organization's
  copy, shared half byte for byte (section 14): `APPROVE` carries the
  `ACK <sha>` summary and `REQUEST_CHANGES` the `CHANGES REQUESTED <sha>`
  one, section 11 says whose verdict that is, and every other summary is
  a comment rather than an ack, a forge approval by the pull request's own
  author included (btclib-org/.github#353).

- **`CODE_OF_CONDUCT.md` is gone, and the inherited copy is what GitHub
  shows** (btclib-org/.github#123). Section 14 of the organization
  standard no longer lists it: the file was a pointer to the PSF code of
  conduct, and the copy in `btclib-org/.github` is what a public
  repository of the organization carrying none displays. `test.yml`'s
  `prose` pattern stops naming it, a name nothing matches being a rule
  that has quietly stopped applying; the entry under *CI* below that
  added the name to that pattern describes the tree between that landing
  and this one. Nothing else linked it: on the tree before this,
  `git grep -n -i 'code_of_conduct\|code of conduct'` answered with
  that pattern, the entry just named, and two lines of the file itself.

- **`.gitattributes` is the organization's file** (btclib-org/.github#102).
  Section 14 of the standard names it as the same file in every
  repository, and `tests/verbatim_test.py` there compares the copies it
  finds; this one was its own prose, two comments in its own words with
  `RELEASE_NOTES.md` first and `CHANGELOG.md` under a second paragraph
  about what nothing reads. It is now byte for byte the copy in
  `btclib-org/.github`: one comment, both lines under it, and section 9
  of the standard named as where the rule is recorded. This tree has no
  attribute of its own to keep under `## This repository in particular`,
  so it carries no such heading. `git check-attr merge` still answers
  `union` for both files.

- **`RELEASING.md` says what to do rather than what happened**. Two
  paragraphs were an account of the 0.7.1 rehearsal that failed before it
  worked and of the setup the rename made necessary a second time. What a
  reader needs from them is neither: that a trusted publisher can only be
  registered by an owner of the project, so a name an unrelated project
  holds on an index cannot be registered from here and the run stops at
  the token exchange with `invalid-publisher` having built the whole
  matrix; and that a registration is per project name, so a name this has
  not been done for needs it done on both indexes before anything is
  published under it. Both now say that, in the present tense, and
  `gh run rerun <run id> --failed` is named where the recovery is
  described, the artifacts being already built.

- **Read the Docs serves `btclib-secp256k1`, and `.readthedocs.yaml`
  says so** (issue #302). The project was published under the old slug
  and `README.md`'s badge, the link behind it and `pyproject.toml`'s
  `documentation` url all named the new one, so the URL this package
  advertises everywhere -- including in the metadata of every version
  already on PyPI, and in the bodies of the v0.8.0 and v0.7.1.1 GitHub
  releases, neither of which a pull request can edit -- answered 404.
  The slug has been renamed on the dashboard and all of them resolve.

  What the file's comment still records is the half that has not moved:
  no version named for a release has been built, so `/en/v<version>/` is
  a 404 where both siblings serve it. `stable` and `latest` both answer
  200, and the twenty-one tags moved with the project, so what is
  missing is the automation rule and not a build --
  btclib-org/.github#26 carries it, with the command that re-derives all
  of this.

- **The benchmarks link in `README.md` names the file that exists**
  (btclib-org/.github#22). The Comparison section pointed at
  `btclib-benchmarks/blob/main/results/libsecp256k1-wrappers.md`, which
  `#152` wrote on 2026-08-14 and `btclib-org/btclib-benchmarks#11` renamed
  on 2026-08-15, one day later, when that repository named every result
  file for what it answers. The table is `results/01-libsecp256k1.md`,
  titled "The libsecp256k1 wrappers", which is what the link text already
  said.

  `links.yml` is what found it, on its Monday run of 2026-08-17, and that
  run has been red ever since with nobody acting on the notification. It
  is the sentinel working: a link rots because somebody edits a different
  repository, which is the one case reading a diff here cannot catch.

- **`docs/source/conf.py`'s toctree comment stops enumerating the pages
  a glob already derives** (issue #313). It said "Four pages of the
  toctree are this repository's README, CONTRIBUTING, SECURITY and
  RELEASE_NOTES", and `docs/source/index.rst` lists six of them: the
  comment missed `REVIEWING` and `CHANGELOG`, both of which have a
  `*_link.md` shim and are globbed into `INCLUDED` twenty lines below it
  exactly as the four it named are. Its "no CHANGELOG at all" clause was
  flatly false by the time it was read.

  The count and the list were the same defect twice. `ls
  docs/source/*_link.md` is the set, and `INCLUDED`'s own
  `glob("*_link.md")` is what the code reads, so the comment now points
  at the derivation instead of restating its result -- which is what
  keeps it right the next time a shim is added or dropped. The
  comparison against `btclib`'s root files went with it: which files a
  sibling repository shims is that repository's business, and a
  paragraph here that tracks it is a paragraph that goes stale when
  something happens somewhere else.
- **Three hyphenated tokens stop being split across a line break**
  (issue #318). Markdown joins two source lines with a space, so a word
  wrapped at its own hyphen renders with the hyphen and then a space
  inside it: `README.md`'s "read-any-number-of-times" came out as
  "read-any- number-of-times", and `CHANGELOG.md`'s "33-" and
  `RELEASING.md`'s "fast-forwarding" the same way. The source looks
  right, which is why reading a diff does not find them -- the one that
  opened the issue was found by scanning rendered `<code>` spans in
  built HTML across the organization's documentation.

  Nothing gates it. markdownlint has no rule for it, and `sphinx-build
  -W` is not asked whether a token means anything. `git grep -n -E
  '[A-Za-z0-9]-$' -- '*.md'` is what finds them, and it now answers
  nothing here; it answers nothing in the sibling repositories either,
  so this was the tree that had them. Whether that command becomes a
  hook is btclib-org/.github#71, since a rule about markdown wrapping
  belongs to every repository or to none.

- **`CONTRIBUTING.md` sends a contributor to the organization standard**
  (btclib-org/.github#52). `README.md` in `btclib-org/.github` states
  the toolchain, the lint gate, the workflow set and the branch rules
  once for this repository and its siblings, and it claims to be linked
  from each repository's `CONTRIBUTING.md`. Nothing here named it: the
  mentions of that repository in this tree were every one of them an
  issue-number citation — in a workflow comment, a hook comment,
  `CHANGELOG.md` and `RELEASING.md` — and not one of them a pointer
  to the standard. `git grep -n 'btclib-org/\.github'` is what re-derives
  them, a list here going stale the next time one is cited. So a
  contributor
  following `CONTRIBUTING.md` to `REPOSITORY.md` to `CLAUDE.md` was
  never told a document above them existed — and a rule stated only
  there was one they could not find. The pointer is in the opening
  rather than in `REPOSITORY.md` or `CLAUDE.md`: the audit and the
  normalizing checklist that standard carries are performed *holding*
  it, so the reader who arrives without it is the contributor, and this
  is the file that reader is already in — and the one of the three the
  documentation build renders, `docs/source/contributing_link.md`
  including it. Hence the absolute github.com url, the shape a sibling
  repository is linked with elsewhere here: a relative destination
  resolves against the rendered site.

- **`CONTRIBUTING.md` and `CLAUDE.md` catch up with `test.yml`'s
  `--frozen`** (btclib-org/.github#8). The organization standard's
  `--locked`, never `--frozen` rule is stated flatly, and the wheel-build
  steps of `test.yml` (`build-cibuildwheel`, `build-dynamic`,
  `build-sdist`, the Windows cross-build) have used `--frozen` since
  `test.yml` was first written, with a comment beside the first of them:
  they run after the `dev-version` action has rewritten `pyproject.toml`
  on the rehearsal path, and `--locked` refuses exactly that
  disagreement, `uv sync --locked` measured to fail there with "The
  lockfile at `uv.lock` needs to be updated" where `--frozen` measured to
  pass. The rule was not a copy nobody examined; two other files were
  stale. `CONTRIBUTING.md`'s `Build wheels on <os>` reproduction command
  had dropped the flag, so it no longer matched the step it claims to
  reproduce, and `CLAUDE.md`'s "uv commands pass `--locked`, never
  `--frozen`" line stated the rule with no exception, which is wrong
  about a job it also documents elsewhere. Every other repository of the
  organization was checked the same way (`grep -rn -- '--frozen'
  .github/workflows/` in `btclib`, `bitcoin-core-rpc` and
  `btclib-benchmarks`): each hit there is inside a comment explaining why
  the flag is *not* used, and no `run:` step passes it.

- **The Slack badge is gone from `README.md` and `CONTRIBUTING.md`.**
  The badge block's own comment states the criterion — a badge reports
  state, which is why "we use ruff" is not one — and this badge reported
  a route instead, to a channel of the course workspace btclib was first
  taught in. What answers a question here is the issue tracker and a
  pull request, which leave the answer where the next reader of these
  files can find it, and a chat message does not. The badge stood alone
  in both files, with no prose sending a contributor there, so each
  block loses a line and nothing else changes. Both siblings do the
  same, so that the badge goes everywhere it is rather than in one
  place, and the organization profile no longer names Slack either.

- **`RELEASING.md` checks the breaking-changes list against the API
  itself, with griffe** (#292, closing #291). Both sibling repositories
  already had this step; `v0.8.0.2` to `v0.8.0.3` is what makes it not
  hypothetical — a module removed, eight trailing-underscore names gone,
  four signatures changed and three functions' parameters renamed, all
  correctly recorded by hand in that release's own `RELEASE_NOTES.md`,
  but nothing would have caught it if it hadn't been. The command both
  siblings use fails here: `uv run` syncs the project first, which
  builds the C extension, and that build does not exist to check yet in
  a fresh clone. The new step uses `--isolated --no-project -s .`
  instead, griffe reading only Python source.
- **Prose stops stating counts nothing checks** (#293, #294): a
  cross-reference by "step N" into RELEASING.md's numbered list, which
  the list itself proved fragile by moving once this cycle (#292);
  GitHub's own platform limits (concurrent jobs, the plan table,
  artifact retention), dated rather than removed, since they are
  someone else's settings and can move without notice; and counts of
  this repository's own growing things — a `.dev<run><attempt>` worked
  example, a redundant entry-point count, and two `detect-secrets`
  baseline sizes, one of which had already drifted:
  `.secrets.baseline`'s documented 53 findings against the actual 54.
- **`RELEASING.md` gets a "Rebuild a release from its tag" section,
  scoped to the sdist** (#304, closing #298). Both siblings needed
  `SOURCE_DATE_EPOCH` and a `.github/scripts/normalize_sdist.py` step
  because `setuptools.build_meta`'s sdist writer stamps the checkout's
  own clock, sub-second, when the variable is unset. This repository's
  backend is `hatchling.build`, whose sdist and wheel writers default
  to a fixed placeholder timestamp instead of the clock, which two
  independent rebuilds of already-published tags (`v0.8.0` and
  `v0.8.0.4`) reproduced byte for byte with neither a `SOURCE_DATE_EPOCH`
  step nor a normalizing one. The section says so, rather than leaving
  a reader who knows the siblings' files to go looking for a script
  that was never needed and conclude it was forgotten. It also says why
  the wheels stay out of scope: they are `cibuildwheel` output over the
  vendored C library, and pinning a timestamp would not make two builds
  of one the same bytes — the compiler, its version and the toolchain
  the runner happened to have are inputs nothing here pins.

- **`RELEASING.md` records why no CycloneDX bill of materials is
  attached to this repository's releases**, unlike btclib's. This
  package's `Requires-Dist` names only `cffi`; the dependency it
  actually wraps, the vendored libsecp256k1 C library at its
  pinned commit, does not appear there, for either wheel this
  package ships — statically linked into the extension in a
  static build, a shared object beside it in a dynamic (ABI-mode)
  one. btclib's `RELEASING.md` carries the reasoning; see its
  "Read the bill of materials attached to the release" step and
  btclib-org/btclib#1159 for the evaluation.

- **`RELEASING.md` says what would reopen that decision**
  (btclib-org/.github#24). Stating a limitation is not the same as
  stating that it can lift: what keeps the vendored library out of the
  document is what the generator reads, so a generator that learned to
  describe a submodule pin as a component would make the question worth
  asking again, and the section gave a reader no reason to expect the
  answer ever to change. It now carries that trigger and names the
  issue holding it, which is open — btclib-org/btclib#1159, cited
  beside it for the evaluation, is not, and watches nothing.
- **`.github/mutation/bindings.toml`'s comment on why the mutation config
  lives under `.github/` no longer cites a tool this repository does not
  run** (#314). The reasoning had been carried across from btclib, where
  check-manifest gates a pull request and treats `.github/` as a directory
  already safe to leave out of the sdist; nothing here runs check-manifest,
  so a reader checking the claim found a tool never wired into this tree
  and could not tell whether the placement was still right or the tool had
  gone missing. The comment now names what answers the same question here
  instead: `suite-sdist` in `test.yml`, which installs from the built sdist
  and compiles the vendored library across its matrix, and would fail were
  anything a build needs missing from it. The placement itself is unchanged
  — cosmic-ray takes its configuration's path as an argument, so nothing
  forces a name or a place — only the reason given for it.

- **`REVIEWING.md` asks a review to run what a diff decides with.** A
  regex, a grep, a pattern in a hook, a script or a query decides an
  outcome by matching or computing, and a review of one executes it
  rather than reading it — against the shapes the diff's own prose
  claims to cover, and against the shapes the tree actually holds. A
  claim the prose makes about the tree takes the same treatment, "every
  link here is already `./`-prefixed" being one `git grep`'s worth of
  evidence and the reason a change is offered as safe.

  What earned the rule is this repository's own review of the
  `local-link-prefix` pygrep hook, pull request #317: it traced the
  pattern by hand across inline links, reference definitions, anchors,
  schemes and badge links, and acked. The leading clause `\[[^]]*\]\(`
  cannot cross the `]` that closes an image's alt text, so on the badge
  shape `[![alt](./src)](./href)` it examines the image source and never
  the destination the link itself carries, which is left free to lose
  its `./` unreported — and the badge shape is what the block at the top
  of `README.md` and of `CONTRIBUTING.md` is built from. The sibling
  review that ran the clause against a real line found it
  (btclib-org/bitcoin-core-rpc#192); tracing it did not.

  The section says what it is not, `claude-review.yml`'s prompt telling
  a review here not to re-run the gates: those run what the rest of the
  tree already exercises, where a pattern a diff adds has been run
  against nothing until a review runs it. The prompt is unchanged — it
  names `REVIEWING.md` rather than restating it, so the standard moves
  without the workflow being edited.

- **`REVIEWING.md` says when a gate already run is relied on rather than
  repeated, and `CLAUDE.md` says which checks a pull request is gated
  on.** The condition is the sha and the record: where the gates have
  been run on this very commit — the required checks running beside a
  review, or an author handing over a branch they gated and stated the
  result of — the review relies on that run and names whose it is, and
  where there is no such run it runs them itself. A run on another tree
  is not a run on this one, so a rebase voids it, the branch having been
  gated before the tree moved under the gate.

  What earned it is `claude-review.yml`'s prompt, whose reason for not
  running the gates was that a second run of them would cost a runner
  slot. That is an argument about price, and a reviewer reading it
  generalizes it into "running costs, so do not run" — which is the
  disposition that acked the `local-link-prefix` pattern of the entry
  above without running it. The prompt now carries the instruction and
  points at `CLAUDE.md` for why the reliance is sound, which is also
  what keeps its hunk small: a pull request editing that file cannot be
  reviewed at all, the action refusing to run under a workflow differing
  from the default branch's copy (btclib-org/.github#58).

  It leaves the entry above where it was. The gates exercise what the
  tree already held, so what a diff decides with has been run by nothing
  whether they ran or not, and a review runs that either way.
- **`REPOSITORY.md` reads the whole workflow-permissions object back and
  says the value is untested against the organization default**
  (btclib-org/.github#23). The read-back was there, but as
  `--jq '.default_workflow_permissions'`, which drops
  `can_approve_pull_request_reviews` — the field that decides whether a
  run can approve a pull request, and so whether the one rule saying
  somebody other than the author approves has a way around it. It reads
  back `false`. What the section did not say at all is which side of the
  organization default this repository is on: it already held `read`
  when that default moved there on 21 August 2026, so it was never
  observed following the move, and an override set before that day is
  indistinguishable from an inheritance. That is recorded as untested
  rather than known good, with the `PUT` that moves this repository by
  hand the next time the organization default moves, and a link to the
  organization standard for why no endpoint can answer it. Documentation
  only: nothing was set, and the read-back is the same object before and
  after.
- **`.readthedocs.yaml` records that no release of this package has ever
  been built under a name of its own** (btclib-org/.github#26). Read the
  docs activates a new tag from an automation rule of its own; this
  project has none, so every build of this file has been `latest`, which
  follows `main`, or `stable`, which read the docs moves to the highest
  release tag and rebuilds by itself. No version named for a release has
  ever been built, v0.8.0.4 included, and `/en/v<version>/` is therefore
  a 404 here where both siblings serve it — that URL being what a reader
  is given wherever a version is named. What is *not* broken is the
  build: `stable` runs this file against a release tag's tree and
  succeeds, so what is missing is the URL and not an untested build. The
  comment says exactly that, a reader of the file otherwise having
  nowhere in this tree to learn it — `REPOSITORY.md` has no Read the
  Docs section, where btclib's does.

  The slug is the other half and is #302's. Both halves are dashboard
  actions rather than anything a pull request reaches, so what lands
  here is the record beside the file: #302 for the slug, #295 for
  the release check that reads the rendered tag URL and stays blocked
  while there is none, and btclib-org/.github#26 for the commands that
  re-derive all of it. That check would be reachable only on a tag, the
  shape btclib-org/.github#49 is about — a reason to order it after the
  URL exists rather than a change to what that issue asks.

- **The same file carries the reasoning its siblings give for leaving uv
  unpinned.** Nothing about this repository made it different: no
  dependabot ecosystem watches this file, so a pin here is a version
  nobody bumps, and `--locked` makes the uv version irrelevant to what
  gets installed — `uv.lock` decides that, and a uv too old to read the
  lock fails loudly rather than resolving something else. The
  `docs/requirements.txt` sentence gains the half that says why the
  group and the lock are the single declaration, which was the argument
  for having no such file and had been left out.

- **`[tool.pydoclint]`'s reason for `skip-checking-short-docstrings =
  false` argued from what the check would find, not from what a
  docstring here says** (btclib-org/.github#114). Section 4 of the
  standard decides the key by the form a docstring's contract takes:
  `false` where a section is how it is stated, the default where prose
  states it. The comment instead argued that the default would let a
  short docstring pass unread — the argument section 4 rejects when a
  tree at the default makes it. This package's docstrings state their
  contract in `Args` and `Returns` sections; the two that carry
  neither, `Signer.wipe` and `SecretNonce.wipe`, take no argument and
  return nothing, so they owe neither section under any setting of the
  key. The comment now gives the form as the reason; the value is
  unchanged.

- **`CLAUDE.md`'s primary-checkout paragraph names the read that cannot
  go stale** (btclib-org/.github#255). It said reading the checkout was
  fine and so was `git fetch`, without saying `git fetch` moves
  `refs/remotes/origin/main` and leaves the work tree where it was, so a
  `grep` or a `Read` against the checkout answered for whenever it was
  last brought forward. The paragraph now names `git show
  origin/main:<path>` as the read that does not go stale, and gives the
  fast-forward that brings a clean checkout forward without working in
  it.

- **`README.md` ends with the line naming who supports the work.** The
  organization standard states the line as tier 1's, for the reason
  `SECURITY.md` is: the archive leaves github.com, and a reader who has
  it and not the repository meets the project with no organization
  beside it (btclib-org/.github#98).
- **`CLAUDE.md`'s worktree recipe named the worktree after the issue
  alone, `wt<issue>`** (btclib-org/.github#292). A worktree's
  administrative directory lives in the `.git` of the repository
  `git worktree add` was run from, one per repository, so two
  repositories cannot collide there; what the recipe left uncovered was
  a same-repository collision, between two worktrees of different work
  sharing a generic basename, and a *path* collision across
  repositories, since the workers of one session share one scratchpad
  directory and a session carrying one issue into several repositories
  computed the same target path for each. The recipe now names the
  worktree `wt-<tracker>-<issue>-<repo>-<role>`, most general part
  first: `tracker` because an issue number is unique only within one
  tracker, `issue` against the same-repository collision, `repo` against
  the cross-repository path collision, and `role` against a coder and
  its reviewer holding a worktree at once.
- **The shipped package and this repository's published docs stop
  naming `btclib`** (btclib-org/.github#81). This package is upstream of
  `btclib` -- `cffi` only, and `btclib`'s `secp256k1` extra depends on
  it -- so a reader of `btclib_secp256k1/` or of the built documentation
  is not guaranteed to have `btclib` at all. `__init__.py`'s lazy
  `__version__` docstring named `btclib` as an example of a caller that
  never asks for the version, and loses only the example by dropping the
  name. `README.md`'s ergonomics aside deferred a design tradeoff to
  `btclib` by name; it now defers to the caller generally, the same
  reasoning intact. `docs/source/package-content-policy.md` explained
  why this package's sdist policy carries no include-list check by
  contrasting it with `btclib`'s own script; the same argument now
  stands on the shape of an include list rather than on that comparison.
  `README.md`'s MuSig2 section named `btclib`'s own PSBT machinery and
  API to argue that wrapping libsecp256k1's own session is worth
  something to `btclib`'s test suite -- an argument about the dependent
  rather than about this package, correctly cut whole. What that
  paragraph also carried, and what stays, is the boundary a reader of
  `musig.KeyAggCache`/`musig.Session` needs regardless of `btclib`: a
  PSBT's multi-party signing state is not what `Session` is, that object
  being scoped to one process and one two-round exchange, so whoever
  needs PSBT-level coordination holds that state elsewhere. What stays
  everywhere is the organization that publishes this package and the one
  sentence in `README.md` saying who else uses it, both of which section
  9 of the standard names as the exception. A
  `no-downstream-name-in-package` pygrep hook holds `btclib_secp256k1/`
  to it, case-insensitively -- a downstream name can as easily open a
  sentence or sit in a class-name-style compound as sit mid-sentence, the
  shape every occurrence found here took -- the organization spelling
  and the copyright line's "The btclib developers" excepted.

- **`README.md`'s GitHub badge label names this repository, not the one
  it was renamed from.** The alt text and the link target were both
  updated when the repository moved to `btclib-secp256k1` (#133), but
  the shields.io image label itself still read `btclib--libsecp256k1`,
  the pre-rename spelling baked into the badge's own URL rather than
  into any text a diff of the rendered page would show.

- **`RELEASING.md` re-derives GitHub's artifact retention from the
  `actions/permissions/artifact-and-log-retention` endpoint, in place of
  a figure with a date beside it** (closes #410). Section 9 of the
  organization standard puts the command beside a number, and a date is
  not the cure: it says when the figure was true, where the endpoint
  answers for the day it is read. `days` is the window and
  `maximum_allowed_days` the ceiling the organization's own setting puts
  on what a repository may ask for, so the rest of the sentence -- that
  this repository has not narrowed the retention -- is re-derived by the
  same call. The concurrent-job ceiling in `REPOSITORY.md`'s *Plan-gated
  settings* keeps its dated qualifier for the reason this figure does
  not: that is GitHub's published table for a plan, and no endpoint of
  this repository answers it.

### CI

- **The concurrency ceiling's figure lives only in `REPOSITORY.md`'s
  *Plan-gated settings*** (issue btclib-org/.github#412). Section 10 of
  the organization standard puts it there, beside the plan command and
  GitHub's own table that re-derive it, and asks prose that needs the
  reasoning -- a workflow header, `CONTRIBUTING.md` -- to state it with
  the ceiling unnumbered and point there for the number. A date beside
  the figure is not the cure: the date says when it was true and nothing
  says it still is, where the command answers for the day it is run. The
  headers of `codeql.yml`, `os-ubuntu.yml`, `os-windows.yml` and
  `test.yml` carried it undated, `CONTRIBUTING.md` and `REPOSITORY.md`'s
  *Required checks on main* and *Code quality* with the date. This file
  states it too and is append-only, so those entries stand as written.

- **`pypi-install.yml`'s index wait runs on every trigger** (issue
  btclib-org/.github#49). The `if: inputs.version != ''` guard is gone,
  so a schedule and a dispatch reach the step and ask the index for
  nothing. What the guard bought was a step no cell ran until a release
  ran it, which is how the same shell defect shipped from a sibling's
  copy of this file and then from the copy that never took the one-line
  fix. The empty case is a condition **around** the loop rather than an
  early `exit 0`, and that shape is the whole of what the change buys:
  bash parses a script as it runs, so an exit at the top leaves the loop
  unparsed on every trigger that takes it — measured, a syntax error
  below such an exit prints nothing and returns 0, where the same error
  inside a branch not taken returns 2. Guard removed and loop still
  unparsed is the decision undone in the act of porting it. That issue
  records the decision, taken once for the publishing repositories, and
  the options it declines; it asks for the comment above the step
  verbatim in `btclib`, `bitcoin-core-rpc` and here, drifting prose being
  what made the second shipping invisible on review.

- **`check_vendored_vectors.py` reports an entry it cannot check** (issue
  btclib-org/.github#446). A `tests/README.md` block carrying no
  `repo`/`path`/`commit` triple is listed under "Not checked by this
  run, for the reason named" rather than dropped, which is what the
  module docstring and `_entries_at_tip`'s own already describe and what
  `btclib`'s copy of the script does. Section 14 of the standard leaves
  the copies of this file out of what `tests/verbatim_test.py` compares
  and asks each to state its own scope instead, so the docstring names
  `tests/README.md` as what it parses and says which shapes it declines
  without counting the entries it finds there.

- **Every workflow step is named** (#300). An unnamed step is rendered
  as its command on the run page, which a release run reads by
  expanding rather than by scanning, dozens deep; it also cost the
  alignment work across the three repositories, a step named in two
  files and not the third being harder to recognise as the same step
  (btclib-org/btclib#1141, btclib-org/btclib#1142). Names match what
  `btclib` and `bitcoin-core-rpc` already carry for the same step --
  "Checkout code", "Setup uv", "Cache the pre-commit hook
  environments", "Make the version unique for TestPyPI (rehearsal
  only)" -- and an upload or download names what it moves rather than
  repeating the action. Held deliberately until this repository had no
  open pull request, a whole-file sweep rebasing worst against one that
  had touched only a few lines of the same workflow.

- **`codeql.yml` carries no aggregate job any more** (#355,
  btclib-org/.github#90). Its `on:` block triggers on `push` to `main`
  and on a weekly schedule alone, no `pull_request` among them, and a
  branch rule can only name a context a pull request's own run
  produces -- so `codeql-passed`, producing `codeql: every job passed`,
  named a context no rule could ever require, which the organization
  standard now states as section 10's one rule rather than the two it
  used to hold apart. `analyze`'s two matrix cells are the whole of
  what this workflow contributes to a commit now, one check per
  language. `REPOSITORY.md`'s own account of that context -- kept
  deliberately once already, for the concurrency-slot trade the section
  above it records, and the ordering that mattered around toggling code
  scanning's default setup off -- is corrected alongside: what it
  described as a rule change away is now a workflow change too, and the
  ordering it walked through has nothing left to sequence around.

- **`release.yml`'s prose stays inside the width its neighbours hold, and
  states no count nothing derives** (#340, #342). The paragraph above
  `Check that the tag is on main` left one line at exactly the
  100-column limit `.yamllint.yaml` enforces, where every other line of
  that block wraps between 63 and 73 -- a rewrap begun and not
  finished, invisible to the hook because it sits at the limit rather
  than past it; it wraps the same way as its neighbours now. The
  comment above `github-release`'s sdist-only download named the
  release matrix's asset count as `thirty`; nothing in the workflow
  computes that figure, and it moves with cibuildwheel's own identifier
  list, the skip list and the image matrix, so the sentence no longer
  states one.

- **Three `release.yml` steps that run only on a push now say so in
  their name** (#341). `Check that the tag matches the declared
  version`, `Check that the tag is on main` and `Check that the release
  notes are retitled for the tag` each carry
  `if: github.event_name == 'push'`, and none of the three said
  `(release only)`, the suffix both `btclib` and `bitcoin-core-rpc`
  already carry on the same condition; they do now. `Sign a build
  provenance statement for the sdist` and `Create the release, with
  RELEASE_NOTES.md as its notes` keep their own names: both jobs run on
  `always()` rather than on that event check -- the attest job accepts
  either publish job succeeding, and the release job runs off
  `publish-pypi` succeeding rather than off the trigger directly -- so
  the suffix would misdescribe them, and each already names what it
  does more precisely than the sibling name it was compared against.

- **The rehearsal re-locks, and every build step passes `--locked`**
  (btclib-org/.github#128). The `dev-version` action rewrites the version
  in `pyproject.toml` on the rehearsal path, and the build steps after it
  passed `--frozen`, the organization standard's one exception to
  `--locked`, never `--frozen`, documented in `CLAUDE.md`,
  `CONTRIBUTING.md` and `RELEASING.md` here and nowhere in the standard.
  The standard's decision is that a rehearsal re-locks rather than
  relaxing the flag, which is what `btclib`'s action already did: this
  one now runs `uv lock` after the rewrite, and the six `run:` commands
  of `test.yml` that passed `--frozen` -- `build-cibuildwheel`'s
  `Build wheels`, `build-dynamic`'s `Build wheel` and its two repair
  steps, `build-sdist`'s `Build source`, and `build-windows`'s
  `Build Windows wheel`, one more than the issue counted because that
  one's flag sits on the second line of a `run: |` block its `sed` did
  not reach -- pass `--locked`. Measured on a copy of `main` with the
  action's own script appending `.dev421`: `uv run --locked --only-group
  build python -m build -s` exits 2 with "The lockfile at `uv.lock`
  needs to be updated, but `--locked` was provided"; `uv lock` then
  moves one line, the project's own `version`, and the same command
  exits 0. It also changes what a rehearsal's sdist ships: `uv.lock` is
  in that archive, and the one built with `--frozen` declared `0.8.0.5`
  inside `btclib_secp256k1-0.8.0.5.dev421.tar.gz`, where the re-locked
  one declares `0.8.0.5.dev421`. The exception is gone from the three
  files that stated it, and `os-ubuntu.yml`'s example command passes
  `--locked` too, answering nothing with either flag. The lock in the
  tree does not move: the re-lock happens in CI, on the rehearsal
  alone, and `uv lock --check` in `release.yml` keeps asking that the
  committed one agree.

- **`links.yml` accepts every code lychee would accept unasked, and
  passes no cache flag** (btclib-org/.github#110, btclib-org/.github#111).
  `--accept 200,206,429` replaced lychee's default rather than adding to
  it -- `lychee --help` gives the default as `100..=103,200..=299` -- so
  a host answering 204 to a HEAD, or a redirect ending in a 201, was a
  dead link the weekly run went red on without anybody touching the
  tree. The list is now that default spelled out, plus the 429 the
  comment beside it argues for. `--cache --max-cache-age 1d` went with
  it: a run starts from a fresh workspace and no step restored the file
  lychee writes, so the flag decided nothing between runs, and within
  one lychee requests each unique URL once whatever the flag says --
  measured on this tree's own globs, 135 links and 102 requests. The
  comment crediting the cache with keeping a throttling host from
  reading as dead described a mechanism that was not there, and now
  credits the retries and the timeout alone.

- **`claude-review.yml` reports red on anything but an ack of this
  head** (btclib-org/.github#146). The review job ended at a step
  testing whether the action had run at all, so a `CHANGES REQUESTED`, a
  run that posted no comment, and an ack naming a sha the branch had
  moved past each left the check green. The step `btclib-org/.github`
  carries at `18e6c64` is here now, with its comment: it reads the last
  verdict `claude[bot]` posted on the pull request and fails unless it is
  an `ACK` whose sha is a prefix of the head. Its shell is byte-identical
  to that copy's; two lines of the comment above it are reworded where
  the original pointed at that repository's own `README.md` and its own
  pull request. Run outside the workflow against this repository's pull
  requests, with `REPO`, `NUMBER` and `HEAD_SHA` in the environment: on
  #343 and #333 at their heads it prints `the review acked ...` and
  exits 0; on #343 with another head it exits 1 naming both shas; on
  #337, whose last verdict is a `CHANGES REQUESTED`, it exits 1 saying
  so; on #339 and #338, where no `claude[bot]` comment ends in a verdict,
  it exits 1 saying that. Still not a required check, and red there
  gates nothing. The two copies of the workflow differ beyond this step
  -- the header, the checkout comment, `allowed_bots` and the prompt are
  each this repository's -- and those stay as they were.

- **`release.yml` names its steps** (#300). The steps of this file that
  carried no `name:` have one, where both siblings' `release.yml` names
  all of theirs. GitHub renders an unnamed step as the command it runs,
  so a failing job in a release run was read by expanding steps rather
  than by scanning them, and the same step was harder to recognise across
  the three repositories, which is the cost #300 names. Neither of the
  divergences that issue cites was a missing name --
  btclib-org/btclib#1141 is a step that has one and lacks `shell: bash`,
  and btclib-org/btclib#1142 is a guard at job level -- so what a name
  buys is that the next such comparison is made by scanning, not that it
  would have caught either of those.

  The names are the siblings' own wherever the step is theirs too:
  `Checkout code`, `Setup uv`, `Publish to PyPI`, `Publish to TestPyPI`,
  `Upload the attestation bundle`, `Download the attestation bundle`.
  Where they disagree it is because this package publishes what the
  siblings do not. Each publish job downloads twice where the siblings
  download once, so its two steps are named apart -- `Download the
  wheels` and `Download the source distribution` -- one wheel matrix
  built by the jobs that compile the vendored library and an sdist built
  by a job that does not, against a single `Download the distribution
  files` that would name neither. `attest` and `github-release` take no
  wheels at all, so the siblings' name would have fitted there; they read
  `Download the source distribution` too, so that one artifact is fetched
  under one name throughout the file.

  #300 stays open, being about every workflow here rather than this one:
  the other files keep their unnamed steps until a pull request that
  touches each of them arrives, which is what that issue asks for instead
  of a sweep. Nothing reports one -- `actionlint` has no rule for a step
  without a name -- so the command is what answers:

  ```shell
  grep -nE '^ *- (uses|run):' .github/workflows/*.yml
  ```

- **The merge gate runs one cell of the suite, and the sweeps moved to
  the calendar** (btclib-org/.github#85). `test.yml`'s `suite-static` and
  `suite-dynamic` jobs are gone: two ubuntu images, each walking every
  interpreter against a wheel built earlier in the same run, asked before
  every review on an organization whose plan gives it twenty concurrent
  jobs across every repository. What waits for a review now is the
  `coverage` job -- `ubuntu-latest` on the version `.python-version`
  names -- beside the lint, docs and packaging jobs, and the wheel builds
  that a release publishes the artifacts of.

  `ubuntu.yml` is where those cells went, and it is the third of a set
  `macos.yml` and `windows.yml` already had: both images of a platform,
  every interpreter, compiling the vendored library twice a cell so that
  `BTCLIB_LIBSECP256K1_DYNAMIC` and both branches of `_load_lib` are
  covered. It runs weekly and `release.yml` calls it, so a version cannot
  be published over a platform nothing answered for. Its header carries
  the argument for all three, and the other two now point at it.

  Each matrix runs whole, the cell the gate already covers included. A
  sweep that subtracted the gate would be a matrix with a hole in it, and
  whoever asked what ran would have to re-derive the hole from another
  file.

  What it costs, said here rather than found later. A regression on an
  interpreter or an architecture the gate no longer reaches sits on
  `main` until the weekly sentinel for it runs. Pip's *selection* among a
  directory of wheels tagged for several interpreters is now asked
  nowhere -- each wheel is still tested by the cibuildwheel job that
  builds it, and `check-dist` still installs one by path into an empty
  environment, but nothing chooses between them. And no suite runs
  against the dynamic wheel as a package any more: `test-command` in
  `pyproject.toml` reaches cibuildwheel's static wheels alone,
  `build-dynamic` and `build-windows` build without testing, and
  `check-dist` imports the dynamic wheel rather than running the suite
  through it. What the sentinels cover is the dynamic extension compiled
  from the tree, which is `_load_lib`'s second branch and not the
  artifact pip resolves to where no static wheel matches. `ubuntu.yml`'s
  header records both, beside each other.

  With no consumer of a whole image's set left on a branch, the wheel
  shortcut widens to ubuntu too, as it already applied on macOS and
  Windows: a pull request builds one interpreter's wheels per image,
  which is what answers whether this tree still builds there, and
  `check-dist` takes its wheel from `build-dynamic`, which builds whole.

  Every schedule here is on the organization's grid, which gives a
  workflow its day and its hour and this repository its minute. Eight
  crons moved and a ninth is new; `published.yml` and
  `vendored-vectors.yml` go from monthly to weekly with the rest, a month
  having been a sample rate nothing derived from their subjects. The grid
  is section 10 of `btclib-org/.github`, which is why the cadence table in
  `CONTRIBUTING.md` no longer names a day and `CLAUDE.md`'s copy of it is
  gone: one calendar covering the organization is one thing to remember,
  and a copy of it per repository is one more thing to keep true in each.

  `tests/test_interpreters.py` reads the three sentinels' matrices where
  it read `test.yml`'s two `PYTHONS` blocks, the declaration it compares
  against `requires-python` and the classifiers having moved with the
  cells. It reads each file separately and requires the three to be
  equal, rather than comparing their union: each sentinel's matrix
  comment already says the other two carry the same list, and a union is
  a reading in which a list that drifted in one file is covered by the
  other two. `windows.yml` spelled PyPy `pypy-3.11` where the others
  spell it `pypy3.11`, which is what the new check found first.

- **The interpreters this package claims are the ones it runs on**
  (btclib-org/.github#83). `requires-python`, the per-version
  `Programming Language :: Python ::` classifiers and `test.yml`'s own
  `PYTHONS` block are one fact written three times, and nothing compared
  them. `tests/test_interpreters.py` does: the floor is the lowest
  classifier, the classified set and the matrix's CPython set are each
  other, and the PyPy classifier is present exactly when a PyPy
  interpreter runs.

  The drift it catches is the kind that misleads somebody who is not
  reading this repository — PyPI shows a classifier to whoever is
  choosing the package, so a version left behind when a floor moves is
  an interpreter advertised and never touched.

  What it does not encode is the calendar. The organization standard's
  rule is that a library covers every Python still in support, which
  moves twice around each October; python.org keeps that schedule and a
  test that hard-coded a date would be one more thing to move. The claim
  here is the weaker and checkable one: whatever the three say, they say
  the same thing.

  `Programming Language :: Python :: 3` was missing beside `:: 3 :: Only`,
  where the three sibling repositories carry both. Added — and outside
  what the test above reads, which is deliberately the per-version
  classifiers alone: `:: 3` is a claim about the major version rather
  than about an interpreter the matrix could run.

- **The mypy hook's pins are checked against `uv.lock`**. The type gate
  runs in an environment of its own, built from the mirror's `rev` and
  its `additional_dependencies`; the editor cannot use that environment,
  this package being a compiled extension whose import does not resolve
  where nothing built one, so it reads the project's instead. The two
  are the same mypy only while the two declarations say so, and what
  said so was a procedure -- `.pre-commit-config.yaml`'s own "moved by
  hand, with the lint and test groups of uv.lock".

  `tests/test_hook_pins.py` makes it a red test instead. It is the
  second declaration section 4 of the organization standard names as the
  price of this branch, and the part that was unchecked is now the part
  that fails: a `uv lock` moving mypy, `cffi`, `types-cffi`, `hatchling`
  or `pytest` without the hook following is silent otherwise -- both
  environments still build, and mypy still passes in each, against
  different versions.

  Parsed rather than loaded, for the reason `test_copyright.py` gives:
  `tomllib` arrives in 3.11 and the floor here is 3.10, and no group
  carries a yaml parser. Each of the three ways the pins can drift was
  made to happen and watched to fail.

- **Which of section 7's conventions this suite tests is declared, and a
  test says the declaration is true** (btclib-org/.github#32).
  `tests/README.md` gains a table naming each convention the organization
  standard lists that this repository tests and the module that tests it,
  followed by a line naming the ones it does not.

  **Some of the eight and not the rest**, which is the point of declaring
  it rather than leaving it to be inferred: section 7 says a repository
  needs the conventions its own prose states, so an absent convention
  test reads exactly like a convention this repository does not have.
  The reasons differ and are given one by one. The public surface is not
  a convention this package has -- nothing here declares `__all__` --
  and input validation and the calling convention are the two bullets
  that rest on walking one, so `test_core.py` refusing plenty by hand is
  not what section 7 asks for. The changelog is the near miss:
  `test_vendored_data.py` forbids exactly the count that bullet forbids,
  of `tests/README.md` rather than of the two history files it names.
  The import graph and the build system have nothing standing in for
  them.

  `tests/test_conventions.py` is what keeps the declaration from being
  prose -- section 7's own rule applied to section 7 itself -- and its
  four assertions were each checked by making the declaration wrong in
  that way and watching the suite go red.

- **`test_vendored_data.py` stops assuming the Summary is the last
  section**. `_summary()` sliced from its heading to the end of the file,
  which was true while it was last and stops being true the moment a
  section is added after it -- silently, its patterns then reading prose
  it has no claim about. The change above is what would have made it
  false, so it is what fixes it: the slice now ends at the next `##`.

- **A Dependabot pull request can be reviewed**
  (btclib-org/.github#77). `claude-review.yml`'s review job fails on one,
  twice over. The credential is the first half and is fixed off the tree:
  a `pull_request` run whose actor is `dependabot[bot]` reads from
  GitHub's Dependabot secret store rather than from Actions secrets, and
  that store was empty, so the guard fired exactly as designed. The
  second half is this: the action refuses a run a bot initiated unless
  the bot is named — "Workflow initiated by non-human actor".

  `allowed_bots: "dependabot[bot]"`, named rather than `*`: the input's
  own description warns that on a public repository `*` lets an external
  App invoke the action carrying a prompt it wrote. The mention job takes
  no such input, what triggers it being somebody writing `@claude`.

  Without it a Dependabot pull request is the one class that can never
  carry the ack of record `REVIEWING.md` requires — the class whose whole
  value is landing promptly, `latest.yml` having reported on the same
  upgrade the day before. Measured on btclib-org/bitcoin-core-rpc#207,
  the first Dependabot pull request opened after the credential guard
  landed.

- **Every workflow comment read end to end, and `codeql.yml` stopped
  calling itself a gate** (btclib-org/.github#22). #142 moved this
  analysis off `main`'s required checks and removed its `pull_request`
  trigger, correctly, and updated the `on:` block to say so. Three
  statements #114 had written survived it, in the same file: the header
  called this "the fourth gate"; the `analyze` job said "neither name is
  a required check -- the aggregate below is", which the `on:` block
  twelve lines up already contradicted with "no longer a required check
  on main"; and the job carried `if: ${{ !github.event.pull_request.draft
  }}` under a comment saying "ready_for_review is a trigger type above",
  in a workflow that has no `pull_request` trigger at all, so the
  expression could only ever read empty. `main` requires three checks
  here -- `Lint and type-check`, `Build the documentation` and `test:
  every job passed` -- and the file now says so once, where it used to
  say two different things and imply a third. The dead condition is gone,
  taking btclib's own wording for why there is none.

- **`latest.yml`'s lint job says what it actually reaches** here, which
  is not mypy (btclib-org/.github#22). The header and the job both
  claimed mypy moves with `uv lock --upgrade` "through the local hook
  that shells out to uv", and that this is "the reason the lint job
  below exists at all". No hook in `.pre-commit-config.yaml` shells out
  to uv: mypy is `mirrors-mypy` at a pinned `rev`, and the packages it
  type-checks against are pinned by hand in `additional_dependencies`,
  as that file's own comment says. The sentence is btclib's, where it is
  true -- its mypy hook is `repo: local` running `uv run --locked ...
  mypy`. Section 4 of the organization standard calls this "a trade-off
  with two right answers rather than a rule", and by its own criterion a
  package whose types rest on a handful of stubs takes the second: the
  configuration is right and the comment was wrong. What the job does
  reach is `pre-commit` itself, from the lint group, which is worth a
  weekly run and is now what it claims.

- **`published.yml` is on no weekday, and two files put it on Tuesday**
  (btclib-org/.github#22). `links.yml` and `mutation.yml` both enumerate
  the weekday sentinels as links, published, latest, Dependabot; its cron
  is `23 6 1 * *`, monthly, and has been since the run stopped being
  weekly. The same sentence was fixed in btclib by btclib-org/btclib#1236
  and in bitcoin-core-rpc before that: three copies of one calendar, and
  this is the shape btclib-org/.github#76 is about.

- **Three cron-minute lists and three counts replaced by the commands
  that re-derive them** (btclib-org/.github#22). `macos.yml` named five
  of this repository's minutes where there are eight, `windows.yml` six,
  `vendored-vectors.yml` four; each list was complete when it was
  written. `vendored-vectors.yml` also said `tests/README.md` pins "the
  three vendored test vectors", where it pins ten, and called a
  `49 4 1 * *` cron "the weekly schedule". `test.yml` said
  `.github/scripts/` holds "the three of them", where it holds four, and
  that "two tests" load a script by path, where three do. Every one of
  them now points at `grep -h 'cron:' .github/workflows/*.yml`, at
  `git ls-files .github/scripts`, or at nothing at all -- a count written
  out is complete on the day it is written.

- **`codeql.yml` and `docs.yml` stop saying `release.yml` calls three
  workflows** (btclib-org/.github#22). It calls six: `lint`, `docs`,
  `test`, `macos`, `windows` and `published`, five of which declare the
  `concurrency-suffix` input the two comments are about. `codeql.yml`'s
  was true when #114 wrote it and drifted; `docs.yml`'s was written by
  `35c6931`, the very commit that added two of the calls it does not
  name.

- **`test.yml`'s prose allowlist gains `CODE_OF_CONDUCT.md` and
  `REVIEWING.md`, and records why `AUTHORS.md` is not on it**
  (btclib-org/.github#22). The comment describes the list as "the prose
  files of the root and of .github"; three of the eleven root markdown
  files were missing from it, so editing one spent the whole matrix to
  prove it changes nothing built. `AUTHORS.md` is the one that must stay
  off: the wheel carries it as a license file, named by
  `WHEEL_LICENSE_FILES` in `.github/scripts/verify_wheel_contents.py` and
  asserted by `tests/test_wheel_contents.py`, so adding it would skip the
  matrix on a change `check-dist` reads. That reason is now in the
  comment, because the sentence as it stood invited exactly that edit.

- **Prose repairs with nothing behind them but the reading**
  (btclib-org/.github#22). `latest.yml` said `uv.lock` moves on "a
  monthly dependabot pull request" and could sit unseen "five weeks",
  where `.github/dependabot.yml` has said `interval: weekly, day:
  thursday` since #111 -- and where line 55 of the same file already said
  "Thursday is left for Dependabot". `codeql.yml` said Tuesday is "shared
  with no other cron here, nor with btclib's or bitcoin-core-rpc's", where
  both siblings analyse on Tuesday deliberately and it is the minute that
  is unique. `links.yml`'s "Eighty-six distinct external URLs" is
  eighty-seven seventeen days later, and its narrower glob is now
  explained rather than left to look like an omission: the nine markdown
  files btclib's and bitcoin-core-rpc's globs would add carry no external
  URL at all. `macos.yml` carried the one comment line in these thirteen
  files past eighty columns, at eighty-five, which is how the paragraph
  came to be reread.

- **A markdown line does not end inside a word**
  (btclib-org/.github#71). Markdown joins two source lines with a space,
  so a word wrapped at its own hyphen renders with the hyphen and then a
  space inside it. This is the repository the rule came from: #318 fixed
  three of them here, in `README.md`, `CHANGELOG.md` and `RELEASING.md`,
  and the one that started it was found by scanning rendered `<code>`
  spans in built html rather than by reading markdown -- the source
  looks correct, which is why reading a diff does not find one.

  Nothing here read the output: markdownlint has no rule for it, the
  width rules read a line rather than what two lines become, and
  `sphinx-build -W` is not asked whether a token means anything. A
  `pygrep` hook now does, for the reason `local-link-prefix` beside it
  is one. The rule and what the hook cannot see -- a code span whose
  content breaks at a `/` or a `.` renders the same way and has no
  hyphen to match -- are in section 4 of the organization standard,
  which the comment points at rather than restates.

- **`claude-review.yml` stops counting the required checks, and here
  the count was wrong** (btclib-org/.github#22). "The four required
  checks stay what they are": `main` requires three in this repository.
  The sentence is `btclib`'s, where four is right, and it travelled with
  the workflow -- being true in the tree it was written in is exactly
  what let it be wrong in the two it was copied to, this one and
  `btclib-benchmarks`.

  Nothing checks a workflow comment: `actionlint` reads the workflow,
  `zizmor` reads it for injection, and prose beside them reads as
  authoritative for sitting there. What the paragraph is for survives
  without the number -- this job is not a required check and must not
  become one, a model's judgement not being a branch rule -- so it now
  says the required checks stay what they are and sends the reader to
  `REPOSITORY.md` and the endpoint.

  Found by the sweep that issue asks for, run here over the claims a
  command can settle: every workflow named in a comment exists, every
  cron matches the day its comment claims, and the trigger claims match
  each `on:` block, `codeql.yml`'s "no `pull_request` trigger" included.
  The prose half of the sweep -- reading every comment end to end, which
  is how a stale claim that reads like a true one is found -- is not
  done, and is what keeps that issue open.

- **`.yamllint.yaml` keeps the default rule set on, and stops carrying
  one tree's claims** (btclib-org/.github#40, and the shared file's own
  defect found reviewing that change). Two things, one file.

  The claims first: the file recorded the findings of a survey run
  somewhere else — "80 reports 62 lines against 8 at 100" — as settled
  fact, in a file shared byte-for-byte across the organization's
  repositories. A number measured in another tree and copied here is not
  a measurement of this one, and nothing in the file told the reader who
  checked it so. It now states the rule and the command that re-derives
  the numbers in whichever tree is asking.

  The defect that came with the shared copy is `extends: default`.
  yamllint enables no rule a configuration does not name, so a file that
  lists `line-length` and `document-start` and extends nothing runs those
  two alone: indentation, trailing whitespace, duplicate keys and the
  rest of the default set silently off, while the file's own prose said
  only `comments` and `truthy` were. A lint gate passes either way — a
  check nobody runs cannot fail — which is why the copy travelled. This
  repository was the one still carrying `extends: default`, so adopting
  the shared file unchanged would have turned the set off here too; the
  shared file gains it back instead, with the two exceptions named under
  `rules:` where a reader can see them rather than inferred from what is
  missing. `.pre-commit-config.yaml`'s comment above the hook follows:
  it described a width check, which is what the hook was, and now names
  what actionlint and zizmor still do not read -- a key written twice, a
  block indented under nothing. Nothing new is reported in this tree:
  `git ls-files '*.yml' '*.yaml' | xargs uvx yamllint` is clean before
  and after.

- **`.taplo.toml` stops carrying one tree's furniture**
  (btclib-org/.github#40). It justified `reorder_keys` and
  `array_auto_collapse` by naming things that are one tree's — "the ruff
  rule sets", "a module to the mutation session" — where the reasons are
  that a table's order is an argument rather than an accident, and that
  one indent across every toml in the organization is the point of having
  a formatter. It is now the copy the sibling repositories carry, which
  argues from the rule and says outright that nothing in it may be true
  of one tree only. `indent_string` and `array_auto_collapse` do not
  move, which taplo rewriting nothing here is what shows.

- **`[tool.uv]`'s `required-version` comment stated the wrong reason**
  (#299): it read as though the floor were the version the uv-lock hook
  of `.pre-commit-config.yaml` pins, but that hook pins `0.12.5` while
  the floor reads `>=0.12.0` -- the two numbers were never the same
  one. The real constraint is Dependabot's own uv-ecosystem updater: it
  runs `uv lock` with exactly the uv it bundles
  (`dependabot/dependabot-core`'s `uv/Dockerfile`, `0.12.1` at the time
  of writing) and refuses instead of upgrading itself when that uv
  falls short of this key. btclib's issue #485 is what a floor ahead of
  it costs: every lock update it attempted, security ones included,
  failed with `tool_version_not_supported` before a single one started.
  `0.12.1` still clears `0.12.0`, so the floor itself does not move here
  -- only the comment does.
- **`docs.yml`'s unresolved-link grep now carries both known shapes**,
  one of two companion fixes for btclib-org/btclib#1157, which
  btclib-org/btclib's own PR closes. MyST renders a link its
  `RootFileLinks` transform cannot resolve as `href="#<target>"`
  verbatim, so what the grep matches depends on how the target was
  written -- `href="#[A-Za-z0-9_.-]*\.md"` for a bare `SECURITY.md` with
  no `./`, most of this package's own root-file links, and `href="#\./`
  for `./REVIEWING.md` and `./RELEASE_NOTES.md`, which CONTRIBUTING.md
  and CHANGELOG.md write with the `./` the rest of this package's links
  omit -- the same shape the comment this replaces claimed the package
  never used. This job ran only the bare-name grep, which is blind to
  either of those two live links breaking. Built the documentation with
  a deliberately unresolved link of each shape and confirmed the added
  grep reports it before removing it; `sphinx-build -W --keep-going`
  passes on both unchanged, since neither is the broken *reference* `-W`
  already catches -- a link myst resolves happily and is dead anyway is
  the whole reason this second check exists.

- **`lint.yml`'s pre-commit cache key now carries the runner image and
  the interpreter, not only `.pre-commit-config.yaml`'s hash** (#296).
  What the cache holds is compiled artifacts and interpreter-linked
  virtualenvs, so restoring one built on a different runner image is not
  a graceful miss but a hit that hands the run a broken environment, the
  failure surfacing as whichever hook touches it first -- the config
  hash alone would have survived an `ubuntu-latest` rotation, 22.04 to
  24.04 and the next one, and kept restoring an environment built on the
  image before it. Both siblings already key on `runner.os`, the
  `ImageOS` environment variable read by a new `Identify the runner
  image` step, and `.python-version`'s hash alongside the config's; this
  repository's file is now the same, `restore-keys` included so a
  revision bump in the config stays a warm start rather than a cold one.

- **Every `run:` step that can land on a Windows runner declares
  `shell: bash`** (btclib-org/btclib#1148). `suite-latest` in
  `latest.yml`, `suite-windows` in `windows.yml`, and
  `build-cibuildwheel` and `suite-sdist` in `test.yml` each carry a
  `windows-latest` or `windows-11-arm` matrix cell, where the default
  shell is PowerShell and `"$GITHUB_ENV"` and the rest of the POSIX
  spelling are literals rather than variables; `build-cibuildwheel`'s
  `Build wheels` step already sits beside one step that declares the
  line for exactly this reason, and named the other Windows steps of
  this file it did not yet reach. All six affected steps are one plain
  command each and run identically under either shell today, so nothing
  shipped broken -- the hazard is the next conditional, substitution or
  loop added to one of them, which would fail only on Windows.
  `latest.yml` and `windows.yml` run on neither a pull request nor a
  push to `main`, so such an edit's first execution would be a scheduled
  run; `test.yml`'s two steps are on the merge gate itself, where the
  Windows cells of `build-cibuildwheel` and `suite-sdist` are exercised
  on every pull request, but a shell-less step there would still go
  green having run the wrong interpreter's syntax rather than the
  intended one.

  Enumerated by parsing every workflow file's `jobs.*.strategy.matrix`
  (`os` and `include`) and `runs-on` with PyYAML, and flagging a `run:`
  step whose job's runner set contains `windows` and which declares no
  `shell:` of its own and inherits none from a job-level `defaults.run`
  -- `actionlint`, the pinned linter in the pre-commit gate, reports
  nothing for this shape, measured on a minimal workflow with a POSIX
  `for` loop and no `shell:` under both a literal `windows-latest` and a
  matrix naming it. `btclib` and `bitcoin-core-rpc` had the same defect
  in their own copies of `latest.yml` and `windows.yml`
  (`windows-arm.yml` in `bitcoin-core-rpc`), fixed in a pull request of
  their own; `btclib`'s `test.yml` carries no Windows row and
  `bitcoin-core-rpc`'s carried one further instance of its own.
- **`docs.yml`'s unresolved-link check is one grep again**
  (btclib-org/.github#20). The second pattern, for a bare destination ending
  `.md`, has nothing left to catch now that the `local-link-prefix` hook
  refuses that spelling, and it was no superset of the first even before: a
  character class of name characters stops at the `#` of an anchor, so
  `#README.md#build` is a shape both patterns pass over -- and that is what
  this repository's own `CONTRIBUTING.md` would have rendered. The step's
  comment carries the reasoning. What is left is `href="#\./`, and the hook is
  what makes it sufficient rather than merely first.

- **`latest.yml`'s pre-commit cache is keyed on the runner image and the
  interpreter rather than on the config hash alone**
  (btclib-org/.github#25). #296 put those segments into `lint.yml`'s key
  and #309 corrected this file's comment, which had claimed the bare key
  was "as in `lint.yml`"; the key itself was out of that pull request's
  scope and is what changes here. What the cache holds is virtualenvs,
  so the config hash alone survives an `ubuntu-latest` rotation and
  restores environments built on the previous image — not a graceful
  miss but a hit, surfacing as whichever hook touches the broken
  environment first. `lint-latest` is the job with the most to lose from
  that: it runs to report what a new release of a dependency breaks, so
  a failure the cache caused arrives looking exactly like the one the
  workflow exists to find, and is chased in the tree. The `Identify the
  runner image` step reading `ImageOS` from a shell, the key over
  `runner.os`, that output and `hashFiles` of `.pre-commit-config.yaml`
  and `.python-version`, and `restore-keys` still naming the image so a
  partial restore cannot cross an image boundary, are all `lint.yml`'s.
  The comment now carries this job's own reason for the key, with
  `git grep -n 'pre-commit-\${{' -- .github/workflows/` beside it as the
  command that re-reads both keys together.

- **`scorecard.yml` runs the OpenSSF Scorecard against this repository**
  (issue #387, btclib-org/.github#339), section 10's sentinel keyed on a
  repository being public and not a fork:
  `gh api repos/btclib-org/btclib-secp256k1 --jq '.fork, .private'`
  answers `false` and `false`. `publish_results: true` feeds the score
  `api.scorecard.dev` serves and files what it finds as code-scanning
  alerts; `id-token: write` is the transparency-log entry the publish
  asks for, `security-events: write` the alert upload. Its triggers are
  the action's own rather than section 10's usual set -- `push:` on
  `main` only, no `pull_request`, no `workflow_dispatch` -- and it
  carries a `schedule:` block: Saturday and hour 03 from section 10's
  calendar, minute 08 from this repository's own row in that section's
  second table. btclib-org/.github#363 proposes that row and is open
  rather than landed as of this entry. No badge: that is a separate
  pull request, and `fuzz` is out of scope here, its design unresolved
  at btclib-org/.github#342.

- **`claude-review.yml` posts its verdict as a pull request review, not
  a comment** (issue #387, btclib-org/.github#340). `gh pr review <n>
  --approve --body "<summary>"` carries `ACK <sha>` and
  `--request-changes` carries `CHANGES REQUESTED <sha>`, both inside
  the review body; a reading that reaches no verdict still posts as a
  plain `gh pr comment`, as every summary did before this. The guard
  step that refuses a green run posting no verdict now reads
  `repos/$REPO/pulls/$NUMBER/reviews` rather than
  `issues/$NUMBER/comments`, matched against the head sha the same way.
  GitHub refuses only a *self*-approval, and this workflow never runs
  as the pull request's author, so nothing stops it approving one; the
  job stays what it was, not a required check.

- **`claude-review.yml` converges on `btclib-org/.github`'s current
  copy again: a job-level gate, a guard that reads the SDK's own error
  fields, and a verdict posted as a `COMMENT` review rather than an
  approval** (issue btclib-org/.github#364, btclib-org/.github#385,
  btclib-org/.github#340). The review job has ended `is_error: true`
  since 2026-08-23 on every `pull_request` run sampled across the four
  repositories the first of those issues measured, this one included --
  `num_turns: 1` and `total_cost_usd: 0` together saying the first
  turn never completed billably, not that none ran. Nothing in these
  repositories changed across the moment the runs turned red, which is
  a narrower claim than the cause lying outside them;
  `if: vars.CLAUDE_REVIEW_ENABLED == 'true'` now gates both jobs,
  unset organization-wide, so the job skips cleanly instead of failing
  loudly on every pull request until the shared workflow or credential
  that issue points at is fixed. It sits on the job and not on a step:
  a step that declines to run still leaves `steps.review.outcome` at
  `skipped`, which the guard below reads as a review that never ran.

  That guard, `Refuse to report a review that never ran`, now runs on
  `!cancelled()` rather than only when the execution file is missing,
  and reads `api_error_status`, `stop_reason` and `.result` off that
  file when `steps.review.outcome` is not `success` -- fields the
  action's own log sanitizes out of the result message it prints, and
  writes unsanitized to the file `steps.review.outputs.execution_file`
  already names.

  The verdict itself moves from `gh pr review --approve` /
  `--request-changes` to `gh pr review --comment`, always: OpenSSF
  Scorecard's `Code-Review` check excludes a bot's review of any kind,
  approving or otherwise, so the self-approval reasoning the previous
  entry gave for preferring an approval over a comment does not survive
  it -- what a review buys over a comment is only that the forge
  records it under `pulls/<n>/reviews`, which the guard already reads.
  The last line stays `ACK <sha>`, `CHANGES REQUESTED <sha>` or `NACK
  <sha>`, the guard's regex now accepting `NACK` alongside the other
  two, and the read-back treats a null review body as empty rather than
  aborting the whole page it sits on.

  The prompt's own citations of the standard are adapted rather than
  copied, following section 14's rule for a receiving copy. `.github`'s
  own copy cites `README.md` because that file is the standard there;
  a citation naming a rule section 11 actually holds is ported to name
  section 11 instead -- "section 11 of the organization's standard",
  and "section 11's *Review*" for the subsection. The one citing
  `README.md` for the standard as a whole -- the rules a finding cites
  living in section 9 and in *How to use this file*, not in section 11
  -- is ported to "the organization's standard" with no section
  number.

- **`claude-review.yml`'s comments name the `gh pr` subcommands the
  prompt uses, word the `mention` job's credential refusal for the job
  it guards, and argue the concurrency cost without a plan-dependent
  figure** (issue btclib-org/.github#398, btclib-org/.github#402,
  btclib-org/.github#405, btclib-org/.github#410). The prompt reaches
  the CLI through `gh pr
  diff`, `gh pr view` and `gh pr review --comment`, so the comment
  explaining why `claude_args` is a folded scalar spells out `diff,
  review and view`. The step guarding `mention` -- the job that answers
  an `@claude` comment and reviews nothing -- is `Refuse to answer
  without a credential` and says the workflow answers nothing, taken
  byte for byte from `btclib-org/portanode`, with the comment above it
  naming the review job's reason rather than restating it. The header's
  argument for one more job per pull request rests on the ceiling being
  the organization's and shared with the other repositories' matrices,
  and sends a reader to `REPOSITORY.md`'s *Plan-gated settings* for the
  ceiling and for the command that answers the plan setting it: a
  figure written into a comment is one no hook reads and no test
  compares, so it goes on reading true after the plan moves.

- **`claude-review.yml`'s verdict check reads the last claude[bot] entry
  across every page of `pulls/<n>/reviews` before asking whether it is a
  verdict** (closes #394). `--paginate` fetched pages separately and the
  filter selected only matching bodies before taking the last of those,
  so a page whose newest claude[bot] entry carried no verdict -- a
  declined reading arriving after an acked or changes-requested run --
  silently fell back to an earlier page's stale verdict. `--slurp`
  flattens every page first, and the filter now takes the
  chronologically last claude[bot] entry whatever it says, emptying the
  verdict the same way a page with no such entry at all does.

- **The same file's `CLAUDE_REVIEW_ENABLED` comment cites
  `section 11's *Review*` alone** (closes #404), matching every other
  citation of that subsection in this file. It had appended the
  subsection name to the full `section 11 of the organization's
  standard` form, a shape none of the file's own later citations use.

- **`scorecard.yml`'s cron comment states the settled fact rather than
  the state of btclib-org/.github#363** (closes #401). The row schedules
  Saturday, hour 03 from section 10's calendar, decided by that issue,
  which is closed; the header's count of Scorecard's own checks drops
  with it, matching the sibling repositories' wording for the same
  paragraph.

- **`check_vendored_vectors.py`'s docstring says weekly, which is what
  `vendored-vectors.yml` schedules** (closes #409). The cron is Monday
  and that workflow's own header rejects a monthly cadence in as many
  words. The cadence is load-bearing rather than decorative: the
  docstring's reason for skipping an entry already documented as behind
  is that a run would otherwise re-report the same gap, and how often a
  run happens is what makes that argument weigh what it weighs.
  `btclib`'s copy of the script says weekly too.

- **`codeql.yml` gains a `pull_request` trigger and a `codeql: every job
  passed` aggregate, together** (issue btclib-org/.github#459,
  btclib-org/.github#349). Either half alone is inert: a branch rule can
  only name a context a pull request's own run produces, and the
  `analyze` matrix produces one per language rather than one name to
  hold. Nothing requires the aggregate and this does not ask that
  anything should -- that rule lives outside the tree and
  `REPOSITORY.md` reads it back from the endpoint; what lands here is
  the option, which is what the ceiling on concurrent jobs had cost.
  The OpenSSF Scorecard's `SAST` check reads the same trigger, asking
  whether the analysis ran on the commits of merged pull requests. The
  concurrency group takes the pull request's number where there is one,
  and both jobs take the draft and closed conditions every job of
  `test.yml` carries, so a closed run cancels the run its own group
  holds rather than the analysis of the merge commit.
  `bitcoin-core-rpc` carries this shape.

### The gate

- **`[tool.ruff.format]` excludes `*.md`** (closes #397). `ruff format`
  reads the python fences of a markdown file and reflows them; `ruff
  check` does not read markdown at all, `ruff check --show-files .`
  listing no `.md` and `ruff check SECURITY.md` answering "No Python
  files found". The gate reaches those fences through neither, both
  ruff-pre-commit hooks carrying `types_or: [python, pyi, jupyter]`, so
  a bare `ruff format .` from the repository root reformatted
  `SECURITY.md`'s fenced examples -- collapsing the extra spaces that
  align their trailing comments -- with nothing red anywhere to say the
  tree had moved. The key is under `format` rather than in
  `[tool.ruff]` above because that is the scope the two commands
  measure, and it is there at all for the reason `[tool.typos.files]`
  gives beside its own: the bare invocation answers what the hook
  answers.

- **`show_error_codes` leaves `[tool.mypy]`** (btclib-org/.github#191).
  mypy has error codes on: `Options` carries `hide_error_codes`, `False`
  before any configuration file is read, and no `show_error_codes`
  attribute at all -- `config_parser.py` accepts that key only through
  its generic `show_`/`hide_` inversion, and `mypy --help` writes the
  spelling that changes the default, `--hide-error-codes`. Section 6 of
  the organization standard drops the line from its sample for that
  reason and keeps `show_column_numbers`, whose default is `False`.
  Measured on the mypy `uv.lock` pins, against a file with one
  incompatible return: the diagnostic and its `[return-value]` code are
  byte for byte the same with the key and without it.

- **`pyroma` builds this project with a backend `[build-system]` admits,
  and runs on pre-commit.ci** (btclib-org/.github#197). Section 12 asks
  that a hook building the project build it with the backend that
  declaration admits. pyroma reads the metadata through `build`, whose
  non-isolated path imports the backend out of the hook's own
  environment, so the hook carries `additional_dependencies:
  ["hatchling>=1.27"]`, which is `[build-system]`'s own specifier. That
  path checks nothing beyond the backend it imports: the hook
  environment holds hatchling and pyroma's own dependencies and neither
  the cffi nor the cmake requirement declared beside it, and

  ```shell
  PIP_NO_INDEX=1 uv run --locked --only-group lint \
      pre-commit run pyroma --all-files
  ```

  passes. With the line removed the same command dies in pip, the
  traceback ending in the isolated fallback installing what
  `[build-system]` requires -- the network pre-commit.ci does not give.
  So `pyroma` leaves the `ci:` block's `skip:` list, where
  `submodule-pin` stays for the reason its own comment gives, and
  `REPOSITORY.md`'s paragraph on that list names the hook it holds.

- **`enable_error_code` is the organization's list**
  (btclib-org/.github#165). Section 6's optional mypy error codes are one
  list, the same in every repository that runs mypy; this tree's carried
  `narrowed-type-not-subtype`, which the locked mypy reports under bare
  `--strict` with no code enabled at all, and lacked `explicit-override`
  and `unused-awaitable`. The comment beside the array now names the
  standard instead of walking a survey of this tree and a comparison
  against btclib's, a per-tree survey being the rule that let the lists
  drift. `explicit-override` is the one code of the two with findings
  here, every one a method of the build backend overriding
  `FFIExtension` or hatchling's `BuildHookInterface`: those methods carry
  `@override`, from `typing` at 3.12 and from `typing_extensions` below
  it, so `[build-system] requires` gains `typing_extensions` under a
  `python_version<"3.12"` marker -- resolved at build time and pinned by
  no lock file, like everything else in that array. The mypy hook
  declares the same package among its additional dependencies, what the
  checked files import being declared there.

- **The test modules are `*_test.py`, and `name-tests-test` runs at its
  default** (btclib-org/.github#131). Section 7 of the organization
  standard states one spelling and names the hook that enforces it at
  its default; this tree was `test_*.py` throughout and passed
  `--pytest-test-first` to hold the hook to that. Every module under
  `tests/` is renamed with `git mv`, the argument is gone, and every
  reference in prose, comments and workflows names the new file --
  `git grep -P '\btest_[a-z_]+\.py\b'` answers with `CHANGELOG.md`
  alone, whose earlier entries record the names as they were. Both
  spellings are pytest's default collection patterns, so no test is
  collected or dropped by the move; what it buys is a `git grep` that
  keys on one pattern across the organization. `.secrets.baseline` is
  regenerated with the command `CONTRIBUTING.md` gives, and differs from
  the one before in the filenames and nothing else.

- **`pretty-format-json` runs, over the hand-written json**
  (btclib-org/.github#130). It was off with a comment saying the only
  json tracked here was the two `ecdsa_*` vector files; the tree has
  tracked the BIP327 and BIP352 vectors and `.claude/settings.json`
  since. The hook now runs
  with `tests/` excluded as a directory -- every json there is an
  upstream vector `tests/README.md` pins to a blob sha and a verdict,
  which a reformat would void silently -- and `.vscode/` excluded for the
  reason `check-json` gives, so what it formats is the hand-written file,
  and `check-hooks-apply` has a subject to see.

- **`toml-comment-width` and `decoded-subprocess-encoding` run**
  (btclib-org/.github#134). Section 4 of the standard lists both local
  hooks without a condition and this tree ran neither. The first holds a
  toml comment to 80 columns, a trailing unbreakable link exempt; every
  comment in `pyproject.toml` was already at the width, by reading. The
  second refuses `text=True` and `universal_newlines=True` on a child
  process, which decode with the locale's encoding: the call sites, in
  `tests/extension_test.py`, `tests/mutation_counts_test.py` and the
  scripts under `.github/scripts` that parse what a child printed, pass
  `encoding="utf-8"` instead -- the same text mode, named.

- **`CHANGELOG.md` stops asking for the blank line a union merge drops**
  (btclib-org/.github#138). MD022 and MD032 are off for this file alone,
  by a comment at its head and not by an edit to `.markdownlint.jsonc`,
  which is section 14's verbatim copy: a rebase of two branches that
  each appended a section joins them without the blank line between, and
  the rule would then fail the gate on a file that never conflicted. The
  comment says when it goes back on.

- **`CLAUDE.md`'s roster of the gate names only what gates** (issue
  #323). It said "`lint`, `docs`, `test` and `codeql` are the gate", and
  `codeql` is none of it: the endpoint returns three contexts, and the
  workflow has no `pull_request` trigger at all, so there is nothing for
  a branch rule to require and nothing a merge could wait on. The claim
  sat a few lines under the paragraph stating the required checks
  correctly, and that adjacency is what made it worth fixing rather than
  leaving: `REVIEWING.md` now has a reviewer *rely* on those runs where
  they are on the record, so a file naming a fourth one turns a
  documented reliance into a wrong one — a reviewer waiting for a run
  that will not come, or acking on one that holds nothing. It is also
  wrong in the direction nobody audits, claiming more is gated than is.
  What replaces it says where `codeql` does run, the push to `main` a
  merge creates and the weekly cron, which is what its own `on:` block
  argues at length. The `release` half of the sentence was sound and
  keeps its reasoning, with "the merge gate has already scanned"
  corrected to the analysis that actually reads that tree.

- **Coverage measures `tests/` as well as the package**
  (btclib-org/.github#7). `[tool.coverage.run] source` named
  `btclib_secp256k1` alone, so the one thing the 100% ratchet said
  nothing about was the suite enforcing it: a helper no test calls and a
  branch no fixture takes are dead code carrying the authority of a
  test. `source = ["btclib_secp256k1", "tests"]` is what the sibling
  repositories already name, and it found four gaps here rather than
  none.

  Two are closed by a test that had been missing. `point_add` in
  `test_vectors.py` is the independent arithmetic the recovery id 2 and
  3 fixture is built against, and its only caller, `point_mul`, never
  hands it the identity on the right nor two points that cancel -- so
  the group law's two special cases were reference code nothing
  exercised, and a reference that is wrong is wrong in a way no vector
  reports. `_calls` in `test_secret.py` reads a call whose function is
  neither a name nor an attribute and answers nothing for it, which is
  precisely the blind spot the population of
  `test_every_function_that_takes_a_secret_out_offers_into` is defined
  by: a producer invoked as `table[key]()` is not in it. The new test
  runs the helper as well as reading it, so the pair of assertions is a
  finding -- the secret does come out, and the walk reports no call --
  rather than a restatement of the code. It is a module-level function
  for a reason worth recording: `inspect.getsource` of a nested one
  answers an indented block, which `ast.parse` refuses outright.

  The other two are `raise AssertionError`, in the stubs
  `test_submodule_pin.py` and `test_verified_signing.py` substitute to
  prove a path is never taken. No test can cover those lines, and the
  reason is stronger than reachability: executing one is the run in
  which the suite is red, so a green run cannot reach it and no amount
  of testing would. They join `raise RuntimeError` in `exclude_also`,
  which is the same argument the entry above them already makes. The
  package raises no `AssertionError`, so nothing shipped is excluded by
  it. `# pragma: no cover` twice was the alternative, and it records the
  decision once per occurrence instead of once.

- **`check-shebang-scripts-are-executable` is on** (btclib-org/.github#7).
  It sat commented out beside `check-executables-have-shebangs` under
  one comment covering both, and that comment was right about one of
  them: `git ls-files -s` reports mode 100644 for every path here, so a
  hook selecting on `types: [text, executable]` matches nothing and
  `check-hooks-apply` would say so. Its converse selects on
  `types: [text]` alone and matches every file in the tree whether or
  not any carries a shebang, so the same measurement enables it rather
  than excluding it -- what it enforces is the pair, and the day a file
  needs a shebang it also needs `chmod +x`.

  That no file has one today is a fact about how these scripts are
  invoked, not an omission: hatchling `exec()`s `scripts/hatch_build.py`
  and `scripts/cffi_build.py` from inside the build,
  `scripts/README.md` gives the in-place build as `uv run python
  scripts/cffi_build.py`, and the three under `.github/scripts/` run as
  `python .github/scripts/<name>.py` from `.pre-commit-config.yaml` and
  the workflows. The caller names the interpreter every time, so a
  shebang would announce one nothing consults -- and, unpaired with the
  execute bit, would cost this guard. `fix-byte-order-marker`, the
  entry of the same shape, was already on.
- **`check-dist` gains a wheel-content check**,
  `.github/scripts/verify_wheel_contents.py`, closing this repository's
  half of btclib-org/btclib#1160: `check-wheel-contents`, configured
  here since `ignore = ["W003", "W009"]` entered `pyproject.toml`, reads
  metadata and a wheel's declared top level; it has no way to say a
  member is present and zero bytes, and `--package btclib_secp256k1`
  -- the flag that would diff the wheel's package tree against this
  checkout's -- reports the compiled artifact every wheel this project
  ships as "not in package tree" whether or not it belongs, since that
  artifact sits beside `btclib_secp256k1/` rather than inside it. The
  new script asks both questions by hand instead: that
  `btclib_secp256k1/` in the wheel is exactly what this checkout's own
  directory has, and that the kind-appropriate top-level artifact -- one
  compiled extension for a static wheel, the ABI-mode module and the
  shared `libsecp256k1` for a dynamic one -- is there and not empty.
  `docs/source/package-content-policy.md` states the policy in prose,
  and `tests/test_wheel_contents.py` compares it against the script's
  own constants in both directions, the same pairing `btclib`'s sibling
  script and page keep. The sdist is not this script's subject:
  `[tool.hatch.build.targets.sdist] exclude` here is an exclude list
  rather than `btclib`'s include one, so the failure `btclib`'s own
  script answers for -- a file the tree gains and the manifest does not
  name, silently absent from the archive -- does not arise the same way,
  and modelling the members the vendored `secp256k1/` submodule alone
  contributes would be an allowlist nobody could maintain for a
  question `exclude` already answers by construction.
- **A `local-link-prefix` hook refuses a local markdown link
  destination that does not begin with `./`, and every link here now
  begins with one** (btclib-org/.github#20). `docs.yml` greps the built
  html for `href="#./`, which is what myst renders in place of a link
  `docs/source/conf.py`'s `RootFileLinks` transform cannot resolve. One
  pattern can key on one spelling, and this repository wrote two:
  `CHANGELOG.md`, `RELEASE_NOTES.md`, `REVIEWING.md` and one line of
  `CONTRIBUTING.md` wrote `./REVIEWING.md`, while the rest of
  `CONTRIBUTING.md` and all of `CLAUDE.md`, `RELEASING.md` and
  `REPOSITORY.md` wrote the bare name -- so a link of the second kind
  breaking rendered an anchor the grep was not looking for. Rewriting
  those is the smaller half of this; the hook is what keeps the drift
  from coming back, and it is the same hook in every repository of the
  organization, `pinned-rev`'s arrangement rather than a shared hook
  repository that does not exist.

  The rule is the prefix and not the extension, and the table in
  btclib-org/btclib#1175 is what decides that: `DOES_NOT_EXIST.txt`,
  `sub/DOES_NOT_EXIST.md`, `DOES_NOT_EXIST` and `../DOES_NOT_EXIST.md`
  each reach MyST's fallback and each is missed by the union of both
  greps, so an `.md`-scoped rule would leave all four writable. `../`
  is the row with nothing downstream behind it at all: the transform
  *declines* a target normalizing above the repository root, so that
  shape reaches the fallback by design and renders `href="#../X.md"`,
  which the surviving grep does not match and should not be widened to
  reach — the hook is the only place it can be caught. A link reference
  definition, `[label]: page.md`, renders the same fallback and carries
  no `(`, so the pattern has a second branch for it, anchored at the
  start of a line so that a reference *use* followed by a colon is not
  mistaken for one.

  Measured here too, by building this documentation with an
  unresolvable link written each way: `./page.md`, `./page.md#anchor`,
  `./page.txt`, `./sub/page.md` and an extensionless `./page` each
  render `#./` followed by the destination, so the one grep sees them
  all; the same destinations without the `./` render the destination
  alone, which no pattern reaches without also matching the autodoc
  anchors these pages carry. `CONTRIBUTING.md`'s link to the README's
  Build section was a live instance of the gap -- an anchor after a bare
  name, where the bare-name grep's character class stops.

  A badge, `[![alt](src)](href)`, needed the pattern's link text to step
  over the image inside it: written `[^]]*` it stops at the `]` closing
  the alt text, so the scan checked the image `src` and never the
  badge's own destination -- measured on the built html, where a badge
  href renders exactly what a plain href renders. Link text is
  therefore `(?:[^]]|\]\([^)]*\))*`, which reaches the destination
  behind the image and still checks the `src` by backtracking. This
  repository's `README.md` and `CONTRIBUTING.md` carry badge links, none
  of them violating the rule.

  `uvx pre-commit run local-link-prefix --all-files` re-derives the
  whole of it.

- **The `typos` hook is `repo: local`, pinned through
  `additional_dependencies: [typos==1.49.0]`, rather than a
  `crate-ci/typos` mirror pinned by `rev:`** (issue
  btclib-org/.github#399). `autoupdate` walks every `repo:` entry except
  `local` and `meta`, and `crate-ci/typos` re-tags a moving `v1` alias
  onto the same commit as each release, which `git describe --tags`
  then names by creation date -- `autoupdate` would propose that alias
  on every run and `pinned-rev` above would refuse it on every run, so a
  mirror entry here can only ever answer that refusal, never converge.
  `language`, `entry`, `args` and `types` are upstream's own typos hook
  definition, copied in rather than fetched, matching
  `btclib-org/.github`'s own `.pre-commit-config.yaml` byte for byte.

- **`tests/conventions_test.py`'s `_CONVENTIONS` carries section 7's
  last bullet, "the suite opens no socket", and `tests/README.md` places
  it under "Not tested here" with the reason** (issue
  btclib-org/.github#458). The tuple is the vocabulary the declaration
  is written in -- a name outside it fails the check -- so a tree short
  a bullet can put that convention in neither half of the declaration,
  and the suite stays green while what it asserts is a bullet behind.
  Not tested rather than tested because section 7 asks for a walk over
  the call sites and there are none: `git grep -lw socket -- '*.py'`
  answers `tests/conventions_test.py` alone, the tuple entry itself,
  where the same command with `subprocess` names the files that start
  one and is the control that the pathspec reaches code. Neither file's
  prose states a total any more, the tuple being what a reader counts.

### Packaging metadata

- **`check-sdist` gates the sdist against what git tracks** (#344).
  Section 12 of the organization standard asks it of every repository
  that builds an sdist, and this was the one tree the standard's own
  exemption used to cover, on the strength of an exclude-list archive
  rather than an allowlisted one. Run with `--installer=pip`, which
  reads this hook's own environment rather than resolving `uv`
  regardless of what `[build-system]` declares, and
  `additional_dependencies` is that table's `requires` verbatim: `build
  --no-isolation` checks the whole of it before calling the backend,
  packing an sdist asking nothing of the cffi and cmake requirements
  themselves. `--inject-junk` found seven common OS and editor droppings
  `.gitignore` did not stop from reaching the archive --
  `.Spotlight-V100`, `.Trashes`, `Thumbs.db`, `ehthumbs.db`, a vim swap
  file, an AppleDouble sidecar and the wildcard spelling of `.DS_Store`
  that plain `.DS_Store` in `.gitignore` does not match -- now excluded
  in `[tool.hatch.build.targets.sdist]` beside the build
  artifacts the same table already kept out. `.python-version` is the
  one tracked file `[tool.check-sdist]`'s `git-only` now names on
  purpose: both tracked and `.gitignore`-matched, it pins the
  interpreter a checkout resolves against, which is the only place
  anything reads it.

- **`COPYRIGHT` leaves the wheel and the sdist** (btclib-org/.github#135).
  That issue decides that every package of the organization ships the
  same license files and `COPYRIGHT` is not among them: the holder a
  consumer needs is in `LICENSE`, and `COPYRIGHT` is the source of a
  source-file header rather than a statement to a consumer. So
  `license-files` is `["LICENSE", "AUTHORS.md"]`, and because hatchling's
  sdist target ships every tracked file unless told otherwise, the file
  is named in that target's `exclude` too. Measured on `uv build` before
  and after: the wheel's `dist-info/licenses/` loses `COPYRIGHT` and the
  `License-File:` line for it leaves `METADATA` and `PKG-INFO`; the sdist
  loses `COPYRIGHT` and `CODE_OF_CONDUCT.md` (above) and nothing else.
  `WHEEL_LICENSE_FILES` in `.github/scripts/verify_wheel_contents.py`,
  `tests/test_wheel_contents.py` and the page under `docs/` that states
  the script's constants say the same set, and the verifier, `twine
  check --strict`, `check-wheel-contents` and `pyroma --min 10` each
  exit 0 on the new archives.

- **`[project].name` takes the canonical hyphen** (btclib-org/.github#277).
  It was declared `btclib_secp256k1`, the import package's own spelling,
  where the organization standard's section 3 asks every publisher's
  `name` for PEP 503's hyphen regardless of what the import package
  takes. The wheel filename and the `.dist-info` directory are
  unchanged: PEP 427's escaping rule already folds either spelling to
  the same `btclib_secp256k1-<version>`, and `uv.lock`'s own package
  record already carried the hyphenated form before this change.

### The release path

- **A `public-api` job runs `griffe check` against the tag before the
  one being cut** (issue #387, btclib-org/.github#326), converging on
  `btclib`'s own job of the same name. Section 12 of the organization
  standard puts this in the release path rather than on a merge gate: a
  pull request breaks the public surface deliberately before 1.0, and a
  gate reporting every such break has nothing to say about which of them
  are allowed, where the release path's answer arrives while
  `RELEASE_NOTES.md` is already being written. griffe does static
  analysis rather than importing the package, so the job needs no C
  toolchain, no submodule checkout and no built extension: measured
  against a bare checkout of `v0.8.0.4`, the comparison succeeds
  unbuilt. `_btclib_secp256k1`, the compiled cffi extension
  `__init__.py` imports, is a leading-underscore name and is out of the
  public surface griffe compares on either side of the comparison,
  `stubs/_btclib_secp256k1.pyi` on the search path or not, both measured.
  `-s . -s src` is what carries the comparison across "The package sits
  under `src/`" above: measured clean between `v0.8.0.4`, with
  `btclib_secp256k1/` at the repository root, and a `src/`-layout tree.

- **`build-sdist` pins the sdist's `mtime` to the tagged commit's date**
  (#345, btclib-org/.github#140). Section 12 of the organization
  standard asks every publisher for a `SOURCE_DATE_EPOCH` step and a
  normalizing one regardless of what its own backend already does, one
  process across the three repositories rather than one bounded by
  whichever backend happens to need it; `RELEASING.md` used to explain
  the absence of both by a `setuptools.build_meta` backend neither
  sibling has carried since before this file was written, and by a
  script it called a no-op, which the standard's own correction on
  btclib-org/.github#140 withdraws -- the step does not sit over a value
  that is already right, it replaces one. Measured before this change:
  hatchling's sdist writer stamps `1580601600` on every member when the
  variable is unset, `1580601600` being neither the moment of the build
  nor the tagged commit's date, and honours the variable exactly when it
  is set. `.github/scripts/normalize_sdist.py` is the siblings' script
  cut down to the one field hatchling does not already write this
  repository's way: measured with `tarfile.getmembers()`, ownership is
  already `uid`/`gid` `0` and `uname`/`gname` `""`, and mode is each
  member's own git-tracked executable bit -- `secp256k1/autogen.sh` and
  the small set of vendored tools beside it stay executable on a plain
  extract, which flattening mode to one constant would have undone.
  `tests/normalize_sdist_test.py` covers the script the way the
  siblings' own does. `RELEASING.md`'s "Rebuild a release from its tag"
  runs both steps now, and no longer explains their absence.

- **A `documented` job asks read the docs whether it built the tag**
  (closes #295). It waits for
  `https://btclib-secp256k1.readthedocs.io/en/<tag>/` to be served and is
  red if it never is: green means the release has a permanent URL of its
  own, which is the one to link wherever the version is named.
  `/en/latest/` answers 200 regardless, serving the last build that
  succeeded whatever that was, so an eye on the site cannot catch a tag
  that was never built. The rendered URL rather than the v3 API, which
  would put a credential in a job that gates nothing; and nothing needs
  the job in return -- a late documentation build is no reason to
  withhold a wheel, and the fix for a red run is a build on read the
  docs' side rather than a moved tag. That property is what made the
  ordering matter: `github-release` carries the `always()` that keeps a
  skipped ancestor from swallowing it, so a job able to fail the run is
  not one more way to lose the GitHub release. What no pull request here
  can supply is the automation rule that activates a tag on read the
  docs' side, a dashboard action tracked at btclib-org/.github#26 —
  which is why this job asks the site rather than asserting anything
  about the rule: what a run can see is whether a tag is served, and no
  sentence here states what somebody else's dashboard holds on the day
  it is read. `RELEASING.md` gains the step that reads
  the job's verdict, saying what a red there means and what it does not,
  and `.readthedocs.yaml` names the job instead of calling the check
  blocked.

### `notice-rgx` derives from `COPYRIGHT`

- **A test compares them** (#346, btclib-org/.github#135). `CPY` checks
  every source file's header against `[tool.ruff.lint.flake8-copyright]`'s
  `notice-rgx`, which is `COPYRIGHT`'s text transcribed by hand as a
  regex, and nothing checked the regex against the file it was
  transcribed from: a `COPYRIGHT` edited without the regex, or the
  other way round, passed every gate. `tests/copyright_test.py` now
  derives the expected pattern from `COPYRIGHT` itself and asserts
  equality, deliberately narrower than `re.escape` for it: that
  function's own special-character set is the same across every
  CPython and PyPy version this package supports, but is
  unconditionally wider than what's committed -- it also escapes `#`
  and whitespace, for `re.VERBOSE` safety, where `notice-rgx` does not
  -- so deriving through it would fail this test's round trip on every
  supported interpreter alike, not on some of them.

### `README.md`'s badge head follows section 2's fixed order

- **`wheel`, `implementation` and `github/v/release` join the badge
  block, and every remaining badge takes its place in the order section
  2 of the organization standard fixes, sentinels included for every
  weekly workflow this tree runs** (issue #387, btclib-org/.github#338).
  `wheel` and `implementation` read `img.shields.io/pypi/wheel` and
  `img.shields.io/pypi/implementation` off the files a release uploaded;
  `github/v/release` reads the forge rather than the index, next to the
  PyPI version badge it is paired with. Every badge path naming the
  distribution now takes PEP 503's hyphen, `btclib-secp256k1`, rather
  than the import package's `btclib_secp256k1` -- the version,
  downloads, development-status and supported-Python-versions badges
  and the PyPI and pepy links beside them. The documentation-build badge
  image now points at `app.readthedocs.org`; `readthedocs.org` answers
  that path with a redirect to it.
- **The `scorecard` sentinel joins the row, last among the sentinels**
  (issue #387, btclib-org/.github#338). Not in calendar order with the
  rest: btclib-org/.github#358 is the open question of whether a
  Scorecard badge's place is a stated rule or each tree's own reading of
  a silent one, and `btclib` and `portanode` both currently place it
  last regardless of whether their own calendar row exists yet -- this
  matches that precedent rather than deciding #358 unilaterally.

### `docs/_build/` leaves `.gitignore`

- **`.gitignore`'s `docs/_build/` entry is gone** (issue
  btclib-org/.github#411). `build/` already
  covers `docs/build/html`, the directory the documented `sphinx-build`
  command in `CONTRIBUTING.md` and `docs.yml` writes to:
  `git check-ignore -v docs/build/html/index.html` names `build/` as the
  matching pattern, and `docs/_build/` matches none of it.

### `README.md` drops the badge linking to the repository

- **The badge row's link to the repository on GitHub is gone** (issue
  btclib-org/.github#381). Section 2 of the organization standard
  refuses it now: the badge renders the repository's name because the
  URL says so, and the row is an audit, so the item that measures
  nothing is the one that does not belong in it. `[project.urls]`'s
  `repository` key already carries the same link for the reader who
  meets this file as the long description an index renders or as the
  `README.md` an unpacked sdist carries.

### `README.md` names the vendored libsecp256k1 release

- **The `Versioning` section names the pinned release as a link to the
  upstream tag** (closes #428). `check_submodule_pin.py` reads that link
  out of `README.md` and exits 1 where the file links to no release at
  all, which fails the `submodule-pin` hook and with it the lint gate, a
  required check, for every branch; `release.yml`'s `version-check` job
  and `vendored-vectors.yml`'s `pin` job read the same line with the same
  expression. It stands where the numbering rule's parenthetical example
  was, that example naming the same version without linking it, and ahead
  of `The name`, the section that names an older release: what each of
  those checks reads is the first link in the file.

### The sentinel schedules are section 10's calendar, in family order

- **Every `cron:` here fires at the instant section 10's calendar gives
  that workflow and this repository** (issue btclib-org/.github#480). The
  calendar's rows sit in the order of what they ask about -- the data a
  tree ships and did not write, the depth its suite is tested to, what it
  depends on and what it publishes, its platforms, its own health and its
  security -- so a workflow's day and hour follow its family. The minute
  is this repository's row in that section's second table, and it does not
  move. `dependabot.yml` is untouched, section 10 keeping `deps-latest` on
  the day before Dependabot's own. The comments beside the schedules
  follow: no header names a day the calendar does not give the workflow it
  sits in, and `tests/mutation_counts_test.py`'s docstring names no day at
  all, a weekly session being read whenever it runs.

- **`README.md`'s badge block is section 2's three groups** (issue
  btclib-org/.github#480). What the software is opens with the release
  identity as a pair, the PyPI version beside `github/v/release`, which is
  how section 2 says those two are read: where they disagree, a release
  reached the forge and not the index. The licence and `wheel` sit in that
  group, this tree having a `LICENSE` and publishing wheels, and section 2
  derives the row from such properties rather than curating it. The CI
  group is the gates in the order a commit meets them, Read the Docs among
  them because it answers `passing`, `failing` or `unknown` as the
  workflow badges around it do, and then the sentinels in the calendar's
  order -- so the badge order is the calendar order over that subset, and
  the two move together or not at all. The Scorecard badge is the OpenSSF
  group, and section 2 reads it as the last of the sentinels without being
  among them, `scorecard` being the calendar's last row.

### What the workflow table and the `paths` filter name

- **`CONTRIBUTING.md`'s workflow table carries a `scorecard` row, and
  the sentences around it that claim an exception name it** (closes
  #413). That workflow runs on `main` and on its weekly schedule and
  takes no `workflow_dispatch`, its triggers being
  `ossf/scorecard-action`'s rather than section 10's; it gates nothing
  and could not, producing no pull request run for a branch rule to
  name, and what it finds arrives as code scanning alerts beside
  CodeQL's. `REPOSITORY.md`'s *Token permissions* names every job that
  asks for more than the read-only default, with the anchored `git grep`
  that re-derives them beside it, where it had named `release.yml` as
  the only workflow asking at all, and its *Required checks on main* say
  why that workflow is outside the rule, it carrying no `pull_request`
  trigger to produce a context; `codeql.yml`'s own comment stops
  claiming that same exclusivity for its `security-events: write` and
  points at the permissions section.
- **The gate block makes the vendored submodule a precondition of all
  three gates rather than of the documentation build alone** (closes
  #422). Installing this package compiles libsecp256k1 out of
  `secp256k1/`, so the test and documentation commands cannot build the
  environment without it, and the lint gate, which installs no project,
  needs the vendored clone all the same: `submodule-pin` resolves the
  release `README.md` names in that clone's own refs, which is what lets
  the hook run offline. A `git worktree` starts with that directory
  empty however complete the checkout it was made from, and a worktree
  is the path this repository puts a session on. The documentation job's
  own copy of the command goes with the hoist.
- **`vendored-vectors.yml`'s `paths` filter is unchanged, and its header
  now says what weighs it** (closes #424). Section 10 of the standard
  weighs a `paths`-filtered `pull_request` on a calendar workflow by the
  wait one run adds to the checks a pull request already has, rather
  than by how many branches the list selects. Every path in this one is
  a path `test.yml`'s `prose` pattern does not exempt, `README.md`
  included, so a branch the filter selects is running the wheel and
  suite matrix regardless, against a run here that is a script and a
  keyserver fetch. The table's row for the workflow says a pull request
  touching what it reads, where it said a change to itself.

### A heading with no block is reported, and the version link names its hazard

- **`check_vendored_vectors.py` lists a `###` heading owning no fenced
  block under `skipped`, and `README.md`'s prose declaration of the
  wrapped libsecp256k1 release now says, where the three checks that
  parse it are, why it is prose and what breaks it** (closes #415, #429).
  `_entries_at_tip` only ever named a heading from inside the loop over
  fenced blocks, so a heading with none of its own -- a group heading
  superseded by finer ones, or a pin whose block an edit broke -- was
  absent from both `entries` and `skipped`, contradicting the module
  docstring's own promise; it is now named under `(no fenced block)`,
  which of the two shapes it is being left for the reader, same as
  `btclib`'s copy does not yet do (btclib-org/btclib#1447). Separately,
  `check_submodule_pin.py`'s module docstring records why `README.md`
  stays the one declared value rather than moving to a fourth,
  machine-written place -- the submodule pin is already the machine's
  ground truth the prose is checked against -- and names the hazard left
  open by that choice: `_NAMED.search` and the two workflows' `sed |
  head -1` take the *first* matching link in the file, not the one under
  `Versioning` by name, so a second such link placed earlier would win
  silently. `release.yml`'s own copy of the expression points back at
  that paragraph, and `tests/submodule_pin_test.py` gains the reversed
  case: a link placed *before* the named one wins instead of being inert.

### The vendored-vectors sentinel reproduces, and its script has a test

- **`Running what CI runs` gives `vendored-vectors` a bullet, with the
  command for each of its two jobs** (closes #432). That section's own
  sentence says every sentinel but `links` runs locally, and this is the
  one it named nowhere. `check` is the script under the `--dry-run` the
  `pull_request` trigger passes, which is what a run by hand wants too,
  and `pin` is the keyserver fetch, the tag verification and the two
  commits whose agreement is the answer. What the bullet says past the
  workflow's own lines is where a local run differs from a runner's:
  `--recv-keys` writes into whichever keyring it is pointed at,
  `fetch --force` moves the named tag inside the vendored clone, and
  `${named}` is braced because zsh reads the `:r` of the unbraced form
  as a history modifier and fetches a ref upstream does not have.
- **`tests/vendored_vectors_test.py` holds `check_vendored_vectors.py`
  to the report its module docstring promises** (issue #434). The README
  sample it parses carries one entry of every shape the parser tells
  apart, so a shape that stops being recognised moves a heading between
  `entries` and `skipped` instead of leaving it out of both — a pin the
  report then reads as checked and clean, which is what #415 was. Each
  outcome of `report` is asserted as the `gh` subcommand it reaches for,
  with both subprocess boundaries stubbed: what the script asks upstream
  and what it writes on an issue are not a suite's to run. The
  entry-point guard is reached through `runpy` rather than through a
  subprocess, which would run those lines in an interpreter nothing here
  measures.

  The other half of that issue stays open, `.github/scripts` being
  outside `[tool.coverage.run]`'s `source` still.
  `coverage run --source=.github/scripts` over the whole suite is what
  says why that is not one diff with this: every line and branch of this
  script is reached and the scripts beside it fall short, so moving the
  ratchet over the directory is a decision about them rather than about
  this one.

### The downloads badge links to the plural pepy URL

- **The downloads badge's link target is
  `pepy.tech/projects/btclib-secp256k1`** (closes #436). Section 2 of
  the organization standard fixes the plural; the singular answers `308`
  and reaches the page only for as long as pepy goes on forwarding it,
  which is a dependency on somebody else's redirect and is recorded
  nowhere here. That is the reason that section gives for the Read the
  Docs host it fixed the same way. The image,
  `static.pepy.tech/badge/btclib-secp256k1`, is section 2's own spelling
  and does not move.

### The distribution's name is hyphenated where a requirement writes it

- **`README.md`'s move-off-the-old-name block and the two install
  commands in `RELEASING.md` spell the distribution `btclib-secp256k1`**
  (closes btclib-org/.github#524). Section 3 of the organization
  standard makes the hyphen the canonical spelling and asks a
  requirement for it wherever it is written, a block somebody is meant
  to copy included; PEP 503 folds the two spellings before a resolver
  matches, so what the written form decides is what a reader copies out
  and types. The sentence introducing that block says which spelling
  each of the two edits takes, the import package keeping its
  underscore.

### The normalization step is this file's, the property section 12's

- **`RELEASING.md`'s *Rebuild a release from its tag* names the property
  — a published sdist reproduces from its tag — as section 12 of the
  organization standard's, and the steps between the tag and the archive
  as this file's** (closes #441). That section asks a `RELEASING.md` for
  those steps with the reason beside each, so replacing one of them is a
  change here and not there. Its refusal of the other reading stands
  beside it: a publisher does not weigh whether its backend has made a
  step redundant.

### `pyproject.toml`'s `homepage` names this tree's own documentation

- **`[project.urls] homepage` reads `https://btclib-secp256k1.readthedocs.io`,
  matching `documentation`** (issue btclib-org/.github#533). A releasing
  tree provides documentation, and its home is that documentation rather
  than `btclib.org`, a sibling's project page. `documentation` stays: an
  index showing the two fields as one link is cheaper than the field
  tools read for that purpose specifically.

### `REPOSITORY.md` reads private vulnerability reporting back

- **A `Private vulnerability reporting` section carries the `gh api
  .../private-vulnerability-reporting` call and its `{"enabled":true}`
  answer** (issue btclib-org/.github#468). The organization standard's
  *Root files* section makes the setting every tier's regardless of
  which tier owns `SECURITY.md`, and a record silent about it could not
  have shown the setting turned off. The topics already carried their
  own readback, the `diff` against `pyproject.toml`'s `keywords` further
  up this file.

### `dev` reaches every group this tree declares

- **`pyproject.toml`'s `dev` group now includes `check` and `mutation`
  alongside `test`, `lint`, `build` and `docs`** (issue
  btclib-org/.github#498). Section 1 of the organization standard's
  dependency-group table gives `dev` as every group above, and neither
  omission had that rule's own exception on it: `check` is what a
  scheduled or release job reads distribution files with and `mutation`
  is the scheduled mutation runner, but nothing about either tool
  installing conditions its resolution on the platform the way `fuzz`'s
  marker does, so a developer's `uv sync` reaches both for free. `uv.lock`
  moves with it.

### `REPOSITORY.md`'s Dependabot and topics claims are read back

- **The *Dependabot* section carries the `gh api
  .../automated-security-fixes` call and its
  `{"enabled":true,"paused":false}` answer** (closes #448). Dependabot
  security updates are a repository setting rather than a line in
  `.github/dependabot.yml`, so nothing in the tree could have shown the
  sentence claiming them on to be wrong. The *Plan-gated settings*
  section runs a call whose answer carries the same field and reads only
  the secret-scanning ones out of it, which is why this readback is the
  setting's own endpoint rather than a second copy of that call.
- **The *Topics* section's `sed` range keys on `keywords = [`, which is
  how `pyproject.toml` spells the assignment** (closes #449). The range
  read `keywords=[`, matched nothing, and left the `diff`'s right-hand
  side empty, so every topic came back as drift on every run and whether
  or not the two lists agreed — which they do. A sentence beside the
  command now says that an empty right-hand side is the `sed` and not
  the `keywords`.

### `REPOSITORY.md` says what it covers, and what it passes over

- **The file states its scope — the settings the organization standard
  asks about — in place of the blanket claim to be the whole of what is
  set outside the tree** (issue btclib-org/.github#551). Section 11 of
  that standard rejects the blanket claim because no command checks it:
  the repository document answers with fields the standard states no
  rule about, and telling those from the settings a repository decides
  is a reading. The perimeter left is section 16's checklist and the
  sections that state a rule, which the standard fixes rather than the
  endpoint.
- **A *What this file passes over* section at the foot says what falls
  outside that scope**, so that a setting the file is silent about reads
  as a decision rather than as an omission. It names the
  repository-document fields no call here quotes and the standard states
  no rule for, with the `grep` over the standard that shows the absence
  and the control that makes those zeros readable; the endpoints
  answering empty, an empty answer recording no decision; and what the
  scope reaches and this file does not, each with its issue — the
  default branch, issue btclib-org/.github#549, and the Read the Docs
  project, issue btclib-org/.github#564.

### Claims that nothing re-derived

- **`REPOSITORY.md`'s `gh api` calls name the repository instead of
  `gh`'s `{owner}/{repo}` placeholder** (closes #452). The placeholder
  resolves against whatever repository the shell is standing in, so a
  command copied out of a file whose whole subject is one repository's
  settings answers for the checkout it is pasted into, with nothing in
  the answer saying which one that was; the *Topics* section's `diff`,
  which reads `pyproject.toml` from disk on its other side, is the
  sharpest of them. The convention is stated where the calls are
  introduced, with the `grep` that says the file still holds to it, and
  `gh pr view` takes `--repo` for the same reason. The shared half of
  `CONTRIBUTING.md` keeps the placeholder, being the same file in every
  repository of the organization and able to name none of them.
- **`RELEASING.md`'s install checks, and the attestation check on the
  releases page, take the version from the tree** (closes #438). `uv
  version --short` reads what `pyproject.toml` declares, which
  `version-check` refuses to let a tag differ from, so the release check
  installs what was just published; the rehearsal's `.dev<run><attempt>`
  suffix is the only part of any of those versions still typed. What the
  install checks replace is `0.7.1`, which PyPI serves under the name
  this distribution was renamed from and not under this one, so the step
  that decides whether a release is good could not resolve; the
  attestation check named a `btclib_secp256k1-0.7.1.tar.gz` that the
  download beside it does not produce, the v0.7.1 release on this
  repository carrying the old name's sdist.
- **The install command in `README.md`, the one the bug form asks for,
  and the two prose lines naming the distribution spell it
  `btclib-secp256k1`** (closes #444). Section 3 of the organization
  standard asks the hyphen of a requirement wherever it is written, a
  command in a document included. The prose names the releases'
  versioning and the authors, which are the distribution's and the
  repository's; the underscore is the import package's, and stays
  wherever a module path or an artifact name is what is written. Where
  the name is written and no requirement is — a flag's value in a
  workflow and in `CONTRIBUTING.md`, a deployment URL, the tag message
  `RELEASING.md` asks for — it is untouched: whether the canonical
  spelling reaches those is btclib-org/.github#581.
- **`.lycheeignore`'s comment keeps its argument without counting the
  tree, and so does `links.yml`'s** (closes #440). Section 9 of the
  standard refuses a total nothing re-derives, and neither file could
  have reported its own going stale: what the ignore list says is prose
  to lychee, and the count sat beside the retry settings it justified.
  The weekly run is what answers it, and the comment points at the
  command that lists it.
- **`RELEASING.md`'s `gh` calls name the repository, and the `pypi`
  deployment branch policy is read back in one file rather than two**
  (closes #455). A release is carried out from a checkout of this
  repository, so the placeholder resolves correctly for whoever follows
  the file top to bottom; what it does not survive is a step copied out
  and run somewhere else, and the sharpest of those is a `PUT` merging a
  pull request by a number a sibling repository has too. The calls
  taking a run id or a pull request number named no target at all, which
  no `{owner}/{repo}` grep would have found; the convention is stated
  where the file opens, with the `grep` that catches the placeholder
  form beside it. The policy the one-time setup read back is
  `REPOSITORY.md`'s *Publishing* section's, that file being where a
  setting is recorded and this one where the procedure is.
- **`RELEASING.md`'s tagging step reads the tag from the tree** (closes
  #456). `uv version --short` gives what `pyproject.toml` declares and
  `version-check` fails a tag naming anything else, so the tag, its
  message and the verification before the push come from one reading
  rather than three substitutions. The two blocks that act on an earlier
  release — recreating one whose GitHub release was skipped, rebuilding
  one from its tag — keep typing theirs, that being which release is
  meant and not something the tree answers, and derive the file names
  beside it from that. `gh release create --verify-tag` guards the first
  of the two, aborting on a tag the remote does not carry rather than
  creating one from the default branch.
- **`REPOSITORY.md`'s probe paragraph says what its `grep` reaches, and
  what it does not** (closes #459). A `gh api` call carries the
  repository inside a REST path, which an unqualified one necessarily
  leaves behind for the placeholder grep to catch; `gh pr view` takes it
  in a `--repo` flag, which a call omitting the flag leaves nothing
  behind for that same grep to see. `RELEASING.md`'s own probe paragraph,
  closed under #455, states the identical pair of shapes.
- **`RELEASING.md`'s merge step fetches before it reads `origin/main`,
  and prints the commit it asks about** (closes #458). A merge pressed
  on GitHub moves the branch on the forge and leaves the checkout's
  `refs/remotes/origin/main` at the pull request's own base until
  something fetches, so `gh run list --commit "$(git rev-parse
  origin/main)"` asked about that base. What answers is the base's own
  `push` runs, green and carrying the same workflow names as the runs the
  step is waiting for. `gh run list` prints no column for the commit, and
  the title it does print is that commit's own subject, which says which
  commit answered only to a releaser who already knows the subject to
  expect. `git fetch origin` now runs first, and the sha is echoed before
  the `gh run list` call takes it.
- **`RELEASING.md`'s tagging step tags the commit `origin/main` names
  rather than `HEAD`** (closes #460). The step before it merges the
  release pull request on the forge, which moves `main` there and
  leaves the checkout on the release branch; a bare `git tag` defaults
  to `HEAD`, so the pushed tag named a commit the squash merge never
  puts on `main`'s own history, caught only by `release.yml`'s ancestry
  check after the push already ran. The tag now takes the same ref the
  step above already fetched, and its name still comes from this
  checkout's own `pyproject.toml` -- the two agree because the version
  bump is exactly the change that squash carried onto `main` unchanged.

### `check_vendored_vectors.py` no longer cites a closed `btclib` divergence

- **The module docstring drops the sentence claiming `btclib`'s own copy
  does not yet report a heading owning no fenced block, and states
  instead why the identical-skip-line collapse `btclib-org/btclib#1451`
  gave that copy is declined here** (closes #445). `btclib-org/btclib#1447`
  gave `btclib`'s copy the report this script's own docstring already
  promised; once it landed, citing it as still open made the sentence
  false. The collapse is declined because `tests/README.md` gives every
  heading here exactly one fenced block, so no skip line this script
  builds ever repeats -- a property of this file today, not a rule the
  parsing above enforces.

### The vendored-vector re-check drops a citation `#397` was never about

- **Neither `check_vendored_vectors.py`'s docstring nor
  `vendored-vectors.yml`'s header cites `#397` for matching `btclib`'s
  own copy** (closes #462, closes #465). `f509895` wrote that citation
  into both on 6 August; this tracker's `#397`, which is what a bare
  `#397` written here resolves to, was opened on 25 August and is about
  `ruff format` reformatting `SECURITY.md`. It is dropped rather than
  repointed: `0e74c1a`, which introduced `tests/README.md`'s pin
  convention that same day, cites no issue for it either.

### The coverage ratchet reaches `.github/scripts`

- **`[tool.coverage.run]`'s `source` in `pyproject.toml` names
  `.github/scripts` beside `btclib_secp256k1` and `tests`, so
  `fail_under = 100` admits nothing short of full coverage there
  either** (closes #434). `check_submodule_pin.py`'s `pinned_commit` is
  exercised directly in `tests/submodule_pin_test.py` rather than only
  through the stub every other test there substitutes for it, and its
  entry-point guard runs through `runpy.run_path` the way
  `tests/vendored_vectors_test.py`'s already does. `mutation_counts.py`'s
  `main` body and `enumerated_mutants` are reached the same way in
  `tests/mutation_counts_test.py`, alongside its existing subprocess test
  rather than instead of it: that one is what proves the script still
  runs the way its own docstring invokes it,
  `python .github/scripts/mutation_counts.py session.sqlite`, in an
  interpreter this suite measures nothing in. `verify_wheel_contents.py`'s
  all-clear branch is reached in `tests/wheel_contents_test.py` by a run
  over wheels with nothing to complain about, which its existing `main`
  tests never build.

### The release pull request opens the next version's sections

- **`RELEASING.md`'s release pull request closes the "work in progress"
  sections of `CHANGELOG.md` and `RELEASE_NOTES.md` and opens the next
  version's above them, in the one pull request** (closes
  btclib-org/.github#528). Opened in a pull request of their own after
  the release's, the sections were absent from `main` for as long as
  that pull request took to land, and a branch landing in between would
  have had nowhere but a release it is not in to file its entry, with
  nothing to say so. The version bump to the placeholder stays in the
  pull request that opens the next version, `version-check` comparing
  the tag against what `pyproject.toml` declares. Section 12 of the
  organization standard is the decision; this is its port.

### The verbatim files are the standard's copies, byte for byte

- **`.gitattributes` states the union price as section 9 of the
  standard does** (issue btclib-org/.github#423): the driver is a
  checkout's and the forge does not apply it, so a pull request whose
  `CHANGELOG.md` or `RELEASE_NOTES.md` overlaps its base is reported
  `CONFLICTING` however cleanly the pair merges locally, and a rebase on
  a checkout is what clears it.
- **`.markdownlint.jsonc` points at section 14 of the standard for who
  carries it** (issue btclib-org/.github#316), in place of an
  enumeration of trees.
- **`CONTRIBUTING.md`'s shared half is btclib-org/.github's** (issue
  btclib-org/.github#281): the half is replaced whole rather than each
  change applied by hand, a hand-written list of them being what comes
  up short. Among them, *The landing queue* points at `REPOSITORY.md`'s
  *Plan-gated settings* for the ceiling's figure (issue
  btclib-org/.github#412).

### `REPOSITORY.md`'s perimeter is section 11's

- **The scope statement carries section 11's three limbs in the
  standard's own words** (issue btclib-org/.github#582): the pronoun
  whose nearest antecedent was section 16's checklist now names the
  standard, and the third limb -- the settings a behaviour the standard
  describes rests on -- is what admits `has_issues` and `.visibility`
  below.
- **The opening no longer claims that nothing in the file is recoverable
  by reading the tree** (issue btclib-org/.github#571): the topics and
  `.homepage` have a copy in `pyproject.toml`, which *Topics* and *No
  website* already said, so the clause names those two and holds of the
  rest.
- **`.visibility` and `has_issues` are read back, under *Features***
  (issue btclib-org/.github#584, issue btclib-org/.github#550): section
  10's `scorecard` sentinel reads a public repository and nothing else,
  and `CONTRIBUTING.md`'s tracker rule rests on the issues switch. The
  foot stops listing `has_issues` among the fields the standard states
  no rule about.
- **`has_wiki` and `has_projects` are outside the perimeter** (issue
  btclib-org/.github#550), by section 11's sentence rather than by a
  grep of the standard, which no longer answers zero for either.
- **`squash_merge_commit_title` and `squash_merge_commit_message` are
  read back with the merge-method flags** (issue
  btclib-org/.github#568), with what section 11 sets them to beside the
  answer.
- **`.default_branch` is read back** (issue btclib-org/.github#549),
  under *Branch protection*, and the foot stops naming it as a gap; the
  Pages read-back was already in place.
- **The Read the Docs project is read back from its own API, under a
  section of its own** (closes btclib-org/.github#564): `latest` a
  branch following `main`, `stable` the tag `git tag` sorts highest, the
  active tags the automation rule's result, and the organization-wide
  GitHub App as the connection, with the repository's own hook list
  empty. The foot's paragraph quoting the retired webhook rule goes with
  it.
- **The Actions and Dependabot secret stores answer empty by the
  standard's decision, not for want of use** (issue
  btclib-org/.github#572): the token is the organization's, at
  `visibility=all`, so the two stores leave the facility bullet and get
  the organization store read back beside them.
- **The foot no longer lists which fields of the repository document
  the sections quote**, the sections being what says so.

### The free-threading classifier is a claim about the merge gate

- **`tests/interpreters_test.py` gates the `Free Threading` classifier
  on the merge gate running a free-threaded build** (closes #476, issue
  btclib-org/.github#577). Section 3 of the organization standard
  declares the classifier where the gate exercises that build and names
  the enforcement: the biconditional that gates the PyPy classifier,
  with the gate's own interpreters as its second side. That side is
  `test.yml` and not the platform sentinels, whose `3.14t` cell runs
  beside a landing and blocks nothing — a sentinel passing is the ground
  the standard declines. Neither side holds in this tree, so the test
  lands green, and it goes red on whichever side moves alone.

### The release's publish jobs opt back in past a red `public-api`

- **`publish-testpypi`, `publish-pypi` and `published` open their `if:`
  with `always()` and name the results they do require** (issue
  btclib-org/.github#484). `public-api` exits non-zero on any break in
  the public surface since the last tag, which is what a cycle with
  breaking changes produces by design, and a bare `needs:` refuses to
  start a job whose listed dependency failed: the publish jobs list it,
  so a red `public-api` leaves the upload unstarted and, behind the
  upload, everything guarded on its success. `published` lists
  `publish-pypi` alone and still needs an `always()` of its own, a bare
  `needs:` reading back through the listed job's `needs:` chain, so the
  widening on `publish-pypi` does not reach it. Section 12 of the
  organization standard is the rule, with the rejected alternatives
  beside it.
- **`RELEASING.md` reads the release run job by job for `skipped`, as a
  step of its own** (issue btclib-org/.github#484). A skipped job carries
  no step and turns nothing red, so a run that lost its post-publish
  check to the wiring above reads as a run that finished; the step names
  the command, which jobs are expected to read `skipped` or red on a
  given trigger, and that `gh run rerun --failed` does not reach a skip.

### `tests/README.md` declares the hand-rolled property layer

- **`properties_test.py` is declared as section 7's property layer,
  hand-rolled rather than hypothesis, with the reason** (issue
  btclib-org/.github#426). Section 7 keys the layer on the property
  section 10 keys the fuzzer on and asks a tree answering it with
  hand-rolled properties to say so in `tests/README.md`; the reason is
  where the suite runs, `[tool.cibuildwheel]`'s `test-requires` and the
  sdist job installing `pytest` alone, and the cost named beside it is
  the search a fixed chain does not do.

### The badge row carries the qualifier section 2 asks of it

- **Every workflow-status badge at the head of `README.md` carries
  `?branch=main`** (issue btclib-org/.github#579): each answers for
  `main` or answers `no status`, where the unqualified badge falls back
  to another branch's run when `main` has none. The pre-commit.ci, Read
  the Docs and Scorecard badges are outside the rule.

### `links.yml` asks lychee for the fragment too

- **`.github/workflows/links.yml` passes `--include-fragments`** (issue
  btclib-org/.github#583). A link into a heading is then checked as an
  anchor and not only as a page, where the forge serves the page and
  drops a fragment it cannot resolve, so a heading renamed in the tree a
  link here points into is red in this run rather than nowhere. The check
  reads the page already fetched for the link and adds no request, and no
  fragment this tree links to fails it today. The
  `blob/main/README.md#<heading>` anchor `REPOSITORY.md` carries is read;
  the bare `github.com/btclib-org/.github#<heading>` shape that file and
  `CONTRIBUTING.md` cite the standard by is answered by the repositories
  API instead, once lychee holds the workflow's token, and
  btclib-org/.github#630 is where that is weighed.

### The index wait is a script with a test

- **`.github/scripts/wait_for_pypi_release.py` is what
  `pypi-install.yml` waits with, in a `wait-for-index` job the install
  matrix `needs:`, and `tests/wait_for_pypi_release_test.py` is what
  drives it** (issue btclib-org/.github#509). A schedule and a dispatch
  pass no version and take the empty-tag branch, so the retry, the
  per-request timeout and the `::error::` of the loop this replaces were
  reachable on a release call and nowhere else. The test substitutes the
  transport and the clock and advances the clock past the deadline, which
  is what section 10 of the organization standard asks of a step waiting
  on something outside the run, btclib-org/.github#466 having decided
  that shape for this class.
- **The budget is a deadline and not a count of attempts times an
  interval**, so what the job's `timeout-minutes` is compared against is
  the one number the script states, and every request is bounded by what
  is left of that deadline as well as by its own timeout. No repair is
  claimed in it: the attempts and intervals of the loop this replaces
  multiplied out to well inside the timeout of the job that ran them.
  The deadline itself is the five minutes that loop named as its budget,
  chosen rather than measured -- nothing here times how long the index
  takes to serve an upload.
- **One job ahead of the matrix rather than a step inside every cell.**
  The question is about the index and not about a platform, so it is
  asked once; the cells that install still check nothing out, which is
  what makes the import they verify resolve to what pip installed. The
  wait job's checkout is sparse and reaches `.github/scripts`, and the
  script takes the standard library alone under `uv run --no-project`,
  so nothing of this project is built or installed to run it.
- **`[tool.ruff.lint.per-file-ignores]` exempts the script from
  `print`**, as it does every other script under `.github/scripts`: what
  it prints is what the log of the step running it shows, which is the
  case that rule is not about.

### The documentation wait is a script with a test too

- **`.github/scripts/wait_for_readthedocs_build.py` is what
  `release.yml`'s `documented` job waits with, and
  `tests/wait_for_readthedocs_build_test.py` is what drives it** (issue
  btclib-org/.github#573). A tag push is the only trigger that reaches
  the wait, so a loop kept in the workflow file is first executed on the
  day a release depends on it, the same reasoning that moved the index
  wait beside it. The job checks out `.github/scripts` alone and runs
  the script under `--no-project`, the shape `pypi-install.yml`'s wait
  job already has.
- **The request carries a `User-Agent`.** The Cloudflare zone in front
  of read the docs bans the interpreter's own default
  (`Python-urllib/3.14`) outright, so a request sent without one is a
  403 against a tag that is in fact served, and the wait would burn its
  whole deadline and annotate an error on every release. `curl`, which
  the loop this replaces called, is not banned, so the loop never needed
  one.
- **The budget is a deadline rather than a count of attempts**, compared
  against the job's own `timeout-minutes` as one number against one
  number. The loop this replaces already fitted inside that timeout, so
  the deadline is chosen against the job's figure rather than to repair
  an overrun.
- **This takes no empty tag as nothing to wait for**, which is where it
  parts from the release wait beside it: that one runs on every schedule
  and dispatch and takes an empty version as nothing to do, while
  `documented` is guarded by the event and a branch ref would spend the
  whole deadline on a URL that answers 404 by construction.
- **No trigger reaches this from a GitHub runner.** `documented` has no
  rehearsal, so what the script does against read the docs was measured
  from outside a runner, and Cloudflare can weigh address reputation
  alongside the user agent on a request the runner actually sends.

### `.gitignore` no longer tells a reader `.python-version` is ignored

- **The `# python` / `.python-version` pair is replaced with a comment
  saying the file is tracked** (issue #469). git applies no ignore rule
  to a path this tree already tracks, so the entry said the opposite of
  what the tree does; the comment names `pyproject.toml`'s
  `requires-python` as the other half of what uv reads to pick the
  interpreter.

### RELEASING.md's rebuild section verifies the attestation, not the index

- **`Rebuild a release from its tag` verifies the rebuilt sdist with
  `gh attestation verify --repo --signer-workflow`, replacing the digest
  comparison against the index** (closes #470). Both sibling publishers
  verify the rebuilt file against its attestation rather than against
  what the index serves, and only the sdist reproduces in this tree, the
  limit issue #439 tracks, so the wheels stay outside what this section
  checks.

### The retitle comment in release.yml names the step, not its position

- **The comment above `release.yml`'s "Check that the release notes are
  retitled for the tag" step now names RELEASING.md's `close the release
  notes` step, replacing a reference to "Step 2"** (closes #471).
  `close the release notes` is the third numbered item of *Cutting a
  release*, not the second, and naming a step rather than counting it is
  the shape RELEASING.md already uses for "the step that opens the next
  version".

### The `.python-version` entry at `3141333` cites `(issue #469)` on a closed issue

- **The `.python-version` entry, landed at `3141333`, cites
  `(issue #469)` for an issue that same commit's own subject closes, and
  stays exactly as landed** (closes #491). The next entry to close an
  issue cites it `(closes #N)`; this one is left as the record of a tree
  that, at the time, did not.

### The mypy hook's `types-cffi` pin is `2.1.0.20260827`, matching `uv.lock`

- **`.pre-commit-config.yaml`'s mypy hook and `uv.lock` both carry
  `types-cffi==2.1.0.20260827`, replacing `2.0.0.20260518`** (closes
  #478). `deps-latest.yml` resolves every dependency at latest, so the
  two disagreed there and `tests/hook_pins_test.py`'s
  `test_every_pin_is_the_locked_version` failed on every suite cell of
  that sentinel. mypy type-checks this package clean against the newer
  stubs.

### `deps-latest.yml`'s `lint-latest` job checks out the submodule and its tags

- **The `lint-latest` job's checkout step now carries `submodules: true`
  and `fetch-depth: 0`, the two keys `lint.yml`'s own checkout step
  carries for the same hook** (closes #487). Without them,
  `submodule-pin` failed with "the submodule is not checked out" and
  `check-sdist` failed with "Git only: secp256k1", on every run of that
  job regardless of what any dependency resolved to at latest.

### A convention name wrapped in its middle is read as it is written

- **`tests/conventions_test.py` collapses the whitespace of the *Not
  tested here* list and then of each name in it** (issue
  btclib-org/.github#651). `strip()` takes whitespace off a name's ends
  and leaves what an eighty-column wrap puts in its middle, so a name the
  break splits matched none of section 7's and was reported as a
  convention the declaration invented -- a red test on a declaration that
  reads correctly in the file. `tests/README.md`'s line here breaks at a
  semicolon, so nothing was red; what goes is the dependence on where the
  column falls, which nothing enforces. `btclib-benchmarks` reads its own
  line this way, its wrap falling inside a name.

### The `.gitattributes` comment names the driver's sides and one anchor

- **The comment above the two `merge=union` lines is `btclib-org/.github`'s
  wording** (issue btclib-org/.github#646): `union` keeps `ours` first
  and then `theirs`, each of merging and rebasing is named for which
  side it calls `ours`, and the comment reads the driver as resolving
  two branches writing an entry at one anchor rather than a bullet
  appended to one of a few changelog groups.

### `REPOSITORY.md` states the plan ceiling in prose, not in a dated table

- **`REPOSITORY.md`'s *Plan-gated settings* states the concurrent-job
  ceiling and the macOS one beneath it in prose, instead of reproducing
  GitHub's table with a date beside it** (issue btclib-org/.github#639).
  Section 10 of the organization standard rejects the dated number: the
  date says when it was true and nothing says it still is, where
  `gh api orgs/<org> --jq .plan.name` beside the linked table answers for
  the day it is read. The sentence that argued from the macOS figure is
  kept and sourced to that table; the figures for plans this
  organization is not on go with the table, no command here re-deriving
  them.

### `CLAUDE.md`'s worktree block puts the removal line in a fence of its own

- **`git worktree remove --force "$WT"` no longer sits under a line
  that ends in a placeholder** (issue btclib-org/.github#676): the
  assignment above it fails on its own redirection, and a shell that
  discards that failure as a parse error reads the next line as a fresh
  command, so a paste made before the placeholders were filled reached
  the removal against whatever `$WT` a previous run of the same block
  had left set. The removal now stands in a fence of its own, with
  prose between the two fences saying why the first closes early, so a
  reader reaches it only by pasting it on purpose.

### `compile_static_unix` pins the mtime of the object it links on macOS

- **On Darwin, `compile_static_unix` sets the intermediate object's mtime
  to hatchling's own fixed epoch before linking it, replacing the mtime a
  fresh compile always gave it** (closes #498, closes #502). ld64
  attaches a debug map to the extension it links whenever the compile
  carries `-g`, as this interpreter's own `CFLAGS` does, and that debug
  map's `N_OSO` stab records the object's own mtime; ld64's own default
  `LC_UUID` is a hash of the linked output's content, so a fresh mtime on
  every compile carried into a fresh `LC_UUID` on every link -- the
  divergence issue #497 measured and the one byte issue #439's own first
  measurement found outside it and could not place. Issue #498's own
  proposal, `-Wl,-no_uuid`, asks ld64 to drop the load command instead of
  fixing what varies, and dyld on this measurement's machine refuses to
  load a bundle missing one at all, "missing LC_UUID load command";
  pinning the mtime instead addresses the varying input, and two static
  wheel builds of one checkout, cleared between them, now produce one
  digest. CMake's own build of the dynamic wheel's `libsecp256k1.dylib`
  carries no `-g` and needed no equivalent, which repeated builds of it
  confirmed rather than assumed.

### `REPOSITORY.md` reads both variable stores back for the review switch

- **The file records `vars.CLAUDE_REVIEW_ENABLED`, the switch
  `claude-review.yml` guards its jobs with** (issue
  btclib-org/.github#682). Both variable stores are read back: the
  repository's because a variable set here would take precedence over
  one of the same name set on the organization, and the organization's
  for the empty name list section 11 reads as the switch's off state --
  with a `total_count` beside it, a store that prints nothing at all
  when it answers needing one to show the call reached it. The
  repository's `actions/variables` leaves the facilities whose empty
  answer records no decision, from that block's prose list and from its
  loop alike, that zero now being half of what records this one.

### `REPOSITORY.md` names `is_template` among the fields no rule reaches

- **`is_template` is named among the fields of the repository document
  `REPOSITORY.md` passes over** (issue btclib-org/.github#691). It is in
  that document, in none of that file's `--jq` objects and named nowhere
  in the standard, which is the class the block enumerates; a field of
  that class it does not name is silent in both places at once, and
  reads as one nobody looked at rather than as one weighed and left out.

### `wheel-reproducibility.yml` builds a wheel twice, member by member

- **`.github/scripts/check_wheel_reproducibility.py` builds this
  project's wheel twice from one checkout and compares the two archives
  member by member, and `wheel-reproducibility.yml` runs it on every
  platform the release builds a wheel on** (closes #500). Issue #439's
  stage 1 asks whether a wheel this project builds reproduces byte for
  byte; issue #497 answered that for macOS by building twice and
  comparing the archives by hand, and this is the same measurement made
  repeatable and reaching the platforms that measurement could not. A
  whole-archive digest says two wheels differ and nothing past that,
  which is why the new script compares member by member instead: it
  names which member disagrees and, for it, whether the bytes match and
  whether the stored `mtime`, permission bits and compression method do.
  It is a sentinel rather than a gate, the property not holding on every
  platform yet, and which platform answers green is the workflow's own
  output on the Actions tab rather than a list kept in this file.

### `compile_static_unix` strips the build directory from the debug map's stabs

- **On Darwin, `compile_static_unix` now compiles with
  `-fdebug-compilation-dir=.` and links with `-Wl,-oso_prefix,.`, so the
  debug map's `N_SO` and `N_OSO` stabs name the object's bare filename
  instead of the directory the build ran in** (closes #503). Issue #497
  corrected #439's own first measurement: `strings` finds no debug map
  at all, while `nm -pa`'s `OSO` stab and a raw `grep -a` over the
  linked object both surface the worktree's absolute path, which
  `cee5f6d`'s mtime pin left untouched, that pin addressing the stab's
  mtime rather than its path. Two static wheel builds of one checkout,
  each from a differently named directory, now produce one digest,
  member for member. CMake's own build of the dynamic wheel's
  `libsecp256k1.dylib` carries no `-g` and attaches no debug map at all,
  which repeated builds of it confirmed rather than assumed.

### `wheel-reproducibility.yml` also runs on a pull request touching the build

- **A `pull_request` trigger joins `schedule` and `workflow_dispatch`,
  scoped by `paths` to `scripts/**`, `pyproject.toml`, the `secp256k1`
  submodule pointer, `.github/scripts/check_wheel_reproducibility.py`
  and the workflow file itself** (closes #508). Both existing triggers
  are inert off the default branch, so a change answering issue #510 --
  issue #439's Windows stage -- could only be dispatched and measured
  after landing; this trigger lets that branch be measured first.
  `REPOSITORY.md`'s required-checks rule still excludes the workflow,
  now for a reason of its own rather than the one every other excluded
  sentinel shares: Windows does not reproduce yet, so requiring the
  check would fail a pull request for that platform's own standing
  defect. `CONTRIBUTING.md`'s workflow table says a pull request
  touching what it builds.

### `zizmor`'s `self-repository` audit is declined, and `pyroma` holds at 5.0.1

- **Bumping the `zizmor-pre-commit` hook to v1.30.0 turns on the
  `self-repository` audit, which flags the workspace-relative
  `uses: ./...` sites in `release.yml` and `test.yml`; `.github/zizmor.yml`
  now ignores those findings rather than adopting GitHub's `$/...` form**
  (closes #512). `$/` is what the audit recommends and what the runner
  accepts, but actionlint -- the hook holding these same workflows to a
  zero-finding bar -- has no released version that parses it: v1.7.12
  predates GitHub's introduction of the syntax, and
  [rhysd/actionlint#711](https://github.com/rhysd/actionlint/issues/711)
  is still open asking for support. Adopting `$/` now would trade a
  zizmor finding for an actionlint one on each of the same lines.
- The same bump moves `ruff-pre-commit` to v0.16.5 and `uv-pre-commit` to
  0.12.7, neither surfacing a new finding. `pyroma`'s own bump to `5.1b1`
  is not taken: PyPI's latest stable release is still `5.0.1`, and
  `pyroma --min 10` runs in the gate that rates every release's sdist, not
  a place for a packaging linter's prerelease score to move the floor.

### `check_wheel_reproducibility.py` builds its two halves from two directories

- **The sentinel now extracts `HEAD` twice, with `git archive`, into two
  freshly named directories of different lengths as well as different
  names, and builds and diffs the wheel from each, rather than building
  twice inside the one checkout it runs in** (closes #509). #439's own
  record of the four stages named the gap precisely: the comparison
  #497 and #500 grew into answers "does this checkout build the same
  wheel twice", not #439's own question, "does this commit build the
  same wheel", and #503 was exactly the class of difference invisible to
  a one-directory comparison -- a build directory two builds sharing one
  checkout hold constant by construction. `copy_source_tree` closes that
  gap with two `git archive` calls per copy, one for the checkout and
  one for the `secp256k1` submodule, since a gitlink names a commit
  rather than a tree and the outer archive does not walk into it.
  Reverting #503's own fix in a scratch copy and rerunning the
  two-directory comparison turns the extension's own member red again,
  its content differing between the two builds; with the fix in place
  the two builds go back to agreeing, member for member. Building from
  `HEAD` rather than from the checkout in place is a side effect worth
  naming on its own: an uncommitted edit sitting in the checkout is no
  longer part of what either build sees, since it is not part of the
  commit the question is about.

### `compile_static_msvc` links the Windows extension with `/Brepro`

- **The static extension's own link, on native Windows, now carries
  `/Brepro`** (closes #510). Issue #439's Windows stage measured two
  builds of one checkout producing two `.pyd` files that agreed in
  every respect but one field, `link.exe`'s own `TimeDateStamp`, and one
  debug directory entry (`IMAGE_DEBUG_TYPE_POGO`) whose own timestamp
  mirrors it, with no CodeView entry present at all -- so the other
  candidate the issue named, the CodeView debug directory's GUID, was
  never in play. `/Brepro` asks the linker to derive the `TimeDateStamp`
  from the content instead of the moment it ran, and the same two
  builds now agree, the debug directory carrying a new entry in its
  place, `IMAGE_DEBUG_TYPE_REPRO`, a content hash rather than a
  timestamp. `cl.exe`'s own `/Brepro` is not added beside it: that one
  addresses an *object* file's own embedded timestamp, which nothing
  downstream of this build reads, the final image's `TimeDateStamp`
  being `link.exe`'s alone to set. The vendored library CMake builds
  ahead of it needed nothing of its own: it carries no `/Zi` under the
  `Release` configuration `scripts/cffi_build.py` actually builds,
  checked against the build's own configure summary rather than
  assumed. The Windows-only diagnostic step added to measure which
  field moved is not kept: `.github/scripts/check_wheel_reproducibility.py`'s
  own byte and crc32 comparison already catches a regression here, and
  the one thing the diagnostic step added beyond that -- naming which
  field -- is a question this entry now answers.

### The sentinel builds each platform on two images and diffs the pair

- **`wheel-reproducibility.yml` carries a second GitHub image for every
  platform it measures, each job keeps the wheel it built as an
  artifact, and an `across-images` job downloads the pair and diffs the
  two archives member by member** (closes #514). #439's exemption, which
  `RELEASING.md` and section 12 of the organization standard both state,
  names the compiler, its version and the toolchain the runner happened
  to have as the inputs nothing pins: that is a claim about two
  environments, and everything measured under #439 until now is two
  builds inside one. The second image of each pair is a different OS
  release rather than another label for the same one -- Ubuntu 22.04
  against 24.04 on both architectures, macOS 15 against macOS 26 on
  both, Windows Server 2022 against 2025 -- and the Windows arm64 pair
  is the one whose images share an OS build and differ in the Visual
  Studio they carry, which is the compiler moving with nothing else.
  Each image still builds twice, so a difference between two images is
  attributable to the image rather than to either one's own drift --
  on every platform whose own two builds agree, which #522 is Linux not
  yet doing.
- `check_wheel_reproducibility.py` grows the two entry points that
  separation needs: `--keep-wheel` saves the first build's wheel before
  the two are compared, so an image whose own builds disagree still
  hands its half over, and `--across-images` compares the wheels the
  images left without building anything. A filename that differs between
  two images is one line of that comparison and not the end of it: a
  macOS runner's deployment target reaches the platform tag, so
  `macosx_15_0` against `macosx_26_0` renames the wheel while saying
  nothing yet about the members inside it, and the members are compared
  either way.
- `tests/wheel_reproducibility_platforms_test.py` held the sentinel's
  image list equal to `build-cibuildwheel`'s, which a second image per
  platform makes impossible to keep. The invariant it asserts is now the
  containment -- an image the release builds a wheel on that the
  sentinel does not is a wheel nothing measures -- together with the
  pairing, since a platform down to one image is one whose across-images
  comparison has nothing to compare.
- **The answer is that no platform's two images build one wheel**, run
  [33693367257](https://github.com/btclib-org/btclib-secp256k1/actions/runs/33693367257):
  the compiled extension differs on every pair, and on both macOS pairs
  the wheel is named differently as well -- `macosx_15_0` against
  `macosx_26_0` -- with `WHEEL`, which carries that tag, differing with
  it. The Windows arm64 pair is the cleanest of them, its two images
  sharing the OS build `10.0.26200` and differing in the Visual Studio
  they carry: `_btclib_secp256k1.cp314-win_arm64.pyd` is 1512960 bytes
  off the 2022 toolset and 1521664 off the 2026 one, the compiler moving
  with nothing else around it. So the exemption `RELEASING.md` states is
  confirmed rather than narrowed, and pinning the image by digest, the
  Xcode and the MSVC toolset is #524. That run's Linux cells are red
  within one image too, which is #522 and not this.

### The Linux extension no longer records the directory it was built in

- **`compile_static_unix`'s compile carries `-ffile-prefix-map=<the build
  directory>=.` wherever it is not the Darwin branch's
  `-fdebug-compilation-dir=.`** (closes #522). The interpreter's own `CFLAGS`
  carries `-g`, so the compiler records the directory that compile ran in as
  the compile unit's `DW_AT_comp_dir`, whose string the link copies into the
  extension's own `.debug_line_str`: two builds of one commit from two
  differently named directories differ there by exactly the difference between
  the two names. What the wheel member's own byte counts show need not equal
  that, the sections after `.debug_line_str` being realigned behind it: in
  this measurement the eight-byte alignment of `.symtab` needed one byte less
  padding after the longer path, so the member differed by one byte less than
  the string did. #509's two-directory comparison is what surfaced it, on
  every Linux cell and on no other platform, which is the gap that comparison
  was built to close. Both compilers take `-ffile-prefix-map`, where
  `-fdebug-compilation-dir` is clang's alone: gcc, which is `/usr/bin/cc` on
  the Linux images, rejects that one as an unrecognized option.
  `-fdebug-prefix-map` would serve here too and is taken by both as well;
  `-ffile-prefix-map` is preferred to it because gcc's own manual defines it
  as equivalent to specifying all the individual `-f*-prefix-map` options,
  `__FILE__` and the profile paths along with the debug information. It is
  also a floor a non-Darwin build did not carry before: an option a compiler
  does not have is an error rather than a warning, so a toolchain older than
  this flag fails the build outright instead of quietly reproducing the
  difference. The vendored library CMake builds beside it needs nothing of its
  own: that configure runs `Release`, whose own summary prints `-O2` and no
  `-g`, so its objects carry no debug information for a directory to sit in.
  Both halves were measured on both Linux images: without the flag `readelf`
  reads each extension's `DW_AT_comp_dir` as the directory that build ran in
  and the two wheels disagree, and with it both read `.`, a raw scan of either
  extension finds neither directory, and the two wheels agree member for
  member.

### `.github/scripts` extracts with a filter every interpreter accepts

- **`check_wheel_reproducibility.py` sets `TarFile.extraction_filter`
  rather than passing `extractall(filter="data")`** (closes #529). That
  keyword is a `TypeError` on Python 3.10.11, which is what cibuildwheel
  pins `cp310` to on the macOS and Windows images — one patch release
  below the 3.10.12 that backported PEP 706 — where a manylinux image
  carries a current patch instead: in run
  [33698474828](https://github.com/btclib-org/btclib-secp256k1/actions/runs/33698474828)
  those images ran 3.10.20 and their wheel jobs were the green ones. An
  assignment is one statement on every interpreter, where a
  `sys.version_info` branch is one no single interpreter takes both ways
  and `.github/scripts` is measured under `fail_under = 100`. Setting no
  filter at all is the other shape and trades this red for another: 3.12
  and 3.13 raise a `DeprecationWarning` where nothing sets one, which
  `filterwarnings = ["error"]` makes a failing test.
- Where `tarfile.data_filter` is absent the fallback is `fully_trusted`,
  CPython's own behaviour before the filter existed, and what makes that
  acceptable is that `_extract_archive` reads `git archive HEAD` over
  this repository and nothing else. `wheel_reproducibility_test.py`
  asserts it against a hand-built archive naming a parent directory,
  since no interpreter the local gate runs takes the fallback at all.
- `CONTRIBUTING.md` records what these scripts run under, the keyword
  being an instance of a class: mypy's `python_version` is a minor
  version and refuses a patch, so no static check tells 3.10.11 from
  3.10.12, and the wheel jobs that run the suite under `cp310` are
  narrowed on a pull request to one interpreter per image — which leaves
  a script reaching past the floor to go red on the push to `main`.

### A test repository does no line-ending translation

- **`init_repo` writes `* -text` into each repository's
  `.git/info/attributes`** (closes #535). The GitHub Windows images set
  `core.autocrlf` in the global configuration and a fresh `git init`
  inherits it, so `git archive` handed back `[project]\r\n` where the
  commit holds `[project]\n`, and
  `test_copy_source_tree_extracts_the_submodule_from_its_own_repository`
  went red on the Windows jobs of `test` that install from the sdist —
  run
  [33698474828](https://github.com/btclib-org/btclib-secp256k1/actions/runs/33698474828),
  under Python 3.14 and so nothing to do with #529's `TypeError`. An
  attribute rather than `core.autocrlf = false` in the repository's own
  configuration, which a global `core.attributesFile` marking files text
  overrides in turn where `-text` is not overridden; and in `.git/info`
  rather than a committed `.gitattributes`, so that what a test asks to
  be committed stays the whole of what the archive holds.
- A test asks the question from any platform, pointing
  `GIT_CONFIG_GLOBAL` at a configuration git itself writes: `autocrlf`,
  `core.eol`, and an attributes file marking every path text. The first
  key alone reproduces the runner and pins only the symptom — a
  repository of its own saying `core.autocrlf = false` survives it, so a
  test carrying that key alone stays green against the alternative this
  entry declines. The other two are what make the test fail when
  somebody reaches for it.

### The `wheel-reproducibility` sentinel takes its calendar slot

- **`.github/workflows/wheel-reproducibility.yml` fires at the instant
  section 10's calendar gives it, and `README.md`'s badge row carries
  it** (closes #538). btclib-org/.github#698 is where the row was
  settled: Sunday, hour 02, the sentinel seated among the security rows
  that day holds and taking the hour below them, the band growing
  downward where a family's own hours are taken. The minute is this
  repository's row in that section's second table and does not move. The
  comment beside the schedule states the day the grid gives the
  workflow, replacing a reason for a day picked against the slots this
  tree itself had in use, and the dispatch beside it names no day at
  all.
- The badge goes between `links` and `codeql`, which is the calendar's
  order over the sentinels this tree runs: `sdist-rebuild`, which the
  calendar puts between those two, is a workflow this repository does
  not schedule.

### The worktree recipe ends `git worktree add` in its placeholder

- **`CLAUDE.md`'s worktree recipe puts `-b <branch>` last, so the
  command ends in its placeholder** (issue btclib-org/.github#687).
  With the placeholder ahead of `"$WT"`, a paste made before it is
  filled in has `<` open a file named `branch` for reading and `>`
  create a file at the path `$WT` holds. The recipe's last line removes
  the worktree, so the path a second paste starts from has no directory
  at it and the redirection has nothing to fail on.
- The paragraph under the fence carries that reason and cites section 9
  of the organization standard, where a bare placeholder is required to
  end its command.

### The sentinel diffs the wheel the release uploads

- **`wheel-reproducibility.yml` carries a `repaired` job, and
  `check_wheel_reproducibility.py` a `--repaired` entry point, that
  build through `cibuildwheel` twice and diff the pair** (closes #515).
  What every other job here builds is `uv build`'s wheel, which stops
  at the archive `hatchling` writes; `cibuildwheel` runs the same
  `scripts/cffi_build.py` and then repairs the wheel with the tool it
  defaults to on that platform — `auditwheel` on Linux, `delocate` on
  macOS, `delvewheel` on Windows, `[tool.cibuildwheel]` naming no
  `repair-wheel-command` of its own. What that hands back is the
  repair's own file rather than the build's, and it is what PyPI
  receives.
- One interpreter and no test command, on the images
  `build-cibuildwheel` builds a release wheel on. `rebuild` has only
  ever measured one interpreter, `uv build` leaving one wheel for the
  interpreter uv resolves for the project, so an unnarrowed job would
  answer a question this file asks nowhere else — and, unlike on the
  gate, no later run reaches the identifiers it skips, which the
  workflow's header states as a limit rather than covers. The test
  command is dropped because what this asks is whether two archives are
  the same bytes; and a second image per platform would ask the
  across-images question a second time, which the `uv build` wheel is
  already asked.
- `tests/wheel_reproducibility_platforms_test.py` holds the new list
  against `build-cibuildwheel`'s as an equality, where `rebuild`'s is a
  containment: a job asking whether the uploaded wheel reproduces has
  to ask it of the images that upload one, and an image it builds that
  the release does not is runner-minutes spent on a wheel nobody
  installs.
- `two_source_copies` is where both entry points now name the two build
  directories, so `#503`'s property — two paths differing in length as
  well as in name — is stated once rather than per caller. A repaired
  build can leave more than one wheel, Linux compiling a `manylinux`
  and a `musllinux` one from a single interpreter, so `--repaired`
  pairs the two sides by filename and reports a wheel only one side
  built as its own line: that is the pair never having been compared,
  which must not print like agreement.

### The documentation build does not pass `--keep-going`

- **`sphinx-build` is spelled `-n -W -b html` in `docs.yml`,
  `.readthedocs.yaml`, `CONTRIBUTING.md` and `docs/README.rst`** (issue
  btclib-org/.github#347). Section 2 of the organization standard is
  where that is settled, with the rejected alternative beside it.
- The comments in `docs.yml` and `.readthedocs.yaml` credit `-W` with
  reporting every warning a build raises before failing at the end of it.

### Every build of a distribution pins `SOURCE_DATE_EPOCH`

- **Every job of `test.yml` that builds a wheel exports
  `SOURCE_DATE_EPOCH` from the commit date, as `build-sdist` does
  for the sdist, and `[tool.cibuildwheel.linux]`'s
  `environment-pass` carries it into the container the Linux build and
  its repair run in** (closes #539). `hatchling` stamps the members it
  writes at a constant of its own where the variable is unset, and the
  repair a wheel build is followed by does not: `auditwheel` repacks
  from a directory it extracted the wheel into and gives every member
  the clock of the moment, and `delocate` gives it to the members it
  rewrites. That timestamp is the whole of what separates a published
  static wheel from a rebuild of its own commit in the image that built
  it, which is #439's property within one environment; the compiler and
  the toolchain, which that issue and section 12 of the organization
  standard both name, are what the across-image half still turns on.
  The `py3-none-*` wheels `build-dynamic` and `build-windows` publish
  beside them carry the same pin and no measurement, nothing building
  one of them twice.
- The commit date rather than `hatchling`'s constant, which is the
  other candidate and the one that would have needed no value from
  outside the tree. `hatchling` reads the variable for a wheel as it
  does for an sdist, so the archive carries one instant under either
  choice and the archive does not decide it. What decides it is the
  release: the sdist is stamped at the commit, so a constant would
  publish files disagreeing about when they were built, and section 12
  asks for the epoch exported from the tagged commit. A rebuilder
  recovers it with the `git log -1 --pretty=%ct` that `RELEASING.md`
  already names for the sdist.
- `wheel-reproducibility.yml`'s `rebuild` and `repaired` jobs export it
  too, so what the sentinel diffs is the build the release runs rather
  than one differing from it in an exported variable. `repaired` is the
  job the pin turns green: `uv build` leaves the repair out, and
  `hatchling`'s fallback made `rebuild` agree without it.
- `tests/build_timestamp_test.py` reads both workflows, asks which jobs
  run a build frontend, and requires the export of each, the value
  included. The export is per job, so a wheel job written by copying a
  neighbour is how one arrives without it, and a wheel that reproduces
  on one trigger and not another is worse than one that reproduces on
  neither: it looks fixed.
- `RELEASING.md`'s *Rebuild a release from its tag* says what the static
  wheels reproduce within, that the `py3-none-*` ones have no
  measurement behind their bytes, and which job measures which.
- `CONTRIBUTING.md`'s *Running what CI runs* gives the export to the
  three wheel recipes there: the section promises the command that
  reproduces a job, and a wheel built without it differs from that job's
  in every member's timestamp. `check_wheel_reproducibility.py`'s
  docstring reads `RELEASING.md` for the across-image claim alone, that
  file no longer being one of the two that say a wheel does not
  reproduce at all.

### The coverage ratchet is met before a push, and on both linkages

- **`addopts` carries `--cov` and `--durations=8`, so a bare
  `uv run pytest` is the 100% ratchet** (closes btclib-org/.github#431).
  A gate CI alone runs is one a change meets after it is pushed.
  `--cov` sits ahead of `--durations=8` rather than last: it takes an
  optional value, so as the final token it swallows the first path the
  command line gives, and `tests/conftest_test.py` is what keeps it off
  the end.
- **`tests/conftest.py` gates a run that asked for less than the suite
  at nothing, and lets it report all the same.** `fail_under` applies to
  every report coverage writes, so a run of one module would end in
  `Required test coverage of 100.0% not reached` -- true of that run and
  saying nothing about the tree. What counts as asking for less is
  section 8 of the organization standard's set: a path that leaves a
  `testpaths` entry out, `-k`, `-m`, `--deselect`, `--ignore`,
  `--ignore-glob`, `--lf`. `pytest tests` is none of them, being what a
  bare run already collects, which is what btclib-org/.github#430 is
  about; the threshold is written to `config.known_args_namespace`, the
  copy pytest-cov reads, and an explicit `--cov-fail-under` outranks it
  either way.
- **The coverage job of `test.yml` runs the suite against each linkage,
  names each run's data file with `COVERAGE_FILE`, and gates the union
  beside the static run's own 100%.** A given build has one branch of
  `_load_lib` and not the other, so the dynamic run cannot execute the
  linked-in one and is asked for `--cov-fail-under=0`; what the combined
  report gates is a line neither linkage reaches, and its threshold is
  `[tool.coverage.report]`'s rather than a copy in the workflow. The
  rejected alternative is an `exclude_also` naming the linked-in branch
  with its reason, honest only where the dynamic build is not shipped,
  and this repository publishes both.
- **A run whose question coverage is no part of passes `--no-cov`**: the
  platform sentinels, `[tool.cibuildwheel]`'s `test-command`, the sdist
  suite job of `test.yml`, and the mutation session, whose mutants are
  reached by no test on purpose. `deps-latest` keeps the measurement
  instead: it resolves every dependency at its newest, and a release
  that moves the number is what that sentinel is there to report. The
  flag needs the plugin installed to parse, so `test-requires` and the
  sdist job's `pip install` name pytest-cov beside pytest.

### The reproducibility sentinel cites the issue that would close the gap

- **`wheel-reproducibility.yml`'s header names #524 where it says why
  the workflow is a sentinel and not a gate** (closes #551). Two images
  of one platform do not build one wheel yet, and pinning the image, the
  Xcode and the MSVC toolset is that issue. The header pointed at a
  record kept on #439 instead, which is the umbrella its landed stages
  close rather than the question still open. The tree's other citations
  of #439 stay: in that same header, in
  `check_wheel_reproducibility.py`'s docstring and in `RELEASING.md`,
  each names it as the origin of the question this measures or as what
  section 12 of the organization standard's exemption cites, and an
  issue cited for what it asked is the record rather than a place to
  look next.

### A `RELEASING.md` placeholder takes its own fence, and the next guards it

- **The run id, and the tag of the release being recreated, stand in a
  fence with nothing under them, and the fence that consumes either
  writes it `${name:?}` and chains its commands with `&&` where it
  holds more than one** (issue btclib-org/.github#745). Section 9 of
  the organization standard puts a line that writes in a fence of its
  own, the parse error guarding only the line it sits on: an
  interactive shell discards a line ending in a placeholder and reads
  the next line of the same fence as a fresh command. The split and the
  guard answer two different pastes. The split answers the passage
  taken whole, where the placeholder line is discarded and what stands
  under it runs; the guard answers the second fence taken alone, where
  the value is merely unset and there is no parse error to discard
  anything. Pasted unfilled and on its own, each of these fences runs
  no command and creates no file, under `zsh`, `bash` and `sh` alike,
  interactively and read as a script.
- The chain is a run-time guard as well, which is why it stays where it
  serves both: a rebuild that carries on past a failed `uv build`
  normalizes and verifies whatever `dist/` already held.
- A paste of the block that recreates a skipped release wrote
  `notes.md` into whatever directory the reader was standing in and
  reached `gh release create` under it; the block that reads a run job
  by job asked the API for `runs//jobs`, whose 404 reads as an answer
  about the run; and the rebuild block reached `git submodule update`
  and the `uv` build with the reader's own directory as their working
  directory.
- The tag of the recreate block and of the rebuild section is
  `v<version>` rather than a released version spelled out. A version
  spelled out is a value the reader never had to supply, so it
  satisfies `${tag:?}` and the block acts on whatever release the file
  happened to name.
- The rehearsal's attestation check assigns the run id instead of
  writing it into the `gh run download` line (issue
  btclib-org/.github#740). Inline, `<run id>` is a redirection rather
  than a parse error, so it guards only while the reader's directory
  holds no file called `run`; with one there, the line creates a file
  named `--repo` and the `gh attestation verify` below it runs.

### `RELEASING.md` names the gap a pin closes and the two it does not

- **The section on rebuilding a release from its tag gives the Linux
  half as the one a pin closes and the macOS and Windows halves as
  declined, where its sentence sent a reader to #524 for all three**
  (closes #554). A rebuild is a check only where the environment it
  needs is something the person running it can obtain: the container
  the Linux build compiles in is addressed by the digest of its content
  and `docker pull`able by anyone, which is #524, where `xcode-select`
  and `-vcvars_ver` choose among what a runner image GitHub retires
  already carries and a verifier without a Mac cannot run the check at
  all. What the macOS and Windows wheels carry instead is the PEP 740
  attestation `publish-pypi` uploads with every file, which says who
  built one and where rather than what is in it.
- A verifier who rebuilds a released static wheel outside the image
  that built it and gets other bytes reads there that this is the
  expected outcome and not a defect, and that on those two platforms it
  is the end state rather than a fix that is coming. #439 asked for
  exactly that sentence: an attestation reads as one guarantee over
  every file it covers, and nothing in the release told a verifier
  which outcome to expect from which file.
- `wheel-reproducibility.yml`'s header carries the same correction, and
  says why every platform keeps its row in `across-images`: a platform
  that is not expected to pass is what would say so if it started
  passing.

### `conf.py`'s `myst_heading_anchors` comment names only this tree's own reason

- **The comment above `myst_heading_anchors` says CONTRIBUTING.md's own
  anchor link and the depth of `## Build` are why this tree sets 2, with
  no claim about another repository's `conf.py`** (closes #519).

### `.readthedocs.yaml`'s `-W` comment matches what sphinx does

- **The comment above the Read the Docs build command says `-W` reports
  every warning the build raises before failing at the end of it, the
  same claim `.github/workflows/docs.yml`'s comment makes for the same
  command** (closes #546).

### `release.yml`'s retitle-check comment states its current reason

- **The comment above "Check that the release notes are retitled for
  the tag" no longer says what the check used to be, only what the
  fallback it guards against actually fires on** (closes #489).
  github-release's own fallback fires on an *empty* section, not on a
  non-empty "work in progress" heading, and that is the reason the
  comment now gives for checking more than a section's existence.

### `vendored-vectors.yml` names upstream's cross-reference step

- **The comment above "Import the libsecp256k1 maintainer keys" names
  the README step upstream asks a human to perform by what it does —
  cross-reference each fingerprint against a source its owner controls
  — instead of by its position in a numbered list** (closes #490). The
  list is `bitcoin-core/secp256k1`'s own, a document this organization
  does not control and no gate here reads, so reordering it no longer
  falsifies a citation nothing here would catch.

### The `ci:` block names `lint.yml` instead of counting its runners

- **The comment explaining what `skip: [submodule-pin]` still gates
  names `lint.yml` directly rather than counting how many workflows run
  `.pre-commit-config.yaml`** (closes #493). `deps-latest.yml`'s
  `lint-latest` job now runs the same file too, so the count had
  already moved; naming the required check is the fact that does not.

### `CONTRIBUTING.md`'s lint entry reproduces the gate the lint workflow runs

- **The `Lint and type-check` entry gives `uv run --locked --only-group
  lint pre-commit run --all-files`, the command `lint.yml`'s own step
  runs and the one `Three gates decide a merge` already names two
  screens earlier** (closes #506). `uvx pre-commit run --all-files`
  resolves whatever `pre-commit` version the index holds the day it
  runs, not the one `uv.lock` pins, so it reproduced a different gate
  than the one that decides a merge.

### `CONTRIBUTING.md`'s workflow table gives `links` its own trigger

- **The workflow table splits `links` and `mutation` into their own
  rows, `links`'s `when` column naming the `pull_request` trigger
  scoped to its own configuration** (closes #513). `mutation.yml`
  carries no such trigger, so the one row the two shared read as true
  of both where it was only true of `links`.

### `CONTRIBUTING.md` names `wheel-reproducibility`'s `repaired` job

- **The `wheel-reproducibility` bullet gives the `repaired` job's own
  local command, pinning `SOURCE_DATE_EPOCH` first, and the table row's
  `what it varies` column names its matrix too** (closes #547).
  `repaired` builds the file PyPI actually receives -- the wheel
  `cibuildwheel` repairs with `auditwheel`, `delocate` or `delvewheel`
  -- where `rebuild` stops at the archive `hatchling` writes; without
  the pin, `auditwheel` and `delocate` stamp the moment they ran, so two
  sequential local builds disagree and the command reports a wheel that
  reproduces as one that does not. `rebuild`'s own recipe in the same
  bullet gains the identical export, since `hatchling`'s own fallback
  constant would keep its two local builds agreeing either way and what
  the pin buys there is agreement with the wheel a release actually
  builds. The `repaired` command needs `cibuildwheel` on `PATH` and, for
  the Linux platform, a container runtime.

### `CONTRIBUTING.md`'s `Build sdist` entry pins the timestamp and normalizes

- **The `Build sdist` entry runs `python -m build -s` under the build
  group, exports `SOURCE_DATE_EPOCH` first and runs
  `.github/scripts/normalize_sdist.py` after, matching what `test.yml`'s
  `build-sdist` job runs** (closes #548). The normalizer refuses to run
  without the variable set and rewrites every member's `mtime` after
  the build, which is what decides whether the local archive's bytes
  match a published sdist.

### A pull request builds `cp310`, the floor `requires-python` declares

- **`build-cibuildwheel`'s pull-request narrowing sets `CIBW_BUILD` to
  `cp310-* cp311-win_arm64` rather than `cp314-*`** (closes #533). cp310
  is the interpreter `requires-python` declares as the floor, and the
  second pattern is windows-11-arm's own floor: `[tool.cibuildwheel]`'s
  skip line excludes `cp310-win_arm64` on every trigger, there being no
  interpreter on that native arm64 runner to build it with. The
  previous choice, `cp314-*`, shared the gate's own suite cell
  interpreter, so a branch built nothing older, which is what #529
  cost: a keyword absent from Python 3.10.11 landed green on a pull
  request and failed only once the push to main built `cp310` for the
  first time.

### An editable install's `WHEEL` carries the same tag a standard build would

- **`scripts/hatch_build.py`'s build hook now rebinds `get_default_tag`
  on the live `WheelBuilder` instance to the tag it already decided for
  a standard build** (closes #534). `WheelBuilder.build_editable_detection`
  and `build_editable_explicit` (hatchling 1.32.0) each set
  `build_data["tag"]` from `self.get_default_tag()` before either one
  reads `build_data["infer_tag"]` or a `build_data["tag"]` this hook
  already set, so an editable install of a static build carrying a
  `cpNN` extension came out `py3-none-any`, and uv's cache served one
  interpreter's `.so` to any other interpreter it built for next.

### `schedule` and `workflow_dispatch` are told apart

- **`CLAUDE.md`'s bullet on dispatching a workflow off `main` now says
  `workflow_dispatch` runs a branch's own copy of a workflow already
  landed on `main`, where it said dispatching one from a branch was
  impossible** (closes #525). `schedule` still fires only from the
  default branch, but `--ref <branch>` runs that branch's copy of any
  workflow whose trigger already exists on `main`, so a change to
  `release.yml` or to a sentinel is measurable before it merges; only a
  workflow that has never landed on `main` is unreachable until then.
  `wheel-reproducibility.yml`'s own header made the same claim about
  `workflow_dispatch` under its `pull_request` trigger and is corrected
  with it, the trigger's own reason -- a pull request measured without
  anyone dispatching by hand -- left standing.

### `REPOSITORY.md` cites the gap keeping the sentinel out of the branch rule

- **The paragraph exempting `wheel-reproducibility.yml` from the branch
  rule now cites what the workflow's own header names, where it named
  #510** (closes #542). #510 closed with every `rebuild` cell green,
  Windows included; what keeps the sentinel out of the rule is
  `across-images` failing on every platform: pinning the Linux
  container is #524, and pinning the Xcode and the MSVC toolset macOS
  and Windows builds use is declined instead.

### The group-flag comments state the argument, not a snapshot count

- **`test.yml`'s coverage step comment and `CONTRIBUTING.md`'s `The
  environment and the gates` justify `--no-default-groups --group test`
  by the shape of the difference -- `uv run` syncs the environment
  itself, and leaving the flags off syncs the wider default groups --
  rather than by the two package counts neither file re-derives**
  (closes #549). The step comment's clause naming what a prior sync had
  installed also described a two-step sync-then-run setup this workflow
  no longer runs.

### The `actionlint-py` pin carries the prompt to revisit `$/`

- **`.pre-commit-config.yaml`'s `actionlint-py` entry now carries a
  comment asking whoever reviews the next bump of that pin to re-test
  whether a released actionlint parses GitHub's `$/...` syntax, and, if
  it does, to drop `.github/zizmor.yml`'s `self-repository` ignores
  together with the workspace-relative `uses:` migration** (closes
  #517). `pre-commit.ci`'s weekly autoupdate is what moves that pin, so
  a bump pull request is the moment somebody is already looking at the
  actionlint version; nothing tracked that moment before.
  `.github/zizmor.yml`'s own comment now points at the pin rather than
  restating the argument.

### `check_wheel_reproducibility.py`'s `--repaired` needs the timestamp pinned

- **`build_repaired_twice_and_compare` returns 1 and prints
  `SOURCE_DATE_EPOCH is not set` before either build runs, rather than
  building twice and comparing** (closes #559). Left unset, `auditwheel`
  and `delocate` stamp every member they rewrite at the moment they ran,
  so two sequential builds of one unchanged commit disagree on
  `date_time` and the script reports a wheel that reproduces as one
  that does not. The module's own docstring's `--repaired` example now
  exports the variable first, matching the dedicated step
  `wheel-reproducibility.yml`'s `repaired` job already runs before the
  same command.

### A bare placeholder ends its command, or takes a fence of its own

- **`CONTRIBUTING.md`, `RELEASING.md`, `REPOSITORY.md`, `SECURITY.md`
  and `tests/README.md` no longer write a bare placeholder with another
  word after it on the line** (closes btclib-org/.github#740). Section 9
  of the organization standard puts a bare placeholder at the end of its
  command, where the `>` closing it has nothing to open and the line is
  a parse error before it is a command. With a word after it, that `>`
  takes the word as its target: in a reader's directory holding a file
  of the placeholder's own name the `<` succeeds, the line runs, and the
  redirection creates a file named `rev-parse`, `-s`, `..main`, `--jq`,
  `--repo`, `.tar.gz` or `:bip-0340`. Pasted unfilled and on its own,
  each fence changed here creates nothing, under `zsh`, `bash` and `sh`
  alike, interactively, on stdin and as a file argument.
- `REPOSITORY.md`'s `gh api` calls put the endpoint after `--jq` and its
  `gh pr view` the pull request number after the flags, and
  `RELEASING.md`'s griffe check puts the release tag after `-s`, so that
  the placeholder is what ends the line.
- Where the placeholder sits inside a word no order ends the command in
  it, so the value takes a fence of its own with nothing under it to
  reach and the fence that consumes it writes `${name:?}`: the sdist
  version `SECURITY.md` verifies the attestation of, the upstream commit
  `tests/README.md` re-checks a pin against, and the previous version
  `RELEASING.md` reads the cycle's log from.
- `CONTRIBUTING.md` reads the hooks path with `git rev-parse --git-path
  hooks`, which answers with the primary checkout's `.git/hooks` from
  any worktree of it, rather than with a `-C <worktree>` whose own shape
  keeps the placeholder in the middle of the command.
- The pair of calls whose redirection lands on an absolute path is left
  alone, btclib-org/.github#725 being where that question sits, and so
  is the pair in `CONTRIBUTING.md`'s shared half, which is the
  standard's copy and the same bytes in every tree. Neither pair writes,
  measured the same way: `git rebase --onto <new-base> <old-base-sha>
  <child>` gives the shell `> <` and fails at the parse, and the
  remaining targets are absolute paths.

### The public-API check searches both layouts the tags carry

- **`RELEASING.md`'s griffe command passes `-s . -s src`**, where `-s .`
  alone finds no `btclib_secp256k1` to load and the check cannot run.
  `src` is where this tree keeps the package and `.` is where a release
  from before it moved under `src/` keeps it, so a comparison against
  such a tag loads neither side without the other; `release.yml`'s own
  griffe step carries the same pair, with the same reason written at
  it.

### `tests/extension_test.py` reads the installed `WHEEL`'s own tag back

- **A new test asserts the currently-installed distribution's `WHEEL`
  never carries `Tag: py3-none-any`** (closes #564). #534's fix reaches
  into an undocumented hatchling property to make an editable install
  see the tag `scripts/hatch_build.py` already decided, and nothing
  ran that path against anything but a hand-run reproduction; a
  hatchling release keeping `get_default_tag` and `get_best_matching_tag`
  by name while changing what calls the former, or what an editable
  build does with its return value, would regress silently to the
  universal tag with `mypy` unaffected, since a rename or removal is
  the one failure mode strict type-checking against hatchling's own
  `py.typed` types already catches. The test reads the distribution
  the suite's own interpreter already has installed rather than
  driving a second build, so it exercises the real, unmocked editable
  dispatch at gate speed instead of a mock of it, on every interpreter
  and every linkage the existing matrix already runs.

### `CONTRIBUTING.md` names what a plain `uv sync` does not rebuild

- **`CONTRIBUTING.md`'s `The environment and the gates` gains a
  paragraph saying that a `git pull` changing `scripts/hatch_build.py`
  is not itself enough to reach a `.venv` a `uv sync --locked` already
  considers satisfied, and names the flag that forces the rebuild**
  (closes #561). `uv sync --locked` there reports the package
  `Checked`, not rebuilt, measured against the exact editable install
  #534's fix corrected: `--reinstall-package btclib-secp256k1` forces
  it, and `--refresh-package btclib-secp256k1` alone does not, which
  the paragraph beside it does not say either.

### A merge no longer cancels the sentinel run measuring it

- **`wheel-reproducibility.yml`'s concurrency group cancels a pull
  request's own in-flight run when the pull request closed without
  merging, and queues behind it instead when the pull request
  merged** (closes #523). Pull request #520 (issue #509) is the
  measurement behind the fix: its real run, `33691065182`, was
  cancelled by the `closed` event's own run, `33691087266`, which the
  `rebuild` job's `if` then skipped, so the pair reads in the run list
  as an ordinary superseded run rather than as a measurement that never
  happened. The `closed` event's own run still lands in the same group
  on a merge, but no longer cancels the run already there, which is
  then free to finish against the head that landed.

### The `public-api` search paths name the end each one serves

- **`release.yml`'s comment on `griffe check`'s `-s . -s src` names
  which end of the comparison each search path serves, and what has to
  be true for `-s .` to come off** (closes #566). `v0.8.0.4`, the tag
  the job resolves as the previous release, keeps `btclib_secp256k1/`
  at the repository root, where this tree keeps it under `src/`, and
  either path alone raises `ModuleNotFoundError` at the end the other
  one serves. The tags before `v0.8.0` name the package
  `btclib_libsecp256k1`, and the job's nearest-tag resolution never
  reaches back to them.

### A static macOS build's configure targets the interpreter's own floor

- **`Secp256k1CFFIExtension.build_c`'s CMake configure now passes
  `CMAKE_OSX_DEPLOYMENT_TARGET`, read from the interpreter's own
  `sysconfig` `MACOSX_DEPLOYMENT_TARGET`, for a static build with
  nothing already exported** (closes #526). Where nothing is exported,
  the vendored library compiled for whatever macOS version the build
  machine runs, while the extension linking it targeted the
  interpreter's floor instead, and `ld` warned on every member of the
  archive built newer than that floor; a bare `uv build --wheel`, with
  no `MACOSX_DEPLOYMENT_TARGET` exported, now links a static extension
  whose single `LC_BUILD_VERSION` load command names that floor
  throughout. An already-exported value is left to CMake's own
  initialization from it, untouched by this, and a dynamic build --
  which links nothing this extension compiles -- never receives the
  option at all.

### The distribution's name is hyphenated where a command names it

- **An argument naming the distribution writes `btclib-secp256k1`:
  `uv sync`'s `--reinstall-package`, `pip install`'s target and its
  `--no-binary` and `--only-binary` values, `pip show`'s argument, the
  name `wait_for_pypi_release.py` asks the index for, and the message
  `RELEASING.md` gives a release tag** (closes #573). Section 3 of the
  organization standard reaches wherever the thing named is the
  distribution rather than the import package, and `[project].name` is
  `btclib-secp256k1`. `check-wheel-contents --package` and
  `griffe check` keep the underscore, each taking a module to find --
  in the wheel's library, and on a search path. PEP 503 folds the two
  spellings before a resolver matches them, so what the written form
  decides is what a reader copies out and types.

### The sentinel builds the wheels the release's other two jobs upload

- **`wheel-reproducibility.yml` gains a `dynamic` job and a
  `cross-windows` job, each building the wheel one job of `test.yml`
  uploads twice over and diffing the two archives member by member**
  (closes #540). `build-dynamic` builds the ABI-mode wheel of the
  platforms its own matrix names, with `python -m build`, and repairs
  it in the job with `auditwheel` or `delocate`; `build-windows`
  cross-compiles the `win_amd64` one on a Linux runner with nothing
  repairing it afterwards. `publish-pypi` uploads both under the
  `*-wheels-*` pattern that collects the static wheels, so what these
  reproduce to is a property of files on the index. Whether they do is
  this workflow's own output on the Actions tab, a red platform being
  what says the answer is no.
- **`check_wheel_reproducibility.py` gains `--dynamic` and
  `--cross-windows`, which build through `python -m build` and hold the
  environment that selects the linkage themselves.** The frontend, the
  repair and the platform tag are each that job's own rather than `uv
  build`'s or `cibuildwheel`'s, so neither entry point is an existing
  one with a variable exported around it. Holding the variables in the
  script is what stops an entry point named for a linkage from building
  the static wheel, agreeing with itself and reporting green on a
  question nothing asked.
- **`tests/wheel_reproducibility_platforms_test.py` holds the `dynamic`
  job's matrix against `build-dynamic`'s, as equality.** That is how it
  already holds `repaired`'s against `build-cibuildwheel`'s, and for
  the same reason: an image uploading a release wheel and missing here
  is a wheel nothing measures, and one here uploading none is runner
  time spent on a file nobody installs. `build-windows` has no matrix,
  so `cross-windows` has no list to hold against anything.
- **`RELEASING.md`'s paragraph on the `py3-none-*` wheels says the
  sentinel builds each of them twice, and that a second image is what
  stays unasked of them.** Those wheels carry the pinned timestamp for
  the reason that paragraph already gives; what has moved is that the
  archive it produces is now compared against another of the same
  commit.

### The publishing environments' `url:` links the PyPI page canonically

- **`release.yml`'s `pypi` and `testpypi` environments link
  `https://pypi.org/project/btclib-secp256k1/` and
  `https://test.pypi.org/project/btclib-secp256k1/`** (closes #581).
  Section 3 of the organization standard links a PyPI page in that
  form, and spells the distribution there as it is spelled wherever a
  person writes the name for somebody to copy out. `pypi.org/p/<name>`
  redirects to `/project/<name>/` carrying whatever spelling it was
  handed, so the short form costs the reader the hops and leaves the
  underscore in the address they arrive at. GitHub puts the value on
  the deployment's `environment_url`, where it is a link a reader
  follows.

### The workflows without a push trigger keep the run a merge would cancel

- **`links.yml` and `vendored-vectors.yml` queue a merged pull
  request's `closed` event behind the run measuring it rather than
  cancelling it, taking the expression `wheel-reproducibility.yml`
  already carries** (closes #571). Neither has a `push` trigger, so
  nothing runs either on the commit a merge creates, and the schedule
  is the next reading a merged change gets: that is the shape #523
  measured, where the cancelled run reads in the run list as an
  ordinary superseded run rather than as a measurement that never
  happened.
- **`codeql.yml`, `docs.yml`, `lint.yml` and `test.yml` keep
  `cancel-in-progress: true`.** Each triggers on a push to `main`, so
  the commit a merge creates gets a run of its own and the cancelled
  pull request run is superseded rather than lost. Which of them backs
  a required check is not what decides it: `codeql.yml` backs none and
  keeps `true` for the same reason `lint.yml` does.

### The Linux container the static wheels compile in is named by digest

- **`[tool.cibuildwheel.linux]` names the manylinux and the musllinux
  image by the digest of its content** (issue #524). A digest is
  `docker pull`able by anyone and outlives the runner image that hosted
  the build, so it states the environment of a released static Linux
  wheel to somebody who was never on the machine. `cibuildwheel`
  resolves its own `manylinux_2_28` and `musllinux_1_2` aliases to
  those same objects, through a table inside the version `uv.lock`
  pins; what naming them in `pyproject.toml` buys is that the image is
  a line there, so a `cibuildwheel` release moving it is a diff.
- **Nothing updates the digests, and the comment beside them says so.**
  The ecosystems `.github/dependabot.yml` declares are
  `github-actions`, `uv` and `gitsubmodule`, none of which reads a
  `[tool.cibuildwheel]` key. What says the value has to move is a build
  failing on an interpreter the pinned image does not carry.
- **`RELEASING.md` and `wheel-reproducibility.yml`'s header say that no
  job builds one commit through that container on two host images**
  (issue #584). `across-images` reads `rebuild`, which compiles with
  `uv build` on the runner, and `repaired`, the job that builds through
  `cibuildwheel`, carries one image per platform.

### `RELEASING.md` says which Linux wheels the container digest covers

- **The *Rebuild a release from its tag* section separates the static
  wheels `build-cibuildwheel` compiles inside the container from the
  `py3-none-manylinux*` wheels `build-dynamic` compiles on the runner**
  (closes #579). The second job runs `python -m build` with no
  container, so `[tool.cibuildwheel.linux]` is not read by it at all,
  and `auditwheel` names what it repairs for the glibc the compiled
  object requires: the `manylinux` in those file names is a
  compatibility tag rather than an image.

### The release wait's test names the distribution as its caller does

- **`tests/wait_for_pypi_release_test.py` invokes
  `wait_for_pypi_release.py` with `btclib-secp256k1`, the name
  `pypi-install.yml` passes it** (closes #586). Section 3 of the
  organization standard spells the distribution with the hyphen
  wherever a person writes the name for somebody to copy out, and the
  script's usage line is written that way; a test standing in for that
  call is one of those places.
- **`_URL` carries the same spelling because the script builds the
  request from the argument.** `f"{INDEX}/{package}/{version}/json"` is
  what the substituted transport records, and the assertion comparing
  that against `_URL` is what makes the constant the argument's own
  consequence rather than a link chosen beside it.

### A test holds `cancel-in-progress` against the workflow's push trigger

- **`tests/cancel_in_progress_test.py` fails a workflow that takes the
  `closed` pull request type, carries no `push` trigger on `main` and
  sets `cancel-in-progress` to a bare `true`** (closes #585). That
  combination is #523's defect, and `yamllint`, `actionlint` and
  `zizmor` each exit 0 on it: the rule relates two keys, so no line hook
  reaches it.
- **A workflow with a reason to cancel unconditionally under both keys
  changes the test rather than marking itself exempt.** A marker in the
  workflow would be one more line a copy carries along, which is the
  failure the test exists to catch.

### `claude-review.yml` takes the closed pull request type

- **`.github/workflows/claude-review.yml`'s `pull_request` trigger takes
  the `closed` type, and the review job declines to run on it** (closes
  #591). Merging or closing a pull request is neither a push nor a
  synchronize, so a review still held in that pull request's concurrency
  group survives it, and the type is what lands the closed event in the
  group. The review's subject is the pull request, so what the
  cancellation costs is a verdict on a pull request that has stopped
  taking changes, against a shared concurrency slot and a model call the
  workflow's own header says are not free.
- **Whether the closed event reaches a group held on a job rather than
  on the workflow is not measured** (issue #593). Every neighbour taking
  the type holds its group at the workflow level, where the run enters
  it before any job's `if` is read; `claude-review.yml` holds one per
  job, so that a push superseding a review leaves an `@claude` question
  running beside it. `tests/cancel_in_progress_test.py`'s docstring
  cites the issue where it states the two kinds of group alike, that
  clause being what the type rests on here.
- **`tests/cancel_in_progress_test.py` carries the exception, rather than
  the workflow marking itself exempt.** `claude-review.yml` has no `push`
  trigger, so the `closed` type puts it in the shape that test fails;
  `_ANSWERS_ABOUT_THE_PULL_REQUEST` names the reason it is excepted, and
  a test beside it turns red where the exception exempts nothing.
- **The negative case for the module's `closed` pattern is a trigger
  rather than a workflow.** Every `pull_request` trigger here takes the
  type, so what shows the pattern does not match any `types:` list is
  `claude-review.yml`'s own `issue_comment` list.

### The check-run reads take the commit sha from a fence of their own

- **`REPOSITORY.md`'s two `check-runs` calls take the sha from a fence
  of their own** (closes btclib-org/.github#777). The endpoint's path
  continues past the placeholder, so the `>` closing `<sha>` takes
  `/check-runs` as its target and a paste made before the value is
  filled in reaches for a file at the root of the filesystem rather than
  in the directory the reader is standing in, which is where a sweep for
  what a paste created looks. Section 9 of the organization standard
  leaves a fence of its own to a placeholder whose command's own shape
  refuses the end position, which is the shape `SECURITY.md`'s
  attestation check and `tests/README.md`'s pin re-check already carry.
- Both command fences write `${sha:?}`, so that either of them pasted on
  its own stops before asking the endpoint about a commit nobody named.
  This pair is `btclib-org/.github#725`'s shape in this tree.

### The merge-cancellation entry cites `(issue #509)` without acting on it

- **The *A merge no longer cancels the sentinel run measuring it* entry,
  landed at `def38ee`, cites `(issue #509)` for an issue it does not act
  on, and stays exactly as landed** (closes #577). Pull request #520
  closed #509, so what that bullet says is true and its parentheses are
  the defect. An issue an entry only names belongs in the sentence; this
  one is left as the record of an entry that put it in the parentheses.

### `RELEASING.md`'s rebuild section stops naming which issue section 12 cites

- **The sentence closing the two-environment rebuild section no longer
  asserts which issue section 12 of the organization standard cites for
  a compiled wheel's exemption** (closes #557). `btclib-org/.github#748`
  moved that citation off `btclib-org/btclib-secp256k1#439`, so a
  sentence restating a number from another repository's file went false
  the moment that file's own citation moved again. `#439` remaining the
  umbrella over both rebuild halves is this tree's own fact and stays;
  which number section 12 carries is the standard's to state.

### `repaired` builds a second host image on Linux, and `across-images` reads it

- **The *The Linux container the static wheels compile in is named by
  digest* entry's third bullet said no job builds one commit through
  that container on two host images (issue #584); `repaired` now
  carries a second host image on `linux-x86-64` and `linux-aarch64`,
  reused from `rebuild`'s own pair, and `across-images` compares it**
  (closes #524). The two families are read as separate directories
  rather than merged into one: an unrepaired `uv build` wheel and a
  `cibuildwheel`-repaired one of the same interpreter are not the same
  file, and a line saying they disagree would mean nothing.
- **`compare_one_platform` pairs a set of wheels per image by name where
  an image can hold more than one, and otherwise compares the two
  images' one wheel each through `diff_wheels` regardless of name.** A
  macOS or Windows runner's deployment target reaches the platform tag,
  so two images of one of those platforms can name the one wheel each of
  them built differently while the question about its members is still
  open; pairing that pair by name would read the name difference as two
  wheels with nothing in common and never compare a member. Linux's
  `manylinux` and `musllinux` wheels, from the one interpreter, are where
  a name is what tells two genuinely distinct wheels apart.
- `build_repaired_twice_and_compare` takes an optional `keep_wheel`
  reached through `--repaired --keep-wheel <dir>`, since a Linux
  `cibuildwheel` run leaves a `manylinux` wheel and a `musllinux` one
  from the one interpreter.

### `claude-review.yml`'s concurrency group moves to the workflow level

- **`claude-review.yml` groups per workflow rather than per job now, so
  a closed pull request event lands in the group when the run is
  created, before either job's `if` is read** (closes #593). Whether a
  job-level group -- what the review job carried until now -- ever
  claimed anything for a job an `if` skipped was never established, and
  stays that way; moving the group removes this file's dependence on
  that answer rather than supplying one. The key discriminates by
  `github.event_name` so the review's own group and an `@claude`
  mention's never collide, a mention falling back to `github.run_id`,
  unique to its own run, which is what an absent concurrency block left
  every mention with before.

### Section 9's comment and placeholder rules land in this tree's markdown

- **Every trailing `#` comment on a command line inside a `shell` fence
  moves to prose above the fence, `CLAUDE.md`'s `WT=` line loses the
  trailing example that gave its mid-path placeholder a word to redirect
  into, `REVIEWING.md`'s standalone placeholders go bare, and the
  whole-line `#` comments opening `CONTRIBUTING.md`'s `detect-secrets`
  fence -- two of them carrying an apostrophe -- move to prose the same
  way** (closes btclib-org/.github#789) (issue btclib-org/.github#771,
  issue btclib-org/.github#786, issue btclib-org/.github#772). `zsh`
  leaves `INTERACTIVE_COMMENTS` unset, so a trailing comment's words
  reach the command as arguments, and an apostrophe among them opens a
  quote the fence never closes -- which is what killed the
  `detect-secrets` fence under an interactive `zsh` and is fixed the
  same way section 9 fixes a trailing comment. `CLAUDE.md`'s comment
  additionally sat after the `WT=` line's own placeholder, giving its
  closing `>` a word to redirect into and turning an unfilled paste into
  a write at the root of the filesystem instead of a parse error at the
  shell.

### `CLAUDE.md` names what this session measured of its gates and API

- **`wheel-reproducibility.yml`'s `across-images` job is now named as
  red by design on Linux's `rebuild` half, with the Linux-repaired half
  named as the one a red run still has to keep green.** `rebuild`
  builds through a plain `uv build` entering no container, so its half
  of `across-images` measures the host image's own toolchain rather
  than this tree; the repaired half, added by #524, builds inside the
  pinned container and is what the sentinel actually claims.
- **`CLAUDE.md` now names the invocation that reaches
  `markdownlint-cli2` directly** — `uv run --locked --only-group lint
  pre-commit run markdownlint-cli2 --files <file>` — the hook being a
  node dependency outside the `lint` group and unreachable through
  `uv run --only-group lint markdownlint-cli2` on its own.
- **`CLAUDE.md` now names `pre-commit`'s log spelling of the sdist
  hook, `check sdist`, against the `check-sdist` id
  `.pre-commit-config.yaml` gives it**, so a grep for the wrong
  spelling no longer reads as the hook not having run.
- **`CLAUDE.md` now names the organization Actions endpoint as the
  control for this repository's own empty variable and secret
  stores**, since both of the repository's own endpoints answer
  `total_count: 0` and neither can tell a real absence from a store
  nobody has populated at either level.
- **`CLAUDE.md` now names how the `merge=union` driver's blank-line
  damage to `CHANGELOG.md` escapes both `git diff --numstat` and
  `git rebase`'s own exit code**, and that reconstructing the file
  from the new base's blob is what catches it where those two do not.

### secp256k1-zkp is vendored as a second submodule, pinned at a commit no tag names

- **`.gitmodules` now carries `secp256k1-zkp` beside `secp256k1`, pinned
  where #603 decided rather than at a release: zkp cuts no tags** (closes
  #604, issue #603). The published wheels do not build against it and no
  wrapper reads it yet; #605 is what first does. The vendored-source
  review this pin stands on read the delta against mainline's own tip
  rather than the whole tree, `src/modules/` and `include/` only: the
  core modules both trees share are changed in the same places, not
  replaced, and what is new to this package is zkp's own extra modules
  and its own `musig`, unreachable from mainline at any pin.
- **`check_submodule_pin.py` gained a second half for a submodule with no
  release to resolve**: README.md now declares the zkp pin as the url of
  its GitHub commit page, and the check compares that string directly
  against the index's gitlink, reading neither a tag nor the vendored
  clone at all. The mainline half is untouched; the two run independently
  and a single failing commit reports whichever pin disagrees, not merely
  the first one checked.
- **The sdist now carries a second vendored tree, and the exclude list
  gained the entries the local-autotools-debris risk shares with
  `secp256k1`'s own** — the flat filenames only, not the nested autotools
  boilerplate directory, whose exact contents at the pinned commit this
  change does not verify (btclib-org/btclib-secp256k1#611).
- **The CI matrix's own `submodules: true`/`recursive` checkouts are left
  as they are.** Every one of them now also clones `secp256k1-zkp`, which
  no job yet builds; measured against this pin, a shallow clone of it
  costs on the order of a second and single-digit megabytes, small next
  to the minutes those jobs already spend compiling `secp256k1`, and
  scoping every checkout down to `secp256k1` alone would touch its own
  fetch-depth semantics in each of them for that saving. `lint.yml`,
  which runs `check-sdist`, needs both submodules checked out regardless,
  for the sdist it builds there to be the one this package actually
  ships.
- **`CLAUDE.md`'s worktree recipe now runs `git submodule update --init`
  with no path, initializing every submodule rather than naming
  `secp256k1` alone**, which a second submodule made false: `check-sdist`
  answers "SDist matches git" against an sdist missing a whole
  uninitialized submodule's content, reading `git ls-files`, which
  reports a submodule as its own gitlink rather than as the files under
  it (btclib-org/btclib-secp256k1#612, reproduced against `secp256k1`
  alone and not this change's own defect to carry).

### The sdist excludes name the aux directory upstream actually uses

- **`pyproject.toml`'s sdist-exclude entries for the autotools boilerplate
  a local `./autogen.sh && ./configure` leaves behind now name
  `autotools-aux/`, not `build-aux/`** (closes #611). The previous
  entries matched nothing at either submodule's pin: reasoned from
  upstream's `Makefile.am` rather than measured, they named a directory
  upstream had already renamed before `secp256k1`'s pinned `v0.8.0`. The
  replacement list is the file `./autogen.sh && ./configure` actually
  wrote, run against a disposable clone of each submodule at its own
  pin, and `secp256k1-zkp` gets the same nested entries `secp256k1`
  does, confirmed the same way rather than assumed to match.

### A hook refuses an uninitialized submodule ahead of check-sdist

- **A new `submodules-checked-out` pre-commit hook fails, naming which
  submodule, where any `.gitmodules` lists is not checked out** (closes
  #612). `check-sdist` trusts `git ls-files --recurse-submodules`, and
  that flag silently omits an uninitialized submodule's content from its
  own answer rather than erroring on it, so the sdist and the comparison
  it is checked against agree on shipping nothing for that submodule at
  once. The hook runs ahead of `check-sdist` in
  `.pre-commit-config.yaml` and reads `.gitmodules` and the filesystem
  only, so it costs nothing `check-sdist` was not already going to
  spend. Whether the silent omission itself is upstream `check-sdist`'s
  to fix is argued on the issue rather than assumed; the guard here does
  not wait on that answer.

### `cffi_build.py` grows a fourth, flag-gated path over secp256k1-zkp

- **`BTCLIB_LIBSECP256K1_ZKP=true` builds a second static extension,
  `_btclib_secp256k1_zkp`, over the vendored secp256k1-zkp submodule,
  every one of its own modules turned on** (closes #605). Unset, which
  is every build this project ships, `scripts/cffi_build.py`'s
  `ffi_ext_zkp` is `None` and `scripts/hatch_build.py`'s hook skips the
  `pyproject.toml` `cffi_modules` entry naming it rather than building
  it: a static file has no environment variable to condition an entry
  on, so the decision moves into the build description, where the flag
  is already read. `BTCLIB_LIBSECP256K1_DYNAMIC` or
  `BTCLIB_LIBSECP256K1_CROSS_COMPILE` alongside the flag raises before
  either does anything, rather than silently ignoring it: two
  dynamically linked cores are not a combination this project has built
  or tested. `scripts/README.md` and `stubs/_btclib_secp256k1_zkp.pyi`
  -- the second, so strict mypy typechecks a module that exists only
  after the flagged build -- describe it the way the three ordinary
  paths and the primary extension's own stub already are.
- **`Secp256k1CFFIExtension` and the new `Secp256k1ZkpCFFIExtension`
  share their CMake, architecture and header-preprocessing logic through
  a new `VendoredCMakeExtension`**, so that the two extensions' own
  differences -- which submodule is read, which of its CMake modules are
  turned on, which of its headers the cdef comes from -- are the whole
  of what either subclass states. The header-stripping pattern widens
  from `#include` to allow whitespace before `include`: three of
  secp256k1-zkp's own headers spell their own include of `secp256k1.h`
  that way, which the unspaced pattern left in the concatenated blob for
  `gcc -E` to fail resolving, there being no `-I` on that command for it
  to find the file through.
- **`test.yml` gains one job, `zkp`: Linux x86-64, one interpreter,
  static only**, matching the coverage job's own argument for measuring
  once rather than across the matrix. It proves the fourth path compiles
  and imports, then runs the tests marked `zkp` -- a marker
  `pyproject.toml` now registers, none carrying it yet, #607, #608 and
  #609 being what adds them. `pytest -m zkp` therefore exits 5, pytest's
  own "no tests ran", and the job's own step is the one place that
  exit code is treated as expected rather than as a failure.
- **The sdist exclude list gains `/_btclib_secp256k1_zkp.*`, beside the
  primary extension's own root-artifact entry**, which does not also
  match it: gitignore-style matching treats `.` as a literal character,
  so `/_btclib_secp256k1.*` needs a literal dot immediately after
  `_btclib_secp256k1`, which `_btclib_secp256k1_zkp.so` does not have.
  Running `scripts/cffi_build.py` directly with the flag set leaves this
  artifact at the repository root the same way the primary extension's
  own entry already guards against.

### A sentinel verifies the secp256k1-zkp pin's signer

- **`vendored-vectors.yml` gained a `zkp-pin` job, the external anchor
  the zkp submodule pin did not have** (closes #613). `_check_zkp_pin`
  is a self-consistency check entirely inside this repository, by
  design; this is the network half, in the shape the existing `pin` job
  already has for the mainline submodule, answering a narrower question
  because secp256k1-zkp cuts no tags: who signed the pinned commit, not
  that a project released it. Neither project's own `SECURITY.md` names
  that person, Andrew Poelstra -- so the fingerprint recorded is his,
  cross-referenced against his own site the way the existing job's
  comment already asks a human to do, and against GitHub's independent
  copy of the same key. It records that he personally authored and
  signed the one commit pinned today, not that he dominates the
  project's history: measured, he is seventh by author count, at
  roughly 4% of it, with three other contributors together holding
  around two thirds -- so a re-pin authored or signed by someone else is
  the likelier case, and fails this job until that pull request adds
  their own fingerprint the same independently-sourced way, a cost
  stated in the workflow's own comment rather than left to be
  rediscovered. That key is expired without being revoked, so the job
  reads GnuPG's own status codes directly rather than `git
  verify-commit`'s exit code, which fails a merely-expired key exactly
  as it would a forged one.
- **A sentinel, not a gate**, for the reason every network check in that
  workflow already is one, confirmed against `REPOSITORY.md`'s required
  checks rather than assumed.

### `btclib_secp256k1.zkp` always exists, and loads its extension lazily

- **The subpackage always exists; the flagged extension it wraps mostly
  does not** (closes #606). `import btclib_secp256k1.zkp` always
  succeeds and never imports `_btclib_secp256k1_zkp` -- nothing in
  `__init__.py` reaches into the subpackage either, so importing the top
  package still costs nothing for a second core it may never load. The
  first access to `zkp.ffi` or `zkp.lib` is what reaches for the
  extension, through a module-level `__getattr__` of the same shape
  `_load_lib` already has; where the build has none, the `ImportError`
  it raises names `BTCLIB_LIBSECP256K1_ZKP=1` and the sdist rather than
  leaving a caller with the bare "No module named".
- **`btclib_secp256k1.zkp.context` holds a context of its own**, created
  and randomized the way `context.py` does for the primary one, and read
  the same lazy way: `import btclib_secp256k1.zkp.context` on its own
  needs no flag either, so `docs/source/btclib_secp256k1.rst` documents
  it without one. Its own `check()` raises what secp256k1-zkp reported
  on the calling thread, through a thread-local pair of callbacks of its
  own -- a call made through zkp's `lib` is never explained by the
  primary package's `check()`.
- **beta is the namespace, restated in the subpackage's own module
  docstring rather than as a runtime warning**: #283's decision, and a
  `DeprecationWarning`-style category was declined because this
  project's own `filterwarnings = ["error"]` would turn every `zkp`
  import, here and downstream, into a hard failure for a status the
  namespace already states for free.
- Expose no module yet: #607 is `zkp.musig`, next.

### The worktree-removal fence stops on an unset `WT`

- **`CLAUDE.md`'s worktree-removal fence reads `git worktree remove
  --force "${WT:?}"`, replacing the bare `"$WT"`, and the paragraph
  above it says what the `:?` is doing there** (issue
  btclib-org/.github#790). That removal stands in a fence of its own
  because the block above it ends in a placeholder, so it is pasted
  alone into whatever shell the reader is in: bare, `"$WT"` expands to
  the empty string where nothing set it and the command runs on that,
  where `${WT:?}` makes the expansion fail and the removal does not run.
  Section 9 of the organization standard asks for both halves -- a fence
  with nothing in it that fails at the parse is live, so it writes each
  value the reader was to set as `${name:?}`, and prose beside the fence
  says what `:?` is doing there, since a reader who is not told deletes
  it. The prose added is `btclib-org/.github`'s own sentence, byte for
  byte.

### `claude-review.yml`'s fork comment names a repository that is not a fork

- **The job header's argument for comparing by `full_name` rather than
  by `.fork` illustrated the distinction with `btclib-org/bbt`, which is
  not a fork** (issue btclib-org/.github#456). The argument stands --
  `.fork` is a property of the head repository rather than of the pull
  request -- and only the example had stopped instancing it. The
  replacement is `btclib-org/bbt`'s own wording, landed there first as
  [PR 8](https://github.com/btclib-org/bbt/pull/8), adapted only in the
  repository the `gh api` readback names: `gh api
  repos/btclib-org/btclib-secp256k1 --jq .fork` answers `false` here too.

### The uv floor moves again, to the ceiling Dependabot bundles today

- **`[tool.uv]`'s `required-version` moves from `>=0.12.1` to
  `>=0.12.7`, the ceiling Dependabot's own uv-ecosystem updater bundles
  today** (issue btclib-org/.github#448). Section 1 sets the floor at
  the ceiling rather than below it because that updater runs `uv lock`
  with exactly the uv it ships and refuses rather than upgrading
  itself, so a floor above the ceiling would silently stop every lock
  update it attempts; the failure the floor guards against is an
  *older* uv rewriting the lock, and raising it as the ceiling rises is
  always safe.

### `README.md` and `SECURITY.md` say which vendored library answered

- **`README.md`'s Design section names the library behind each call:
  everything outside `btclib_secp256k1.zkp` is libsecp256k1, everything
  under it secp256k1-zkp** (closes #610, issue #603). A namespace rather
  than an argument per call, because the libraries overlap by name and
  not by API -- `musig` is in both, and the fork's is mainline's entry
  points plus the ones its adaptor signatures need. The criterion that
  flips the flag's default, putting secp256k1-zkp in the published
  wheels, is quoted from #603 rather than paraphrased.
- **The *Wrapped modules* table is scoped to mainline, and the `zkp`
  namespace takes a paragraph after it**, naming its own `lib`, `ffi`
  and `context` and sending a reader to the API documentation for which
  modules are there: that set grows a module at a time, where a list
  here would be a line every such change has to remember to edit.
  `silentpayments` runs the other way and is said to -- secp256k1-zkp
  has no such module at the pinned commit, so BIP352 is mainline's
  alone. *Build* names `BTCLIB_LIBSECP256K1_ZKP`, pointing at
  `scripts/README.md` for the variables choosing among the compile
  paths.
- **`SECURITY.md` says which library answered a call, so that a reporter
  does not have to derive it**: `btclib_secp256k1.zkp` delegates to the
  fork, which is beta because it cuts no tag for a vendored-source
  review to anchor against and publishes the modules it adds beyond
  mainline as experimental. The fork's own security policy names the
  address mainline's does, so where a flaw in the C code goes is the
  same either way; what differs is that no published wheel carries the
  extension behind the namespace, making a report under `zkp` a report
  about a build made from source. The subpackage's own module docstring
  defers this status here, and the argument it gives for declining a
  runtime warning stays with it.

### `btclib_secp256k1.zkp.musig` wraps every entry point zkp's musig header declares

- **zkp's own MuSig2 -- `KeyAggCache`, `SecretNonce` and `Session`
  shaped like `btclib_secp256k1.musig`'s own, built over zkp's `ffi`,
  `lib` and `ctx`, never mainline's** (closes #607). #283's structural
  finding is why: zkp's `nonce_process` takes a sixth argument, an
  optional adaptor point, `musig_adapt` and `musig_extract_adaptor`
  read the `nonce_parity` a session built by *that* call reports, and
  every opaque struct this needs -- keyagg cache, session, secnonce,
  even a plain `secp256k1_pubkey` -- is a distinct cffi type from
  mainline's, measured directly: passing one across raises `TypeError:
  ... the types are different`. So nothing here calls
  `btclib_secp256k1.keys` or `.xonly`; only `_scalar.py`'s
  pure-argument helpers and `_secret.wipe` cross the boundary safely.
- **Every entry point defers `ffi`, `lib` and `ctx` to its own call**,
  rather than importing any of the three at module scope: importing
  this module is what Sphinx's autodoc does to document it, and the
  documentation build never sets `BTCLIB_LIBSECP256K1_ZKP`.
  `docs/source/btclib_secp256k1.rst` now carries `:members:` for it.
- **Validated against BIP327's own vectors**, the same files
  `tests/vectors_test.py` reads for mainline, run unchanged against this
  module. BIP327 defines no adaptor extension, so that path is checked
  by round trip instead: pre-sign, adapt with a known secret, extract
  the secret back out of the two signatures.
- **The `coverage` job's ratchet gains a third run, over the flagged
  build.** Neither the static nor the dynamic run this ratchet already
  measures sets `BTCLIB_LIBSECP256K1_ZKP`, so this module's own lines
  are unreachable by either; a third step runs the tests marked `zkp`
  against the flagged build, its own data file joining the other two on
  the same `coverage combine` line the dynamic run's already sat on.
  The static step also gains `--cov-fail-under=0`, the dynamic step's
  own flag: it is no longer the one run of the three that meets 100 on
  its own, `btclib_secp256k1.zkp.musig` being a line it cannot execute
  either. The union alone stays gated at 100%. The separate `zkp` job is
  unchanged by this: it proves the fourth build path compiles and
  imports on a clean runner, which is a different question from
  coverage.
- **Neither the `coverage` job's new step nor the separate `zkp` job
  tolerates pytest's exit 5** on the tests marked `zkp`: a selection
  collecting nothing is the failure it is everywhere else, now that
  this branch's own tests carry the marker and are collected by both.
- **The `Example:` blocks carry no `>>>` prompts.**
  `tests/examples_test.py` discovers a package's modules through
  `pkgutil.iter_modules`, which does not descend into subpackages, so a
  doctest under `zkp` is never collected on any build -- measured
  directly, not assumed (issue btclib-org/btclib-secp256k1#621, which is
  where that gap is tracked and is not this branch's to close). Written
  as doctests, these blocks would have claimed a coverage
  `CONTRIBUTING.md` does not give; as plain illustrative code they claim
  none.
- **The 100% floor is a property of the union, measured in CI; the
  ordinary local `pytest` command stays light and no longer reaches
  it.** `btclib_secp256k1.zkp.musig` is opt-in behind
  `BTCLIB_LIBSECP256K1_ZKP` by decision (#603), and this suite never
  imports it without the flag -- `tests/zkp_musig_test.py` and
  `tests/zkp_musig_vectors_test.py` both `importorskip` out,
  `tests/all_test.py` excludes `zkp` by name, and
  `tests/examples_test.py` does not descend into subpackages -- so none
  of its lines is executed by the suite, though an unflagged
  environment can plainly import the module itself, the way the
  documentation build does for its own `:members:`; nothing in it can
  be *called* there either, every entry point opening with a
  `_boundary()` that raises `ImportError` naming the flag. At landing,
  the plain command reported **92.49%**, not 100%, and that shortfall
  was not the module alone: `[tool.coverage.run]` names `tests` in
  `source` too, so the two test files above were measured the same way
  and each stopped at its own `importorskip`, reported missed rather
  than absent from the table. All three files short, not a broken
  tree. Making the union the documented local gate was declined: it
  would force every contributor to build a second C library with CMake
  for an ordinary gate. So was an `omit` on the flagged test files: the
  same exemption already declined once in this campaign, in another
  spelling. `CONTRIBUTING.md`'s gate section now says so, and carries
  the command that re-derives the number should it ever move.

### `zkp.ecdsa_s2c` wraps sign-to-contract and the anti-exfil protocol

- **Every entry point `secp256k1_ecdsa_s2c.h` declares, wrapped one for one**
  (closes #609): `opening_parse`, `opening_serialize`, `sign` and
  `verify_commit` for sign-to-contract, and the four `anti_exfil_*`
  functions the header's own module docstring lays out as the ECDSA
  Anti-Exfil Protocol -- the reason this module wraps the anti-exfil
  half rather than deferring it, that being what the module exists for
  in production. Every entry point reads `zkp.context.ctx` -- and,
  through it, `zkp`'s own `ffi` and `lib` -- lazily inside itself rather
  than at the module's own top level, which is what lets
  `docs/source/btclib_secp256k1.rst` carry its `:members:` without the
  documentation build ever setting `BTCLIB_LIBSECP256K1_ZKP`. A
  signature crosses this module's boundary in the 64-byte compact form
  only; an opening crosses it as the 33-byte compressed serialization
  `opening_serialize` writes and `opening_parse` reads back, `sign` and
  `anti_exfil_signer_commit` answering it directly.
- **Pinned by `src/modules/ecdsa_s2c/tests_impl.h`'s own two fixed
  vectors**, reproduced against this wrapper rather than against a bare
  call: the key of `0x55` repeated, the message of `0x88` repeated, and
  for each vector the opening `sign` answers and the opening
  `anti_exfil_signer_commit` answers for the same data used as a host
  commitment. The full anti-exfil protocol is run end to end against
  random keys too.
- **A `secp256k1_pubkey` or `secp256k1_ecdsa_signature` the primary
  package's `dsa` or `keys` module parses is not pointer-compatible with
  what this extension's own calls expect**, two independently built
  cffi extensions never sharing a struct type even where the C layout
  agrees -- measured directly, `TypeError: ... the types are different
  (check that you are not e.g. mixing up different ffi instances)`. So
  `anti_exfil_host_verify`'s public key and every signature this module
  parses are parsed again here, against `zkp`'s own `ffi` and `lib`,
  rather than through the primary package's modules. `_scalar.py`'s
  `octets` and `scalar` cross that boundary safely and are reused
  unchanged, working through `ffi.buffer` and `ffi.typeof` rather than
  opaque struct identity.
- **A hand-written stand-in, not the flagged extension, is what reaches
  100% coverage of this module unflagged**: none of the functions this
  module wraps exist in the primary extension, so unlike `zkp.context`'s
  own tests -- which reuse the primary package's real, always-built
  `ffi` and `lib`, sharing context creation and both callbacks with
  secp256k1-zkp's own header -- nothing here could reuse a real
  implementation of them. There is no longer a single build the
  `coverage` job's ratchet measures: it is the union of three, one
  flagged, gated at 100% after `combine` (#607). The tests driving the
  real fixed vectors and the end-to-end protocol are marked `zkp` and
  guarded with `pytest.importorskip("_btclib_secp256k1_zkp")`: the
  `coverage` job's own third step selects and runs them against the
  flagged build, folding them into that union, and the ordinary static
  and dynamic runs skip them cleanly rather than failing. The separate
  `zkp` job selects them the same way, for a different question -- that
  the fourth build path compiles and imports on a clean runner, not
  coverage.

### `zkp.generator` and `zkp.rangeproof` wrap generators and range proofs

- **`zkp.generator` wraps every declaration of `secp256k1_generator.h`
  and `zkp.rangeproof` wraps every declaration of
  `secp256k1_rangeproof.h`, in one pull request because the second calls
  into the first for the commitment and the generator each of `verify`,
  `rewind` and `sign` takes** (closes #608). Both defer `ffi`, `lib` and
  `ctx` to each function's own first call rather than to import, the
  same seam `zkp.context`'s own `__getattr__` docstring gives a reason
  for, and neither reaches for the flagged extension merely by being
  imported.
  Two libsecp256k1-zkp objects with no counterpart in mainline's own
  cdef, `secp256k1_generator` and `secp256k1_pedersen_commitment`, are
  what forced two local array-building helpers rather than
  `btclib_secp256k1._cdata.array`: that helper's `ffi.new` is mainline's,
  which declares neither struct, so an array of either built through it
  is an "undefined type name" `ffi.error`, measured rather than assumed.
- **`generator.h()` reads `secp256k1_generator_h` from the library at
  call time rather than carrying a copy of its serialization**, which is
  what lets a caller's own independently-computed pin of the same
  generator be checked against the library itself and not against a
  copied literal.
- **`rangeproof.sign` asks `secp256k1_rangeproof_max_size` for its proof
  buffer rather than carrying a fixed size.** The issue's own body named
  a constant the header does not define; the worst-case buffer size is a
  runtime answer from the library, not a `#define`, and is not a promise
  about a future version of it either.
- **Every real-vector and property test needs `BTCLIB_LIBSECP256K1_ZKP`,
  and is guarded by `pytest.importorskip("_btclib_secp256k1_zkp")` and
  `pytestmark = pytest.mark.zkp`**, so an unflagged run skips the two
  files cleanly instead of failing to import them. The wrapper modules
  themselves reach the tree's coverage floor from a pure-python stand-in
  driven the same way `zkp_test.py`'s own `STAND_IN` is; the two
  real-vector files' own lines are counted missed by the `coverage`
  job's static and dynamic steps, `source` naming `tests` in
  `[tool.coverage.run]`, and are covered instead by that job's third
  step -- `pytest -m zkp` against the flagged build, #607's own addition
  -- whose data joins the other two on the same `coverage combine` line.
- Fixed vectors lifted from secp256k1-zkp's own `tests_impl.h`: `2*G`'s
  generator and commitment serialization and their malleated-marker-byte
  cases from `test_generator_fixed_vector` and
  `test_pedersen_commitment_fixed_vector`, and the proofs of
  `test_rangeproof_fixed_vectors`. `generator.h()`'s x-coordinate is
  checked against btclib-org/btclib#1055's own independent pin of the
  same generator.

### `CONTRIBUTING.md`'s submodule transcript is a captured run

- **The `git submodule init` and `git submodule update` transcript under
  *The environment and the gates* is the output of a clone of this
  repository** (closes #629). `.gitmodules` names `secp256k1-zkp`
  alongside `secp256k1`, where the sample output that block carried
  named `secp256k1` alone: a reader comparing it against their own
  terminal saw one registration and one clone where git prints one of
  each per submodule. The absolute clone destinations are elided and the
  `checked out` line git prints per submodule is left out, both noted in
  the sentence under the block. That line names the commit the gitlink
  holds, which moves with the pin, and `detect-secrets` reads a bare
  40-hex as a high-entropy string.
- **The prose around it speaks of the vendored libraries rather than of
  the one.** A `git worktree` starts with those directories empty rather
  than with `secp256k1/` alone; `git submodule update --init` with no
  path after it reaches every submodule `.gitmodules` names; and the
  lint gate fails outright where one is not checked out at all,
  `submodules-checked-out` asking that on every invocation.

### The conflicting-lint-rules comment names no ruff revision

- **The comment opening `[tool.ruff.lint]`'s `ignore` list sends the
  reader to ruff's own `docs/formatter.md`, under "Conflicting lint
  rules", with no version beside it** (closes #635). Ruff runs here from
  two pins that move independently -- `.pre-commit-config.yaml`'s hook
  `rev` and `uv.lock`'s own `ruff` entry -- so no one figure describes
  both, and nothing re-derives one written in a comment: a hook bump
  moves the first, a lock refresh the second, and neither reads this
  file. The version decided nothing either. `docs/formatter.md` at ruff
  `0.16.3`, `0.16.4` and `0.16.5` differs only in the `rev:` of its own
  pre-commit example, the list of rules the formatter conflicts with
  identical across them --
  `gh api "repos/astral-sh/ruff/contents/docs/formatter.md?ref=<tag>"`
  is the read. What answers the question against whatever ruff this
  tree runs today is the command the comment already names beside it,
  `ruff format --check .`, which prints the warning directly.

### Every guard that walks the package descends into `zkp`

- **`tests/citations_test.py` reads the sources recursively** (closes
  #622). `Path.glob` lists a directory's direct children alone, so
  nothing under `src/btclib_secp256k1/zkp/` reached the reader and a
  test named in a docstring there was held to no test existing --
  `tests/docs_test.py` reads the same tree with `rglob` and does
  descend, which is the disagreement between them. Nothing under the
  subpackage cites a test, so what changes is what the guard covers
  rather than what it reports.
- **`tests/secret_test.py`'s walk descends into the subpackage, and
  `_calls` dedents the source before parsing it** (closes #626). A
  function defined inside a module-level `else:` block --
  `btclib_secp256k1.zkp`'s own `__getattr__` is one -- comes back from
  `inspect.getsource` still indented, and `ast.parse` answers that with
  `IndentationError`, which is not the `OSError` the walk catches. The
  population the walk finds is unchanged by the descent: nothing under
  `zkp` calls `_secret.take`, those modules importing `wipe` alone. A
  module is keyed by the name it is reached through, `zkp.musig` rather
  than `musig`, the two being different modules of this package.
- **The secrets the subpackage answers do not pass through `take`**
  (issue #640). A secret that never goes through it is what the walk
  cannot see, which SECURITY.md records for
  `silentpayments._found_output`; the secret adaptor
  `zkp.musig.extract_adaptor` recovers, the blinding factors
  `zkp.generator` answers and the one `zkp.rangeproof.rewind` recovers
  are read out of their buffers with `ffi.unpack` the same way. The
  walk's own docstring names them, and what to do about the wrappers is
  that issue's rather than this branch's.
- **`tests/all_test.py`'s census walks the subpackage** (closes #627).
  `zkp.musig` and `zkp.ecdsa_s2c` are ordinary modules with ordinary
  `__all__` lists whose entry points defer the extension into their own
  first call, so the census asks them what it asks the modules above
  them, and `test_every_module_is_declared` names what it finds for the
  subpackage it sits in. `zkp.ffi`, `zkp.lib` and `zkp.context.ctx` are
  served by a module-level `__getattr__` that loads the flagged
  extension, so `hasattr` propagates the `ImportError` an unflagged
  build gets: `exported_name_exists` reads a name instead, counting an
  `ImportError` naming `BTCLIB_LIBSECP256K1_ZKP` as a name the module
  serves, and `test_an_exported_name_that_is_not_there_is_reported`
  holds it to answering false for one nothing serves. `zkp.context`'s
  `ffi` and `lib` go into `UNEXPORTED`, that module's own comment
  giving why they are assignments where `ctx` is an annotation.
- **`CONTRIBUTING.md`'s coverage paragraph says what an unflagged run
  executes under `zkp.musig`** (closes #645). What keeps the plain
  `pytest` command short of the ratchet is that nothing calls into that
  module without the flag, not that nothing imports it: the census and
  the walk above both do, and so does the documentation build for its
  own `:members:`, so what an unflagged run executes there is
  module-level lines and no function body. The command already in that
  section is what says how much that comes to.
- **`tests/all_test.py`'s docstring names the underscore exception
  without a total** (closes #647). Nothing in the file re-derives how
  many modules sit directly under the package --
  `test_every_module_is_declared` compares two sorted lists and never
  their length -- so a number there is a line every new module has to
  remember to edit.

### `pyproject.toml`'s comments say why, not what the file used to say

- **The comment above `[tool.hatch.build.targets.sdist]`'s exclusion
  list dates nothing by the vendored submodule's pin** (closes #637).
  Its closing clause put an upstream rename "before the pinned v0.8.0",
  and `.github/dependabot.yml` carries a `gitsubmodule` ecosystem: the
  pull request that moves that pin touches the gitlink and leaves this
  file alone. What a reader of the list needs is why its entries come
  from a run at each pin rather than from upstream's own `Makefile.am`,
  and that is now said in the present tense: none of the submodule
  entries the comment introduces exists until
  `./autogen.sh && ./configure` are run, so a stale one matches nothing
  and fails nothing, and one matching a file a submodule tracks fails
  nothing either (btclib-org/btclib-secp256k1#655) -- `check-sdist`
  reads this very list through its hatchling plugin and subtracts what
  it matches from the tracked files it reports missing.
  `git submodule status` answers in one line which commit is pinned,
  about the tree in hand.
- **The comment above `[project]`'s `dependencies` stops naming the
  floor the file used to declare** (closes #642). Section 9 of the
  organization standard keeps history out of prose that lands, and this
  clause is not the kind that goes stale -- an immutable past constraint
  cannot -- so what it costs is the comment's subject rather than its
  truth. The sentences before it already give every floor its own
  present-tense reason: `ffi.unpack` arrives in cffi 1.6, 1.17 is the
  first release supporting CPython 3.13, and 2.0 the first supporting
  3.14 and the free-threaded build. The present-tense equivalent would
  restate the sentence above it, a single loose floor being exactly the
  resolver picking "a cffi that cannot know them", so the clause goes
  rather than being rewritten.

### The zkp tests make the extension state they need instead of inheriting it

- **The state a build with no flagged extension is in is what a
  `without_the_extension` fixture makes, for every test that drives
  either branch of the loader** (closes #623). It writes `None` over
  `sys.modules["_btclib_secp256k1_zkp"]`, the import system's own
  negative cache, so `importlib.import_module` raises out of it whatever
  is on disk; and it empties what `btclib_secp256k1.zkp`'s and
  `btclib_secp256k1.zkp.context`'s `__getattr__` write into their own
  module globals on first access, since a read that finds one of those
  warm never calls the `__getattr__` under test. Both halves are needed
  under `BTCLIB_LIBSECP256K1_ZKP=true`, where the extension imports and
  the tests of the modules wrapping zkp-only entry points fill those
  caches for real, pytest-randomly deciding whether they run first.
  `test_importing_the_subpackage_does_not_reach_the_extension` asks a
  fresh interpreter instead, the shape
  `tests/extension_test.py`'s own `_imported_modules` already uses:
  `sys.modules` in the interpreter running the suite answers about
  everything that ran before it, never about the import. Declaring the
  build was the declined alternative: this tree declares one with a
  `pytest.importorskip("_btclib_secp256k1_zkp")` at the top of the
  module and a `pytest.mark.zkp` beside it for the flagged runs' own
  `-m zkp`, which would skip this file in the static and dynamic runs --
  the unflagged builds every published wheel carries -- and leave the
  loader's failure branch driven only where the extension is present.
- **`test_check_with_nothing_reported` empties `zkp.context`'s own
  thread-local before it calls `check`.** No wrapper in the subpackage
  calls `check` at all, so a call through zkp's `lib` that violates a
  precondition leaves its reason on the thread for whichever `check` a
  caller makes next -- the contract `tests/callbacks_test.py`'s module
  docstring states for the primary package.
  `zkp.musig.SecretNonce.partial_sign` refusing a mismatched private key
  is such a call, and under a flagged build that reason is what the test
  would otherwise inherit.
- **The `ImportError` that path raises names `BTCLIB_LIBSECP256K1_ZKP=true`**
  (closes #631), which is the value `scripts/cffi_build.py` compares
  against: a reader following `=1` builds the sdist without the flagged
  extension and meets the same `ImportError` again. The `match=`
  patterns in `tests/zkp_test.py` name that value too, so the message
  and the guard on it move together.
- **`zkp/context.py`'s `__getattr__` docstring says the modules wrapping
  zkp-only entry points read `ctx` inside each call rather than at their
  own import** (closes #633), which is what `zkp/musig.py`'s
  `_boundary`, `zkp/ecdsa_s2c.py`'s `_bindings` and `zkp/generator.py`'s
  and `zkp/rangeproof.py`'s `_handles` do.
  `docs/source/btclib_secp256k1.rst`'s own comment above the `zkp`
  stanzas states the same thing, and rests on it: a module-scope read
  would make `import btclib_secp256k1.zkp.musig` raise `ImportError` in
  every environment without the flag, the documentation build among
  them.
- **`tests/zkp_generator_test.py`'s and `tests/zkp_rangeproof_test.py`'s
  autouse fixtures clear those same caches on the way in as well as on
  the way out** (closes #646). Each installs a fake extension, and every
  test in either file calls a wrapper that reads `zkp.context.ctx`
  before anything else, so a cache another test left warm is what the
  *first* test of either file runs against -- the fake installed and
  never consulted, and the failure naming whatever the real library
  answered. `tests/zkp_ecdsa_s2c_test.py`'s own `_clean_extension_cache`
  already clears both ways and is the shape these two now take. The
  names are dropped with `pop` on each module's own `__dict__` rather
  than tested for with `hasattr`, which does not answer False for
  `zkp.ffi`: its own `__getattr__` raises `ImportError` where the
  extension is absent.
- **`tests/all_test.py`'s public-name census asks whether a name is a
  submodule of the module holding it, rather than whether its value is a
  `ModuleType`** (closes #654). A cffi `Lib` answers
  `isinstance(value, ModuleType)` True without being one: its `__mro__`
  is `Lib`, `object` and `issubclass(_cffi_backend.Lib, ModuleType)` is
  False, but it reports `module` as its `__class__`, which is what
  `isinstance` consults where that differs from `type()`.
  `btclib_secp256k1.zkp.context.lib` holds such an object once the
  flagged extension has been loaded, so the census dropped `lib` there
  under a build carrying that extension and kept it under one that does
  not, while `UNEXPORTED` records both `ffi` and `lib` -- a guard whose
  answer depended on the build rather than on the source. Comparing a
  value's `__name__` against the qualified name it is bound under is
  what the dropped filter was for, a submodule becoming an attribute of
  its package as soon as anything imports it, and it reports a module
  bound under any other name instead of dropping that too. Two tests
  hold it: one drives the discrimination against a stand-in of the shape
  measured on a real `Lib`, which every unflagged run collects, and one
  drives the census against the extension itself, marked `zkp` and
  guarded with `pytest.importorskip` so that `-m zkp` -- the selector of
  the flagged jobs in `.github/workflows/test.yml` -- is what runs it.

### `CLAUDE.md`'s worktree paragraph names the gate and the zkp build flag

- **The paragraph under the worktree recipe names the lint gate as what
  fails where a submodule is not checked out** (closes #644).
  `.pre-commit-config.yaml`'s `submodules-checked-out` hook looks for a
  `.git` of its own under every path `.gitmodules` names and exits 1
  naming each one missing, so `uv run --locked --only-group lint
  pre-commit run --all-files` fails on a worktree holding `secp256k1`
  and not `secp256k1-zkp`, with no project installed and nothing built.
- **`check-sdist` is named as the gate that says nothing there.** It
  compares the sdist it builds against `git ls-files --cached
  --recurse-submodules`, and that command prints nothing at all for a
  submodule that is not checked out -- not the files under it and not
  its gitlink -- so the missing tree is absent from both sides of the
  comparison and the hook answers "SDist matches git" (#612). The
  paragraph said instead that nothing in the gates says so, and that
  the gitlink is what `git ls-files` reports there.
- **The build's clause is present tense and names the flag that decides
  it.** `scripts/cffi_build.py` builds the vendored `secp256k1-zkp`
  where `BTCLIB_LIBSECP256K1_ZKP` is `true` (#605), where the paragraph
  described a build that had yet to read that submodule at all.
- **The `#612` citation keeps its issue and loses its parenthetical.**
  The clause beside it addressed the reviewer of the branch that wrote
  the sentence, on whether the defect was that branch's own to carry,
  which is not a question anybody reading `CLAUDE.md` asks.

### `tests/examples_test.py` reaches a docstring under `zkp`

- **`_modules()` enumerates with `pkgutil.walk_packages`** (closes
  #621). `pkgutil.iter_modules` lists the top package's own children and
  stops at `btclib_secp256k1.zkp` itself, so a doctest anywhere under
  that subpackage was collected by neither
  `test_the_examples_of_a_module_run` nor
  `test_the_package_carries_examples_at_all`, on any build.
- **The walk carries an `onerror` that raises.** With none,
  `pkgutil.walk_packages` swallows the `ImportError` a package raises as
  it is descended into and yields nothing from under it, which leaves
  the enumeration at what `iter_modules` returns and the tests reading
  it passing over the difference.
  `test_a_subpackage_that_will_not_import_stops_the_enumeration` holds
  it to that, refusing the subpackage with a meta-path finder.
- **A module under `zkp` is parametrized with the `zkp` marker and
  guarded by `pytest.importorskip("_btclib_secp256k1_zkp")`**, the pair
  the test modules under `tests/` use. Its examples run in the flagged
  step of the coverage job and in the `zkp` job, and skip where an
  unflagged build leaves them nothing to call into.
- **`test_the_package_carries_examples_at_all` parses the examples
  rather than running them**, that test reaching every module
  `_modules()` names and so the ones the test above skips.
  `doctest.DocTestFinder` is what `doctest.testmod` finds them with, so
  counting what it parses asks the same question of the package without
  entering an example. `optionflags=doctest.SKIP` is the rejected
  alternative: it suppresses execution too, but `attempted` counts a
  skipped example only from Python 3.13, and `requires-python` here is
  `>=3.10`.
- **The `Example:` blocks of `btclib_secp256k1.zkp.musig` and
  `btclib_secp256k1.zkp.ecdsa_s2c` are doctests**, `>>>` prompts and
  expected output, in place of the literal blocks that cited this issue
  for not being run.
- **`CONTRIBUTING.md` qualifies its sentence about where an example
  runs**: a docstring under `btclib_secp256k1.zkp` runs where the
  flagged extension is built, and the paragraph says where in CI that
  is.
- **`pyproject.toml`'s comment on the `zkp` marker names the guard that
  sits inside a marked test**, beside the one at the top of a marked
  module.
- **`tests/examples_test.py`'s module docstring carries no count.**
  Section 9 of the organization standard asks for none, and `CLAUDE.md`
  gives the reason a number of wheels in particular is a liability: it
  is a line every matrix change has to edit, with nothing failing when
  it is not edited.

### The badge row's links carry the qualifier the runs page reads

- **Every workflow-status badge link at the head of `README.md` carries
  `?query=branch%3Amain`** (issue btclib-org/.github#762): the runs page
  filters on that spelling and ignores the image's `?branch=main`, so the
  page a badge opens lists the runs the badge answers for.

### The routing section names each vendored library's own tracker

- **`CONTRIBUTING.md` sends a flaw in a vendored library's C to that
  library's own tracker, and says how a reader tells which library
  answered** (closes #638). The import line is the discriminator, the
  same one `SECURITY.md` routes a vulnerability by: what answers under
  `btclib_secp256k1.zkp` is BlockstreamResearch/secp256k1-zkp, and what
  answers outside it bitcoin-core/secp256k1. The bullet names
  `.gitmodules` as where a vendored submodule's upstream is written, so
  the rule holds for a submodule vendored later.
- **The section's heading and its opening sentence count no
  repositories**, and the bullet for this repository says the bindings
  drive what they wrap. Section 9 of the organization standard asks for
  no counts, and a count of repositories is a line a second vendored
  library falsifies.

### The vendored-bump convention turns on what the upstream publishes

- **`CONTRIBUTING.md`'s conventions bullet says what a bump owes by what
  the upstream publishes** (closes #639), rather than by naming one
  submodule. A pin at the commit a release tag names carries the version
  number and the `RELEASE_NOTES.md` line naming the wrapped release with
  it; a pin at a commit no tag names carries neither and is reviewed
  against the commit it replaces.
  `gh api repos/BlockstreamResearch/secp256k1-zkp/releases` answers an
  empty list, where the same call for `bitcoin-core/secp256k1` does not.
- **`.github/dependabot.yml`'s comment describes the entry it sits
  above**: the `gitsubmodule` ecosystem is configured per directory, so
  the entry at the repository root covers every submodule the
  `.gitmodules` there names. The entry itself is unchanged.

## v0.8.0.4

### `musig` wraps MuSig2, closing the one exception `lib` was for

- **Every `musig` entry point.** Parse and serialize for
  `pubnonce`, `aggnonce` and `partial_sig`; `pubkey_agg`, `pubkey_get`,
  `pubkey_ec_tweak_add` and `pubkey_xonly_tweak_add` for key
  aggregation; `nonce_gen`, `nonce_gen_counter` and `nonce_agg` for
  round one; `nonce_process`, `partial_sign`, `partial_sig_verify` and
  `partial_sig_agg` for round two. Closes #282, "may deserve an issue of
  its own" in #156, and unblocks
  [btclib#1048](https://github.com/btclib-org/btclib/issues/1048) (the
  bindings as a test oracle for `btclib.ecc.musig2`) and
  [btclib#1049](https://github.com/btclib-org/btclib/issues/1049)
  (delegating `partial_sig_verify_`).

  `secp256k1_musig_keyagg_cache` and `secp256k1_musig_session` have no
  serialization -- "no serialization and parsing functions (yet)" in the
  header's own words -- and #87 declined an opaque *handle* for exactly
  that shape, "a handle is a lifetime someone has to own and invalidate."
  `_secret.py` recorded the clause that reopened it: the handle "belongs
  where the signing state lives," and a MuSig2 session is that place.
  `KeyAggCache` and `Session` are the exception taken, held state beside
  `ssa.Signer` and `keys.PubkeyTweakChain` -- and, unlike either of
  those, not chosen for a saving over octets that do not exist to be
  saved: *Outposts past the boundary* in the README says why the
  existing rule for holding an object does not reach them.

  `SecretNonce`, the third class this module adds, is the one that has
  to be wiped: `ssa.Signer` is the model, a `with` statement overwriting
  it whether the block signs or raises, and a wiped object refusing to
  sign rather than signing with the zeros. libsecp256k1 already zeroes a
  secnonce inside `partial_sign` -- "will abort if given a secnonce that
  is all zeros" -- for a session that runs to completion; what
  `SecretNonce` adds is the wipe for one abandoned before that, which
  the C side never sees. SECURITY.md now names two such buffers instead
  of one. The check and the wipe are also made safe against two threads
  sharing one `SecretNonce`: `_take` reads `self._secnonce` and clears
  it as one atomic step under a lock private to the instance, rather
  than as two statements a scheduler could interleave between -- which
  on the free-threaded interpreter this package ships a wheel for
  (`cp314t`) would otherwise let two threads both pass the check and
  both drive `secp256k1_musig_partial_sign` over the same secnonce at
  once, the MuSig2 nonce-reuse condition that leaks the private key.

  `partial_sign` verifies the partial signature it makes, by default:
  the C call "does not verify the output partial signature, deviating
  from the BIP 327 specification," and its header recommends verifying
  with `partial_sig_verify` "to prevent random or adversarially
  provoked computation errors" -- `ssa.sign`'s own argument for its
  `verify`, on a signature assembled from more moving parts than a solo
  one.

  A parse failure and a semantic failure both answer libsecp256k1's bare
  `0`, with nothing on the thread for `context.check` to raise: `KeyAggCache`,
  `nonce_agg` and `Session.partial_sig_agg` each parse their array one
  contribution at a time under its own name instead of handing a
  comprehension to the array they build, so a `ValueError` on a bad
  public key, nonce or partial signature names its position -- "public
  key at index 2" rather than a refusal that could be any of them. A
  handful of failures that examining every C code path showed
  unreachable given already-parsed objects -- `nonce_agg`'s own
  aggregation, `pubkey_agg`'s, `nonce_process`'s, and
  `partial_sig_agg`'s -- are `RuntimeError` instead, matching the
  distinction `pyproject.toml`'s coverage configuration already draws
  between the two exceptions this package raises.

  `tests/test_vectors.py`'s BIP327 cases now drive `musig` itself rather
  than the raw bindings underneath it, `tests/test_musig.py` is new,
  holding the three classes to the lifetime `tests/test_signer.py`
  already holds `ssa.Signer` to, and `tests/test_concurrency.py` races
  threads on one `SecretNonce` to hold the lock above to the guarantee
  it exists for. The README's *Wrapped modules*, *Design*, *Outposts
  past the boundary* and *Thread safety* sections, REVIEWING.md's own
  checklist, and `tests/README.md`'s vendored-vector record, are
  updated with it; `docs/source` gains the module's stanza.

## v0.8.0.3

### A tag-integrity ruleset closes the last unsigned link in the release chain

- **`tag-integrity`, `target: tag`, `refs/tags/v*`: `required_signatures`,
  no bypass actor.** `release.yml` publishes to PyPI on `push: tags:
  ["v*"]`, and until now that tag was the one unattested link in an
  otherwise fully-signed chain — every commit reaching `main` already
  carried a verified signature, `main-integrity` requiring it with no
  bypass actor, but nothing stopped an annotated, unsigned tag from
  triggering a release. RELEASING.md's tagging step already produces a
  signed tag (`git tag -s`); the ruleset now enforces the same thing at
  the repository-settings level rather than only documenting it. No
  `deletion` or `non_fast_forward` rule: RELEASING.md's own recovery
  path deletes and re-tags a release that failed before the PyPI
  upload, and either rule would block that. Created directly by the
  maintainer, a live repository-infrastructure change rather than a
  pull-request review — this entry documents it. Existing tags are
  unaffected, the ruleset applying to pushes going forward only.
  Sibling repository btclib closed the same gap as issue #1022.

### Claude reads a pull request against REVIEWING.md

- **`claude-review.yml`**, two jobs: one on every non-draft pull request,
  whose prompt names `REVIEWING.md` rather than restating it, so the
  standard moves without the workflow being edited; one answering
  `@claude` in a comment, carrying no prompt of ours on purpose — the
  action reads the comment that triggered it. It gates nothing and must
  not: `main`'s required contexts are named outside the repository, and
  a review that held a merge would make a model's judgement a branch
  rule. The gates are not re-run, `test.yml`, `lint.yml` and `docs.yml`
  running them beside it on the same sha.

  Three things it refuses to do silently, each measured in btclib before
  being asked not to. Without `CLAUDE_CODE_OAUTH_TOKEN` the action
  reviews nothing and reports **success**. Without `id-token: write` it
  dies before authentication, the action minting a GitHub OIDC token at
  startup whatever the Anthropic credential is. And it refuses to run at
  all when the workflow file differs from the copy on the default
  branch — a pull request must not be able to edit the workflow holding
  the credential — reporting that refusal by skipping, green. It now
  fails on an empty secret and on an empty `execution_file`, which is
  exactly when no review was written. The consequence is deliberate: on
  a pull request that adds or edits this file the job is red until the
  change is on `main`.

  The automatic job skips a pull request from a fork, which is not a
  policy but what secrets do: none but `GITHUB_TOKEN` reaches a runner a
  fork triggered. `@claude` still answers there, `issue_comment` being a
  base-repository event. It is also the one workflow in
  `CONTRIBUTING.md`'s table taking no `workflow_dispatch`, both jobs
  reading the pull request or the comment that triggered them.

### The pull request is the only way into main, and the review has a standard

- **The landing convention says what is in force: the squash button.**
  `CONTRIBUTING.md` said the landing is "a push rather than a button",
  `REPOSITORY.md` titled a section for the push its bypass was for, and
  `CLAUDE.md` kept a fast-forward exception for a stacked pull request.
  The `main-self-merge` bypass now reads `pull_request` mode, so it
  excuses the approving review a solo-maintainer repository cannot
  produce and excuses nothing else: a direct push to `main` is refused
  for everyone, the holder included. The ruleset also names `squash` as
  the only merge method it accepts, stating the constraint where the
  rule is rather than only in a repository toggle. What the exception
  bought — a stacked child keeping its base — is paid for with a rebase
  instead, a button recreating rather than moving whatever the count of
  commits: GitHub's documentation has rebase-and-merge "always updates
  the committer information and creates new commit SHAs". The
  configuration is the organization's, identical in btclib,
  bitcoin-core-rpc and btclib-benchmarks.

- **`REVIEWING.md` is the standard a review is written against**, the
  reviewer's half of `CONTRIBUTING.md`: what a review establishes before
  it gives an ack, what a finding must contain and how it labels its
  severity, and what becomes of everything a reviewer notices that the
  diff is not about — every collateral finding is filed as an issue
  rather than asked for in a comment. It states no new rule; the rules
  it cites stay in the files that state them. Registered the way
  `CONTRIBUTING.md` is: a page of the sphinx toctree through a
  `reviewing_link.md` shim, named from the README and from `CLAUDE.md`,
  which is the file a repository-aware reviewer reads.
  `.claude/commands/review.md` is it as the `/review` command. The body
  is deliberately the text btclib carries, one section excepted: the
  questions a review of *this* tree asks and a generic one would not.

### The recoverable check takes that key too

- **`recovery.sign` and `recovery._sign_` take a keyword-only `pubkey`**
  (#246), the key the recovered one is compared with, so that
  `_abort_unless_recovered` no longer derives a key the caller is
  holding. Everything around it is what #245 settled for `dsa` and is
  not restated in a second shape: the key is taken on trust, it is
  refused beside `verify=False` in both halves, and octets are parsed at
  the boundary so that a mistyped argument is refused before anything is
  signed rather than arriving as a verdict on a signature the caller now
  has.
- **The dearest check of the three, and the same saving as `dsa`'s.**
  Measured in one session with `dsa.sign` beside it so the two
  are comparable rather than merely printed together -- an Apple M5,
  macOS 26.6, arm64, CPython 3.14.6, nine rounds of 3 000 calls with the
  minimum of each kept, the private key handed in as octets in every row,
  and the unchecked signature run a second time so the noise has a figure
  of its own:

  | `recovery.sign` | per call | the check |
  | --- | --- | --- |
  | `verify=False` | 12.07 | |
  | the key derived, as before | 35.00 | 22.93 |
  | a compressed key handed in | 29.67 | 17.60 |
  | an uncompressed key handed in | 27.49 | 15.42 |
  | the point already parsed, through `_sign_` | 27.25 | 15.18 |
  | `verify=False` again (the noise) | 12.09 | ±0.02 |

  `dsa.sign` in that same session was 12.14 unchecked, 31.97 with the key
  derived and 24.55 with an uncompressed one handed in, so its check went
  19.83 to 12.41 -- both within a few tenths of #245's own session, which
  is between sessions and not within either. The 7.51 removed here is
  `secp256k1_ec_pubkey_create` and nothing besides: timed alone in the
  same session it is 7.53. The 2.18 between the two serializations is the
  field square root that recovers y and the 0.24 under it is the
  uncompressed parse only the private half avoids, both agreeing with the
  2.02 and 0.26 measured for `dsa`. What is left is what a recovery and a
  comparison cost over a verification, and it is the same ~3 microseconds
  before and after -- 22.93 against 19.83 derived, 15.42 against 12.41
  handed in -- which is what says the argument removed the derivation and
  changed nothing else.

  Which also settles a guess #246 made before anything was measured:
  "It is the scheme whose check is doing the most work, so the saving is
  largest". The check is the most work, 22.93 against 19.83; the saving
  is not larger. 7.51 here against 7.42 in `dsa` is 0.09, in a session
  whose own noise row is ±0.02 but which calls a 0.16 difference between
  the two square roots "agreeing" -- and both land on the 7.53 the call
  costs timed alone, which is the reading that matches "and nothing
  besides". The saving is one `secp256k1_ec_pubkey_create`, in both
  modules, at one price.
- **A mismatch now has three causes, and two of them share an answer.**
  The key given is not this private key's, the recovery id is not the
  signature's, or the computation faulted; the first is an argument and
  the other two are not. One comparison separates them and it is paid
  only where something already went wrong: the recovered key against the
  derived one. Where those agree the signature is the signer's and the
  argument is wrong, which is the `ValueError`; where they do not, the
  signature does not recover its own signer, which is what a wrong id and
  a fault both look like from here. That they share the `RuntimeError` is
  the decision rather than an oversight -- a caller of `sign` cannot pass
  an id at all, it coming back from `secp256k1_ecdsa_sign_recoverable`
  beside the signature, so an id that is not the signature's is a fault
  by the time the check runs.
- **So the discrimination is `dsa`'s shape, and the third cause is what
  the issue asked about.** #246 left open whether `recovery` should take
  the argument at all, the saving being the largest and the diagnosis
  having the most ways to go wrong. What decided it is that the third
  cause needs no third message: it is unreachable from any argument of
  `sign`, and where it is reachable -- through the parsed signature the
  private half takes -- it is the fault the `RuntimeError` already names.
  So the cost of taking the saving is one comparison on a path that was
  already failing.
- **The case no other module in this package can write.** A wrong
  recovery id is one `parse_compact` away, so all three causes are
  reachable with no stand-in anywhere:
  `test_a_wrong_id_under_a_right_key_is_not_reported_as_a_wrong_key`
  signs once and asks the real libsecp256k1 three questions -- the
  signature's own id under the signer's key, the other id under that same
  key, and the signature's own id under a stranger's -- and holds the
  first to passing and the other two to the two different exceptions.
  Both misdiagnoses are what it rules out: a right key with a wrong id
  reported as a wrong argument, and a wrong key reported as a fault.
- **The rest of the group is `dsa`'s, asserted again here** rather than
  assumed to carry over: the same signature and the same recovery id
  whichever way the check got its key and in both serializations of it,
  the refusal of a key beside `verify=False` in both halves, octets that
  are not a key refused before signing, and the property over forty keys
  and messages -- which is a stronger sentence here than there, since the
  key handed in has to be the single key the signature recovers rather
  than one of the keys it verifies under.
- **The README's section on the check carries the tables**, and the
  sentence that said the saving was "available and not yet taken" for
  `recovery` is now the one that says what taking it cost.

### A scalar may be memory the caller can overwrite

- **`_scalar.scalar` takes a cffi array of exactly 32 octets and hands it
  on unconverted** (#247), so wherever a private key or a tweak is
  accepted, `ffi.new("unsigned char[32]", ...)` is too. It is the only
  argument of these bindings that is not copied at the boundary, and the
  reason is what the copy would be: an immutable `bytes` of a secret,
  which nothing can overwrite and which stays until the collector gets to
  it. A caller signing again and again under one key can now hold it in
  memory it owns and wipe that when done, with no `bytes` of the key made
  per call. What that gives up is stated where `octets` states the
  opposite -- the copy is also what stops a caller changing the octets
  libsecp256k1 is reading -- and it is the caller's to give up, the
  buffer and its synchronization being theirs already.
- **What decided the shape is where the coercion actually binds**, and
  the issue's premise was wrong about it. #247 reasoned that a
  `dsa.Signer` holding a buffer "would have to turn it back into a
  `bytes` on every call". It would not: `dsa._signed` and `dsa._checked`
  hand libsecp256k1 the pointer, exactly as `ssa.Signer` bypasses
  `keypair` per signature, so a prototype signer holding
  `ffi.new("unsigned char[32]")` produced byte-identical signatures
  before this change and hoisted 0.37 microseconds of 23.42 -- an Apple
  M5, macOS 26.6, arm64, CPython 3.14.6, nine rounds of 3 000 calls with
  the minimum kept, the checked call with its key handed in as the
  anchor and run again for a noise of 0.02. Which leaves the README's
  verdict on speed where it was.
- **It binds on the derivation, and the sharpest case is a diagnosis.**
  `keys._pubkey_from_prvkey_` asks for a scalar, so a key in a buffer
  could not have its public key derived at all -- and the failing branch
  of `dsa._checked`, which derives precisely in order to tell a wrong
  argument from a fault, answered `TypeError: the private key must be
  bytes or an int, not __CDataOwn`. A caller whose hardware had faulted
  was told they had mistyped an argument they passed correctly, which is
  the misdiagnosis #245 built that branch to avoid. So the door is open
  for the diagnosis rather than for the microsecond, and
  `test_the_discrimination_holds_for_a_key_held_in_a_buffer` holds both
  sides of it with the key in a buffer.
- **Any item type an octet wide, because what crosses is a re-view.**
  `ffi.from_buffer` over `ffi.buffer` answers an `unsigned char[32]`
  pointing at the caller's own memory, which is the one item type cffi
  will pass to `const unsigned char *`: without it the acceptance would
  be `char` and `unsigned char` alone, and `uint8_t[32]` -- what a C
  programmer writes for 32 octets -- would clear every check and die at
  the boundary in cffi's words about an internal ctype. Not `ffi.cast`,
  which answers the same pointer for nothing and does **not** keep the
  memory alive: measured, a cast whose owner is dropped and collected
  reads 32 octets that no longer hold the key, with no error anywhere.
  `from_buffer` keeps a reference to what it views.
- **Three obligations pass to the caller with the copy**, and the
  docstring names them because none of them exists for a `bytes`. The
  octets must stay put for the whole call, which is more than one read:
  `secp256k1_ecdsa_sign` loads the scalar (`secp256k1.c:555`) and derives
  the nonce from the same pointer (:563), and `dsa._sign_` reads it again
  per grinding attempt and in `_checked`'s failing branch -- so a write in
  between gives a nonce and a signature under two different keys, arriving
  as the fault `RuntimeError`. The memory must outlive the call, which no
  python argument has had to promise: a cffi view -- a slice, a cast --
  does not keep its owner alive, measured, and a dangling one reads freed
  memory as a key. And the length is the declaration's word, `ffi.sizeof`
  answering what the type says: a cast of 8 octets to `unsigned char[32]`
  clears every refusal and has libsecp256k1 read 24 octets of whatever
  follows, which cffi cannot report and so neither can this.
- **Three refusals, because what follows is a bare pointer** libsecp256k1
  reads 32 octets from. A *pointer* rather than an array, whose
  `ffi.sizeof` is 8 and says nothing about what it points at -- the trap
  `_secret.wipe` records from the other side, where that number would
  have wiped a quarter of a private key and reported success. An array of
  wider items: `uint32_t[8]` is 32 octets of whatever this machine's byte
  order made of them, refused for the reason `octets` refuses a
  `memoryview` of wider items. And an array of the wrong length, which is
  the check every other scalar gets and the one a bare pointer cannot be
  given later.
- **A `str` is refused before the question is asked, and that is a bug
  the suite caught rather than a case somebody thought of.**
  `ffi.typeof` reads a str as a *cdecl*: `"x" * 32` comes back as cffi's
  own `error: undefined type name`, which is neither this function's
  `TypeError` nor about the argument -- and `"char[32]"` is worse, being
  a cdecl that resolves, measures 32 octets, and would have been passed
  to libsecp256k1 as a str.
  `test_type_checks_refuse_what_merely_has_a_length` failed on the first
  spelling the moment the branch was written; the second was found
  looking for why, and both are cases now.
- **Four call sites copy the octets, and had to be taught to.**
  `keys.prvkey_negate`, `keys.prvkey_tweak_add`, `keys.prvkey_tweak_mul`
  and `silentpayments._create_outputs_` allocate a buffer of their own --
  the first three because libsecp256k1 writes the answer through that
  pointer, the last because this package wipes it in a `finally` -- so
  handing them the caller's memory would negate or zero the key that was
  passed in. They spelled it `ffi.new(cdecl, scalar(...))`, whose
  initializer is `bytes` or a list and never a cdata, so each refused one
  of the two obvious cdecls with cffi's own message about an internal
  `char[32]`: `unsigned char[32]` failed in the three `keys` functions and
  `char[32]` in `silentpayments`, and `ssa.nonce_bip340` therefore failed
  for *half of all keys*, reaching `prvkey_negate` only where the point
  has odd y. `_secret.scalar_buffer` is now the one statement of that
  copy -- `ffi.new` then `ffi.memmove`, which takes either source and
  makes no `bytes` of the secret in between -- and it says which of the
  two reasons each site has.
- **The sweep is what would have caught it, and now exists.**
  `tests/test_bytes_like.py` drove every entry point with bytes, a
  bytearray and a memoryview; it drives them with a 32-octet buffer too,
  swapping the private keys and tweaks of its own table by identity. It
  asserts the answer is the same *and* that the caller's octets are still
  there afterwards, which is the half a comparison of answers cannot see.
  Reverting one of the four sites fails it on that row. The parity branch
  gets a case of its own beside it, `PRVKEY` being 7 and even-y, so that
  the half of `nonce_bip340` no table row reaches is driven with 5 and 6
  and both parities are asserted to occur.
- **The public annotations do not widen, which was the cost the issue
  named.** `CData` is `Any`, so `BytesLike | int | CData` on `dsa.sign`
  would have stopped mypy checking every caller's private key. Only
  `scalar`'s own parameter widens: the entry points still declare
  `BytesLike | int`, so a `float` is still refused statically at the call
  the caller made, while a cdata still arrives because `ffi.new` answers
  `Any`. What is given up is mypy checking this package's own calls of
  `scalar`, whose run-time check is the one that was doing the work.
- **The cffi stub gains what the question reads**: `_CType.kind`,
  `.cname` and `.item`, and `typeof` now takes a cdata as well as a
  cdecl -- `Any`, as `sizeof`'s parameter already is for the same reason,
  cdata being what that file cannot name. It was opaque because nothing
  read what cffi answered, and its docstring says what now does. Two
  functions join it, `from_buffer` and `memmove`, being the two halves of
  what a caller's octets can become.
- **Whether a `dsa.Signer` is worth having is still
  btclib-org/btclib#982's question**, and this does not answer it. What
  it does is take the blocker away: the wiping ground that issue would
  have to be argued on no longer needs a signer at all, a caller holding
  the buffer and calling `dsa.sign` getting the same thing.

### The check takes a public key the caller already has

- **`dsa.sign` and `dsa._sign_` take a keyword-only `pubkey`**, the key
  the check verifies under, so that a caller who already holds it does
  not pay for deriving it again. It is taken on trust and never checked
  against the private key on the way in: checking it would cost the
  point multiplication the argument exists to avoid.
- **What that saves is most of what ECDSA's check costs over BIP340's.**
  Measured on an Apple M5, macOS 26.6, arm64, CPython 3.13.14, the five
  shapes alternated in one process, 9 rounds of 3 000 calls with the
  minimum of each kept, and the unchecked signature run again at the end
  so the noise has a figure of its own -- ±0.04 against an unchecked
  11.72. The check is **20.20** deriving the key per call, **15.08** with
  a compressed key handed in, **13.06** with an uncompressed one, and
  **12.80** with the point already parsed and `_sign_` called directly.
  The 7.40 between the first and the last is the derivation, which is
  `secp256k1_ec_pubkey_create` through `keys._pubkey_from_prvkey_`;
  timed alone in a session of the same shape it is 7.31, against a
  noise of ±0.14. The 7.55 the README carries and the 7.16 measured for
  `secp256k1_keypair_create` are that other call rather than this one,
  and land within half a microsecond of it because the two do the same
  work. Within the handed-in rows, 2.02 is what a compressed key costs
  to parse over an uncompressed one -- the field square root -- and
  0.26 is the uncompressed parse: what the parse adds back above the
  fully parsed row, not slices of the derivation. Under all of it is a
  bare verification, which is what BIP340's check has always been.
- **A failed check now says which of two things failed**, and that is
  what makes the trust affordable rather than merely cheap. A key that
  is not this private key's makes the verification fail exactly as a
  faulted computation does, and reporting one as the other would tell a
  caller their hardware is wrong because they passed the wrong argument.
  So the failing branch, and only the failing branch, derives the key
  and asks again: `RuntimeError` where the signature does not verify
  under the key the private key actually has, `ValueError` where it does
  and the one handed in is simply not it. The rare branch pays the
  derivation the common one saved.
- **The trust cannot let a bad signature through**, which is the
  property the whole argument rests on and is now a test rather than a
  paragraph. The keys a signature verifies under are a property of that
  signature -- `recovery.recover` walks them -- so a key fixed before
  the signature exists is not one of them.
  `test_a_key_fixed_in_advance_cannot_pass_a_signature_of_another_key`
  holds that over forty keys and messages.
- **And it catches a fault the derived check cannot.** A private key
  corrupted before it was signed with passes the derived check in
  silence: the signature and the key it is verified against come out of
  the same corrupted octets and agree. A key handed in came from
  somewhere no fault in that call could reach, so it does not agree --
  which means the `ValueError` names the likelier of two causes rather
  than the only one, and the docstring says so.
- **Both halves of the discrimination are held to.** The `ValueError`
  side has a case of its own; the `RuntimeError` side has one too, and
  it needs a substituted verification because no input reaches it --
  `raise RuntimeError` is outside the coverage ratchet, so nothing else
  would have said that stubbing the second verification to succeed
  turns every genuine fault under a handed-in key into a report that
  the caller mistyped an argument. That mutation now fails the suite.
- **And the saving itself is asserted rather than only measured**
  (#251). What the argument buys is the early return in `_checked`, and
  deleting that return changed no answer: a correct key reached the
  derived comparison, which agreed and gave back the same signature, so
  every other case of the argument passed with the derivation paid for
  again -- the figures above false and nothing red.
  `test_the_derivation_the_argument_saves_is_not_made_at_all`
  substitutes the multiplication for one that raises, and the signature
  coming back at all is what says it was never made. That mutation now
  fails the suite, and it failed nothing before.
- **Refused rather than resolved**, as `aux_rand32` beside `grind`
  already is: a key given with `verify=False` raises, being a caller
  contradicting themselves, and octets that are not a key are parsed and
  refused on the way in rather than arriving as a failed check on a
  signature the caller now holds.
- **Not on `ssa`, and deliberately.** The check there is 13.2
  microseconds whether the key is held or not, the keypair already
  holding the point, so the argument would buy nothing and sell one
  thing: a second reason a check can fail, and the discrimination step
  that reason costs. btclib-org/btclib#982 has the measurement.
- **Not folded in for `recovery`, and taken there in a change of its
  own** (#246, the section above). `_abort_unless_recovered` derived the
  same key -- `keys._pubkey_cmp_(recovered,
  keys._pubkey_from_prvkey_(...))` -- so the saving available there was
  exactly the one taken here: the recovery stays and the derivation goes.
  What differed was the discrimination, a recovered key that is not the
  one handed in having a third possible cause the two schemes above do
  not, which is the recovery id. That wanted a measurement and cases of
  its own, and is what got them.
- **The README carries all of this**, in the section on the check, which
  said `verify=False` was the only thing a caller could do about the
  cost and is where CLAUDE.md puts the design.

### A signer checks its own signature

- **`dsa.sign` and `ssa.sign` verify what they made before answering
  with it**, under the public key of the very key that made it, and take
  a keyword-only `verify` that defaults to `True` to say so.
  `ssa.sign_custom`, `ssa.Signer.sign`, `ssa.Signer.sign_custom` and the
  private `dsa._sign_`, `ssa._sign32` and `ssa._sign_custom` take the
  same argument with the same default, so no path reaches libsecp256k1
  with a weaker policy than the one above it. A signature that fails is
  a `RuntimeError` and is never returned.
- **The two halves of that arrived by different routes.** For BIP340 it
  is a step of the algorithm rather than a practice around it: *Default
  Signing* ends with "If Verify(bytes(P), m, sig) returns failure,
  abort", and the BIP's own note gives the reason and the escape --
  computation errors, random or provoked, yield a signature that "may
  leak information about the secret key", and the step "can be omitted
  if the computation cost is prohibitive". For ECDSA no standard asks,
  and Bitcoin Core does it anyway at the end of `CKey::Sign`, with no
  way to decline; declining is what `verify=False` is here.
- **What it costs was measured rather than reasoned about**, the
  variants alternated in one process over 7 rounds of 20 000 calls with
  the minimum kept for each -- an Apple M5, macOS 26.6, arm64, CPython
  3.13.14, and a noise row of ±0.04. `dsa.sign` 12.15 against 31.67,
  `ssa.sign` 15.87 against 28.57, `ssa.Signer.sign` 8.18 against 20.82.
  The finding is the gap between the two increments: 19.5 for ECDSA
  against 12.7 for BIP340, the 6.8 between them being the point
  multiplication `secp256k1_ec_pubkey_create` does and
  `secp256k1_keypair_xonly_pub` does not. The step the specification
  prescribes is the cheaper of the two, which is why neither is opt-in.
- **A caller that signs and does not publish pays for a guarantee it may
  not want**, and `verify=False` is the whole of the remedy: the
  signature is the same bytes either way, which
  `tests/test_verified_signing.py` asserts at each entry point rather
  than at one of them.
- **`recovery.sign` is in it too, and asks a different question** (#217).
  It takes the same keyword-only `verify`, defaulting to `True`, and so
  does `recovery._sign_`; what it does with it is recover the public key
  from the signature and refuse one that is not the signer's, rather
  than verify. The difference is the recovery id, which a verification
  does not look at: a signature carrying the wrong one verifies
  perfectly and then recovers somebody else's key, and recovering a key
  is what a caller of that module does with the answer. Core makes the
  same distinction in the same file -- `CKey::Sign` ends in
  `secp256k1_ecdsa_verify`, `CKey::SignCompact` in
  `secp256k1_ecdsa_recover` and `secp256k1_ec_pubkey_cmp` -- and it
  subsumes the verification exactly rather than probably. Recovery is
  not selective: for a given id it answers *the* key under which that
  `r` and `s` verify, so an inconsistent pair does not fail, it comes
  back as a different key -- and fails only where `r` is not the x of a
  point at all, which a faulted `r` is about half the time. Which is the
  stronger argument: the recovered key is by construction the key that
  verifies the signature, so `recovered == signer` **is** a verification,
  with the id checked besides. Nothing is given up by not verifying, and
  that is provable rather than argued.
- **What that check costs was measured in a session of its own**, which
  re-measured `dsa.sign` beside it rather than printing the two
  together: `recovery.sign` 12.02 against 34.41, `dsa.sign` 12.06
  against 31.54 there, agreeing with the 12.15 and 31.67 above. So the
  recovery shape costs 22.4 against ECDSA's 19.5, a recovery being about
  a verification's work with the comparison and the derivation making up
  the rest. Same method as the rest, noise +/-0.02.
- **`_abort_unless_recovered` turns `_recover_`'s `ValueError` into a
  `RuntimeError`**, which is the one place the two exception kinds of
  this package meet. "No key can be recovered" is an argument error of a
  signature a caller handed in, and nothing of the sort for one made a
  line earlier: what it reports there is the computation having gone
  wrong, which is what a `RuntimeError` means throughout.
- **The three do not check quite the same region**, which is worth a
  sentence and not a change. `ssa` verifies the 64 octets it answers
  with; `dsa` verifies the signature object and serializes it after, so
  the encoding is outside what was checked. `recovery` is the case worth
  the sentence most: what its check reads is the id inside the
  `secp256k1_ecdsa_recoverable_signature`, and the id the caller
  receives is the one `serialize_compact` writes afterwards -- so the id
  is outside the checked region exactly as the DER is. Core does the
  same, `CKey::SignCompact` recovering from `rsig` and not from the
  octets it filled, and for the same reason: the serializers are
  memcpy-shaped where the signing is arithmetic.
- **`xonly._from_keypair_` is new**, and is what makes the BIP340 half
  cheap: `xonly.from_keypair` is now that call with a serialize behind
  it, where reaching the key through the public half would have written
  a point out only to lift it back, and a lift is a field square root.
  It is the one private half whose object is a keypair, so
  `test_every_private_half_is_paired` excuses it from the parametrized
  tables the way it already excuses `ssa._verify_` and
  `xonly._tweak_add_`, and a test of its own holds the equality.
- **The fault is out of reach for the two that verify, and reachable for
  the one that recovers.** No input makes a fresh ECDSA or BIP340
  signature fail its own verification, so in `dsa` and `ssa` the `raise
  RuntimeError` is excluded from coverage for the reason every other one
  is. What is tested there is the wiring around it: the verification is
  substituted for one that refuses, and each entry point is held to
  raising rather than returning -- and, in the other direction, to *not*
  raising where `verify=False` was passed, which is the only assertion
  that sees the flag at all: the signature is the same bytes whether or
  not it was honoured, so a `verify` ignored altogether answers exactly
  what it should. Replacing every `if verify:` with `if True:` leaves
  the rest of the suite passing, which is how that hole was found rather
  than argued for. The keys of both y parities are signed with as well,
  both parities asserted to occur, because a check read off the wrong
  half of the negation BIP340 prescribes would pass for the wrong
  reason. `recovery` is the exception, and it is the test that says what
  the check is for rather than that the raise is wired to it: what that
  check reads is the recovery id, a wrong id is one `parse_compact`
  away, and `test_the_recovery_id_is_what_the_check_catches` produces
  the fault from an input and holds real libsecp256k1 to refusing it
  with no stand-in anywhere — the other parity of the same `r` recovers
  somebody else's key, ids 2 and 3 recover nothing, and the octets
  refused three lines up still verify as a plain ECDSA signature.
- **`dsa.sign` carries a `noqa: PLR0913`** and the reason above it: six
  arguments where the rule allows five, and the alternative is an
  options object for one function whose four questions group with
  nothing.
- **The default is Bitcoin Core's, and what it costs is now in the
  docstrings** (#224). Whether `dsa.sign` should default to
  `verify=False` — no standard asking the check of ECDSA, and the caller
  paying for a public key the signing itself did not need — was asked
  and answered the other way: one policy across the three modules, which
  is `CKey::Sign`'s, and a caller that has measured the check against
  its own threat model turns it off by name. A default per scheme would
  make the safer answer the one a reader has to look up, and
  `verify=False` is already the whole of the remedy. What was missing is
  the magnitude: the docstrings priced `grind` at "what the octet is
  worth" and left the check that is on by default at "a point
  multiplication and a verification", which is its shape and not its
  size. `dsa.sign` says 31.67 microseconds against 12.15 now, `ssa.sign`
  28.57 against 15.87 with the 6.8 between the two increments named as
  the `secp256k1_ec_pubkey_create` ECDSA has to do and BIP340 does not,
  and `recovery.sign` 34.41 against 12.02, the dearest of the three.
  `ssa.Signer.sign` carries the ratio rather than a third increment —
  20.82 against 8.18, the check being more than half again a signature
  whose keypair was built already, where `ssa.sign`'s is four fifths of
  one, and 1.545 against `dsa.sign`'s 1.607 is where BIP340's cheaper
  check costs what ECDSA's does — and `ssa.sign_custom`, the entry point
  btclib calls, carries `sign`'s figure with the sentence that a longer
  message costs more to sign and to check by the same hash. The figures
  are the ones measured above rather than a second session. `dsa.sign`
  also says what a caller grinding *outside* the call pays, that being
  one check per attempt where the wrapper's own `grind` checks only the
  attempt it settles on — which is the reading the caller that raised
  the issue was getting.
- **The record said the fault is not tested, and a test produces one**
  (#225). The bullet above opened "The fault itself is not tested,
  because no input produces one", which was true of #216 and false after
  #218: `recovery`'s check reads the recovery id, a wrong id is one
  `parse_compact` away, and the test that produces one holds real
  libsecp256k1 to refusing it with no stand-in. The test module's own
  header carried the same sentence and was qualified in #218; this file
  was not, so the record stated of the suite the opposite of what the
  suite does — the same defect as the "eight entry points" count #218
  removed, a claim about the tests that the tests disprove. It now
  carries the qualification the test module already found. Two lines
  from the same tail go with it: the docstring of
  `test_a_signature_that_does_not_verify_is_not_answered_with`
  documented `refusal` as "unused where the test does not refuse one",
  which was true of the other readers of `SIGNERS` and false of exactly
  this one, where it is the `match=`; and the 34-character line of this
  file's own prose, between lines of 69 to 72, which was the reflow a
  qualifier insertion did not get. That last one is why the paragraph
  above is rewrapped whole rather than at the line named: inserting the
  qualification left two more widows of the same shape, at 14 and 27
  columns, so a fix line by line would have closed one instance of the
  class and opened two. #233 counts the thirteen this change does not
  reach. No hook reflows prose, which is why every one of them passed
  the gate.
- **`SIGNERS` stops handing a test an argument no body reads** (#226).
  It grew a third element in #218 and that closed a real gap: before it
  one `match="signing produced"` matched all three modules, so the test
  could not say which failure it had provoked. The cost was that four
  tests are parametrized over the table, one reads the refusal, and the
  three that do not each carried two lines of docstring explaining that
  they do not — which is how that sentence reached the fourth.
  `SIGNING_CALLS` is the calls alone and `REFUSING_CALLS` the call with
  its refusal, both derived from `SIGNERS` in a comprehension, and the
  name goes with the refusal: it is the `ids=` and no body has ever read
  it, so five tests stop declaring it and five docstrings stop excusing
  it. `_DEFAULTING` is the same move on the one table that is not
  `SIGNERS` — a mapping of the ten functions whose default is asserted,
  its keys being those ids. The mapping the issue proposed instead —
  `_REFUSALS` keyed by module, with `SIGNERS` back to pairs — is
  declined for the reason the issue states against itself: a row would
  no longer be the whole truth about its entry point, and finding a
  module by splitting a test id on `.` is a weaker statement than the
  message written beside the call. The ids are stated once as well,
  every table here being those rows in that order.
- **The module docstring of `tests/test_verified_signing.py` names the
  tests it points at** (#256). Two of its landmarks were positions rather
  than names, and each had come to name the wrong test. "The last test in
  this file" arrived with #217 meaning
  `test_the_recovery_id_is_what_the_check_catches`, and #245 appended the
  `dsa` group after it. "The last of those tests" meant
  `test_a_wrong_id_under_a_right_key_is_not_reported_as_a_wrong_key` and
  arrived with #246 -- which in that same diff put two tests after the one
  it points at, so it was false in the commit that wrote it. That is the
  whole argument against the form: a position is a claim nothing checks,
  and an append falsifies it in silence, sometimes its own. Both now name
  the test.
- **And the account of the two key-handed-in groups gains the third thing
  they hold**, in one clause for both halves rather than one for `dsa`:
  that the saving is asserted and not only priced, by
  `test_the_derivation_the_argument_saves_is_not_made_at_all` and
  `test_the_derivation_the_recoverable_check_saves_is_not_made_at_all`.
  Raised as a non-blocking review finding on #254, where folding it into
  that diff would have put the asymmetry in a second place. What a name
  still does not buy is a check -- a rename falsifies it as quietly as an
  append falsified a position -- which is #258, and the count in the same
  docstring is #259.
- **And that check exists now** (#258). `tests/test_citations.py` reads
  every backticked span in this suite and in the package's own sources,
  and holds each one that spells a test name to being a test that exists.
  The package half is not incidental: `btclib_secp256k1/dsa.py` names
  cases behind a claim it makes about itself, and so does
  `btclib_secp256k1/recovery.py`, so a rename can falsify a shipped
  docstring.
- **The reader is the whole of the design**, and two shapes are why. A
  citation is wrappable -- `tests/test_docs.py` breaks
  `test_no_documented_module_has_gone_away` at an underscore across two
  lines -- and a pattern anchored to one line does not report that as
  dangling but never sees it, which is the failure a guard must not have;
  so a span is collapsed, of whitespace and of the `#` a wrap inside a
  comment block adds. And a cited name may be somebody else's:
  `tests/test_vectors.py` names rust-secp256k1's own `test_low_r` to say
  which upstream vector it reproduces. Those are listed with where each
  comes from and each is held to still being cited, so the list cannot
  become names nobody removed. Text rather than the syntax tree, which
  inverts `tests/test_secret.py`'s reasoning for the opposite population:
  there a mention had to be told from a call, and here the mention is the
  subject -- half of them in comments no tree carries.
- **The module reads every source but itself**, which is what makes the
  staleness half mean anything: it names the exempted test in order to
  explain the exemption, so reading itself would let the guard keep its
  own exemptions alive, and its reader's cases are citations held as
  fixtures rather than prose -- one of them a name that deliberately does
  not exist. `CHANGELOG.md` and `HISTORY.md` are out of scope for a
  different reason than noise: a released section is that release's
  account of itself, and a check over it would ask for the record to be
  edited whenever the tree moves.

### The frames between an entry point and libsecp256k1

- **Five entry points are spelled out rather than composed of their
  halves**: `keys.parse` and `xonly.parse`, which delegated to their
  `_parsed`, `keys.pubkey_tweak_add`, which was three calls, and
  `dsa.verify` and `ssa.verify`, which parsed through one call and
  verified through another. What a python frame is worth was measured by
  alternating the two spellings in one process, 7 rounds each and the
  minimum kept for each -- an Apple M5, macOS 26.6, arm64, CPython
  3.13.14: `keys.parse` of 65 bytes 0.010 of 0.205 and of 33 bytes 0.013
  of 2.324, `xonly.parse` of 65 bytes 0.012 of 0.485, `ssa.verify` 0.009
  of 14.275, `dsa.verify` 0.035 of 11.813, `keys.pubkey_tweak_add` 0.037
  of 3.403. Small everywhere, and largest where the call is shortest.
- **`dsa.sign` is composed still, and that is a measured result rather
  than an omission.** Three spellings were tried -- `_sign_` inlined, the
  DER serialization inlined, and both -- and all three land within 0.03
  microseconds of the composed one and on the wrong side of it. A
  signature is 11.9 microseconds of libsecp256k1; two python frames do
  not show against it, and a body written twice for nothing is worse
  than the frames.
- **Measuring the two spellings one after the other is what made them
  look bigger.** Run in sequence rather than alternated, the same
  comparison reported 0.027, 0.083, 0.154 and 0.261 for four of the
  calls above -- two to four times the alternated figure, and for
  `dsa.sign` a saving that is not there at all. The machine drifts under
  a benchmark, and a pair measured in a fixed order gives the drift to
  one side of it.
- **Every private half stays, and removing them was measured before it
  was declined.** They are what a caller holding a parsed object does
  not pay a parse for, and that is worth 0.558 microseconds per call
  against a 65-byte key, 2.676 against a 33-byte one -- where the parse
  is a field square root -- and 2.687 on a tweak applied to its own
  output. Two orders of magnitude more than the frames are worth, and in
  the opposite direction: deleting them to save a frame on the octets
  path would cost the object path a parse at every call. `ssa.Signer`
  and `keys.PubkeyTweakChain` are the same trade already made.
- **So five bodies are written twice**, once taking octets and once
  taking the object, and the equality is asserted rather than assumed:
  `tests/test_parsed_keys.py` holds every public half to its private
  one, pair by pair and over both serializations of a public key, and
  `test_every_private_half_is_paired` makes an unpaired half an absence
  rather than a test nobody wrote. That test is what makes the
  duplication survivable, and it is why it was not extended to
  `recovery`, `ellswift` or `silentpayments`, whose entry points no
  benchmark reaches and which still compose.

### What a crossing costs, and what stops being paid for it

- **`context.guarded` is gone, and every call it held is now a bare
  call.** It cleared the thread, ran the libsecp256k1 call, and raised
  whatever the illegal callback had recorded, which turned a refused
  object into an exception at each of the twenty-six places it was
  used. Measured around one trivial C call, it cost 0.201 microseconds
  of the 0.292 that call took — an Apple M5, macOS 26.6, arm64, CPython
  3.13.14, minimum of 9 rounds of a million calls — and an entry point
  crossing twice, as `keys.pubkey_tweak_add` does, paid it twice.
  `context.check` is unchanged and still exported: what it reports is
  now every caller's to ask for, and its docstring says when.
- **and what a refused object does instead is the contract this
  changes.** Where the wrapper read a return code it still raises, with
  its own message rather than libsecp256k1's — `keys.serialize` of a
  NULL pointer is a `RuntimeError` naming the serialization, where it
  was a `ValueError` naming `pubkey != NULL`; `xonly.serialize`,
  `xonly._drop_y`, `xonly.from_keypair`, `recovery._to_der_`,
  `recovery.serialize_compact`, `dsa.serialize_der`,
  `dsa.serialize_compact` and `silentpayments.serialize_label` moved
  from `ValueError` to `RuntimeError` with it, libsecp256k1 answering
  the same 0 for a refusal as for a failure of its own. Where the
  wrapper believed the return value, there is now no exception at all:
  `dsa._verify_` and `ssa._verify_` answer `False`, `keys._pubkey_sum_`
  answers `None`, `keys._pubkey_cmp_` answers an ordering, `dsa._is_low_s_`
  answers `True`, and `ecdh._shared_secret_` answers 32 bytes that are a
  shared secret with nobody. Each is driven in `tests/test_callbacks.py`
  rather than described, the ECDH one because it is the gravest: the
  call succeeds, the answer is the right length, and only the thread
  says it is worthless.
- **No entry point taking octets is in that position**, which is why the
  trade is worth stating separately from the cost. `verify`,
  `pubkey_tweak_add`, `shared_secret` and the rest parse what they are
  given, so the objects they hand libsecp256k1 are ones it has just
  built and the refusal cannot arise; a bad key is the parse's
  `ValueError`, and the thread is left clean. What is given up belongs
  to a caller passing a `secp256k1_pubkey` of its own to a `_foo_` half,
  and `keys.pubkey_verify` on the octets it came from is what settles it
  once instead of at every call.
- **`_scalar.octets` and `_scalar.scalar` answer `bytes` without asking
  the questions `bytes` already answers**, 0.034 microseconds against
  0.080 on the same machine. The two `isinstance` tests, the
  `memoryview` width test and the defensive copy are what a `bytearray`
  or a `memoryview` needs, and are what the slow path still does; the
  exact type is asked once in front of them. `dsa.verify` passes three
  arguments through it.
- **`keys.serialize` stopped building its buffer from an interpolated
  cdecl**, 0.313 microseconds against 0.356 with the guard already gone
  and 0.604 before it: `ffi.new` of an `f"char[{size}]"` parses that
  string on every call, and `ffi.sizeof` was called twice where the size
  was in hand. It went to a literal here and then to a hoisted type, for
  the reason and at the price the entry below states; what follows is
  what did not change. The length buffer is still built per call and
  deliberately not hoisted, though it holds the same number every time —
  libsecp256k1 writes 0 into it before it does anything and restores it
  only on success, and it holds what it finds there against 33 or 65 on
  the way in, so one failed call would leave a shared buffer at zero and
  every later serialization, on any thread and of a perfectly good key,
  would be refused. That was measured rather than reasoned about.
- **What the entry points cost now.** Microseconds per call on the
  machine above, the quickest of two passes run in either order so that
  neither tree is the one measured on a warm machine, before against
  after: `keys.parse` of 65 bytes 0.258 and 0.213, of 33 bytes 2.314 and
  2.294, `xonly.parse` of 65 bytes 0.832 and 0.500,
  `keys.pubkey_tweak_add` 4.179 and 3.480, `dsa.sign` in DER 12.063 and
  11.766, in the compact form 12.072 and 11.733, `dsa.verify` in DER
  12.221 and 11.846, in the compact form 12.203 and 11.880, `ssa.sign`
  15.724 and 15.631, `ssa.verify` of a 65-byte key 13.159 and 12.476, of
  an x-only key 14.624 and 14.272. The 33-byte parse is where there was
  nothing to win and the figures say so: the field square root is what
  that row is.

### What importing the package costs

- **`__version__` is read on first access rather than at import** (#210).
  The value comes from where it came from -- the installed distribution
  metadata, so that `pyproject.toml` stays the only place a release bumps
  -- and a module-level `__getattr__` (PEP 562) is what defers reading
  it. `importlib.metadata` pulls `email`, `json` and `inspect` behind it,
  among others.
- **`pathlib` is imported where it is used**, which is the dynamic branch
  of `_load_lib`. A static extension returns from `hasattr(module,
  "lib")` two lines earlier, and a static extension is what every
  platform of the matrix ships by default.
- **It takes both, and deferring `import pathlib` alone would have bought
  nothing.** `importlib.metadata` imports `pathlib` itself, and
  `import pathlib` was the statement *above* the one that read the
  version, so on the file as it was `pathlib` arrived whether that first
  line ran or not: the row below measures it at 0.09 milliseconds, which
  is nothing. The 2.27 that deferring it is worth here is a saving this
  branch creates rather than one that was lying there.
- Every figure below is one session, one build, `__init__.py` the only
  thing that differs, minimum of 12 fresh interpreters each -- an Apple
  M5, macOS 26.6, arm64, CPython 3.14.6. It is the only place this
  decomposition is written down; the docstrings that quote a figure send
  the reader here rather than repeating the split.

  ```shell
  # after each swap, run it once and throw that answer away: a changed
  # __init__.py invalidates its .pyc, and compiling this file is about a
  # millisecond -- most of the number being reported for the branch
  python -c "import time, importlib
  t = time.perf_counter(); importlib.import_module('btclib_secp256k1')
  print((time.perf_counter() - t) * 1e3)"
  ```

  | | ms |
  | --- | --- |
  | as it is now, both deferred | **1.69** |
  | with `import pathlib` back at module level | 3.96 |
  | with the `importlib.metadata` import back instead | 10.98 |
  | the file as it was: both, and the `version()` call | 15.85 |
  | the file as it was, with `import pathlib` deferred alone | 15.76 |
  | as it is now, then reading `__version__` | 15.59 |
  | the file as it was, then reading `__version__` | 15.97 |
  | `_btclib_secp256k1`, the extension, either way | 0.58 |

  The middle rows are marginal costs over this branch, each measured by
  putting one statement back, and they do not add up to the fourth: the
  9.3 of the metadata import already contains `pathlib`'s 2.27, and what
  is left of the 15.85 is the first `version()` call, 4.9 of it.

  The last two rows before the extension are the same number and not a
  saving of 0.4: a caller that reads the version pays what it paid, and
  which of the two comes out ahead is the drift of the machine between
  two batches.

- **The value is stored into the module's namespace on the way out.**
  `sys.modules` caches the module `importlib.metadata` is, not the answer
  `version()` gives, so a `__getattr__` that only defers would leave
  every read after the first walking the metadata again -- 290
  microseconds each, where the attribute it replaced was a dict lookup at
  0.010. Storing it is the usual shape of PEP 562 and makes the second
  read 0.018. It is also what makes the `dir()` sentence below true: the
  interpreter does not memoise a module `__getattr__`, so without this
  the attribute would never appear at all.
- **The reading of the version is outside the `TYPE_CHECKING` guard**,
  in `_read_version`, and only the `__getattr__` is inside it. mypy does
  not check the body of the `else` such a guard takes: with the two
  working lines in there, `return len(version(...))` from a function
  annotated `-> str` passes `--strict`, and `warn_unreachable` does not
  catch it either. Out here the same error is `[return-value]`, which is
  what `py.typed` and *a wrong annotation propagates* ask for.
- **The `__getattr__` is behind `if TYPE_CHECKING`, and that is the
  point of the change surviving the gate.** A module that has one is a
  module mypy stops checking attribute names on: measured on this tree,
  `from btclib_secp256k1 import nosuchmodule` and
  `btclib_secp256k1.typo` both stop being errors under `--strict`, and
  that is the front door of the package. Declaring `__version__: str` to
  the type checker and defining the function only at run time keeps both
  checks, and `tests/test_extension.py` needing a
  `type: ignore[attr-defined]` to ask for a missing attribute is the
  proof that it does.
- **Two tests hold the saving**, `test_import_defers_the_metadata` and
  `test_import_defers_pathlib`: each imports the package in a subprocess
  and asserts what is *not* in `sys.modules` afterwards. Nothing else
  would notice a module-level import added later, here or in anything
  this package imports, which is how the 13 milliseconds arrived. The
  second is skipped on a dynamic extension, which reaches `_load_lib`'s
  other branch and imports `pathlib` legitimately; the matrix runs the
  suite both ways.
- **What it costs a caller** is that `dir(btclib_secp256k1)` does not
  list `__version__` until something reads it, and does afterwards.
  Nothing else changes: the attribute, the `from … import __version__`,
  and reading the metadata directly all answer what they answered.

### The out-parameter that is the caller's to ask for

- **`xonly._from_keypair_` takes its parity pointer, defaulting to NULL**
  (#219), which is the shape the entry below gives `xonly._drop_y` and
  which libsecp256k1 documents in the same words for both:
  `secp256k1_extrakeys.h` says `pk_parity: Ignored if NULL` of
  `secp256k1_keypair_xonly_pub` as it does of
  `secp256k1_xonly_pubkey_from_pubkey`. `from_keypair` allocates one and
  reads it; `ssa._abort_unless_verified`, which threw it away, passes
  nothing. The allocation sits at the one call site that wants it rather
  than behind a helper — `_drop_y` needed `_drop_y_with_parity` because
  it has two such callers, and this has one.
- **It is worth 28% of the conversion and nothing where the conversion
  is**, and both halves of that are the point of taking it. Same session
  shape as the entry below — the two spellings alternated in one process
  over 15 rounds, a noise row beside each, an Apple M5, macOS 26.6,
  arm64, CPython 3.14.6:

  | | with the parity | with NULL |
  | --- | --- | --- |
  | the conversion alone | 0.2384 | 0.1718 |
  | `ssa.sign` with the check on, which is where it runs | 19.9400 | 20.0303 |
  | *noise*, the conversion twice | 0.2353 | 0.2404 |

  −28.0% on the call, +0.45% on the path against a noise row that moved
  2.18% — which is to say nothing, an `ffi.new` being some hundredths of
  a microsecond against a signature and a verification. **So this is
  taken for the convention and not for the speed**: the package had two
  answers to one question, written a week apart, and now has one.
- **One test holds it, and it takes two keys to.**
  `test_the_keypair_parity_is_the_callers_to_ask_for` runs over an even-y
  key and an odd-y one and asserts the 0 and the 1, because
  `ffi.new("int *")` zeroes what it allocates: over an even-y key alone
  every side of every comparison is 0 whether the pointer was written
  through or not, and discarding it inside the helper is then a mutant
  the whole suite passes while `xonly.from_keypair` answers 0 for every
  odd-y key. With both keys that mutant fails at the assertion meant to
  catch it. The same mutation on `_drop_y` fails eight tests, so the
  claim these two conversions now share is one the suite holds on both.

### What a wrapper works out per call, and now works out once

- **An interpolated cdecl is resolved at import, not at every call**
  (#212). `xonly.serialize` and `silentpayments.serialize_label` declared
  their buffer with `ffi.new(f"char[{_XONLY_SIZE}]")`, which states the
  width once — the reason it is an f-string — and costs twice what a
  literal does, cffi having to hash a string built afresh each time:
  0.1219 microseconds against 0.0681. `ffi.typeof` of the same f-string,
  evaluated once at module level, is the literal's price with the width
  still stated once.
- **A literal cdecl is left exactly as it was**, and that is the measured
  half of the same rule. cffi already caches the parse of one, so
  hoisting a literal saves 0.003 microseconds — real, 4.3% on a noise row
  of 0.5%, and an order below the 0.054 an interpolated cdecl gives back.
  That is the size a hoist has to be worth to justify spelling a width
  twice, or naming every cdecl in the package at module level, so every
  `ffi.new` here still spells its cdecl in full — including the two
  beside the hoisted types.
- **`ffi.sizeof` of a buffer whose size is a constant is not asked per
  call**, and that is what asked `keys.serialize` for a type at module
  level: the width is stated once and the type built from it, so the
  buffer and the length cannot say different numbers, and the 0.0175
  microseconds is not paid at every call. `keys.serialize` also decides
  its flag in the branch that picks its buffer, so the one condition is
  asked once. The length *object* is still built per call, for the
  thread-safety reason its comment gives.
- **Every buffer in the package whose bytes are unpacked is spelled that
  way now**, the eight sites that still asked `ffi.sizeof` of a cdata
  per call included: `dsa.serialize_der`, `dsa.serialize_compact`,
  `recovery.serialize_compact`, `hashes.tagged_sha256`,
  `ellswift.create`, `ellswift._encode_`, `ssa._sign32` and
  `ssa._sign_custom`. An int constant states the width, `ffi.typeof` of
  it is the buffer's type, and that same constant is the length — and
  where a module validates an argument against the width it writes,
  `dsa`, `recovery`, `ssa` and `ellswift` check it against the constant
  rather than against a second copy of the number.
- **What the mutants say, which is not that there are more of them.**
  `core/NumberReplacer` emits two mutants per numeric literal — `dsa.py`
  holds 20 and `cosmic-ray init` enumerates 40 of them among its 376 — and
  an AST census of the package counts 67 literals before this change and
  67 after: `ellswift` sheds two and `ssa` one, `hashes` gains one and
  `keys` two, and the surface is the size it was. Only three of the
  seven widths had no int literal anywhere before (`hashes._HASH_SIZE`,
  `keys._COMPRESSED_SIZE`, `keys._UNCOMPRESSED_SIZE`), so six mutants are
  new; the other four replace the seven literals that sat at the
  validation sites — `dsa`'s `!= 64`, `recovery.parse_compact`,
  `ssa._verify_` and `ssa.verify`, `ellswift._decode_` and both of
  `xdh`'s — which were fourteen of their own.
  What changed is what each covers: a width inside `"char[64]"` was
  reachable by no operator, so a wrong *buffer* was a mutation nobody
  could ask about, and the mutable copy answered only for the argument
  check. One number answers for both now, so each of the fourteen tests
  both — same count, more code under each. All fourteen die, each applied
  to the source one at a time with bytecode writing off and a passing
  control run either side.
- **The DER capacity is the one width not written as an int**, and it is
  the site where taking that trade would have cost a kill rather than
  bought one: what `serialize_der` unpacks is `length[0]`, the length
  libsecp256k1 reports back, so 73 leaves the whole suite passing where 71
  fails `test_der_reaches_all_72_octets` — the shape
  `.github/mutation/bindings.toml` records as closed, six of thirteen
  survivors, answered by deriving the capacity from the buffer rather than
  writing it twice. So it keeps `ffi.typeof("char[72]")` with `ffi.sizeof`
  of it, asked at import and not per call. Of the 40 `NumberReplacer`
  mutants `cosmic-ray init` enumerates in the module, the two that fall in
  the declaration block are both on `_COMPACT_SIZE` and none on those two
  lines: the width is stated once and there is no int for the operator to
  move.
- **What consolidating costs, since nothing else records it.** `ellswift`
  had three independently mutable copies of 64 — `_decode_` and both of
  `xdh`'s — and `ssa` had two; each is one constant now, so a single
  mutant changes every site at once and dies on whichever test reaches it
  first. Nothing is hidden today: every one of those seven literals was
  mutated on `main`, one at a time, and each dies on its own. But a check
  that later loses the test that covers it can no longer surface as a
  survivor, and `bindings.toml` asks for a survivor list to be read
  expecting nothing — so the trade is named here rather than left for a
  session to rediscover.
- **Four of the eight save nothing the measurement can resolve, and are
  spelled that way regardless.** The saving is 2.65% to 5.53% of the four
  serializations, and some hundredths of a microsecond of the two
  `ellswift` encodings and the two `ssa` signings, which cost 14.85 to
  30.54 — where timing each of those four against *itself* moves 0.003 to
  0.10, so the effect is under the resolution of its own measurement.
  What decided them is not the figure: a reader cannot see the cost of a
  host, so two spellings of one shape would leave the difference
  unexplainable at both, and a comment saying why a site was *left* alone
  is a comment about a non-change. One spelling is the whole of the
  reason, and the saving is what pays for the four where it shows.
- **`keys.py` derives its two the other way round**, so the six modules
  read alike: it stated `ffi.typeof("char[33]")` and took the size as
  `ffi.sizeof` of that type, where `xonly` and `silentpayments` state an
  int and build the type from it. The int is the spelling that says what
  the number is, and it is the one the whole package uses now.
- **What the eight cost, and what they cost now.** `main`'s spelling of
  each call written out and alternated against the shipped one in a
  single process over one build on the tree this branch lands as,
  minimum of 15 rounds — 500 000 calls for the primitive, 300 000 for
  the serializations, 20 000 for the four hosts — with every pair
  asserted to answer alike before it is timed, and a noise row for each
  site rather than for one of them. An Apple M5, macOS 26.6, arm64,
  CPython 3.14.6, microseconds per call:

  | | main | now | noise |
  | --- | --- | --- | --- |
  | `ffi.unpack` of a 64-byte buffer | 0.0690 | 0.0520 | 0.0005 |
  | `dsa.serialize_compact` | 0.1823 | 0.1765 | 0.0007 |
  | `dsa.serialize_der` | 0.2784 | 0.2665 | 0.0008 |
  | `recovery.serialize_compact` | 0.2720 | 0.2569 | −0.0009 |
  | `hashes.tagged_sha256` of an empty message | 0.5957 | 0.5800 | 0.0007 |

  The per-site saving is 0.006 to 0.016, and it is neither one number nor
  the primitive's 0.017. Within a session the noise rows move under 0.001,
  so no row here is noise; across four sessions the same site moved by
  more than that — `dsa.serialize_compact` between 0.006 and 0.013, the
  lowest of the four every time, `recovery` and `hashes` the highest. So
  what the measurement supports is a hundredth of a microsecond at a
  serialization rather than a figure per site, and no row is a regression.

  And the four hosts the saving disappears into, each timed against itself
  so that the row *is* the resolution: `ellswift.encode` 14.9537 and
  14.8501, `ellswift.create` 19.9003 and 19.9046, `ssa.sign` 30.2860 and
  30.2031, `ssa.sign_custom` 30.5408 and 30.5379 — moving 0.003 to 0.10
  either way around an effect of some hundredths. Every figure in the
  comments of `dsa.py`, `recovery.py`, `hashes.py`, `ellswift.py`,
  `ssa.py` and the last paragraph of `xonly.py`'s is from this session.
- **`_secret.take` zeroes through the view it already holds.** It built
  an `ffi.buffer` to read the secret and then called `wipe`, which built
  a second one over the same cdata. The statement that writes the zeros
  is now `_zero`, which `wipe` calls too, so it is written once — and
  that frame is paid for deliberately: `wipe` twice is 0.1826
  microseconds, `_zero` is 0.1439 and the same statement inlined in both
  places is 0.1314. A quarter of what was on the table, for one copy of
  the line that overwrites a secret rather than two.
- **The parity nobody reads is not allocated.**
  `secp256k1_xonly_pubkey_from_pubkey` documents `pk_parity` as "Ignored
  if NULL", and the callers that want the object alone — `parse`, `_parsed`
  and `_tweak_add_` — are why NULL is the default. `_drop_y` takes the
  pointer as an argument now: 0.1747 microseconds against 0.2425 on the
  conversion alone. `_from_pubkey_` and `to_pubkey` read a parity and go
  through `_drop_y_with_parity`, which is that allocation written once,
  and no saving lands on them — what it adds is some hundredths of a
  microsecond, measurable against both. One figure rather than one per
  caller: it is the same frame at each, and two harnesses put a different
  one of the two ahead, which is the spread of a number this small and
  not a structure. What they get out of this is the C call still written
  once and the call site they had.
- **Two sessions, and each is named where a figure comes from.** Every
  wrapper figure this change quotes — in CHANGELOG.md, HISTORY.md and in
  the comments of `keys.py`, `xonly.py`, `silentpayments.py` and
  `_secret.py` alike — is the one below; every cffi-primitive figure is
  the one after it. An Apple M5, macOS 26.6, arm64, CPython 3.14.6.

  `main`'s spelling of each call written out and alternated against this
  one in a single process over one build, minimum of 15 rounds of
  200 000 calls, a noise row running `main`'s spelling twice, and every
  pair asserted to answer alike before it is timed:

  | | main | now |
  | --- | --- | --- |
  | `_drop_y`, the conversion alone | 0.2425 | 0.1747 |
  | `xonly.serialize` | 0.2569 | 0.1969 |
  | `silentpayments.serialize_label` | 0.2621 | 0.2023 |
  | `_secret.take` | 0.1826 | 0.1439 |
  | `xonly.parse`, 65 bytes | 0.5021 | 0.4295 |
  | `xonly._from_pubkey_`, 65 bytes | 0.5127 | 0.4711 |
  | `keys.prvkey_negate` | 0.3790 | 0.3380 |
  | `keys.serialize`, compressed | 0.3106 | 0.2906 |
  | `keys.serialize`, uncompressed | 0.3101 | 0.2903 |
  | *noise* | 0.2578 | 0.2577 |

  and the primitives, minimum of 15 rounds of 300 000 calls:

  | | first | second |
  | --- | --- | --- |
  | `ffi.new` of an f-string, then of a literal `char[32]` | 0.1219 | 0.0681 |
  | `ffi.new` of a literal, then of a hoisted `char[33]` | 0.0685 | 0.0656 |
  | `ffi.new` of a literal, then of a hoisted `size_t *` | 0.0809 | 0.0774 |
  | `ffi.unpack` with `ffi.sizeof`, then with the constant | 0.0764 | 0.0589 |
  | *noise* | 0.0676 | 0.0680 |

- **`_scalar.scalar` was measured and left alone**, which is the one
  declined here. Asking `type(num) is int` instead of
  `isinstance(num, int) and not isinstance(num, bool)` is one check where
  those are two and excludes `bool` on its own, and it is 0.141
  microseconds against 0.157 — but it needs the range check and the
  serialization written twice, once for the exact type and once for the
  subclass, and the int path is the one this module's own docstring says
  is not the common one: a scalar handed to these bindings in a loop is
  bytes, and that path does not reach the test at all.
- **The stub gains an opaque `_CType`**, which is what `typeof` answers
  and what `new` takes beside a string. Typing that argument `Any`
  instead would be the vacuous type-checking
  `stubs/_btclib_secp256k1.pyi` exists to prevent: `ffi.new(_XONLY_SIZE)`
  — an int where a cdecl belongs, and the size and the type built from
  it now sit a dozen lines apart in the same module — passes `--strict`
  with `Any` and is an `[arg-type]` error with `_CType`.

### Signing under one key

- **`ssa.Signer` builds the BIP340 keypair once** (#153). `ssa.sign` and
  `ssa.sign_custom` build a `secp256k1_keypair` from the private key and
  wipe it in a `finally`, so a caller signing several messages under one
  key pays for it once per signature — and it is about half of what a
  signature costs, being the point multiplication of the public key.
  Measured on this tree, on an Apple M5, macOS 26.6, arm64, CPython
  3.14.6, minimum of 10 rounds of 20 000 calls, microseconds per call:
  `ssa.sign` 15.7, `Signer.sign` 8.2, `secp256k1_keypair_create` alone
  7.3 — the saving is the keypair and nothing else, and it puts one
  signature at the cost the C call itself has. `sign_custom` is the same
  pair, 16.0 and 8.4. What holds the new path to the old one is not that
  agreement: `tests/test_vectors.py` signs every BIP340 vector through a
  signer as well, so both are held against bitcoin/bips' published value
- **and it hands the caller a lifetime, which is the trade it makes.**
  A keypair is the private key in libsecp256k1's layout, in memory this
  package owns and can overwrite, so a signer holds a secret across
  calls where the two functions hold one for the length of one. The
  `with` block is what makes the wipe deliberate rather than forgotten:
  `__exit__` overwrites the keypair whether the block ended in a
  signature or in an exception, `wipe()` is the same instruction by
  hand, wiping twice is not an error, and a wiped signer raises rather
  than signing with the zeros — it cannot be revived, the private key
  being kept nowhere else here. This is the case #87 declined and the
  reason it declined it does not cover: that issue asked whether an
  opaque secret handle buys *assurance*, and the answer was no, the
  python-side copies at import and export being what they are — an
  answer this does not disturb, SECURITY.md's limits being unchanged and
  the constructor still taking a `bytes` or an `int` nothing can zeroize.
  What is new is a measured cost, and it is paid by every caller signing
  more than once under one key. BIP340 only: `secp256k1_ecdsa_sign`
  takes the private key directly, so `dsa.sign` has no keypair to hoist
- **and a signer that is dropped rather than wiped is named where the
  guarantee is made** (#177). SECURITY.md said the cffi buffer holding a
  secret is zeroed before it is dropped, which is true of every one of
  them except this: a signer told neither `wipe` nor `with` is collected
  with the keypair still holding the private key, cffi freeing that
  memory without overwriting it. The sentence now names the exception,
  `Signer`'s own docstring says it where a caller meets the class, and
  `tests/test_signer.py` asserts it — the keypair kept alive by a
  reference of its own, the signer dropped and collected, the key still
  in those octets. A `weakref.finalize` would close it in three lines and
  is deliberately not there: it runs at a time nothing specifies, which
  reads as a guarantee without being one, and the test is what makes
  adding it a decision to reread rather than a silent reversal
- **the two functions are now the signer's two calls with the keypair
  built and wiped around them**, `_sign32` and `_sign_custom` being the
  shared body, so neither side can drift into a second spelling of the
  same checks. One consequence is visible: those checks now happen after
  the private key is turned into a keypair rather than before, so a call
  with *both* a bad private key and a bad message names the key where it
  used to name the message. Each on its own is refused as before, and
  every wipe that happened still happens

### Grinding for a low r

- **`dsa.sign(grind=True)` signs again until `r` is the low one** (#204).
  Bitcoin Core's `CKey::Sign` scheme and not a rephrasing of it: the
  first attempt is the plain RFC6979 signature, and each retry mixes a
  `uint32` counter, little endian in the first 4 of 32 octets, into the
  nonce, until the high bit of `r` is clear and DER therefore spends no
  leading zero octet on it. One octet shorter, about half the time, for
  two signatures' work — measured on this tree, on an Apple M5, macOS
  26.6, arm64, CPython 3.14.6, 2000 distinct keys signed once each, the
  variants alternated in one process, seven rounds with the minimum of
  each kept, microseconds per call: `dsa.sign` 11.7 against
  `dsa.sign(grind=True)` 24.9, at 2.09 attempts on the mean and 14 for
  the worst of those keys. A row running one variant twice is what says
  what the noise is, and it is 0.1.
  Off by default for that reason, and asked for by a caller who wants the
  octet. `dsa._sign_` takes it too; `s` has no counterpart, libsecp256k1
  having already returned the lower of the two, and `recovery.sign` does
  not get one, a recoverable signature being 65 fixed octets with nothing
  to shorten
- **the loop is python, and no C was written** — measured rather than
  assumed, and re-measured on this tree, the first figures published
  having compared loops that differed in more than where they kept their
  buffers. Four loops answering the same signature, alternated as above,
  in the compact form the retry reads: 24.7 for a caller's own loop over
  the public wrappers once per attempt, 24.8 for what landed, 24.6 for
  the same keeping one compact buffer per call, 24.5 for the same again
  with both scratch buffers at module level — which one shared context
  and a documented thread-safety story rule out anyway. Three tenths
  separate the four, against a noise row of one tenth, and a caller's own
  loop is not measurably behind the one inside the package: whatever a
  loop crossing the boundary once per signature could save lies inside
  that spread, and most of what is in the spread is the per-attempt
  serialization the predicate costs rather than the buffer placement,
  the two buffer rows being 0.1 apart. A loop compiled in C would have
  started from the last row, and would have been bought with the one
  property these bindings do not trade: a dynamic build compiles no C at
  all, so a C helper would be a feature the static wheels have and the
  dynamic ones do not. Grinding here is worth having for the scheme and
  the vectors that judge it, not for the microseconds
- **the retry reads the compact serialization, not the DER length**,
  which is not the same question: DER is `6 + lenR + lenS`, so a high `r`
  of 33 octets with an `s` that needs only 31 encodes to 70 octets too —
  about one signature in 500, measured over 200 000 — and a length test
  would take those for low-r ones. The first octet of the compact form is
  the top of `r`, which is what Core's `SigHasLowR` reads
- **`dsa.is_low_r` asks that of a signature a caller did not make**
  (#209), with `dsa._is_low_r_` the half taking the parsed one, as
  `is_low_s` has had since the beginning. Not a rule, unlike that one:
  `verify` asks nothing about `r`, a high-r signature being valid and
  always having been, so what this answers is whether a signature is the
  octet shorter that `sign(grind=True)` makes it. It is where the
  grinding loop's own test now lives too — one spelling of the
  predicate, asked per attempt, which costs about 0.2 microseconds of
  the 24.8 above against the compact buffer the loop used to keep (three
  alternated runs put it between 0.13 and 0.31, where the noise row
  moves 0.1), and buys that what a caller can check is what the loop
  ground to. Asked once of a signature already made, it is 0.5: a
  `parse_der` and a `serialize_compact`, 12.2 against the 11.7 of the
  `dsa.sign` beside it
- **`aux_rand32` and `grind` are refused together**, with a `ValueError`.
  Grinding writes the very 32 octets that argument is, so a caller asking
  for both is asking for two values of one argument; ignoring one of
  them, as Core does with its `test_case`, would make an argument vanish
  where every other one here is checked
- **what judges it is Core's vectors and rust-secp256k1's**, in
  `tests/test_vectors.py`: the two deterministic signatures of Core's
  `key_test1`, which are already low-r at the first attempt and so pin
  that asking for grinding changes nothing; the property
  `key_signature_tests` asserts over 256 messages, together with the
  high-r half of that same test, which says the loop has something to
  find; and rust-secp256k1's `test_low_r`, whose vector takes five
  attempts and so pins the counter itself, in an implementation sharing
  no line with Core's

### The parsed public key

- **`xonly.tweak_add_` tweaks the point, where `tweak_add` tweaks its
  x.** BIP341's output key is an internal key plus the TapTweak hash
  times the generator, and the caller reaching it holds a public key it
  has just validated — which is a `keys.parse`, and for a compressed key
  a field square root. `tweak_add` takes the 32-byte x-only form and
  parses that, so such a caller lifted one x twice:
  `secp256k1_xonly_pubkey_from_pubkey` is a conversion and not a lift,
  and reading the y it is given costs what the square root did not.
  Measured as the entry above, on an Apple M5, macOS 26.6, arm64, CPython
  3.14.6, and by the median of seven alternating rounds of 20 000 calls,
  microseconds per call: `tweak_add` 5.92, `tweak_add_` 3.79, with a
  `mult.mult_` control that moved by 0.06 across the rounds. btclib's
  `script.taproot.output_pubkey` is the caller: it validates the internal
  key through `pub_keyinfo_from_key` and then hands the x-only octets to
  `tweak_add`.
- **It takes a full public key, and that is the module's rule rather than
  an exception to it.** The bytes entry points take the 32-byte form so
  that a y coordinate is never discarded inside an argument check; a call
  taking what `keys.parse` returns and answering 32 bytes discards it in
  plain sight. An odd-y point is tweaked as its negation, BIP341's
  internal key being x-only, and answers the output key `tweak_add`
  answers for the same x — `from_pubkey_` is where that parity is read,
  and takes the same object.
- **`tests/test_parsed_keys.py` pairs it outside the parametrized
  table**, as it pairs `ssa.verify_`: the equality is
  `tweak_add_(keys.parse(sec))` against `tweak_add(from_pubkey(sec)[0])`,
  held over both serializations and over the negated key, so the
  odd-y case is not left to the reading of a docstring.
- **The underscore now means the same thing on the producing side**
  (#159). It meant "takes the parsed key in place of the bytes", which
  covers every wrapper whose *first* act is a parse and none of those
  whose *last* act is a serialization — so a caller composing two of them
  paid, between the two, for a serialization of a point that was already
  in hand and a parse of what had just been serialized. The convention
  reads the same in both directions now, the outer half being the inner
  one with a `parse` in front of it or a `serialize` behind it, and
  `keys.parse` states both. `keys.pubkey_from_prvkey_`,
  `keys.pubkey_combine_`, `keys.pubkey_sort_`, `recovery.recover_`,
  `ellswift.decode_` and `silentpayments.label_` answer with the object;
  `ellswift.encode_` and `silentpayments.labeled_spend_pubkey_` take one,
  the second taking two. Every outer half is unchanged in behaviour and
  cost, and is now written as its inner half with the missing step around
  it, so neither can drift into a second spelling of the same call.
- **Which composition pays what.** Measured as the entries above, on an
  Apple M5, macOS 26.6, arm64, CPython 3.14.6, minimum of 10 rounds of
  20 000 calls, microseconds per call. The unit is one round trip of a
  compressed key: `keys.serialize` 0.35 and `keys.parse` 2.28, against
  0.24 for the uncompressed form, the difference being the field square
  root. So: aggregating five keys the BIP67 way, `pubkey_combine(
  pubkey_sort(keys))` 28.23 against 14.84 for the two inner halves over
  keys parsed once — it is per key, which is why this one is half the
  total; a labeled Silent Payments address, 14.28 against 9.25;
  `xonly.from_pubkey(ellswift.decode(ell))` 7.44 against 4.69; and
  recovering a key to verify with it, 29.57 against 26.75, the
  verification being most of that number either way.
- **`keys.pubkey_combine_` and `keys.pubkey_sort_` were the two v0.8.0.2
  left out**, on the grounds that their inner halves would take lists of
  cffi objects and no caller had asked. The caller is their own
  composition: sorting is what BIP67 and MuSig2 key aggregation do
  *before* adding, and between the outer halves every key is serialized
  and parsed again. `pubkey_sort_` hands back the caller's own objects,
  found by the address each reordered pointer holds — an element of the
  array libsecp256k1 sorted owns nothing, and would dangle the moment the
  caller dropped the sequence it points into. `tests/test_keys.py`
  asserts that identity rather than the value, which is the part a
  serialization comparison would not catch.
- **`xonly.from_prvkey` and `ssa.Signer.pubkey` are two shortcuts rather
  than two halves.** The x-only public key of a private key was
  `xonly.from_pubkey(keys.pubkey_from_prvkey(k))` — 10.49, of which 2.63
  is a round trip of the compressed key nobody wanted — and BIP340 and
  BIP341 want that key and not the point, so the composition is the
  common case and not an exotic one: `from_prvkey` is 7.90. It buys no
  microsecond the halves had not already bought —
  `from_pubkey_(pubkey_from_prvkey_(k))` is 7.87, and `from_prvkey` is
  written as exactly that — which is the whole claim: it is a name for a
  composition whose intermediate nothing here asked for, and the number
  beside it is the round trip, not a third algorithm. `Signer.pubkey()`
  is the one that saves what no pair of halves could: a signer already
  holds the keypair, and the point with it, so reading the key off it is
  `secp256k1_keypair_xonly_pub` and not a multiplication — 0.43 against
  the 10.49 of deriving it a second time. `tests/test_signer.py` holds it
  to `xonly.from_prvkey` and to the key its own signatures verify
  against, parity included.
- **`xonly.from_keypair` is the second wrapper taking a libsecp256k1
  object rather than bytes**, `keys.serialize` having been the only one.
  A MuSig2 session driven through `lib` holds a keypair, which is the
  caller beyond `Signer.pubkey`. There is nothing to check about such an
  argument before the call, so a violated precondition is reachable
  through it: like `keys.serialize` it calls `context.check()`, which
  raises what libsecp256k1 reported *and* takes it off the thread, where
  it would otherwise surface out of the next `check` a MuSig2 caller
  makes. A wiped keypair is the reachable mistake and is reported as the
  zero it holds where the x of a point should be; `tests/
  test_callbacks.py` drives both it and the NULL pointer.
- **`silentpayments` had no inner halves at all**, and its round trip is
  a label: those 33 bytes are a compressed point, so a recipient
  publishing a labeled address paid a square root between `label` and
  `labeled_spend_pubkey`. `label_` answers with the object, `parse_label`
  and `serialize_label` are `keys.parse` and `keys.serialize` for it —
  public now, having been private — and the 33 bytes are still what a
  scan cache is keyed on, so `label` is unchanged and is still what a
  recipient keeping labels as bytes wants.
- **The tables that hold the convention were widened, not trusted.**
  `tests/test_parsed_keys.py` gains a `PRODUCERS` table whose equality is
  `outer(...) == serialize(inner(...))`, and its pairing check now reads
  `ellswift`, `recovery` and `silentpayments` as well, so a producing
  half added and left unpaired fails there; `tests/test_bytes_like.py`
  sweeps the new entry points that take bytes, through a serializing
  wrapper where what they answer is a cffi object, and excuses the rest
  by name.
- **`keys.reserialize` is the validation a caller wants, and the
  conversion nothing here offered.** `serialize(parse(key))` in one call:
  a library proving a public key at its own boundary has `parse` and
  nothing to do with what `parse` returns, and now answers octets instead
  of owning an object's lifetime; a caller holding one serialization and
  needing the other — an uncompressed key to hash compressed, a
  compressed key about to be used several times — had no call to make at
  all, `compressed` being a filter on the form everywhere else rather
  than a conversion to it.

  What makes it worth a name rather than two calls is which form it is
  asked for. `parse` is **0.256 us on 65 bytes against 2.343 on 33**:
  both coordinates are there to read, where a compressed key is a field
  square root. So the uncompressed serialization is a parsed key that
  costs nothing to open, and `reserialize(key, compressed=False)` pays
  the root once and leaves every later call at the price of reading it.
  Measured as the entries above, median of seven alternating rounds of
  20 000 calls, `mult.mult_` control within 0.04.
- **`keys.pubkey_verify` is the validation with nothing kept**, and the
  public-key twin of `prvkey_verify`, which has been there since the
  beginning. A library proving a key at its own boundary has
  `secp256k1_ec_pubkey_parse` and no use for what it produces: `parse`
  hands back an object whose lifetime becomes the caller's, and
  `reserialize` hands back the octets it was given — 0.37 us of
  serialization for an answer that was in the argument. btclib's
  `to_pub_key.pub_keyinfo_from_pub_key` is the caller, and that
  serialization is what it was paying.

  A verdict rather than an exception, as `prvkey_verify` answers one:
  what is wrong with the octets is the caller's to phrase. False for a
  length no serialization has, too, where every other entry point taking
  a key raises — a caller asking whether it holds a public key has asked
  about the length as well.

- **Every entry point taking a public key takes any of its three
  serializations**, and `xonly.parse` is where that is written: 32, 33 or
  65 octets, all of them the same BIP340 key. `02 || x`, `03 || x` and
  `04 || x || y` name one point as far as BIP340 and BIP341 are
  concerned — `lift_x` is the even-y point whatever form the x arrived
  in, and a signer whose point has odd y signs with `n - d` for exactly
  that reason — so the parity is a property of the serialization and not
  of the key. `ssa.verify` and `xonly.tweak_add` used to refuse the
  33- and 65-byte forms, on the reasoning that a key with odd y
  "verifies as the point that is not the one passed": it is not another
  point, it is
  the same key, and what the refusal cost was a lift. Which form to hand
  in is now a question of cost alone — the uncompressed one is read
  rather than lifted, so `tweak_add` on it is **4.11 us against the 5.92**
  of the 32-byte form, whose parse is a field square root like the
  compressed one's.

  `xonly.from_pubkey` answers the parity for a caller that wants to know
  which form it held, and 0 for one that arrived x-only. Nothing about
  the arithmetic moves: `tests/test_parsed_keys.py` holds all four
  spellings of one key — x-only, compressed, uncompressed, negated — to
  the same answer from `from_pubkey`, `tweak_add`, `tweak_add_check` and
  `ssa.verify`.

  This is what <https://github.com/btclib-org/btclib-secp256k1/issues/161>
  builds on, with `keys.reserialize` above: a caller validates, converts
  and operates in octets, and the parsed key stops being something an API
  has to hand around.

- **`keys.pubkey_tweak_mul_sum` is the multi-scalar multiplication, with
  no product crossing the boundary.** A term per key and one sum over
  them is the shape of a verification equation, of a MuSig2 aggregate
  key and of BIP352's tweak data, and written with the public halves
  every product is serialized as 65 octets only for `pubkey_sum` to
  parse them back — the one composition above whose crossing is *per
  term*, where sorting-then-adding pays per key and the others pay once.
  Handed over whole, the products stay `secp256k1_pubkey` objects and
  the boundary is one parse per input and one serialization for the
  answer. Measured on this tree, on an Apple M5, macOS 26.6, arm64,
  CPython 3.14.6, best of seven alternating rounds, uncompressed
  throughout, with `pubkey_from_prvkey` as the noise detector (9.2 µs
  across every round):

  | terms | `tweak_mul` each, then `pubkey_sum` | `pubkey_tweak_mul_sum` |
  | --- | --- | --- |
  | 2 | 19.53 µs | 16.90 µs |
  | 3 | 27.63 µs | 23.76 µs |
  | 5 | 43.87 µs | 37.59 µs |
  | 8 | 68.46 µs | 57.90 µs |
  | 20 | 166.22 µs | 142.37 µs |
  | 64 | 536.50 µs | 459.27 µs |

  So about a seventh of the call from three terms up, a little less at
  two, and it does not shrink with the term count the way the per-term
  combine `pubkey_sum` replaced did. That flatness is what it is: the
  naive form, a term at a time and one sum, with none of the shared
  precomputation of Strauss or Pippenger.
  `secp256k1_ecmult_multi_var` exists upstream and is internal, declared
  in `src/ecmult.h` and not in `include/secp256k1.h`, so the public API
  composes to this shape and no other -- what is saved here is the
  crossing rather than the arithmetic, which matters most where the
  caller is BIP340 batch verification and the asymptotic win is the
  point of the exercise. btclib is that caller
  (<https://github.com/btclib-org/btclib/issues/917>), whose
  `curves.curve._libsecp256k1_multi_mult_` is that composition written
  out and is reached by `mult`, `double_mult_var` and `multi_mult_var`
  with one, two and many terms, by MuSig2's `key_agg`, and by BIP340
  batch verification with two terms a signature.

  **It is the second function here that is more than one libsecp256k1
  decision**, `xonly.from_prvkey` being the first, and the README's
  Design section states the rule the two answer to rather than leaving
  them as exceptions: a composition belongs here when what it saves is
  the crossing between its halves, which is the caller's cost and not
  its own choice, and it is named after the calls it makes. Nothing is
  computed here that libsecp256k1 does not: the terms are
  `secp256k1_ec_pubkey_tweak_mul` and the sum is
  `secp256k1_ec_pubkey_combine`, in the order the equation names them.

  The sum at infinity is `pubkey_sum`'s None, and is likelier here than
  there: a verification equation is written to land on it. The two
  sequences must be of one length, which is the one refusal this
  function raises itself — `zip` would otherwise stop at the shorter and
  answer the sum of whatever paired up.

### The half that speaks in objects is private, and is spelled `_foo_`

- **`foo_` is now `_foo_`, everywhere, and the API break is the point.**
  The trailing underscore said "takes the parsed object in place of the
  octets"; what it did not say is that such a call is past the boundary
  that proves anything. An object is a promise no argument check can hold
  a caller to — `ffi.NULL`, a `secp256k1_pubkey` nothing wrote to, a
  keypair already wiped are all the same to a bare pointer — so these
  belong with the leading underscore that says so. The trailing one stays
  and now says which kind of private: `_verify_` takes a parsed object
  where `_parse_der` is an ordinary helper, and
  `tests/test_parsed_keys.py` reads the modules for names spelled that
  way and fails on one no table pairs. The renamed are
  `keys._pubkey_from_prvkey_`, `_pubkey_negate_`, `_pubkey_tweak_add_`,
  `_pubkey_tweak_mul_`, `_pubkey_combine_`, `_pubkey_cmp_`,
  `_pubkey_sort_`, `xonly._from_pubkey_`, `_tweak_add_`, `dsa._verify_`,
  `ssa._verify_`, `ecdh._shared_secret_`, `recovery._recover_`,
  `ellswift._encode_`, `_decode_`, `silentpayments._label_` and
  `_labeled_spend_pubkey_`
- **`mult.mult_` is `mult.mult_bytes`**, for the same underscore and
  nothing it does: it is a public function answering octets, and it was
  the one name in the package whose trailing underscore meant something
  else — the serialized point against the pair of coordinates `mult`
  answers with. `_bytes` is what the rest of this package calls the
  octets of a thing
- **the convention is stated once, in the package docstring**, where a
  rule about every module belongs; `keys.parse` used to carry it and now
  points at it
- **every kind of object has a public `parse`/`serialize` pair now**, so
  the private halves have something to take and something to hand back:
  `dsa.parse_der`, `dsa.parse_compact`, `dsa.serialize_der`,
  `dsa.serialize_compact`, `recovery.parse_compact`,
  `recovery.serialize_compact` and `xonly.serialize` join `keys.parse`,
  `keys.serialize`, `xonly.parse`, `silentpayments.parse_label` and
  `silentpayments.serialize_label`. `dsa.to_der` and `dsa.to_compact` are
  now the compositions they always were, and `xonly.parse`'s "there is no
  `serialize` beside it, and that is not an omission" is gone with the
  omission it excused — `silentpayments` had copied that serialization
  rather than call it
- **and every wrapper with a parse or a serialize to save has a private
  half**, which is what "symmetric" means here: `dsa._sign_`,
  `_normalize_`, `_is_low_s_`, `recovery._sign_`, `_to_der_`,
  `silentpayments._create_outputs_`, `_prevouts_summary_` and
  `_scan_outputs_` are new. The Silent Payments three are the ones that
  pay: a wallet scanning block after block parses its own spend key once
  rather than once per transaction, and `_prevouts_summary_` hands
  `_scan_outputs_` the summary object where the public halves write those
  octets out of one struct and back into another. `dsa._verify_` takes
  the parsed signature too, so asking `_is_low_s_` and then verifying is
  one parse rather than two
- **`keys.PubkeyTweakChain` hands out the point it holds**, `pubkey()` in
  octets and `_pubkey_()` as the object: a caller reaching the end of a
  BIP32 path had no way to ask the chain what it had arrived at except by
  the last `tweak_add`, and none at all to hand the point on

### What answers for an argument that cannot be checked

- **`context.guarded` is that answer, and it is now every such call's.**
  Three docstrings and a test claimed a violated precondition was
  reachable through "two" wrappers, `keys.serialize` and
  `xonly.from_keypair`. It was reachable through every private half, and
  what came back was measured rather than reasoned about: through
  `keys._pubkey_negate_` a bare `RuntimeError` with libsecp256k1's reason
  left on the thread, through `dsa._verify_` a plain `False`, through
  `keys._pubkey_cmp_` a `0` that reads as "equal", and through
  `ecdh._shared_secret_` a success and 32 bytes that are a shared secret
  with nobody. The message left behind is the misattribution the
  `check()` in `keys.serialize` already existed to prevent: the next
  `check()` — a MuSig2 caller's, about a call of their own — inherited it
- **so the guard clears the thread before the call and checks after it,
  whatever the call answered.** Both halves are needed and either alone
  is a bug: without the clearing an older message is raised out of this
  call, without the check a refusal that shows in no return value is
  believed. It is a context manager because the pair has to be
  inseparable, which is the argument `_secret.take` makes for its own
  pair. The eight failures above are eight `ValueError`s now, each
  carrying libsecp256k1's own text, and `tests/test_callbacks.py` no
  longer counts the exceptions to a rule that has none
- **and it costs 0.22 microseconds a call**, which is worth writing
  down because on the cheapest call it is most of the call. Apple M5,
  macOS 26.6, arm64, CPython 3.14.6, minimum of 11 rounds:
  `secp256k1_ec_pubkey_cmp` through `lib` is 0.084 microseconds and
  `keys._pubkey_cmp_` is 0.300, the difference being the guard and
  nothing else. Three spellings were measured. The pair written out at
  each call site is the cheapest, and is not taken: the clearing without
  the check leaves a message for the next caller to be blamed for, the
  check without the clearing raises an earlier call's message out of
  this one, and the two belong in one place. A
  `contextlib.contextmanager` generator is the dearest, putting the same
  comparison at 0.567 — so the generator's guard is 0.48 a call, and the
  0.27 between the two spellings is more than the entire C call on the
  smallest guarded call in the package. The guard is therefore the
  class, `__slots__` and `__enter__` and `__exit__`, which says "the
  clearing and the check are one thing" as well as a `yield` does and
  costs three method bodies of one line each to say
- **and a fifth of `keys.pubkey_sort` is what settles it** (#186). A
  guard is built once per guarded call, so a composed call builds many,
  and a caller wanting those microseconds back through `lib` is
  reimplementing the operation rather than making one call — where on a
  comparison the advice to drop to `lib` costs them nothing, which is
  why the cheap call is the wrong one to decide on. Same machine and
  method: `keys.serialize` of a parsed point is 0.582 against a
  generator's 0.847, and `keys.pubkey_sort` of twenty keys 21.12 against
  26.99. Sharing one instance rather than building one per call measures
  0.567 against 0.582, which is noise, and would have cost every
  `with guarded():` in the package a rewrite to `with guarded:`
- **the `__exit__` is deliberately not a `finally`,** which is the one
  thing the spelling could get wrong. The block holds the guarded call
  and nothing else, so an exception out of it is some other failure, and
  checking anyway would raise the violated precondition over it —
  reporting the wrong failure and losing the right one. `if exc_type is
  None` is what says so, and two tests in `tests/test_callbacks.py` hold
  the pair, each verified against the mutant it exists to kill

### The copy a caller can take back

- **every producer of a secret takes `into`** (#188), a keyword-only
  writable buffer the secret is written to instead of a `bytes`:
  `keys.prvkey_negate`, `prvkey_tweak_add` and `prvkey_tweak_mul`,
  `xonly.prvkey_tweak_add`, `ecdh.shared_secret` and its private half,
  `ellswift.xdh`, `dsa.nonce_rfc6979` and `ssa.nonce_bip340`. Omitted,
  nothing changes and the `bytes` comes back as before. Given, nothing
  is returned, and the copy the caller ends up holding is one they can
  overwrite — which is the entire claim, and SECURITY.md now states it
  beside the limitation it narrows rather than instead of it. It does
  not wipe the buffer for them; a buffer never overwritten is exactly
  the copy `into` was reached for to avoid, and the obligation is
  stated rather than enforced for the reason `ssa.Signer` has no
  finalizer
- **which is not what #87 declined.** That issue asked whether an opaque
  secret *handle* buys assurance and answered no: a handle is a lifetime
  someone has to own and invalidate, the same shape of requirement that
  keeps MuSig2 out, and its entry side still starts from a `bytes` the
  caller already made. Both halves of that stand. What is new is neither
  a lifetime nor an entry: one keyword argument, one call, no object,
  and it addresses the *exit* — where `_secret.take` had nowhere to put
  the secret except an immutable object nothing can zero
- **`into` is keyword-only, and that is not a style choice.** Passed
  positionally to `dsa.nonce_rfc6979` it would land on `aux_rand32`,
  which takes 32 octets and would have accepted the empty buffer as
  entropy — a wrong nonce, silently, from a call that reads right. The
  suite caught it on the way in; keyword-only is what keeps a caller
  from meeting it
- **and the buffer is proved before anything is copied, the wipe
  happening either way.** A wrong length is refused rather than filled:
  too short raises on the assignment anyway, but too *long* would take
  the secret in its first octets and leave whatever was behind it, which
  reads as a secret with a tail. A read-only view cannot be wiped, so
  accepting one would defeat the facility silently. And a view of more
  than one dimension passes every one of those checks and then fails the
  copy with `NotImplementedError`, while a strided one succeeds and
  leaves the secret scattered through an owner twice its size, so both
  are refused as not contiguous octets. Beyond that the buffer protocol
  decides rather than a type: `mmap` and `array.array("B")` are taken,
  an `mlock`ed `mmap` being a plausible destination for exactly this
  caller, and `memoryview` itself is what refuses a non-buffer. That
  breadth is the run time's rather than the annotation's, which stays
  the two named types until `collections.abc.Buffer` is reachable at a
  3.12 floor: a caller under `mypy --strict` passes the rest as
  `memoryview(x)`, and SECURITY.md says so where the mismatch is met.
  `_secret.into_buffer` is annotated `object` and not
  `MutableBytesLike`, that being the annotation it exists to not trust
- **the wipe is in a `finally`, which is the defect this facility could
  have shipped with.** `take` had no failure mode before `into`, and
  with one on the straight line a refused buffer returned through the
  entry point leaving a live private key in cffi memory that is freed
  without being overwritten -- none of the eight has a `finally` of its
  own, and `xonly.prvkey_tweak_add`'s wipes the keypair rather than the
  key. Nothing is lost by wiping on the way out: the value never reached
  the caller, and the call they retry recomputes it
- **the two secrets `silentpayments` answers are left out**, each being
  one member of a returned tuple where an argument could not say which:
  the tweak of `label`, and the per-output tweak `scan_outputs` hands
  back. SECURITY.md names both rather than claiming every entry point
- **and what holds the set is a walk rather than a list.** A hardcoded
  tuple of eight cannot notice a ninth, which is the whole point of the
  test; `tests/test_secret.py` walks the package for the callers of
  `_secret.take`, and then for whatever calls one of those, and requires
  `into` of each. The second pass is what makes the first honest: a
  public half answers the secret its private half read out without
  calling `take` itself, so `ecdh.shared_secret` is asked by its own
  name rather than caught by accident, and a ninth written that way is
  not left to be checked by hand. The two halves of
  `silentpayments.label` are exempt and named. What the walk reads are
  the calls of a syntax tree and not the text of the source, a mention
  not being a call: `keys.pubkey_tweak_add`'s docstring writes
  `prvkey_tweak_add(k, t)` to say what the private-key side does with
  the same tweak, and matched as text it answers that a public-key call
  produces a private key. The limit that is left is written down beside
  it: a secret that never goes through `take` is invisible to this, which
  is exactly how `_found_output` escaped the first draft of that sentence
- **the cost, which is in the type system rather than at run time.**
  Three `@overload`s per entry point, so that omitting `into` still
  types as `bytes` and a downstream `mypy --strict` sees no change; the
  implementation signature is the union. The third is the one a caller
  needs to *forward* an optional buffer through a wrapper of their own,
  which is how btclib would surface this argument, and with only two it
  is that caller who writes the two-branch version or a `cast`. Four
  negative-typing tests moved from `type: ignore[arg-type]` to
  `[call-overload]`, which is
  what an overloaded call reports, and is the one way this is visible
  to a caller who was already type-checking

### The test a stateful object has to pass

- **the rule the outpost section applies is now stated there** (#191),
  rather than only in <https://github.com/btclib-org/btclib-secp256k1/issues/161>
  where it was reached. That section explained the two objects that
  exist and separated them correctly — a keypair is arithmetic, a parsed
  point is a parse — but the reader who needs it is the one proposing a
  *third*, and what they needed was the test, not the two instances of
  it. It is written as one sentence: what an object saves is the cost of
  rebuilding, from octets, whatever it holds
- **and the saving is that cost by construction, not by measurement,**
  which is the stronger form of the same claim and the one the section
  now makes. `ssa.sign` builds the keypair, signs with it and wipes it;
  `signer.sign` is that middle term with the first already paid, so the
  difference between them is `secp256k1_keypair_create` on any machine,
  and the numbers only add that nothing else of consequence sits in it.
  They are the section's own — 15.82 against the signer's 8.27, of which
  the keypair is 7.55, and 15.82 − 8.27 is that 7.55 — rather than a set
  of its own. The chain gets the same treatment: what it saves is the
  parse it holds, and which parse that is depends on the serialization
  its caller carries — the pair the section states four paragraphs
  above, pointed at rather than restated. That is the sharper form of
  the distinction, because it says why this saving is the one a caller
  can make cheap and the keypair's is not
- **and which figures survive a different machine is said**, because a
  section arguing from microseconds should say which of them it is
  arguing from: the identity, and it carries because it is structural,
  not because a ratio travels better than an absolute. The counts are
  one laptop's
- **two objections are answered before they are raised.** What recovers
  a parse is `keys.parse`, not a cheaper serialization: the
  uncompressed-form argument reaches neither an x-only key, which has no
  second serialization, nor a walk starting from the 33 octets an xpub
  carries, where reaching the uncompressed form costs a `reserialize`
  the chain does not pay — which is the finding of
  <https://github.com/btclib-org/btclib-secp256k1/pull/185>, now in the
  same section and pointed at from here. And statelessness is the other
  side of the ledger, the same argument that keeps MuSig2 out, so the
  two paragraphs point at each other. Ergonomics is weighed by neither,
  deliberately: the line a caller does not write belongs in btclib with
  the lifetimes

### One statement of each thing

- **the duplications are gone**, each of them two spellings of one
  call that could drift apart. `_secret.keypair` is the
  `secp256k1_keypair_create` that `ssa`, `xonly` and `silentpayments`
  each carried verbatim, and it lives beside the `wipe` its caller owes
  it. `xonly.serialize` is the x-only serialization `silentpayments` had
  copied. `keys.parse` and `xonly.parse` take the name the exception
  should use, which is what `silentpayments._pubkey` and `_xonly_pubkey`
  existed for. `dsa.serialize_der` is the DER writer `recovery.to_der`
  had inlined, comment pointing at the original included.
  `_scalar.entropy` and `_scalar.optional_entropy` are the "32 bytes or
  none" of `ssa`, `ellswift.create`, `ellswift.encode`, `dsa.sign` and
  `recovery.sign`. `_scalar.in_range` is the small-int check of a
  recovery id, a parity, an ElligatorSwift party and a label index — and
  it refuses a `float`, which `recid not in (0, 1, 2, 3)` accepted as
  `0.0`. `_cdata.array` is the borrowed-pointer array `keys` built inline
  and `silentpayments` had a helper for
- **`keys.pubkey_verify` and `keys.parse` are one parse now** (#164,
  landed while this was open). Both are `secp256k1_ec_pubkey_parse` and
  they differ in what they do with it: `parse` keeps the object and
  raises when there is none, `pubkey_verify` keeps nothing and answers
  the verdict. `_parsed` is that call, answering the key or None, and the
  two are a line of policy each. It costs `parse` a python call, measured
  on an Apple M5, macOS 26.6, arm64, CPython 3.14.6, minimum of 7 rounds
  of 300 000 calls: 0.269 microseconds against 0.256 on the uncompressed
  serialization, 2.326 against 2.310 on the compressed one, where the
  field square root is what is being paid for. The docstrings quoting
  those two numbers are re-measured with it. The other spelling was
  measured too — `pubkey_verify` catching `parse`'s own `ValueError`
  leaves `parse` untouched and costs 0.15 on a refusal — and it was not
  taken: an exception is what this package answers a caller with, not
  how it decides something it already knows
- **the entropy argument is `aux_rand32` in all five**, BIP340's name for
  what libsecp256k1 spells `ndata` in one place and `rnd32` in another.
  What omitting it means still differs, and the difference is what the
  two helpers are named for
- **the octets of a thing end in `_bytes`**: `hashes.tagged_sha256` takes
  `tag_bytes` and `msg_bytes`, and `silentpayments` takes
  `recipients_bytes`, `taproot_pubkeys_bytes`, `pubkeys_bytes` and
  `tx_outputs_bytes` where its private halves take the parsed objects
  under the same names without the suffix
- **`ffi.unpack` is not `bytes(ffi.buffer(...))`, and the vectors said
  so**: unifying the two idioms turned the `unsigned char[32]` tweak of a
  found Silent Payments output into a list of 32 ints, which
  `tests/test_vectors.py` caught in every BIP352 receiving case. The
  reason it is the exception is now written where it is made
- **the messages of a refusal are one shape**: "invalid private key: not
  in [1, n-1]" wherever that is the whole of what was wrong, and "the
  {name} must be in [0, {upper}]" for the four small numbers

### The signature's two serializations

- **`dsa.sign` and `dsa.verify` take a `compact` flag**, false by
  default. A signature is `r` and `s`; DER is what the wire carries, and
  a caller holding the two scalars had to write an ASN.1 structure around
  them for a call whose first act is to take it apart again — and read
  one back the same way on the answer. `parse_compact` and
  `serialize_compact` have been public since the halves were separated,
  but they speak in the parsed signature, which is exactly what a caller
  doing one thing with it does not want to hold.

  btclib is the caller, and pays it at both ends
  (<https://github.com/btclib-org/btclib/issues/922>): building the DER
  is 0.712 us against the 0.077 of `r.to_bytes() + s.to_bytes()`, and
  reading it back 1.250 against 0.320 — the second of those *per grind
  attempt* under low-r grinding, where the loop parses what it may
  discard. Its recoverable path never had the problem:
  `recovery.sign` answers the compact form, and the comment there says
  why.

- **Which form it is has to be said, and cannot be read off the length.**
  A DER signature of 64 octets exists — `r` and `s` of 29 bytes each —
  and it begins with the 0x30 a compact `r` may begin with too. So the
  flag, rather than a dispatch; and each form is refused as the other,
  which `tests/test_core.py` asserts along with the round trip through
  `to_der` and `to_compact` and the `normalize` flag on either form.

### What a caller asks that is not a use

- **`keys.pubkey_sum` answers the point at infinity, where
  `pubkey_combine` refuses it.** They are one C call and differ in what
  they make of its 0: a sum that is the identity is no public key, which
  is an argument error to a caller that wanted a key and a *value* to one
  doing arithmetic — `P + (-P)` is a point of the group whatever
  libsecp256k1 can hold. What tells that 0 from the other one, an object
  the library could not read, is that the second is reported through the
  illegal callback: `context.guarded` raises it, so what reaches the
  return is infinity and nothing else. btclib is the caller
  (<https://github.com/btclib-org/btclib/issues/917>): its
  `_libsecp256k1_multi_mult_` recognizes an intermediate sum at infinity
  by comparing coordinates, and combines per term rather than once at the
  end so that there are coordinates to compare — measured here on eight
  terms, 64.84 microseconds against the 42.71 of a single combine, and
  the 33.59 of a sum whose terms never cross the boundary at all
- **`xonly.pubkey_verify` and `xonly.to_pubkey` are the two x-only twins
  a caller had to write `0x02 || x` for.** The first is
  `keys.pubkey_verify` for an x coordinate; the second is the lift, and
  the lift is that concatenation — libsecp256k1 converts a point to an
  x-only key and has no call back the other way, so the octets have to be
  built somewhere and this is where the rule about them lives. A key that
  arrives with odd y is negated in the field rather than serialized and
  lifted again, which is the difference between reading a y and finding
  one. btclib's `curves.curve._compressed_sec` exists for exactly these
  two questions
- **`dsa.signature_verify` is the verdict a signature had no way to
  answer**, where a key has had `pubkey_verify` since v0.8.0.3's own
  entry above: the same parse, with nothing kept and no exception to
  catch, and the `compact` flag beside it because the serialization
  cannot be read off the octets. The length is part of the verdict, as it
  is for a key: 63 octets are no compact signature, and `False` is what a
  caller asking whether it holds one wants. `parse_compact` says "invalid
  compact signature" for a wrong length now, where it used to say "the
  compact signature must be 64 bytes" — one refusal for one question,
  which is what a key's parse already did
- **all three are one parse with two callers**, `keys._parsed`'s shape
  repeated in `xonly` and `dsa`: the helper answers the object or None,
  the `parse` raises and the verdict compares. What it costs is the
  python call that entry measured, and what it buys is that a check
  cannot move in one spelling and not the other
- **and the conversion between two serializations keeps two names for a
  signature and one for a key.** `dsa.reserialize` was considered and not
  written: `keys.reserialize` reads the input form off the length, and a
  signature's cannot be read at all — a DER signature of 64 octets exists
  and may begin with the `0x30` of a compact `r`. `to_der` and
  `to_compact` name the input form the way `compact` names it on `sign`
  and `verify`, which is the coherence a third name would have broken

### The nonce each signer derives

- **`dsa.nonce_rfc6979` and `ssa.nonce_bip340` are new** (#155).
  libsecp256k1 exports its two nonce functions as callable pointers --
  `secp256k1_nonce_function_rfc6979` and
  `secp256k1_nonce_function_bip340` -- and both headers were already in
  the parse list, so what was missing was the call through the pointer
  and nothing else. No callback into python, which is what makes this
  unlike the ECDH hash function `ecdh.shared_secret` declines to expose
- **each is called with what its signer passes**, so what comes back is
  the nonce of the signature the same arguments make, rather than a
  derivation that resembles it. That is checked rather than asserted:
  `tests/test_nonces.py` signs and re-derives, `r` being the x of `k`
  times the generator reduced modulo the group order and BIP340's `R`
  the same x without the reduction. The four points #155 lists are
  settled that way -- the algorithm tag is fixed to the signer's (NULL
  for ECDSA, `BIP0340/nonce` for BIP340), `attempt` is an argument
  because RFC6979's contract has a counter even though every signature
  takes the first candidate, `ndata` is the `aux_rand32` every other
  entry point calls it, and the answer leaves through `_secret.take`
- **BIP340's key enters negated where the point has odd y**, and the
  x-only public key with it, because that is the key the signature is
  made with: a wrapper taking the caller's key unchanged would answer a
  nonce no signature was built on, which the odd-y parametrization of the
  test would have caught. Both are derived here rather than asked of the
  caller for the same reason
- **and no auxiliary randomness is the aux of 32 zero octets**, which is
  what libsecp256k1 substitutes and what a python implementation has to
  choose between, BIP340 leaving the aux optional. Asserted, because it
  is the kind of fact a reader would otherwise have to read the C for
- **what they are not is a way to sign in python.** A nonce read out of
  libsecp256k1 has left constant-time code, and the docstrings say so
  where a caller meets them: they are an oracle for checking a
  derivation, which is the gap btclib's `ecc/rfc6979_nonce.py` and
  `ecc/bip340_nonce.py` have had
- **and SECURITY.md gains the limit that has an equation.** Its list of
  what libsecp256k1 writes into a cffi buffer now names the nonce, and
  beside it the thing the other members do not have: a nonce published
  beside the signature it made *is* the private key,
  `d = (s·k - h)/r mod n`. The docstrings warn against signing with one;
  what they could not say, the enumeration being elsewhere, is that it
  must not be stored or logged beside a signature either
- **the identity the oracle rests on is asserted, not assumed**:
  `dsa.sign` passes NULL where the nonce function goes, which selects
  `secp256k1_nonce_function_default`, and this wrapper calls
  `secp256k1_nonce_function_rfc6979`. libsecp256k1's header says they are
  "currently the same pointer", and `tests/test_nonces.py` says so too —
  without it, a split upstream would fail the signature comparisons while
  reporting only that a nonce does not match its signature
- **and the published vectors are what the RFC6979 entry point answers
  to.** `tests/test_vectors.py` already carries the RFC6979 cases with
  their `k`, and now asserts that `nonce_rfc6979` reproduces it: the
  signature comparison holds the wrapper to this package's own signer,
  and this holds it to the value RFC6979 publishes

### The surface and the sentence agree

- **the `mult` module is folded into `keys`** (#173). With `mult.mult`
  removed below, what was left was one function that is
  `keys.pubkey_from_prvkey(num, compressed=False)` with the flag fixed
  and the name hiding it — and a module, everywhere else under
  `btclib_secp256k1/`, is a family of calls around one part of
  libsecp256k1. The abstraction did not hold at its own edges either:
  `mult_bytes(0)` raised "invalid private key", the message of the module
  it delegated to, and a caller wanting the compressed answer had to
  leave for `keys` anyway. What it bought was a name for the operation, a
  scalar times the generator rather than the public key of a private key,
  and that name is one line at a call site that already reads the other
  module's refusal. `keys.pubkey_from_prvkey(num, compressed=False)` is
  the spelling everywhere now, in the package's own docstrings and tests
  included. Done in the window #173 names: 0.8.0.3 is unreleased and
  btclib is adapting to the removal below, so the two are one break to a
  released caller
- **`mult.mult` is gone** (#170). The package docstring opens with "every
  entry point takes octets and answers octets", and that call answered
  `tuple[int, int]` — the one place a point of the curve left as numbers
  rather than as a serialization, `pubkey_cmp`'s int and `prvkey_verify`'s
  bool being verdicts and `from_pubkey`'s parity a flag beside the octets
  it comes with. What it did is `int.from_bytes` twice over the two
  halves of `mult_bytes`, and they cost 0.138 microseconds of a call that
  is some 8.5 — 1.6% of it, and the whole of what the exception was
  worth. The first spelling of this entry claimed the conversions were
  *cheaper* inside the function, 8.549 against 8.578, which is noise read
  as a direction: the removed function did those same two conversions
  behind a python frame, so the ordering the code implies is the other
  one, and three alternating rounds put the two within each other's
  spread. What is stable is the 0.138. The module docstring carries the
  two lines a caller writes instead
- **and `xonly.from_keypair` stays, with the rule widened to cover it**
  (#169). It takes a libsecp256k1 object and is not half of a
  parse/serialize pair, which the docstring's "an object crosses only
  where a caller already holds one" did not account for. The reason it is
  not an exception is that a keypair *has* no serialization to make a
  bridge out of: `secp256k1_keypair` holds a private key in
  libsecp256k1's own layout and the C API never writes one out, so a
  caller that built one through `lib` — a MuSig2 signer — holds something
  no octets could have carried here. The rule now names the two kinds,
  the parse and the keypair, and `from_keypair`'s own docstring points at
  it rather than restating it. Making it private instead would have
  broken the MuSig2 path the README documents, `ssa.Signer.pubkey` being
  the same call only for a keypair this package built.

  The fact #169 says the choice depends on — whether anyone outside this
  package drives MuSig2 through `lib` today — was not established, and
  keeping is the conservative half of that uncertainty: it costs a
  sentence in the rule, where making it private costs a caller who may
  exist an entry point that cannot be worked around, a keypair having no
  serialization to reach `keys.parse` with. What would settle it is a
  downstream search rather than an argument, and it is not on this branch
- **the two are one question**, asked in #169 and #170 of the same
  sentence: an exception to "octets in, octets out" is worth keeping when
  octets cannot carry the thing, and worth removing when they can. A
  keypair cannot be serialized; a point can

### Documentation

- **`ssa.Signer` and `keys.PubkeyTweakChain` are presented as what they
  are**, and the chain's saving is now stated against the walk it is
  actually worth measuring against. The section said five steps are 64.62
  microseconds through `pubkey_tweak_add` and 55.14 through a chain,
  which is true and is the compressed walk; the same path walked in the
  *uncompressed* form, compressed in python where BIP32 wants 33 octets
  to hash, is 54.75 — the chain within the noise. So what the chain saves
  is real against one spelling and a rounding error against the other,
  and what it is unambiguously worth is the line a caller does not write.
  The README says both numbers now, and the section opens by separating
  the two objects: a keypair is arithmetic no serialization gives back, a
  parsed key is a parse the caller can make cheap by choosing the form it
  carries. That is <https://github.com/btclib-org/btclib-secp256k1/issues/161>'s
  own principle, and it is what the measurement says of the two
- **and what the three numbers leave unasked is where the walk starts**
  (#161). The two moves the section describes — hold the point, carry the
  uncompressed form — look as though they compose into a fourth and
  faster spelling, `chain.tweak_add(compressed=False)`, and they do not.
  A chain re-parses nothing in either serialization, the point being what
  it holds, so asking it for 65 octets saves no parse and pays a
  serialization and the caller's own compression line at every step.
  Measured on an Apple M5, macOS 26.6, arm64, CPython 3.14.6, five steps,
  medians of nine alternating rounds with a sha256 control and absolutes
  about 5% above this section's: the composition is 59.27 against the
  chain's 58.62 and the uncompressed walk's 58.26 — a loss of 1.01 where
  the section's own numbers predict 0.98, one compressed parse in against
  five uncompressed parses out.

  The comparison that does decide something is the one nothing here
  asked: the uncompressed walk's 54.75 begins from 65 octets a BIP32
  caller does not have. An xpub carries the 33, so reaching that form
  costs `keys.reserialize` once — a compressed parse and a serialization,
  more than the 0.39 that separated the two walks — and counted, the same
  run puts the walk at 61.55 against the chain's 58.62. So the chain is
  ahead of the spelling this section had called it a rounding error
  behind, on the key its caller actually holds. The README says both now:
  the composition is not worth reaching for, and the parse the chain pays
  at construction is the one the caller could not have avoided. What the
  issue left open is unchanged and rests on that rather than on the cost
  of breaking a released caller — the chain shipped in v0.8.0.1 and
  `btclib`'s `bip32.py` adopted it
- **the outpost section is what the README had no name for**: an outpost
  past the boundary. The private halves hand an object from one call to
  the next; these two hold one across many, for the caller that crosses
  again and again with the same key — a signer signing message after
  message, a wallet walking a BIP32 path one index at a time. Each
  crossing used to pay the conversion at its far end, a point
  multiplication for the keypair and a field square root for the
  compressed key, on a key it had already converted.

  The chain was in no section at all before this, so it now has one, with
  the walk it is for: five steps through `pubkey_tweak_add` against five
  through a chain, which is a compressed parse saved four times. The pair
  of timings first written here was superseded by the entry above, which
  re-measured the walk and added the third spelling of it, so the numbers
  live there and not in two places. The signer's own numbers move from
  the section that described the trade to the one that describes the
  saving: 15.82 against 8.27, of which the keypair is 7.55
- **and the two answer differently under threads, which nothing said.**
  `ssa.Signer` is safe to share, libsecp256k1 taking a keypair const, and
  the README and `tests/test_concurrency.py` both said so — while also
  saying a signer was "the one thing here holding a buffer across calls",
  which `PubkeyTweakChain` had made untrue. A chain is the exception and
  is one by construction: `secp256k1_ec_pubkey_tweak_add` takes its key
  as in and out, so every `tweak_add` writes the point the chain holds,
  and two threads sharing one are two writers of a point rather than two
  walkers of a path. One chain belongs to one thread, and
  `test_a_chain_per_thread_walks_the_same_path` is that usage held to the
  answer of a chain alone
- **why there is no `dsa.Signer` is now the reason rather than the
  mechanism.** The README said `secp256k1_ecdsa_sign` takes the private
  key itself, which is true and is the shape of the C function, not the
  argument. The argument is the equation: BIP340 challenges with
  `e = H(R || P || m)`, so the public key is an input to every signature
  and has to be derived — a point multiplication, kept in the keypair
  with the parity that decides between `d` and `n - d`. ECDSA signs
  `s = k^-1(z + r*d)`, in which `P` does not appear, so there is no
  object derived from the key to hold across calls.

  Measured, because the question is "what would it save": on an Apple M5,
  macOS 26.6, arm64, CPython 3.14.6, minimum of 7 rounds of 20 000 calls,
  microseconds per call, `dsa.sign` is 12.93 and the C call inside it is
  11.43. Of the 1.51 that leaves, `serialize_der` is 0.757, `octets` of
  the message hash 0.081 and the `ffi.new` of the signature 0.078 — all
  of them per signature — and `scalar` of the private key is 0.117, which
  is the whole of what is per key and so the whole of what a signer could
  hoist. `ssa.Signer` hoists 7.55 of 15.82 for comparison, and what
  either costs is the same: a second copy of the secret, alive as long as
  the signer. Worth it for half a signature, not for a hundredth of one.

  The README also now says what *does* cost in `dsa.sign`, and that it is
  the entry above rather than a signer that spares it: the DER
  serialization is 0.757 of those microseconds, and `compact=True`
  answers the 64 octets without writing it
- **Four files said a button is how a pull request lands; none of them
  is** (#176). A pull request reaches `main` as a fast-forward push from
  the command line, squashed locally first where it carries more than one
  commit, which is what keeps the commit signed by the maintainer rather
  than by GitHub's web-flow key — and, where the head that lands is the
  one the gates last ran on, keeps that sha, so a branch stacked on it
  goes on applying instead of needing a rebase and a fresh run of the
  matrix per level. `REPOSITORY.md`'s *Merge methods* said "squash is the only
  method enabled", true of the setting and read as a description of the
  landing; `CONTRIBUTING.md` said "a pull request is squashed on merge …
  the only merge button this repository enables"; `RELEASING.md` merged
  the release "with the squash button"; and `CLAUDE.md` said all three
  buttons were enabled, which stopped being true when squash became the
  only one. The twin change for btclib is
  <https://github.com/btclib-org/btclib/pull/944>, whose merge rule
  differs in the multi-commit case: the squash is made locally here
  rather than pressed.
- **and the ruleset that lets that push through had no section at all.**
  REPOSITORY.md documented the classic branch protection and never the
  two rulesets beside it, so the bypass the fast-forward needs was
  reachable from the prose only through one clause of CONTRIBUTING.md.
  It now has one: `main-integrity` carries the four rules with no bypass
  actor, `main-self-merge` carries the pull request rule and names the
  maintainer, and the split is what lets the review be bypassed — GitHub
  refusing a self-approval — while a signature stays required of
  everybody — though not the whole of the permission either, a push to
  `main` needing `enforce_admins` to stay `false` and the pusher to hold
  `admin` before the bypass is reached at all.

  The sequence is there with it, and so is what GitHub does afterwards,
  which is two different things and was written as one. A pull request is
  marked merged when its head becomes reachable from the base branch, so
  what decides is whether the commit pushed to `main` is the sha the pull
  request names at that moment — not whether a rebase happened, a rebase
  force-pushed to the branch leaving it naming the new one. Push the
  squash to the branch before landing it and the squashed branch is the
  reconciled case too, with the matrix running on the object that lands:
  #185 did that and was marked **Merged**, its head branch deleted by
  `delete_branch_on_merge` a second later. Land the squash straight from
  a worktree and nothing is reconciled and nothing is deleted — btclib's
  #953 is **Closed** with `mergedAt: null`, its issue closed by the
  keyword in the *commit message*, which is the reason for putting it
  there. Getting ahead of the reconciliation costs the same thing btclib
  paid on #930: branch deleted first, pull request Closed with its commit
  on `main` all the same. Two counts were stale besides, both saying four
  required checks where the rule has named three since `codeql` left it
- **and CONTRIBUTING.md was the file that pass did not reach** (#200). It
  said "the one force-push that stays right", and there are two: the
  rebase a contributor makes when their base has moved, and the squash
  the maintainer pushes to their branch at the end — which is the one
  they will actually see, arriving on work they thought was finished. It
  is now named there as the second, and the paragraph on the maintainer's
  path carries the step it was missing: the squash reaches the branch
  before it reaches `main`, which is what leaves the pull request naming
  the commit that lands, so GitHub marks it Merged and the `Closes #N` in
  the description fires. A contributor reading only this file would have
  expected the other outcome, and the two pull requests that landed the
  rule went the way it now describes
- **The worktree recipe checks the submodule out** (#223). CLAUDE.md tells
  every session to work in a worktree and gives the commands that get one,
  and what they set up could not build: a worktree isolates files, a
  submodule is a checkout of its own, and `git submodule status` in a
  fresh one answers a leading `-`. What `uv sync --locked` then says is
  forty lines of CMake and traceback naming the empty `secp256k1/`, closing
  on "Build failures usually indicate a problem with the package or the
  build environment" — the two things that are not wrong — and mentioning
  the submodule nowhere, so a reader who does not already know goes and
  audits their toolchain. `git submodule update --init secp256k1` before
  the sync is the whole of the fix, verified in a fresh worktree rather
  than reasoned about: with it the sync exits 0 and the suite passes in
  that worktree's own venv, without it the sync exits 1. Nothing here was
  unknown — CONTRIBUTING.md documents the submodule for a clone and again
  for the documentation build — but the recipe a session actually follows
  is the one in CLAUDE.md, it reads as complete, and it was the one place
  the line was missing. CI never meets it, every checkout there passing
  `submodules: true`

- **The concurrency ceiling is written down, with the column that
  decides it** (#194). REPOSITORY.md's plan-gated section now carries the
  number that has moved these workflows twice, and it is an attribute of
  the organization rather than a setting of the repository: an
  organization on GitHub Free runs twenty jobs at once, **of which five
  may be macOS**. Paying for Team triples the first and leaves the second
  exactly where it is; only Enterprise moves it. So the macOS column that
  queued for tens of minutes was thirty-five jobs asking for five slots,
  and the split that took those cells out of the merge gate is not a
  workaround for a plan but the answer on any plan below Enterprise —
  which is worth having written down before someone reads the first
  column alone and buys a seat expecting it back
- **The sentinel table names `windows` too** (#184). `windows.yml` became
  a workflow of its own two changes after `macos.yml` did, and the table
  in CLAUDE.md kept listing the sentinels without it — so the paragraph
  under the table still called `macos` "the one sentinel a pull request
  would otherwise have waited for" when there are two, each split by a
  measurement of a different kind: a queue for the first, an
  organization's ceiling of concurrent jobs for the second. The
  measurements stay where they were made, in `test.yml`'s header and
  `windows.yml`'s. Two smaller readings of the same omission go with it:
  the static-then-dynamic pair of steps CONTRIBUTING.md attributes to
  `macos.yml`'s cells is `windows.yml`'s too, and `test.yml`'s aggregate
  job explains its name by there being a second workflow over this matrix
  shape, which is now a third
- **cosmic-ray's own defence against a stale `.pyc` is named rather than
  asserted** (#229). CLAUDE.md said "cosmic-ray does not have the
  problem" after two paragraphs on how a hand-applied mutation loses
  one, and did not say why — which is what let the sentence be read as
  an assumption. It is `cosmic_ray/testing.py`, which sets
  `PYTHONDONTWRITEBYTECODE` in the environment of the test command under
  a comment giving this very reason, so no `.pyc` is written during a
  session; measured by looking at `btclib_secp256k1/__pycache__` before
  and after a real `cosmic-ray exec` over `hashes.py`, one file before
  and the same one after, and the baseline step writes none either. Two
  things go in the same clause because each is what the next reader
  would otherwise re-derive: grepping the package for
  `dont_write_bytecode` finds nothing and proves nothing, the string
  being the environment variable's own spelling; and no flag stops a
  *read*, so a `.pyc` from an earlier `pytest` is still used where its
  size and truncated mtime match — the same window as the hand case,
  which is why that recipe wants the control run and not only the
  variable.
- **Both secrets baselines are `--slim`, so a line that moves stops
  rewriting them** (#230). The files carried `line_number` and
  `generated_at`, and over #221 that meant a rewrite on all four pushes
  recording nothing but one entry's number going 40, 48, 49 as a comment
  block above it grew — a file that changes on pushes with nothing to do
  with secrets being one a reader learns to skip. `--slim` omits both
  fields, and it needs a fresh scan: `--baseline` writes the full form
  whatever it read, `save_to_file` calling `format_for_output` with the
  default `is_slim_mode=False`, where `--slim` is honoured only on the
  branch that prints to stdout. So the exclusion the tree baseline's own
  filter used to supply is spelled out in the command, and both baseline
  files are named in it rather than the one `--baseline` would have
  skipped by itself. Verified rather than assumed: 53 findings in the
  tree baseline and 466 in the vectors one before and after, identical
  as sets of filename, hash and type; both hooks pass; and with a line
  inserted above every finding of `hashes.py` a regeneration is
  byte-identical to the committed file, which is the whole of what the
  churn was. The redirect costs two things and both are written where
  they are paid. One field of the diff — a new secret still arrives as a
  new `hashed_secret` under its filename, and finding *where* takes a
  grep — and the merge `--baseline` was doing, which carried an audit's
  own product forward: `is_secret` and `is_verified`, "verification of
  secrets, both automated and manual" in `SecretsCollection.merge`'s
  words. A scan into a file has nothing to merge, so those marks return
  to their defaults, and slim output prints no `is_secret` when it is
  unset, so the loss would show as a diff of nothing. Nothing is lost
  today, all 53 and all 466 findings being unverified and none carrying
  `is_secret`.
- **Ten lines that stopped short mid-sentence are the paragraphs they
  sit in, rewrapped** (#233). Each is the artifact an insertion leaves
  in a block nothing reflows: the qualifier goes in, the line it lands
  on stops early, and the diff of the change that made it shows a line
  that was going to be rewritten anyway. The unit of repair is the block
  and not the line, which #228 established the hard way — fixing the one
  line #225 named left two more of the same shape. Twelve blocks moved
  across `CHANGELOG.md`, `README.md`, `CONTRIBUTING.md`, `RELEASING.md`
  and `HISTORY.md`, every one of them word-for-word identical to what it
  said before, which is asserted rather than eyeballed: the rewrap
  compares the joined words of the block before and after and refuses to
  write where they differ. Three of the thirteen the issue counted are
  not defects at all and stay: a line before a markdown link of 63, 84
  and 125 columns is short because nothing can follow it, and the filter
  measured the link's first word rather than the link. No hook does
  this, which #233 asked about and answers no. The thresholds are a
  heuristic, a false positive has no `# noqa` to be marked with in
  prose, and a gate that is exact everywhere else is the wrong place for
  one that is nearly right — but the stronger half of that is the false
  *negative*, and this change produced one of its own (#240). Correcting
  a sentence in `CLAUDE.md` left a 35-column line mid-sentence under a
  57-column one, and the detector that had just counted ten of exactly
  that shape -- thirteen reported, ten of them defects -- walked past
  it: 35 is under the 46-column ceiling but 57 is under the 65 the line
  above has to reach, and the line at 57 is itself the same shape and
  over the ceiling. A *pair* of short lines hides a widow, because the
  first break is too long to be flagged and the second has no long line
  above it. So what a hook would have missed here is the instance a
  reader found, which is a better reason to decline it than the noise it
  would have added — and the two short lines left in that paragraph
  after the rewrap are token-forced, 47 columns before a 32-character
  path and 58 before a 40-character one, the same shape as the three
  links. Those are columns and not bytes, which is worth saying where
  the figures are: the second line carries an em dash, three bytes and
  one column, so `awk` in a byte locale and `wc -c` answer 60 where the
  detector's own `len` answers 58, and every figure in this bullet is
  the second kind. No consecutive short pair anywhere in it is what says
  the rewrap is complete, and it is cheaper to check by eye than either
  threshold.
- **The worktree recipe costs a submodule clone, and the sentence under
  it counts it now** (#234). It said the venv and the C build "are the
  whole of the cost" and after the submodule line they are not: a linked
  worktree gets a module of its own rather than sharing the primary
  checkout's, measured at 14 MB under `.git/worktrees/<wt>/modules` and
  7 MB of tree, which is the same "minutes, not seconds" argument the
  other two get. `--reference` is what a session asks about next and is
  measured rather than reasoned about: it works, leaves the module
  directory where git puts it, writes one `objects/info/alternates` at
  the primary's `objects`, and comes to 128 KB against those 14 MB with
  the primary's `core.worktree` untouched. What it costs is that pointer
  — no copy of its own objects, so a `git gc` or a repack in the
  primary, or moving it, can leave the worktree's submodule unable to
  find them. What git keeps apart by giving each linked worktree a
  module of its own is the submodule's *state*, so two worktrees can
  have it at two commits; the object store inside that module follows
  from where the state lives rather than from a refusal to share
  objects, which is why `--reference` may share them and leaves
  `core.worktree` alone. For a recipe that removes the worktree anyway
  that is a trade worth declining knowingly. Two facts measured while
  checking that go with it, both about a sharp edge: `core.worktree` is
  a single value that a second checkout of one submodule can rewrite
  under the first, and does not here; and `git worktree remove --force`
  finishes with an initialized submodule inside, exit 0 and nothing left
  for `git worktree prune`, so the recipe's last line needs no
  companion.
- **`silentpayments` says why its two widths are the package's only
  public ones** (#232). Six modules name a buffer width privately and
  this one does not, which after #221 made "the six modules read alike"
  a claim a reader would test against the seventh. The rule is not the
  one `xonly.py` states about its own: those are the size of a buffer
  the module fills and unpacks, where these are lengths this module
  answers a caller with. `SUMMARY_SIZE` has to be public — `ffi.sizeof`
  of a struct, written down by no BIP, moving when libsecp256k1 moves,
  and unknowable to a caller holding what `prevouts_summary` returned.
  `LABEL_SIZE` is 33 and could be worked out, so what keeps it public is
  that it has been since 0.8.0 and taking a released name private to
  tidy an asymmetry is a break charged to a reader who never asked.
  `keys._COMPRESSED_SIZE` is the same 33 and stays private: two callers'
  arguments are checked against this one, `parse_label`'s octets and the
  labels `_fill_label_cache` takes for `_scan_outputs_`, where nothing
  in `keys` checks an argument against a width at all. What
  `serialize_label` does with it is the other kind of use and is named
  as such — unpacking the buffer this module declared, which is exactly
  what `keys` does with its own.
- **`dsa.verify` says whose refusal the lower-s form is** (#249). The
  docstring motivated the default by who wants it -- "what a caller
  enforcing the lower-s form of its own signatures wants" -- which reads
  as this wrapper choosing between two behaviours libsecp256k1 offers. It
  is the other way round: `secp256k1_ecdsa_verify` accepts the lower-s
  form alone, "to avoid accepting malleable signatures", so `False` is
  that call passed through and `normalize=True` is the one way of not
  passing it through. Which is also what makes the flag unlike the rest
  of this module's booleans: `grind` and `verify` weigh a cost against a
  benefit and `compact` picks a serialization, where this one spends no
  measurable time and pays in the malleability itself -- two encodings
  verifying one message under one key, which whatever hashes or stores
  the signature has both to account for. Bitcoin Core makes the same
  refusal a standardness rule, `SCRIPT_VERIFY_LOW_S`, so a signature
  from elsewhere and a signature a transaction can carry are not the same
  set, and "a caller checking signatures it did not make normalizes" is
  now stated with what it accepts in exchange. `_verify_`'s argument
  entry, which has no prose above it to lean on, points at both.

### CI

- **A pull request that changes only prose no longer runs the matrix**
  (#189). Measured on the last full run before this, 48 jobs and 81.8
  runner-minutes, of which the change that added `windows.yml` to the
  table of sentinels — four markdown files and one workflow comment —
  asked for all of them. `changes` is one ubuntu job that lists the pull
  request's files through the API and answers whether anything the matrix
  reads changed; the five root jobs read it in their `if`, and what hangs
  off them skips on its own. `test: every job passed` already carried
  `always()`, so it still runs and reads `skipped`, which it does not
  treat as a failure, and the branch rule keeps naming the same context.
  Three things the job cannot get wrong, all in the comment above it: it
  runs on every trigger and answers `true` on all but `pull_request`,
  because a `changes` that skipped itself would leave every dependent
  reading an empty output and skip the release path too; `README.md` is
  not prose here, being the long description `check-dist` renders with
  twine and rates with pyroma, which is why the allowlist is written out
  rather than inverted from `*.md`; and `test-passed` takes `changes` as
  a `needs`, so an error listing the files fails the gate instead of
  skipping everything and reporting a pass
- **The suite cells are one job per image, not one per interpreter**
  (#190). In the same run, 30 of the 48 jobs were suite cells and they
  were 11.8 of its 81.8 runner-minutes: what they cost is slots, of which
  an organization on GitHub Free has twenty shared across every
  repository in it, and not time. `suite-dynamic` (eight interpreters on
  two images) and `suite-static` (seven on two) are two jobs each now,
  walking their whole list. Per cell the marginal work is an install and
  a suite, both under half a minute, against a checkout, a setup-python
  and an artifact download paid once per job — so the collapse costs
  little wall clock and pays back twenty-six slots. What it trades away
  is that a cell named the interpreter in the check itself, and the loop
  gives that back where it can: every version runs even after one has
  failed, each inside a fold of its own, and the failures are named
  together at the end rather than the first one aborting the job. The
  list is stated once per job and read twice, by setup-python and by the
  loop, so a version in one and not the other is either an interpreter
  installed and never run or a run that fails on a missing executable
- **A pull request builds one wheel on macOS and Windows, and the rest
  after the merge** (#193). Of the 59.5 runner-minutes the six wheel jobs
  cost, 39.0 were the four jobs that are not ubuntu. What a pull request
  needs to know about a platform whose suite it no longer waits for is
  whether this tree still builds there, and the first wheel answers it:
  the toolchain, the CMake build of the vendored library and the cffi
  extension are what differ per platform, and they do not differ per
  interpreter. So on `pull_request` those four build `cp314-*` alone. The
  two ubuntu images keep the whole set because `suite-static` consumes
  it — pip's selection among a directory of wheels tagged for seven
  interpreters is not a question a directory of one can be asked. A push
  to `main`, a release and a rehearsal all build everything, in a called
  workflow `github.event_name` being the caller's and never
  `pull_request`, so no wheel a release publishes was built under the
  shortcut. What is given up is the window between the two: a break
  specific to one ABI tag on macOS or Windows sits on `main` until the
  push run that follows the merge, instead of being refused at it.
  Measured on the change's own run, those four jobs came to 7.2
  runner-minutes: 14.4 and 5.7 on the two macOS images became 1.5 and 1.2,
  8.7 and 10.2 on the two Windows ones became 1.8 and 2.7
- **and the step that does it needs `shell: bash`, which the first run is
  what said.** Without it the two Windows images run it in PowerShell,
  where `"$GITHUB_ENV"` is not the variable but a literal, so
  `echo "CIBW_BUILD=cp314-*" >> "$GITHUB_ENV"` wrote a file of that name
  and cibuildwheel built all seven wheels anyway. Nothing failed: the step
  was green, the log listed `cp310` through `cp314t`, and the only thing
  that said so was a job duration that had not moved — 9.8 and 10.4
  against a 8.7 and 10.2 baseline — while the macOS images, whose default
  shell is bash, had already dropped to 1.5 and 1.2. A step that is green
  while doing nothing is why the comment above it now carries this
- **The vendored library is no longer configured by what happens to be
  installed on the machine that builds it** (#211).
  `SECP256K1_VALGRIND` defaults to `AUTO`, and `AUTO` is
  `find_package(Valgrind)` — the only `find_package` in the vendored
  CMake. Where the header is on an include path, the library is compiled
  with `-DVALGRIND`, which turns the `SECP256K1_CHECKMEM_*` of
  `src/checkmem.h` from no-ops into valgrind client requests, and
  `SECP256K1_BUILD_CTIME_TESTS` takes its default from it besides. So a
  runner that happened to have one shipped a different library from the
  same commit, in a wheel that says nothing about which one it is.
  `scripts/cffi_build.py` passes `-DSECP256K1_VALGRIND=OFF` now.
- **The defect was reproduced before it was fixed** rather than argued
  from the CMake: configured against a directory holding a
  `valgrind/memcheck.h`, `AUTO` reports `-- Found Valgrind`, puts
  `Valgrind_INCLUDE_DIR` in the cache and `-DVALGRIND` in
  `src/CMakeFiles/secp256k1.dir/flags.make`; `OFF` does none of the
  three, `find_package` not running at all. An empty header is enough,
  the module's compile check only rejecting `NVALGRIND`, so the trigger
  is a header on an include path and not an installed valgrind. Every
  wheel job's configure summary carries the answer —
  `Valgrind .............................. OFF` — which is the audit,
  `scripts/` being outside the coverage gate.
- **The instrumentation in such a wheel runs rather than merely being
  present, and the pin is still not about what it costs.**
  `SECP256K1_CHECKMEM_RUNNING()` is itself a client request under
  `VALGRIND` — `src/checkmem.h` defines it as
  `(VALGRIND_MAKE_MEM_DEFINED(NULL, 0) != 0)` deliberately, memcheck
  having to be detected specifically rather than valgrind in general —
  and it is the left operand of the `&&` at `src/secp256k1.c:104`,
  behind no flag and no `VERIFY`. `secp256k1_context_create` reaches
  that line twice, so a wheel built with `-DVALGRIND` executes two of
  them at import and none afterwards: the other call site is
  `secp256k1_declassify` (`src/secp256k1.c:254`), behind
  `ctx->declassify`, which line 104 refuses to set outside memcheck at
  all. Everything else is `CHECK_VERIFY`, `MSAN_DEFINE`, or under
  `#ifdef VERIFY`. A handful of instructions, once — and what the pin is
  about is that the wheel be a function of the source.
- **`SECP256K1_ASM`, `SECP256K1_ECMULT_WINDOW_SIZE` and
  `SECP256K1_ECMULT_GEN_KB` stay at upstream's defaults, and that is now
  written down** rather than left as three options nobody named. The two
  table sizes (15, and 86 KiB reaching the compiler as `COMB_BLOCKS=43
  COMB_TEETH=6`) are what upstream recommends for a desktop. `ASM` asks
  the build machine a question too — `AUTO` is a compile check, and it
  falls back to `OFF` in silence where that check fails, which a pinned
  `x86_64` would turn into a build error — but it cannot be pinned in a
  line: the macOS `universal2` cell compiles two architectures in one
  pass and the mingw one cross-compiles, so naming an architecture there
  would break the cells that are not it. So one machine question stays
  open, by choice, and the headline above is scoped to the one that is
  closed.
- **The vendored library is compiled once per wheel job, not once per
  wheel** (#192). The six wheel jobs were 59.5 of that run's 81.8
  runner-minutes, and each of them built the whole of libsecp256k1 once
  per wheel: seven interpreters on macOS and Windows, twice that on
  Linux, manylinux and musllinux being separate images. The work is
  identical every time, the library not knowing which interpreter the
  extension beside it will be built for. `scripts/cffi_build.py` still
  deletes the CMake directory before every build — a stale CMake cache is
  a configuration nobody asked for, and that is a different failure from
  this one — because ccache does not need it reused: it hashes the
  preprocessed source and the compiler flags, so it cannot serve an object
  built for another configuration. CMake initializes
  `CMAKE_C_COMPILER_LAUNCHER` from the environment variable of the same
  name, so the whole wiring is one `environment` line in
  `[tool.cibuildwheel.linux]` and `.macos` and a `before-all` that
  installs ccache. Measured on its own run, the four jobs it touches went
  from 40.6 runner-minutes to 32.9: 14.4 to 11.1 on macos-26-intel, 9.9 to
  7.7 on ubuntu-24.04-arm, 10.6 to 9.3 on ubuntu-latest, 5.7 to 4.8 on
  macos-latest. The two Windows jobs, which this does not touch, moved
  8.7 to 11.2 and 10.2 to 10.7 in the same run, which is the size of the
  noise these four are measured against — and that all four moved the
  same way is what the reading rests on. Windows is deliberately out, and
  is 18.9 of those 59.5 minutes: ccache's MSVC support is recent and
  partial, and sccache is a second tool to pin for a saving nothing has
  measured there
- **and the fallback lives in `before-all` because `environment` cannot
  hold one.** The first attempt made the launcher
  `$(command -v ccache || true)`, so that an image without ccache would
  configure with an empty launcher and build as before. cibuildwheel does
  not evaluate `environment` in a shell: it parses the value with bashlex
  and runs each command through `subprocess` with `check=True`. Measured
  against that parser rather than argued —
  `X="$(command -v ccache || true)"` is an `EnvironmentParseError`,
  `X="$(command -v ccache)"` raises `CalledProcessError` where there is no
  ccache, and only `X=ccache` survives. So the launcher is the literal,
  and `before-all`, which *is* a shell, carries the chain: whichever
  package manager answers — the manylinux images ship no ccache and keep
  theirs in EPEL — and, if none does, a passthrough of that name written
  on the PATH, `exec "$@"`, so the launcher always resolves. `ccache
  --version` at the end is what makes the log say which of the two
  happened; on every image of that run it was the real one, 3.7.7 on
  manylinux aarch64, 4.11.3 on musllinux, 4.13.6 from brew on macOS
- **`github-release` needed `always()` too, not just an explicit `if`.**
  The previous fix (v0.8.0.2's own CHANGELOG entry, right below) added
  `needs.publish-pypi.result == 'success' && needs.attest.result ==
  'success'` and reasoned that asking only about direct needs would be
  enough — it was not: v0.8.0.2 published clean and was *still* skipped
  with both of those green. GitHub's needs-based skip is structural, not
  a property of which question a job's own `if` asks: a job with a
  skipped job anywhere in its ancestry is force-skipped regardless of its
  condition unless that condition itself starts with `always()`, and the
  override does not clear the taint for whoever depends on the job that
  used it. `attest`'s `always()` keeps attest itself from being skipped
  when `publish-testpypi` is (always, on a real tag); `github-release`,
  needing `attest`, still sat behind that same skipped ancestor and was
  force-skipped in turn until it opted out on its own. `if: always() &&
  needs.publish-pypi.result == 'success' && needs.attest.result ==
  'success'` is what actually breaks the chain. v0.8.0, v0.8.0.1 and
  v0.8.0.2 all published clean and none produced a GitHub release,
  recreated by hand from each run's own `sdist` and `attestation`
  artifacts every time
- **A change to prose no longer rewrites `.secrets.baseline`** (#198).
  The baseline recorded one finding in `CHANGELOG.md`, and this file
  grows above it: of the forty commits before this one, forty rewrote
  the baseline and thirty-three moved nothing in it but that finding's
  `line_number`. What the rewrite costs is not the command that makes it
  — it is that every open pull request then conflicts there with every
  other and with `main`, whatever either of them touches, which is what
  happened to #183 and #185 within the hour they were both open. The
  finding is a false positive this file's own entry above records: the
  `-DSECP256K1_BUILD_BENCHMARK=OFF` it names is quoted there as
  `cffi_build.py` writes it, and a string in straight quotes is what the
  base64 detector reads. A `pragma: allowlist secret` beside it takes it
  out of the baseline without taking the quotes out of the sentence,
  they being why the detector fires and so what the sentence is about.
  Measured against the alternatives: dropping the quotes also clears it
  and says less; the pragma on the previous line does *not* clear it,
  `is_line_allowlisted` reading `context.previous_line` notwithstanding;
  and excluding the file from the hook would take the keyword and
  provider-token detectors off it too. The baseline is now written when
  a file that has a finding changes, which was 7 of those 40 rather than
  all of them
- **`mutation.yml` says what its session cannot ask** (#222). The
  operators replace arithmetic, comparisons, literals, branches and
  decorators; not one of them puts a different expression in an argument
  list, so which argument a `lib` call is handed — the whole of what a
  binding decides — is mutated by nothing in the session, and a green
  Sunday says nothing about it. `core/VariableReplacer` and
  `core/VariableInserter` are the two that come closest and
  `.github/mutation/bindings.toml` instantiates neither, both declaring
  `cause_variable` and `effect_variable` arguments it does not supply;
  configured they would substitute a random number, which cffi refuses
  where a pointer was declared, and a mutant that dies of a `TypeError`
  proves the boundary type-checks rather than that a test read what the
  call wrote. The instance is the first revision of #220: `ffi.NULL` in
  place of the `int *` its caller allocated left the whole suite passing,
  the key having even y and `ffi.new("int *")` zeroing what it allocates,
  so every side of every comparison was 0 either way. A paragraph in the
  header is the change, and it is what would have made that hole visible
  while the test was being written rather than after. An operator of our
  own, replacing each argument of a `lib.*` call with `ffi.NULL` in turn,
  is what a second instance would justify and what nothing yet does: the
  optional out-parameters of the wrapped surface are the two occurrences
  of `Ignored if NULL` in the vendored headers, both in
  `secp256k1_extrakeys.h` and both now exercised over either answer, plus
  `sigout` of `secp256k1_ecdsa_signature_normalize`, for which `dsa`
  passes `ffi.NULL` already
- **`bindings.toml` records the resolution a consolidated width costs**
  (#231). Its preamble already carries the two shapes that were answered
  in the code and the one equivalence that cannot be, each written down
  so a session does not spend itself rediscovering them; a width
  collapsed to one statement belongs in that list for the opposite
  reason. Two modules had several mutable copies of one number —
  `ellswift` three, at `_decode_` and at both of `xdh`'s checks, and
  `ssa` two, at `_verify_` and at `verify` — and `core/NumberReplacer`
  carries `OFFSETS = [+1, -1]`, a position per offset, so `ellswift`'s
  six mutants are two now and either of them changes every site at once,
  dying on whichever test reaches it first. A check that later loses the
  test covering it can therefore no longer surface as a survivor.
  Nothing is hidden today, the seven constants #221 introduced having
  each been mutated both ways before it landed and all fourteen dying,
  and the paragraph says what the ratchet does and does not catch
  instead: a line that stops running is caught, a line still run by
  another test and asserted by none is what neither question sees.
- **The prose allowlist covers the two file kinds nothing built reads**
  (#239). `changes` answers whether the matrix has anything to check,
  and its pattern was the root and `.github` prose alone — so a pull
  request touching one file the matrix cannot read alongside prose ran
  everything. The mutation configuration is on it now, cosmic-ray taking
  that path as an argument from a workflow the matrix does not contain,
  and so are the detect-secrets baselines, which are that tool's own
  output read by a hook and by a workflow that has no changed-file gate
  at all. It is anchored on the file --
  `^\.github/mutation/[^/]*\.toml$` -- and not on the directory, that
  being the same staleness this declines for workflows in the direction
  that looks cheap: a prefix would exempt in advance whatever a later
  change drops there, and two tests already load a script by path one
  directory over, so such a script would skip the matrix and take its
  own test with it. `.toml` rather than the one filename so a second
  configuration needs no edit; a script belongs in `.github/scripts/`,
  where all three are. Measured before and after against the file lists
  of four real pull requests, with `/usr/bin/grep` rather than this
  machine's `grep`: #236's `bindings.toml` and two markdown files went
  from 23 jobs and 45.7 runner-minutes to a skipped matrix, a baseline
  alone likewise, while #237's `silentpayments.py`, a bare `README.md`,
  a file under `docs/` and an empty list all still run everything. A
  workflow is deliberately not on the list, which is the other half of
  #239 answered rather than omitted: which workflows the matrix reads is
  a judgement — this file, what it calls, and `release.yml` — and a list
  of the rest would be right today and stale the first time a sentinel
  is folded into the gate, which skips a matrix that should have run.
  The comment above the pattern carries that reasoning and the figure.
- **and the list that promises to reproduce each gating job was missing
  the job that decides whether the others run** (#242), which is the same
  step again from the other side. Reproducing it by hand answers the
  opposite where the shell's `grep` is ugrep: `-qv` there takes its
  status from whether the pattern matched anywhere and inverts that,
  rather than from whether `-v` selected a line, so a list mixing prose
  with code — the case the step exists to judge — exits 1 and reads as
  "prose only", the direction that skips a matrix that should have run,
  and nothing says it has. Measured on each shape of file list with the
  pattern taken out of the workflow, and against the runner rather than
  against itself: #237's own list answers "everything runs" as its run
  did, and the pull request carrying this entry answers "prose only" with
  its matrix skipped. Nothing in the tree moves, `test.yml`'s `grep`
  being the runner's, which is GNU's. The entry spells the path out,
  lifts the pattern out of `test.yml` so the two cannot drift, and names
  `-q` as the mechanism rather than `-v`: ugrep takes the same
  file-level path when the output is discarded, which is where dropping
  `-q` lands next, and `-cvE` with a numeric test is what agrees with
  both greps. `test: every job passed` gets an entry in the same pass,
  that being the neighbouring gap and the check a contributor sees red:
  it reproduces as nothing, reading the conclusions of the jobs above it.
- **`test-passed` skips a cancelled run instead of failing it** (#274).
  It carried `always()`, so a run the next push's concurrency group
  already superseded — every needed job reporting `cancelled` — still
  reached the `case " $RESULTS " in *" failure "* | *" cancelled "*)`
  step and turned that into a required check with no defect behind it,
  red beside the newer run's green on the same head sha. The job's own
  comment had called this deliberate, "Cancelled is a failure here too,
  a superseded run being no evidence either way" — the framing #273
  disputes: the case that is wrong is the concurrency one, where the
  cancellation means a newer run is authoritative rather than that this
  tree is unproven. `always()` becomes `!cancelled()`; a skipped
  required check satisfies branch protection the same as a passing one,
  and the step below is unchanged, so a job cancelled on its own rather
  than by the run's own cancellation still fails the gate as before.
- **A closed pull request's run no longer lands in its merge's own push
  run's concurrency group** (#276). `test.yml`, `lint.yml` and
  `docs.yml` grouped by `github.ref` alone, and `github.ref` for a
  closed, merged pull request's run resolves to the base branch's ref
  rather than `refs/pull/N/merge`, landing it in the same group as the
  push the merge itself triggers. The two events fire about a second
  apart on every merge, and after bitcoin-core-rpc's own #136 landed
  there, its `docs` push run for the merge commit was cancelled two
  seconds after being created, before any job started -- required
  checks reading `cancelled` for a commit the run that got to run never
  tested. The group is now
  `github.event.pull_request.number || github.ref`: a pull_request run
  of any action, closed included, groups by the pull request's own
  number instead, which still cancels that same pull request's own
  earlier run exactly as `closed` was added for, and cannot equal any
  push's `github.ref`. `links.yml` and `vendored-vectors.yml` get the
  same fix though neither has a push trigger to collide with, their
  `schedule` and `workflow_dispatch` triggers resolving to the same ref
  a closed run does.
- **`release.yml`'s call into `test.yml` grants `pull-requests: read`
  now, `contents: read` beside it** (#281). A called workflow's jobs
  are capped at what the caller grants, not at what the called
  workflow's own top-level default declares, and `release.yml` granted
  only `contents: read` -- so `test.yml`'s `changes` job (#189), which
  declares `pull-requests: read` to list a pull request's files,
  refused the whole call before a single job started, `version-check`
  included, `changes` never actually reading a file list on a release
  or a rehearsal. Found tagging `v0.8.0.3`: three tag pushes and a
  `workflow_dispatch` all came back `startup_failure` with zero jobs
  scheduled, the REST API answering nothing more than a generic
  "workflow file issue" -- the actual error only shows on the run page
  itself. Nothing had exercised this call since `changes` was added,
  the prior release predating it. `contents: read` is repeated rather
  than left to `test.yml`'s own default because a caller's grant
  replaces the callee's default outright: leaving it off would have
  starved every other job over there of the checkout permission it has
  today, not only `changes` of the one it asked for.

### `HISTORY.md` is `RELEASE_NOTES.md` now

- **Its own H1 always read `# Release notes`; the filename did not.**
  In common usage the two words that were split name the same file,
  where a project that does split them puts it the other way round --
  [Keep a Changelog](https://keepachangelog.com/) defines CHANGELOG.md
  as the curated, human-facing list, which is what this file is here.
  PyPI's own **Changelog** link, read off `pyproject.toml`'s
  `changelog` url, pointed past CHANGELOG.md at the file not named
  changelog -- accurate about its content and wrong about the one thing
  a stranger meets first. `CHANGELOG.md` is unchanged: it is the file
  whose name and contents already agree, and every entry it has ever
  made about the old name stays written as it was true then. Sibling
  repository btclib closed the same gap as issue
  [btclib#1011](https://github.com/btclib-org/btclib/issues/1011).

  Every other reference moved, past `CHANGELOG.md` itself. Two were
  load-bearing: `release.yml` lifts the GitHub release notes out of the
  tag's own section by filename, and its retitle check reads both files
  by name -- a tag whose heading is not retitled is refused in either.
  `.gitattributes` keeps `merge=union` under the new name, so a
  parallel release-note bullet still resolves without a conflict.
  `docs/source/history_link.md` moves to
  `docs/source/release_notes_link.md`, its toctree entry relabelled
  `RELEASE NOTES` to match. No redirect for the old name: this
  repository serves no website of its own to carry one -- its docs are
  built by Read the Docs straight from `docs/source` -- and the file's
  git history is where the old name stays reachable.

## v0.8.0.2

### The parsed public key

- **Verification takes the parsed key a caller already holds** (#147).
  `keys.parse` was public and `keys.serialize` took what it returned, and
  `pubkey_tweak_add_` consumed one — but `dsa.verify`, `ssa.verify` and
  `ecdh.shared_secret` took bytes and parsed them, so a caller holding a
  parsed key had nowhere to put it. Two callers pay for that twice: one
  that validates a key before verifying with it, which is
  <https://github.com/btclib-org/btclib/issues/887> and the other half of
  this pair, and one checking several signatures against one key, which
  is the case `PubkeyTweakChain` exists to stop for tweaks. For a
  compressed key the parse is a field square root, so it is not a
  rounding error next to the verification it precedes. `dsa.verify_`,
  `ssa.verify_`, `ecdh.shared_secret_`, `keys.pubkey_negate_`,
  `keys.pubkey_tweak_mul_`, `keys.pubkey_cmp_` and `xonly.from_pubkey_`
  are the inner halves, and `xonly.parse` is public beside `keys.parse`
  because BIP340 verifies against the x-only key and that is the object
  `ssa.verify_` takes.
- **The convention is one sentence, and it is in `keys.parse`**: the
  inner half takes the parsed key in place of the bytes, and the outer
  half is that inner half with a `parse` in front of it. Nothing else
  differs — every remaining argument is checked exactly as before, a bare
  pointer's length being what no C return code can report, which is why
  these are not quite the "already validated, nothing left to redo" shape
  `pubkey_tweak_add_` was documented as. That one is brought to the same
  rule here: it takes `BytesLike | int` and validates the tweak itself,
  where it took 32 bytes on trust and would have read past the end of a
  shorter value. `PubkeyTweakChain` is unchanged in behaviour, its
  `scalar` call now happening one frame further in.
- **`tests/test_parsed_keys.py` holds every pair to that equality**, over
  both serializations of the key, and holds the table of pairs to what
  the modules export: an inner half added and left unpaired fails there
  rather than going untested. `mult.mult_` is named in it as the one
  trailing underscore that means the older thing — the serialized point
  against `mult`'s pair of coordinates — and has no key to be handed
  already parsed.
- **What is deliberately not there**: `keys.pubkey_combine` and
  `keys.pubkey_sort` take sequences, so their inner halves would take
  lists of cffi objects, and no caller has asked; and there is no
  `xonly.serialize` beside `xonly.parse`, nothing here handing back a
  parsed x-only key for one to take.

### ECDSA signature normalization

- **`dsa.verify` and `dsa.verify_` take a `normalize` flag** (#148),
  false by default. `verify` does not accept a signature outside the
  lower-s form, and which of the two forms a signature carries was the
  signer's choice, so a caller checking signatures it did not make always
  normalizes first — and `normalize` takes DER and returns DER, so that
  is a parse, a normalization, a serialization, and then `verify` parsing
  what came out. libsecp256k1 documents `sigout == sigin` for
  `secp256k1_ecdsa_signature_normalize`, so neither the serialization nor
  the second parse is the normalization's own need: with the flag, the
  normalization happens on the signature `verify` has already parsed.
  <https://github.com/btclib-org/btclib/issues/889> is the caller.
- **A flag rather than a public parsed-signature form**, which is the
  other answer #148 offered and the one that would have followed #147
  exactly. The parsed *key* is a thing a caller holds for its own reasons
  — `keys.parse` is how a key is validated — while a parsed DER signature
  is an intermediate nothing here produces or consumes, so publishing it
  would have meant a `parse` and a `serialize` for signatures and inner
  halves of `normalize`, `is_low_s` and `to_compact` besides, for one
  caller that wants none of them. The flag is the whole of what that
  caller needs, and the default keeps today's refusal for the caller
  enforcing the lower-s form of its own signatures. It is not the
  leniency the README's "nothing is normalized into validity" refuses,
  either: that bullet is about a boundary guessing what the caller meant,
  and this is the caller saying it.

### The benchmark

- **`scripts/benchmark.py` moves to
  [btclib-benchmarks](https://github.com/btclib-org/btclib-benchmarks)**,
  as `scripts/libsecp256k1_wrappers.py`, and the `bench` dependency group
  goes with it (issues #144 and #145).

  The group named `btclib`, `coincurve` and `secp256k1`, which put the
  packages being timed into this repository's lock. `btclib` was the
  wrong way round in particular: it is btclib that depends on these
  bindings, so a benchmark comparand made the dependency circular in the
  one direction a lock can express it — and the copy it resolved was
  `btclib_libsecp256k1` 0.7.1.3 from PyPI, an older release of *this*
  package installed beside the tree it was meant to measure.

  What #144 and #145 asked for — narrowing the comparison to
  wrapper-against-wrapper, and adding `electrum-ecc` to it — is work on
  that script, and it moves with the script rather than being done or
  abandoned here.

  `[[tool.mypy.overrides]]` keeps its `secp256k1` entry and loses the
  other two: that name has a second job here, the vendored C tree being
  picked up as a namespace package of the same name without it.

### CI

- **The generated Code Quality analysis is off.** `Analyze (python)` ran
  on every pull request and every push to `main` from a
  `dynamic/github-code-scanning/codeql` workflow no file in this tree
  declares -- some 52 seconds of a slot each time, out of twenty shared
  with every other repository in the organization, where the same setting
  was on. What it produced cannot be read from outside a browser: there is
  no `code-quality/alerts` endpoint and no `code-quality/analyses`, both
  404, the alert list is empty and every analysis carries `codeql.yml`'s
  own category. REPOSITORY.md gains the section and the endpoint that
  reports and sets it, `code-quality/setup`: not
  `code-scanning/default-setup`, and not the Actions API, which answers
  422 for a workflow this repository does not own.

- **A pull request asks for fifty-one jobs instead of seventy-three**, and
  the number that decided it is a ceiling rather than a wall clock: GitHub
  Free gives an organization twenty concurrent jobs, shared across every
  repository in it, so a commit here, one in btclib and one in
  bitcoin-core-rpc compete for the same twenty. Measured on one pull
  request run, this workflow set asked for seventy-three jobs and 112.9
  runner-minutes, its critical path 1713 seconds of which the median cell
  spent 694 queueing. Two changes, each moving an answer off the review
  path rather than dropping it:
    - the twenty-one Windows suite cells become `windows.yml`, weekly on
    Saturday and called by `release.yml`, exactly as `macos.yml` already
    holds the macOS ones and built the same way -- from the tree, in both
    linkages, two steps of one job rather than a wheel rebuilt per image.
    They were 27.3 of the 112.9 runner-minutes, the largest family of jobs
    in the run and ahead of every wheel build. **The Windows wheel builds
    stay in `test.yml`**, for the reason its header gives of macOS: the
    release publishes the artifacts of that run, and `cibuildwheel` runs
    the suite against every wheel as it builds it, so what moves to
    Saturday is pip's *selection* among them. With both Windows rows gone
    so are the three exclusions `suite-static` carried, each of them a
    wheel that is not built rather than a platform not worth running.
    - `codeql.yml` loses its `pull_request` trigger and keeps `main` and its
    Tuesday schedule, so `codeql: every job passed` is no longer one of
    main's required checks -- three now, and REPOSITORY.md carries the rule
    and the `PATCH` that dropped the context. `zizmor` is a `pre-commit`
    hook, so `lint.yml` still audits these workflows for an injected
    expression on every pull request.

- **`github-release` no longer risks a skip on a release that actually
  succeeded.** Its `if` used to be the implicit default, and that default
  has no arguments: it does not stop at this job's own `needs`
  (`[publish-pypi, attest]`), it looks at the whole graph reachable
  through them. `attest`'s own `if` is `always()`, needed so it can run
  past a skipped sibling — `publish-testpypi` is always skipped on a real
  tag, `publish-pypi` on a dispatch — and the implicit default treats a
  skipped job found two hops back through that `always()`-guarded edge
  the same as a failed direct one. That skipped `github-release` on every
  real release regardless of what `publish-pypi` and `attest` themselves
  did: both v0.8.0 and v0.8.0.1 published clean and neither produced a
  GitHub release, found only because the release was missing rather than
  because anything failed loudly. The `if` is explicit now,
  `needs.publish-pypi.result == 'success' && needs.attest.result ==
  'success'`, asking only the two questions this job has a reason to ask.
  RELEASING.md's "Cutting a release" section carries the recovery this
  cost both times — recreating the release by hand from the run's own
  `sdist` and `attestation` artifacts — for a release that predates the
  fix, or for a `github-release` failure of its own that `gh run rerun
  --failed` still reaches directly

## v0.8.0.1

### Public key tweaking

- **`keys.PubkeyTweakChain` adds a sequence of tweaks to a public key,
  parsing it once** (#138), rather than once per tweak. `pubkey_tweak_add`
  parses its argument and serializes its result on every call, which is
  the right cost for one tweak and a wasted one for a caller who is about
  to feed the result straight back in as the next call's argument — a
  BIP32 path walked one unhardened index at a time, reported at
  <https://github.com/btclib-org/btclib/issues/685>, needs exactly that:
  each step's tweak is a hash of the previous step's serialized key, so
  the bytes have to exist at every step, and the point they parse back
  into is the one the step before had already built and only serialized
  because its own caller — btclib's derivation loop — needed those bytes.
  `PubkeyTweakChain` holds the parsed point across the calls instead: the
  first tweak is the only one that pays for a parse, and every step still
  returns the bytes its caller needs. `pubkey_tweak_add` itself is
  unchanged in behaviour and cost, now sharing its point-addition step
  with the chain through the new `pubkey_tweak_add_`, the inner half of
  it that skips parsing and validating what the caller already has.
  btclib decided against holding the parsed key itself and reaching for
  `lib`/`ctx` directly, which would have left `_BIP32KeyData` holding a
  cffi object where "the key is its serialization" is what keeps that
  loop readable — hence the wrapper landing here rather than there.

## v0.8.0

### The name

- **`btclib_libsecp256k1` becomes `btclib_secp256k1`** (#122), the
  distribution and the import package together, with the extension
  (`_btclib_secp256k1`), its stub and the autodoc page following. `lib`
  named the C library, and a python distribution is not that library.
  Renaming both rather than the distribution alone is what keeps one name
  to explain: the alternative is a distribution and a module that
  disagree forever, and 0.8.0 being unreleased is what makes this the
  cheapest it will ever be. Everything inside the API is untouched.
- **The repository is renamed too**, to `btclib-org/btclib-secp256k1`.
  That was left out of the first pass on the `bitcoin-core-rpc`
  precedent, which renamed the same way and kept its repository, so that
  no url naming it would move; it is in now because a repository called
  after a distribution that no longer exists is the same confusion one
  level up. GitHub redirects the old paths, the api included — a `GET` on
  `repos/btclib-org/btclib-libsecp256k1` answers with the new
  `full_name`, and `gh` resolves it to the numeric id — so nothing
  outside this tree breaks on the day, and every url inside it is updated
  regardless: an address that answers through a redirect is still the
  wrong address to publish.
- **Two lines of `release.yml` were the reason to do it carefully**, and
  no redirect covers them: `github.repository == 'btclib-org/…'` guards
  both publish jobs, and an exact comparison against a name the
  repository no longer has does not fail — it evaluates false and the
  jobs are *skipped*. A release would have built the whole matrix,
  collected every artifact, and published nothing, in green.
- **The trusted publisher is bound to the repository**, which is the
  other half of the same care: the OIDC claim carries it, and this file
  already records a stale registration surviving one rename and costing
  0.7.1.2 an `invalid-publisher` at the token exchange. The pending
  publishers for the new distribution have to name the new repository.
- **No published artifact carries a GitHub attestation yet**, so
  `SECURITY.md`'s verify command takes the new name with no caveat:
  measured rather than assumed — `attest` landed in #113 on 11 August,
  two days after v0.7.1.3, and `gh attestation verify` on that release's
  sdist answers 404 under either name. The first attested release is
  0.8.0.
- **What deliberately did not change.** The vendored library keeps its
  own name wherever it is the subject: the submodule, the headers the
  cdef is made of, the `SECP256K1_*` build flags. And the entries of this
  file and of HISTORY.md that describe releases made under the old
  distribution name, or quote a command carrying the old repository,
  still do: they are the record of what happened rather than of what is
  true now.
- **Nothing bridges the two names on PyPI**, by decision. A final
  `btclib-libsecp256k1` depending on the new distribution would make
  `pip install btclib-libsecp256k1` resolve forward; what it would also
  do is put a package on PyPI whose only content is a redirection, and
  one that has to be deprecated and removed later. The old name stops at
  0.7.1.3 and stays installable, wrapping libsecp256k1 0.7.1, and moving
  is a requirement and an import to edit — the README's own "The name"
  section, which is where a user arriving from the old name lands.
- **The `bench` group now resolves a second copy of the old
  distribution.** btclib requires `btclib_libsecp256k1`, which used to be
  this project's own name, so the lock answered it with the editable
  build of this tree; until the rename reaches a btclib release it
  answers with 0.7.1.3 from PyPI instead, installed beside it. It
  collides with nothing — the import package was renamed too — and costs
  the benchmark nothing, whose btclib rows run with dispatch off. The
  comment in `pyproject.toml` says so where the group is declared.
- **Two things a maintainer has to do outside this tree**, and the first
  one blocks the release: the trusted publisher is registered per project
  name, so PyPI and TestPyPI each need a *pending* publisher for the new
  name, or the release run reaches the token exchange and stops at
  `invalid-publisher` having built the whole matrix. RELEASING.md's
  one-time setup section now opens with that. The second is the Read the
  Docs project behind the new slug, which the badge and the
  `documentation` url already point at.
- **`published` will be red until 0.8.0 is out.** It installs what PyPI
  serves under the name this tree declares, and PyPI serves nothing under
  the new one yet. It is a sentinel, named by no branch rule, and the
  release is what turns it green.

### The release path

- **The release tag is signed.** `git tag v0.7.1` made a lightweight tag:
  a name pointing at a commit, with no signature, no tagger and no date of
  its own. That is the wrong shape for the one ref a release is identified
  by — the PEP 740 attestation binds to it, the GitHub release is created
  from it, and `version-check` refuses a tree that does not match it — so
  it is the thing most worth being able to attest, and a lightweight tag
  cannot be attested at all. `git tag -s -m`, with `git tag -v` before the
  push rather than after, the push being what starts the workflow acting
  on it. libsecp256k1 signs its own release tags and documents verifying
  them in `secp256k1/README.md`, so this is the vendored library's
  standard applied to the wrapper.
- **`-s` explicitly, not `tag.gpgsign`.** The setting belongs in a git
  config, where this document cannot show it; the command here is the
  instruction, and it has to be right on a machine whose config nobody
  has checked. `-m` comes with it: signing implies annotating, and an
  annotated tag without a message opens an editor, which a release step
  must not do.
- Checked rather than assumed: nothing in `release.yml` reads the tag as
  anything but `github.ref_name`, which is the same for a lightweight and
  an annotated tag. The one `refs/tags/...^{}` in that file dereferences
  *bitcoin-core*'s tags, not this repository's.
- **Squash is the only merge method the repository enables**, for a release
  pull request and every other one. The merge commit was refused by
  `main`'s required linear history already, so turning it off takes away a
  button that could not have worked; the rebase merge could have, and what
  it would have done is replay a branch's commits onto a trunk where one
  change is one commit. What a single method takes away is the dropdown:
  GitHub preselects whichever was used last and the dialog that switches
  auto-merge on carries the same one, so the answer could be given hours
  before anything merged, by whoever switched it on, with nothing asking
  again -- which is what REPOSITORY.md's auto-merge section warned about
  and now records as gone. `btclib` and `bitcoin-core-rpc` carry the same
  setting and the same prose.

### The wrapped library

- **libsecp256k1 moves from 0.7.1 (1a53f49) to 0.8.0 (6e2c8bc)**, and the
  package version with it, the two tracking each other by the rule in the
  README's Versioning section. The submodule bump is what decides that
  number, so it is what carries it: `pyproject.toml`, this file and
  HISTORY.md all say 0.8.0, and the fourth-number placeholder 0.7.1.4 that
  was open is gone rather than released — nothing had shipped under it.
- **The symbols upstream removed were not used here.** Checked rather
  than assumed: `secp256k1_context_no_precomp` and the
  `secp256k1_schnorrsig_sign` alias appear nowhere in the package, the
  stubs or the tests, `ssa` having always called `sign32` and
  `sign_custom`. The macro `SECP256K1_GNUC_PREREQ` is also gone from the
  headers, which matters here only in that the headers are preprocessed
  into the cffi definitions: `gcc -E` expands what it finds, and it no
  longer finds that.
- **`ellswift.xdh`'s refusal of an out-of-range key is upstream's**, and
  the suite did not have to change for it. The wrapper already raised
  `ValueError("invalid private key")` on a zero return, and the docstring
  already said a key that is not a valid scalar raises; what changed is
  which keys libsecp256k1 calls invalid.

### What the boundary answers

- **A memoryview of items wider than an octet is refused.** `octets` takes
  the three types that state a value and a width, and a memoryview states
  its width in *items*: `memoryview(array("I", [1, 2, 3, 4, 5, 6, 7, 8]))`
  is eight of them, and the 32 octets `bytes` reads underneath them passed
  the size check as a private key nobody wrote — one that a big endian
  build of the same program would have read differently. It is the one
  shape in which the argument for converting rather than refusing does not
  hold, so it raises `TypeError` naming what it is, and `.cast("B")` is how
  a caller says the octets are what they meant. Nothing else about the
  shape is asked: where the items are octets, `bytes` answers the ones the
  view logically holds, through a stride and over every dimension, so the
  length checked is the length libsecp256k1 will read. mypy cannot see any
  of this — `memoryview` is the annotated type whatever its items are —
  which is why the check is at run time, like the `bool` one beside it

### Silent Payments

- **`silentpayments` wraps BIP352**, the module libsecp256k1 0.8.0 adds,
  through five functions rather than the seven entry points it has: the
  label parse and serialize are not API of their own, a label being 33
  bytes on the way in and out like every other key here. The build asks
  for `SECP256K1_ENABLE_MODULE_SILENTPAYMENTS` explicitly and concatenates
  `secp256k1_silentpayments.h` after `secp256k1_extrakeys.h`, whose types
  it needs — the same ordering constraint musig already had.
- **The prevouts summary crosses as opaque bytes.** libsecp256k1 gives no
  parser or serializer for it, guaranteeing only that it is a fixed size
  and safe to copy, so the binding returns the bytes of the struct and
  writes them back into one of the same size. Its length is therefore the
  only thing checkable about it, and `SUMMARY_SIZE` is asked of the struct
  with `ffi.sizeof` rather than written down, so a libsecp256k1 that
  changes it changes this too.
- **The label lookup is a python callback, and the ECDH hash is still
  not.** The two look alike and are not: the ECDH hash callback would put
  python in the middle of a computation that has an entry point of its own
  (`keys.pubkey_tweak_mul` is the shared point), where a labeled output
  cannot be recognized at all without a lookup only the caller can answer.
  So `scan_outputs` takes the label cache as a mapping and calls back into
  it. Every tweak is copied into a buffer this package owns *before* the
  scan starts, because the pointer the callback returns has to stay valid
  after it returns; and the callback body is a `dict.get` over keys already
  normalized, because cffi has nowhere to put an exception raised inside a
  callback — it prints the traceback and returns a default, which for a
  lookup means "no label", indistinguishable from having worked.
- **`ffi.addressof` joins the stub.** A found output carries its x-only
  public key and its label by value, and each has to reach its own
  serializer as a pointer.
- **The secrets are taken back.** A found output holds the tweak that
  spends it, the sender's keypairs and secret keys hold private keys, and
  the recipient's label cache holds the tweak of every label: all are
  wiped, and each collection is filled *inside* the `try` whose `finally`
  wipes it, an entry later in it being able to raise between them. The
  cache is filled entry by entry for that reason and not built by a
  comprehension, which drops the buffers it already made along with the
  exception — a malformed second label left the first one's tweak in
  memory this package had stopped pointing at.

### Mutation testing

- **A session over the new module found three mutants no test killed**,
  and the three are in tests/ now. The scope needed no change —
  `module-path` is the package, so a module added to it is in scope — and
  what the session cost was worth having:
    - `0 <= m < 2**32` mutated to `0 <= m != 2**32` survived a test that
    drove *both ends* of the bound. `-1` fails the first comparison and
    `2**32` fails the second, so both still raise; the one input that
    tells `<` from `!=` is a value above the bound, and `2**32 + 1` is now
    in the parametrization with the reason written beside it.
    - the two `finally` loops that wipe a secret survived being turned into
    `for buffer in []`, which is a new shape here: every other wipe in the
    package is one statement about one buffer, and these are the first
    over a list. The buffers are locals, invisible from any answer, so
    what kills the mutant is a spy on `wipe` — recording each buffer and
    wiping it for real, then asserting one per secret the call was given
    and every one of them zeroed. The sender's refusal path is asserted
    too: an invalid key later in the list has to leave the ones before it
    wiped, which is why both lists are built inside the `try`.
- **Run it with the filter, or read 110 survivors that mean nothing.**
  `cr-filter-operators` between `init` and `exec` is a step of the
  workflow and not of the toml, so a hand-run session that skips it
  reports every `bytes | int` annotation mutant as a survivor — 110 of
  113 on the first pass here. With it: 94 executed, **0 survived**, 110
  skipped.

### External vectors

- **`tests/bip352_send_and_receive_test_vectors.json`**, vendored from
  `bitcoin/bips` and byte-identical to the blob libsecp256k1 vendors
  itself, drives both directions of every case. Two things it taught,
  both of them assumptions this change made and had to drop:
    - the published `outputs` of a sending case are **alternative output
    sets, not orderings of one**. Where several recipients share a scan
    public key, which of them gets k = 0 is not determined, and each
    assignment gives different keys; comparing with the first entry
    passes 26 cases and fails 15 and 17. What is asserted is that the set
    produced is one of the sets accepted.
    - an input's public key cannot be matched to it by containment alone.
    Case 22's third input is a bare multisig whose redeem script names the
    key of the *first* input, so a key already claimed gets claimed twice
    and the sum comes out wrong. The keys are consumed in order instead,
    which is the order the file publishes them in.
- **The eligibility rules are not reimplemented.** BIP352 states them
  over scripts — a bare multisig, an uncompressed key, a NUMS-point script
  path — and reading scripts is what this package does not do. The vectors
  publish the extracted keys of exactly the eligible inputs, so the test
  walks those and the inputs in step; the one script question left is
  whether a prevout is P2TR, which is what decides between the two key
  arguments and cannot be read off anything else.
- **The three failure cases assert their own message.** No eligible input
  is refused here (`at least one private key`), input keys summing to zero
  is refused by libsecp256k1 (`silent payment output creation failed`),
  and on the recipient's side both are `prevouts_summary` refusing to make
  one — keyed on the vector's own published null `shared_secret`, which is
  what distinguishes them from the case whose scan simply finds nothing.

### CI

- **`version-check` refuses a tag whose release notes are still titled
  "work in progress".** The check it replaces asked only that
  `HISTORY.md` had a section for the tag, and
  `## v0.8.0 (work in progress, not released yet)` *is* a section for the
  tag: it matches `github-release`'s heading regex too, the tag being
  followed by a space, so a forgotten step 2 of RELEASING.md would have
  published the release notes with the five words still on them and
  nothing would have said a word. Measured on this very tree before the
  retitle, where the old check passed and the new one fails on
  `HISTORY.md:8`. It now asks three things of `HISTORY.md` **and**
  `CHANGELOG.md` — a section for the tag, a heading carrying the tag and
  nothing else, and a body that is not empty — and it is btclib's and
  bitcoin-core-rpc's step verbatim, so the three repositories refuse the
  same tag for the same three reasons. The string comparison rather than
  a regex is what keeps `v0.8.0` from matching `## v0.8.0.1`, which here
  is the neighbouring heading rather than a hypothetical: the fourth
  number a release opens as its placeholder. Release-only, like the tag
  comparison beside it: a rehearsal is what runs *before* the retitle.
- **The sdist attached to a GitHub release carries provenance** (#97),
  where only the copy on PyPI did: the publish job generates a PEP 740
  attestation for what it uploads to the index, and the byte-identical
  file on the releases page carried nothing, so whoever pinned to a
  release asset url or mirrored the page had no way to check where it
  came from. `release.yml` gains an `attest` job — `actions/attest`, one
  SLSA build provenance statement, signed with a short-lived Sigstore
  certificate — and `gh attestation verify <file> --repo
  btclib-org/btclib-libsecp256k1 --signer-workflow …` is what checks it,
  the last flag being what makes the answer name a workflow rather than
  accept any attestation this repository has. The signed bundle is
  attached to the release too, as `<tag>.attestation.jsonl`, so
  `--bundle` verifies the same signature without asking the attestations
  API for it. The digest is the index's own, the job downloading the
  `sdist` artifact rather than rebuilding it. The wheels are not signed
  a second time: they are attached to no release, so their only public
  copy is the one PyPI already attests. A job of its own and not two more
  permissions on `github-release`: `id-token: write` and `attestations:
  write` stay off the job that writes releases, and further off the
  matrix that compiles the vendored library. It runs after whichever
  publish job ran, so a dispatch from an arbitrary branch signs nothing
  an environment approval did not let through — and the TestPyPI
  rehearsal exercises it, which on the release path would otherwise
  happen for the first time after PyPI has the files and the tag can no
  longer be moved. `github-release` names both `publish-pypi` and
  `attest` in `needs`: naming `attest` alone would let a dispatch cut a
  release, that job running in a rehearsal too. Not the
  `attest-build-provenance` wrapper the issue proposed, which is a
  composite whose only step is `actions/attest` pinned there to v4.2.1 —
  calling the action directly is what leaves the version that signs
  pinned here.
- **The macOS suite cells left the merge gate for `macos.yml`.** Over six
  pull request runs of `test.yml`, ninety-eight jobs each and thirty-five of
  them on the two macOS images, a macOS job waited 20.8 and 19.0 minutes on
  average for a runner against 2.1 to 2.6 elsewhere — and the wait grows
  with the number of cells asking at once, so in the slowest of the six the
  thirty-one macOS suite cells took the last thirty places before the
  aggregate, their queue rising from 16.7 to 70.2 minutes and the run taking
  95 minutes for 105 minutes of work. The command that re-derives all of it
  is in `test.yml`'s header, next to the matrices those cells left. What
  moved is the suite; the macOS
  *wheel builds* stay, because the release publishes the artifacts of that
  run and the same measurement clears them — they finished at 24.6 minutes
  against the 23.5 of the ubuntu-latest build beside them. Four macOS jobs
  queue, thirty-one contend. `macos.yml` runs the two images over every
  interpreter `test.yml` ran there, half an hour before `latest.yml` on the
  same morning, so the pair reads as a difference: red in both is the
  platform, red in `latest` alone is the upgrade. It builds from the tree
  twice per cell, static and then dynamic, rather than rebuilding the
  wheels the cells used to install — ten minutes of `cibuildwheel` per
  image, and artifact names a release must not confuse with `test.yml`'s.
  It gates nothing, so a macOS regression can sit on `main` for a week;
  `release.yml` calls it, so it cannot be published.
- **The documentation build is `docs.yml`, not the second job of
  `lint.yml`.** A failed docs build and a failed hook are two different
  verdicts about two different things, and one badge and one line in the
  checks list each is what says so — the badge being a `docs` one added
  to the second README row, beside `test` and `lint`, where the row
  already ends with what read the docs makes of the same source. The
  job's display name is unchanged, which is what let it move without
  touching the branch rule: a required context is matched by name, not
  by the workflow that reported it.
- **Every job is named for the question it answers, and the aggregate is
  `test: every job passed`.** `Coverage` said which job it was rather than
  what it gates; the two suite matrices were *both* named
  `Test <version> on <os>`, so every run produced pairs of check runs with
  one name between them, which is the ambiguity a branch rule cannot see
  past — the linkage is in the name now. Renaming the aggregate renames a
  required check, the one change a pull request cannot make on its own:
  REPOSITORY.md carries the `PATCH` that moves the rule first.
- **`release.yml` calls every gate, and the published sentinel after
  itself.** It called `lint` and `test`; `docs` and `macos` are gates it
  was not waiting for, and `published` answers, at the one moment its
  answer changes, whether what was just uploaded can be installed. That
  last one waits for the index to serve the version the tag names before
  installing anything, so it cannot report a pass for the release before
  this one. A call rather than a `workflow_run` trigger, which zizmor rates
  dangerous and rightly: that one runs the default branch's copy of a
  workflow with a token nobody reviewed. The workflow also has a
  concurrency group at last, and it is the one here that must not cancel:
  a version is consumed by the upload that carries it.
- **`published.yml` is monthly, where it was weekly.** What it watches is
  external rot, which nothing in this repository moves, so a week was a
  sample rate without a reason — and the release now asks immediately,
  which is what the weekly was standing in for.
- **The workflows no longer name `master` and `dev`.** Neither branch
  exists. Two of those references were not merely stale: `branches:
  [master]` meant no push to `main` ran the gate at all, and the release
  workflow's ancestry check runs `git merge-base --is-ancestor
  "$GITHUB_SHA" origin/master`, which fails on a ref that is gone — the
  next tag would have been stopped by it. The draft exception that let the
  release pull request through (`github.base_ref == 'master'`) can never be
  true again and is gone with them.
- **CodeQL is `codeql.yml`, not code scanning's default setup.** It was the
  one required check on `main` whose definition no diff could review: a
  repository setting, so the languages it scanned, the queries it ran and
  the day it ran them were readable only through
  `gh api repos/{owner}/{repo}/code-scanning/default-setup`. The workflow
  reproduces exactly what that reported — `actions` and `python`, the
  `default` query suite, weekly — one job per language so a failure names
  the language, `github/codeql-action` pinned to a commit SHA like every
  other action here, and `security-events: write` declared on that job
  alone. The category is spelled as the setting spelled it,
  `/language:<language>`, which is what carries the existing alerts across:
  an upload under a new category closes every one of them as fixed and
  opens a copy. The aggregate is `codeql: every job passed`, for the reason
  `test.yml`'s own is: a branch rule must name an outcome and not a matrix
  cell. Turning the setting off and moving the rule are two steps only a
  maintainer can take, in an order REPOSITORY.md gives — while default
  setup is enabled the workflow still runs and the SARIF is refused at
  processing, so the jobs are red rather than absent, and the rule has to
  stop naming a context nothing produces before it can name the one this
  file does. That exchange has been made; what outlives it is a generated
  `dynamic/github-code-scanning/codeql` workflow uploading *code quality*
  results, which is a separate setting the `code-scanning` endpoint does
  not report.

### The gate

- **The submodule pin is checked on every commit, and its signature
  monthly** (#126). `version-check` in `release.yml` resolved the release
  `README.md` names against upstream and refused to publish a tree pinned
  to anything else — the last gate before publication, and until now the
  only one, so a bump reaching `main` waited for a release to be compared
  with the version the prose claimed. That is the window in which the
  changelog and the release notes about that version get written. The
  check now exists twice more, split by what each half needs:
  `.github/scripts/check_submodule_pin.py` resolves the tag in the
  vendored clone's own refs, which is offline and therefore a hook —
  `submodule-pin`, on every commit, because a `files` pattern cannot
  reach it: pre-commit drops from its file list everything that is not a
  regular file, and a submodule is a directory, so a hook filtered on
  `secp256k1` would never have run on the one commit it is for. Measured
  rather than assumed, by staging a bump and asking for the hook by name.
  GitHub's `paths:` filter is other code and does see the gitlink, which
  is what the sentinel keys on; and a `pin` job in
  `vendored-vectors.yml` fetches the tag object from upstream and runs
  `git tag -v` against the three maintainer fingerprints recorded from
  libsecp256k1's own `SECURITY.md`, which nothing here had ever verified.
  That half is a sentinel because a keyserver that is down is nothing a
  pull request did, and it runs on the pull request that moves the pin
  regardless: a gitlink is a path like any other in a `paths` filter, as
  #106 shows, having `secp256k1` among its changed files. It opens no
  issue where its neighbour does, and the reason is the subject: a vector
  file drifts because upstream edits it in place, while a pin moves only
  in a commit of this repository. `lint.yml` checks out the submodule
  unshallow for the hook, tags being what a `--depth=1` clone has none of
- **`submodule-pin` is skipped on pre-commit.ci**, which is the second
  entry that list has ever had and was found the way the first one's
  reason would have been: the pull request adding the hook went red
  there, with the hook's own message, while every other hook passed
  (#130). Skipping was the cheap answer, and #131 asked for the other
  one — `submodules: true`, a documented key of the `ci:` block — so it
  was tried rather than argued about (#132). With it the clone arrives
  and the hook fails all the same: **the vendored clone is shallow and
  carries no `v0.8.0` tag**, and there is no `fetch-depth` key to ask
  that service for. So the key bought a clone nothing can use and is not
  kept, the skip stays, and REPOSITORY.md now records the gap beside the
  checks the branch rule deliberately leaves out — one third-party check
  this repository cannot make agree with `lint.yml`. What it costs is one
  of the hook's two runners: the required one, `Lint and type-check`,
  checks the submodule out with `fetch-depth: 0` precisely so it has what
  the hook needs, and a developer's own commit has it too
- **The hook says which of the three states a clone without the tag is
  in**: not checked out, checked out but shallow, or a full clone that
  simply lacks the tag — one sentence each, each naming what would change
  it. One message covered all three and told them apart for nobody, which
  is fine for a developer, who has one of them and knows which, and not
  fine for a checkout somebody else makes, where which one it is *is* the
  finding. That is exactly how the pre-commit.ci answer above stopped
  being an inference: the second run of #132 came back naming `shallow`
- **Every required check names the app that produces it.** `test: every
  job passed` and `codeql: every job passed` carried `app_id: 15368` and
  the other two carried none, which REPOSITORY.md recorded as a rule that
  was not uniform in this. An unbound context is satisfied by *any* app
  reporting a check run of that name, so anything installed on the
  organization with `checks: write` could turn `Lint and type-check` green
  with no workflow having run. Both are Actions checks -- the check-runs
  endpoint answers 15368 for each -- so the binding changes nothing a run
  can see, and closes that. The `PATCH` this file already documented is
  what applied it; btclib and bitcoin-core-rpc are bound the same way, so
  the three now read `app_id: 15368` for every context they require
- **`pinned-rev` refuses a `rev` that does not name a released version.**
  Nothing but `pre-commit autoupdate` writes a `rev`, and it offers
  whatever tag the remote's HEAD carries: twice that was not a release —
  `v1`, a floating major tag its owner moves under the pin, and `5.1b1`, a
  prerelease with no `5.1` behind it — and both were merged before anybody
  read the diff, so the review is not the check. pre-commit says as much
  itself for the moving tag, a `[WARNING]` about a mutable reference, and a
  warning is not an exit code. A `pygrep` hook, so the pattern is the whole
  hook, and it was verified in both directions: it names no `rev` this file
  holds, and it names those two by line when they are put back.

- **The bytes-like sweep grew a mapping and a tuple.** `retyped` now
  descends into both, which is what `create_outputs`' pairs of keys and
  `scan_outputs`' label cache need. A mapping has its values retyped and
  its keys left alone, and that is the signature rather than the test
  being lenient: `Mapping` is invariant in its key type, and neither a
  `bytearray` nor a `memoryview` is hashable, so `labels` is declared
  `Mapping[bytes, BytesLike]` — bytes is the only one of the three a
  mapping key can be. mypy is what said so.
- **`silentpayments` is in `MODULES`**, so `test_the_sweep_is_whole` holds
  the new entry points to the sweep the way it holds every other.
- **Both detect-secrets baselines were regenerated.** The tree's picked up
  only line-number shifts; the vendored one picked up 68 `Secret Keyword`
  findings, every one of them a `private_key` or `priv_key` field of the
  new BIP352 file, which is what a published vector file is made of.

### Documentation

- **Three statements that were not true, found by an audit of the package
  rather than by a failure.** Each is the kind this repository's own rule
  is about, a comment saying *why* and the why having stopped being the
  reason: `context._randomize` invited a caller to re-randomize "whenever
  it wants fresh blinding", which is the one call that would take the
  README's thread-safety guarantee away — libsecp256k1 requires exclusive
  access to a context to mutate one, so the invitation now carries the
  condition, and the README says the same where a user reads it.
  `silentpayments._array` explained its NULL by "cffi will not make an
  array of length zero", which cffi does quite happily, `keys.pubkey_sort`
  passing one for an empty sequence; the real reason is libsecp256k1's own
  `ARG_CHECK`, and the same wrong reason was in
  `test_scanning_refuses_an_empty_output_list`. CLAUDE.md said the
  sentinel crons "are on different mornings" while the table under it
  showed two on Wednesday and two on the 1st — corrected when the
  cadences were, and the sentence left behind.
- **The prose stops naming `dev` and `master`, which no longer exist.**
  The workflows were corrected when the branches went; the files that
  describe how this repository is worked on were not, so RELEASING.md
  still told a maintainer to merge `dev` into `master` and to read
  `gh run list --commit "$(git rev-parse origin/master)"` — a command
  that now fails on a ref that is gone, in the one file a release is
  executed from. Two of its twelve steps described work that cannot be
  done and are gone: realigning `dev` onto `master` after a release, and
  opening the draft release pull request between the two branches, whose
  job — somewhere to describe the cycle as it lands — the open sections
  of `CHANGELOG.md` and `HISTORY.md` already do. What replaced the
  release merge is stated rather than implied: the release pull request
  is an ordinary one against `main`, and the ninety-two-commit squash of
  0.7.1 cannot recur, every change now reaching `main` in its own pull
  request as it lands. CONTRIBUTING.md, CLAUDE.md, REPOSITORY.md and the
  pull request template follow, and REPOSITORY.md's branch protection
  section describes `main` — where it said "the three checks", the rule
  has named four since `docs` became one of them.
- **Seven README links, the `changelog` metadata url and the Sphinx
  source links pointed at `blob/master`.** They resolve, GitHub
  redirecting a renamed branch, so nothing was broken and the `links`
  sentinel stayed green; the `changelog` one is what an index puts behind
  "Changelog" on the project page, and `docs/source/conf.py` builds every
  "source" link on Read the Docs from the same string. The pre-commit.ci
  badge was the one that had stopped meaning anything: pinned to
  `master.svg`, it answers `passed` for a branch that has not existed
  since the rename and can never turn red again — measured against a
  branch name that never existed, which answers `unknown`.
- **This file's own preamble says where it starts, not what it holds.**
  "Only v0.7.1.2 is here" was true for exactly one release, and v0.7.1.3
  landing under it made it false without anything failing; every release
  after would have done the same. Where the file starts is the fact it
  was reaching for, and that one does not move.
- **Read the docs builds on the interpreter `docs.yml` builds on**, 3.14,
  which is what `.python-version` says. These docs are built twice, once
  for the website and once as a required check, and two interpreters make
  those two different questions -- a docstring that renders under one and
  fails `-W` under the other is found after the merge, on the service
  whose failure is not a check on the pull request. The file already said
  it matches btclib's, and btclib's moved.
- **Two documented cadences the schedules contradicted.** CLAUDE.md said
  "Dependabot is monthly here on purpose", where
  `.github/dependabot.yml` has declared `interval: weekly` with
  `day: thursday` on all three ecosystems since it was moved there to
  match btclib; and RELEASING.md's step 7 said `published` "runs weekly
  on its own", where its cron is `23 6 1 * *` and this file's own v0.8.0
  entry records the move from weekly to monthly. Neither is a claim
  anything checks, which is why both survived the change they describe.
  The CLAUDE.md sentence was making an argument as well as a statement —
  that `latest` covers for an infrequent Dependabot — and the argument
  was the wrong way round: `latest` runs on the Wednesday *before*
  Dependabot proposes on the Thursday, so what it buys is a diff whose
  result is already known. What it covers that nothing else does is
  `[build-system] requires`, resolved at build time and pinned by no
  lock file, so Dependabot never moves it at any interval.

### Packaging metadata

- **`.gitignore` matches a versioned environment, and the sdist stops
  shipping one.** `.venv`, `venv/` and `venv*/` between them do not
  match `.venv-3.10`, which is what `UV_PROJECT_ENVIRONMENT=.venv-3.10
  uv run --python 3.10 --no-cache pytest` creates — the way of trying
  another interpreter that keeps the default environment rather than
  replacing it, and CONTRIBUTING.md now gives it beside the run that
  replaces one. Nothing downstream caught the leftover: uv writes a
  `.gitignore` holding `*` inside the environment it creates, so `git
  status` was clean, while hatchling builds the sdist from the root file
  alone and shipped the directory — 377 paths against 297 and 13,132,264
  bytes against 3,076,714, measured on `38ee75b` with the environment
  present either way (`tar -tzf dist/*.tar.gz | wc -l`), the rest of the
  archive identical. The totals move with the vendored library and the
  difference does not: it is the environment's `bin` and the four files
  beside it, `lib/` being matched already by the Distribution section
  above. `twine check --strict` passed on it; `pyroma --min 10` raised
  `tarfile.AbsoluteLinkError` on `.venv-3.10/bin/python`, the tarfile
  data filter refusing a link to an absolute path, so the packaging gate
  failed on one symlink rather than on the stray paths, which are the
  difference between those two counts. `check-manifest` names every one
  of them — it compares the sdist with what git tracks — and is not in
  the `check` group; the pattern states the same fact where a file
  becomes invisible rather than where an archive is built. It is
  `.venv*/`, in place of the `.venv` beside `venv*/`: a directory of
  that exact name is matched by it, and by the stock `# Environments`
  block above.

## v0.7.1.3

### Documentation

- **The README badges are the ones that can turn red**, in the order the
  reader asks for them: version, downloads, development status, license
  and supported interpreters on the first line; test, lint, pre-commit.ci
  and the documentation build on the second; the repository and the Slack
  channel on the third, "where is the code" and "where do I ask" being the
  two questions a reader has once the first two lines have answered
  theirs. That third line is where the repository link was already, a
  sentence between two horizontal rules of its own; as a badge beside the
  others it needs neither rule, and the plain-text link that read "Browse
  GitHub Code Repository" now names the repository it opens. The badges
  that report no state — `uv`, ruff, mypy, markdownlint-cli2 and
  `pre-commit enabled` — name a choice rather than measure anything, so
  they open CONTRIBUTING.md, which is the file that says how each choice
  is enforced and what the command for it is, rather than sitting inside
  its "Building and testing" section. ruff is three of them, its
  formatter, its linter and its docstring rules being three gates with
  three documentation pages and three ways to fail, where one badge
  announced them as one; `pre-commit` closes that run because it is what
  runs the others, and the repository and Slack badges close the line, a
  contributor wanting both. The alternative text says what each badge
  means — "PyPI version", "supported Python versions", "test workflow
  status" — rather than naming the site that serves the image: it is the
  accessible name of the link, and a flat list of badges has nothing else
  to carry the meaning. btclib and bitcoin-core-rpc carry the same three
  lines and the same CONTRIBUTING.md run, which is what makes the three
  comparable; the badge sets differ only where the projects do, this one
  having no calendar version to declare.
- **`pubkey_from_prvkey`'s two libsecp256k1 calls are two calls for a
  stated reason** (#89). The Design section claimed every function is one
  libsecp256k1 call, without saying that a function returning a key or a
  signature is two: libsecp256k1 hands one back as an opaque object, and
  only a second call serializes it into bytes. `pubkey_from_prvkey` names
  its two — `secp256k1_ec_pubkey_create`, `secp256k1_ec_pubkey_serialize`
  — as the shape every other producer of a key or a signature shares.
- **The MuSig2 section names what already guards a reused nonce** (#91).
  It said the signing state "already lives" in btclib without naming what
  lives there, which read as an open gap rather than a settled fact.
  `btclib.ecc.musig2.sign` and `btclib.psbt.musig2.partial_sign` are named,
  both zeroing the secret nonce on use, which refuses reuse deterministically
  before a second signature exists.

### Import diagnostics

- **A dynamic wheel's `ImportError` says what it tried, and why each
  attempt failed** (#90). `_load_lib` searches the shared object shipped
  beside a dynamic (cffi ABI) build, and silently dropped every rejected
  candidate's `OSError` while doing it — a wheel repaired by `auditwheel`
  or `delocate` can ship more than one match, only one of which is the
  library, so a directory holding a wrong-platform library alongside the
  right one surfaced only "no loadable shared libsecp256k1 found", with
  nothing said about what was there or why it did not load. Each rejected
  candidate's name and error are now kept, joined into the message when
  none loads, and the last one chained as the exception's cause; a
  directory with no matching candidate at all still gets the shorter
  message, that case never having had one to blame. Closes #88.

### Mutation testing

- **A session run ahead of this release, `_load_lib` having changed
  since 0.7.1.2, found one survivor shape on `rejected[-1]`** — six
  mutants of the same index, all reporting `TestOutcome.SURVIVED`,
  because `test_load_lib_unloadable_candidate` checked only
  `isinstance(exc_info.value.__cause__, OSError)`, true of any candidate
  chained, and because with two rejected candidates `rejected[-1]` and
  `rejected[1]` name the same element regardless, one mutant unkillable
  by any assertion at that length. A third candidate, and an assertion
  that the last name in the `ImportError`'s own message is the one
  `__cause__` reports, killed all six: `path.glob`'s order being
  undocumented, the test pins it with `sorted`, the same way this
  project fixes what a test cannot otherwise hold constant about an
  external call. The session that measured that: 667 jobs, 385 skipped
  by the operator filter, 0 survivors of the 282 that ran.

### The gate

- **The copyright-notice hook is retired for ruff's own `CPY001`** (#85).
  `leoll2/copyright_notice_precommit` existed for exactly one check — a
  missing or altered notice at the top of a source file — that
  `flake8-copyright` already does, selectable under this project's
  existing `explicit-preview-rules` gate rather than needing anything new
  turned on: one less repo to pin, one less hook environment for
  pre-commit(.ci) to install. It also needs no `files:` pattern of its
  own the way the retired hook did, widened from `\.py$` to `\.pyi?$` only
  after `stubs/_btclib_libsecp256k1.pyi` kept a pre-MIT header for as long
  as the narrower pattern missed it — ruff lints `.pyi` files by default.
  And it checks whatever files it is given the same way regardless of who
  is asking, unlike the retired hook, which intersected the files
  pre-commit handed it with newly *added* staged files unless given
  `--enforce-all`, silently checking nothing under `pre-commit run
  --all-files` — the exact invocation the lint workflow runs, and the
  incident this file already records above. `notice-rgx` is COPYRIGHT's
  text as one anchored regex rather than a substring search over the whole
  file, the design rationale moving to `pyproject.toml` beside it.

### Dependencies

- **`cryptography` moves to 50.0.0, closing CVE-2026-69247** (#92).
  Dependabot alert #9 (GHSA-g6cj-pr64-35w5, high) flagged 49.0.0, pulled in
  transitively on Linux via `twine`'s `keyring` → `secretstorage`
  dependency, as inside the range vulnerable to a PKCS#7 `EnvelopedData`
  decryption oracle. Neither this package nor `twine` decrypts PKCS#7, so
  the oracle was unreachable here, but there was no reason to stay in the
  vulnerable range. `secretstorage` only requires `cryptography>=2.0`, so
  no other package needed to move with it.
- **Every other locked dependency moves to its latest compatible
  version** (#93): `uv lock --upgrade`, ahead of the `latest` sentinel's
  own schedule rather than waiting for it. Notable moves: `btclib`
  2023.7.12 → 2026.8.7, pulling in a new transitive `bitcoin-core-rpc`
  dependency (both `bench`-group only, no part of `test`, `lint`, `check`
  or the default group), `ruff` 0.16.0 → 0.16.2, `cibuildwheel` → 4.2.0,
  plus patch bumps to `coverage`, `filelock`, `packaging`, `platformdirs`,
  `setuptools` and `virtualenv` among others. No `pyproject.toml` change.

### Packaging metadata

- **`keywords` names what this package wraps and what it reaches**, where
  it said `bitcoin` and `libsecp256k1` and left the searchable name of the
  curve out along with every wrapped module: `secp256k1`, `cryptography`,
  `python-bindings`, `cffi`, `ecdsa`, `schnorr`, `bip340`, `ecdh`,
  `ellswift`, `public-key-recovery` and `rfc-6979`, which is the nonce
  `dsa.sign` uses. `RFC-6979` is spelled lowercase, as a GitHub topic has
  to be: the list is the repository's topics in the same order, and one
  spelling across the two is what lets them be compared. The order is by
  relevance rather than alphabetical, PyPI showing keywords as the metadata
  gives them and GitHub sorting its own.
- **`musig2` and `bip324` are in that list, and neither is a wrapped
  module.** The vendored library is built with
  `SECP256K1_ENABLE_MODULE_MUSIG` and `secp256k1_musig.h` is among the
  headers the cdef is made of, so all of `secp256k1_musig_nonce_gen`,
  `_nonce_agg`, `_nonce_process`, `_partial_sign` and their neighbours are
  reachable through the `lib` this package exposes -- what MuSig2 has no
  module for is the session its two rounds need, which is the reason
  README's Design section gives for leaving one out. `bip324` is the
  `ellswift` module beside it: the encoding and the x-only ECDH that BIP's
  handshake needs of its keys, and not its transport, which is a cipher and
  a framing layer this package has no part of. The comment beside the list
  states both limits, so a keyword found on PyPI leads to what is here
  rather than to what a reader would assume from the name.
  `elliptic-curves` is the one candidate left out: this is one curve, and
  `secp256k1` names it.
- **the repository now carries those entries as its topics**, where it
  carried none: the pull request above could write the list and not apply
  it, the repository settings living outside the tree. REPOSITORY.md has
  them, as it has every other setting nothing in the tree can recover, and
  with the command that diffs the two lists and exits nonzero when they
  have drifted apart — sorted on both sides, GitHub returning an order of
  its own.
- **this file relaxes MD024 (no-duplicate-heading) for itself**, a group
  heading repeating under every release that has an entry in that group:
  the rule reads that repeat as the accident it usually is, and
  `siblings_only` is what tells the two apart, a duplicate under one
  release heading still failing. It is a `markdownlint-configure-file`
  comment here rather than a line in `.markdownlint.jsonc`, which is
  shared with btclib and bitcoin-core-rpc and says itself that a rule one
  file needs belongs to that file; bitcoin-core-rpc's CHANGELOG.md carries
  the same comment.

## v0.7.1.2

Grouped, and the order runs from what a caller sees to what only
maintainers do. The wrapped
[libsecp256k1](https://github.com/bitcoin-core/secp256k1/releases/tag/v0.7.1)
is the same 0.7.1 (1a53f49). What the public API gained is one function
and two `compressed` flags; what it lost is `recovery.COMPRESSED` and
`ellswift.COMPRESSED`, two copies of a flag macro that `keys.COMPRESSED`
still declares — the one removal here, and the one entry a caller
importing either has to act on. What it also gained is a wider door:
every argument that takes octets takes a `bytearray` and a `memoryview`
as well as `bytes`, which is a widening and breaks nothing. Three things
changed behaviour: the text of one error message, the class
`keys.serialize` raises for an argument no valid caller passes, and the
exception a wrong *type* meets, which is now the boundary's and names
the argument instead of cffi's a call later. Each has its entry below.
Neither file counts its entries:
`grep -c '^- '` does that, whereas a stated number is a line every open
branch has to edit.

### What the boundary answers

- **`keys.pubkey_from_prvkey` is the public key of a private key, in
  either serialization** (#41, #68). One `secp256k1_ec_pubkey_create`
  plus one `keys.serialize`, which is the shape `pubkey_negate`,
  `pubkey_tweak_add`, `pubkey_tweak_mul`, `pubkey_combine` and
  `pubkey_sort` already had — a C operation on a `secp256k1_pubkey`, then
  the serialization with its flag as an argument. Generator
  multiplication was the exception: `mult.mult_` wrote that serialize
  inline with the flag as the literal `2`, so the one producer whose
  input is a private key rather than a point was also the one that could
  not answer the compressed form `keys`' own docstring promises. Put
  structurally, the package could create a `secp256k1_pubkey` from a
  private key, and could serialize one compressed, and never let the same
  caller do both: `serialize` takes a pointer only `parse` hands out,
  that is, bytes already serialized. `mult_` is the `compressed=False`
  case of the new function now and has lost the inline serialize, the one
  duplication of `serialize` the package had, so the API gains a name
  while the code at the cffi boundary shrinks. What it saves a caller who
  had been composing it, measured per call over 2000 random keys, best of
  nine: 7.67 µs, against 7.75 for the byte slice btclib ships, 8.13 for
  `keys.serialize(keys.parse(mult_(q)))` — which pays a
  `secp256k1_ec_pubkey_parse` to undo a serialization the same library
  has just done — and 8.90 for the composition through the coordinates,
  which turns 64 bytes into two ints and re-proves on curve a point
  libsecp256k1 had just produced. Against the slice that is 0.8%, and it
  was not treated as the argument: the argument, with its alternatives,
  is in #41 — the compressed encoding stops being written outside the
  wrapper. btclib reads `sec[64]` rather than `sec[-1]` so that a 33-byte
  answer raises instead of passing off a byte of x as a parity, and keeps
  a test pinning this package's 65-byte serialization from outside it;
  making `mult_` the uncompressed case of one function is what keeps that
  contract true by construction rather than by a downstream test.
  Validated against what is published rather than against the bindings:
  the BIP340 vectors' *public key* column is the x of this call for every
  vector carrying a secret key, 1G is pinned in both forms against the
  generator of SEC 2 v.2 section 2.4.1 and 6G for the odd y no smaller
  key exhibits, and the 128-key sweep compares what libsecp256k1
  serializes with the compression `tests/test_properties.py` composes
  itself, both parities occurring across it. The README quickstart, which
  had been composing `keys.serialize(keys.parse(mult.mult_(prvkey)))` on
  the package's own front page, is the one call now.
- **The `ValueError` of a generator multiplication names a private key**
  where it said scalar, which is the one behaviour a caller can see
  change. `secp256k1_ec_pubkey_create` calls its argument a seckey and is
  what refuses anything outside `[1, n-1]`, so the message names what the
  library refused rather than what the mult module calls it; `mult_`
  answers exactly the 65 bytes it did, opening with `0x04`, and
  `tests/test_core.py` asserts the new text so that the next change to it
  is deliberate.
- **`keys.serialize` raises what libsecp256k1 reported, and takes it off
  the thread** (#73). It is the one wrapper whose argument is a
  libsecp256k1 object rather than bytes, so it is the one place where
  nothing can be checked before the call and a precondition is
  libsecp256k1's to violate: a NULL pointer, or a `secp256k1_pubkey`
  nothing has written to, reached the illegal-argument callback. What
  came back was `RuntimeError("point serialization failed")` — the class
  reserved here for what no input can provoke — while the message
  libsecp256k1 had just written stayed recorded on the thread. The next
  `context.check()` found it and raised it, and that caller is the MuSig2
  one going through `lib`: they were told `pubkey != NULL` about a call
  they never made. That is what `test_check_clears_what_it_reported`
  exists to prevent, and it was reachable from the public API.
  `serialize` calls `check()` on the failing branch now, which raises the
  message as the `ValueError` a caller's mistake is and, raising it,
  clears it; the `RuntimeError` remains for a failure that reported
  nothing. Two docstrings had claimed the case away — `check()`'s own,
  and `test_illegal_argument`'s *"which the bindings' own wrappers cannot
  do"* — and describe it instead.
- **An argument is checked for its type where it is checked for its
  length** (#73, #74), those being one question about a bare pointer.
  `len` answers for a `bytearray` and a `memoryview` as readily as for
  bytes, so both passed every size check and reached cffi, which refused
  them a call later in its own words and about a ctype — `initializer
  for ctype 'unsigned char *' must be a cdata pointer` — naming neither
  the argument nor what was wrong with it; a `float` came back as
  `object of type 'float' has no len()`; and `_scalar.scalar`, annotated
  `-> bytes`, returned the bytearray it was handed. `_scalar.octets` is
  that one check, and every size check across the eight wrapper modules
  is now that call. `keys.pubkey_sort(pubkey)` — one key where a
  sequence of them goes, which bytes being a sequence made silently
  wrong — now says `the public key must be bytes, not int`.
- **And what crosses is octets, not `bytes` alone** (#74): a `bytearray`
  and a `memoryview` are converted rather than refused, and `BytesLike`
  is what the signatures say. #73 had refused them, on the argument that
  converting would widen what every signature promises; the answer is
  that the signatures widened. They are not the leniency a short value
  is — each states a value *and* a width, so nothing has to be
  disbelieved and nothing supplied, which makes them a narrower door
  than the `int` this package has always taken, whose 32-octet width is
  the curve's rather than the caller's. And a caller who holds a secret
  in memory they can overwrite, which is the reason to want a mutable
  buffer and is what SECURITY.md now describes this package doing with
  its own, had been meeting a `TypeError` for it. The conversion is a
  copy taken at the boundary, never a pass-through, so overwriting that
  buffer cannot change what libsecp256k1 is about to read.
  `tests/test_bytes_like.py` drives every entry point taking such an
  argument with each of the three types and asserts one answer, which is
  what makes a call site that checks without assigning fail there rather
  than in a caller's code; a `test_the_sweep_is_whole` holds the list to
  what the modules export, so a function added and not swept is an
  absence that fails.
- **A `bool` is refused where a scalar goes** (#73). `isinstance(True,
  int)` is true, so `True` was the scalar 1 and `False` the scalar 0:
  `keys.prvkey_verify(False)` answered False, the correct verdict on
  zero and not distinguishable from the correct verdict on whatever was
  meant, and `keys.pubkey_from_prvkey(True)` answered the generator.
  That is what separates it from a `float` in the same place, which
  raised then and raises now — the acceptance was invisible in the
  answer, and invisible to mypy too, `bool` being a subtype of `int`.
  For the scalars alone: `recid`, `party` and the y parity are flags
  whose domain is `{0, 1}`, and a bool there is the 0 or 1 it is.
- **The libsecp256k1 buffers a secret passes through are overwritten**
  (#73). SECURITY.md records the python side as inherent, and it is: a
  `bytes` is immutable, so what a caller hands in and what is handed back
  stay until the collector gets to them. The copy in the middle is not
  that — it is memory cffi allocated and this package owns, it is
  writable, and nothing outside these wrappers sees it, so leaving a
  private key in it was an omission rather than a limit. Read out and
  zeroed now: the keys of `keys.prvkey_negate`, `prvkey_tweak_add` and
  `prvkey_tweak_mul`, the taproot signing key of
  `xonly.prvkey_tweak_add`, the shared secrets of `ecdh.shared_secret`
  and `ellswift.xdh`, and the `secp256k1_keypair` of the two BIP340
  signing calls and of the taproot tweak, wiped in a `finally` because
  `_aux_rand32` can raise between its creation and the signature. The
  length is asked of `ffi.buffer` rather than of `ffi.sizeof`: on a
  `secp256k1_keypair *` the latter answers 8, the size of the pointer,
  and wiping 8 octets would clear the first quarter of a private key and
  report success — written that way the new test fails. One copy taken
  back, not safety, and SECURITY.md says which.
- **`recovery.recover` and `ellswift.decode` answer in either
  serialization** (#73), through `keys.serialize` rather than through a
  copy of it. Both wrote the same block — a `char[33]`, a length derived
  from it, the `SECP256K1_EC_COMPRESSED` flag redeclared at the top of
  the module, and a comment pointing at `keys.serialize` for the
  reasoning, which was the argument for calling it. Each takes the
  `compressed` flag every producer in `keys` has, defaulting to the 33
  octets they always returned; reaching the uncompressed form meant
  `keys.serialize(keys.parse(...))` in the caller before. The two
  duplicated `COMPRESSED` constants go with the block, `keys.COMPRESSED`
  being the one that carries the comment explaining why a flag macro is
  written out at all.
- **Three smaller things the same audit turned up** (#73). `noncefc` was
  a typo of `noncefp`, which is what the header calls the nonce function
  pointer, in both signing modules. `ndata`, annotated `bytes | None`,
  was reassigned to `ffi.NULL` before being passed — mypy allowed it only
  because `ffi` is `Any` — and has a name of its own now, with the
  comment saying why a python nonce function is not offered: it would put
  the secret through a python object on every call from inside the
  signature. And `test_safe_abort` created a context on every run and
  never destroyed it, with the flag `769`, which is `SIGN|VERIFY`,
  deprecated since libsecp256k1 0.2 as `context.py`'s own comment says.

### The documented boundary

- **`xonly.tweak_add_check` says what it does with a tweaked key that is
  no point** (#73). Its contract promised `ValueError: if either key is
  not 32 bytes or not a valid x coordinate`. Only the internal key is
  parsed; the tweaked one is compared against the serialization of the
  recomputed point, so 32 bytes which are the x coordinate of nothing
  return False. That is the right behaviour — bytes that are no point are
  the tweak of nothing, and comparing rather than parsing is the whole of
  what this saves over recomputing the tweak — and Returns now says it,
  with Raises naming the key that really is parsed. Nothing in the gate
  could have caught it: `pydoclint` checks that a `Raises` section is
  there, not that it is true, which is the concession recorded below, and
  the suite had asserted the two keys only where both were points.
- **Every function of the package documents its arguments, its return
  value and what it raises.** What lengths are accepted, what is refused
  rather than padded, which failure is a `ValueError` and which a
  `RuntimeError`: that is the most valuable thing this package has, and
  it was prose in the README's *What the boundary checks*, several
  hundred lines away from the functions it applies to. For a package
  shipped as a compiled wheel that was the whole of it — there is no
  source beside the extension for a reader of `help()` or of an IDE
  tooltip to fall back on. The sections are Google style, which the
  `napoleon` already enabled in `docs/source/conf.py` renders, so the
  published reference gained them at the same time. `mult.mult_` and
  `mult.mult` carried the same docstring verbatim — *"Multiply the
  generator point."* — while one returns 65 uncompressed bytes and the
  other a `tuple[int, int]`; each now says which.
- **A `pydoclint` hook holds it**, over `btclib_libsecp256k1` only, with
  its configuration in `pyproject.toml` beside ruff's. It asks for an
  `Args` entry per parameter and a `Returns` section, which is what
  ruff's `D` rules cannot do: they check that a docstring exists, not
  what it says. Two settings carry their reasoning where they are set.
  `skip-checking-short-docstrings` is off, against the tool's default,
  because the default skips a docstring that is only a summary line —
  which is exactly the state this ends, so with the default the gate
  would hold nothing. `skip-checking-raises` is on, which is the one
  concession: pydoclint compares a `Raises` section with the `raise`
  statements of the *body*, and these wrappers raise mostly through what
  they call (`_scalar.scalar`, `keys.parse`, `keys.serialize`), so the
  check would force each docstring to document its own body instead of
  its contract. `Raises` is therefore written and reviewed, not gated;
  ruff's `DOC` rules have the same limitation, so the choice was not
  between tools. Verified by handing it something bad: an argument added
  to `tagged_sha256` and left undocumented is `DOC101` and `DOC103`.
- **The README opens with a Quickstart**, which did not exist: sign and
  verify, ECDSA and BIP340, for someone who has just typed
  `pip install`. It is written as doctests, so it is executed rather
  than only read.
- **Every example is executed**, by `tests/test_examples.py`, over every
  module of the *installed* package and over `README.md`. Through the
  standard library's `doctest` rather than pytest's `--doctest-modules`,
  and the reason is what this package is: `testpaths` is `tests`, and
  widening it to the package would collect the *source* tree — right
  locally, where the extension is an editable build of it, and wrong in
  the wheel jobs, where what has to be exercised is the module inside
  the installed wheel. Importing the package by name gets whichever of
  the two is installed, on every one of the kinds of wheel this project
  ships. The price is that an example has to be deterministic: fixed
  keys, and a verification rather than a signature wherever the value
  depends on randomness that is not pinned. Verified by breaking one
  expected value in the README and one in a docstring, and watching both
  tests fail.
- CONTRIBUTING.md's *Documentation and comments* says both of the above,
  since that is the file contributors read.

### What the wheels are built with

- **Two failures of the build hook say what went wrong** (#75).
  `get_ext_object` raised a bare `RuntimeError` -- no message at all --
  for a `cffi_modules` entry naming an object its script does not define;
  it now names both halves of the entry, which is the only thing that can
  be wrong there, and matters the more because the line is excluded from
  the coverage measure. And `dynamic_platform_tag` subscripted a dict
  literal of three Windows architectures, so a fourth answered `KeyError`
  -- `win-arm32`, which `scripts/cffi_build.py` does aim CMake at, being
  the one the two files disagreed about. It is in the map now, and
  anything else raises a `RuntimeError` naming the architecture, which is
  the policy `shared_library_extension` beside it already had.

- **The static Unix extension is compiled with the interpreter's own
  `CFLAGS`.** `CC`, `CFLAGS`, `CCSHARED` in that order is what
  `customize_compiler` composes for the extensions the interpreter
  builds for itself; `CFLAGS` was dropped entirely, which was two
  defects at once. The cffi glue was compiled with **no optimization**,
  unlike everything CMake builds beside it — on macOS `CFLAGS` carries
  `-O3 -DNDEBUG`, and the `-fPIC` that lives there rather than in
  `CCSHARED`. And on a **universal2** interpreter `-arch x86_64 -arch
  arm64` lives in `CFLAGS` while `LDSHARED` carries them too, so the
  object was compiled single-arch and linked dual-arch: precisely the
  configuration `target_architecture_options` exists to support, and one
  nothing exercises, CI building one architecture per runner. Measured
  by building the static wheel with and without the change, macOS arm64,
  cp314: the object goes 218 104 → 502 944 bytes, `-g` being in `CFLAGS`
  too, and the bundle 1 519 640 → 1 480 072, which is `-O3` reaching the
  compiler. Nothing is filtered out of the flags: on macOS `sysconfig`
  has already run them through `_osx_support`, which is what rewrites an
  `-arch` the toolchain cannot build and an `-isysroot` pointing at a
  missing SDK. What was missing was the splitting — `CCSHARED` went in
  as a single argv element, empty on a mac (clang tolerates it, gcc
  reads it as a missing input file) and wrong the day it holds two
  flags — so `CC`, `CCSHARED` and `LDSHARED` all go through
  `shlex.split` now.
- **A wheel whose extensions disagree on static or dynamic is refused.**
  The tag is a property of the whole wheel, so a wheel holding both
  kinds has no tag that is true of it: `py3-none-<platform>` over a
  `cpNN` extension installs on any interpreter of that platform and
  fails to import on most of them. It used to print and carry on.
  Nothing downstream inspects a tag against the contents it labels,
  which is the argument for refusing rather than reporting, on the one
  place in the build backend where a silent fallback produced a wrong
  artifact instead of a failed build. The running flag it replaces also
  caught one of the two orders only: it started `True` and was cleared
  by a dynamic module, and the message was printed by a *static* module
  finding it already cleared — with the modules the other way round the
  wheel came out `py3-none` with a static extension in it and nothing
  said so at all. A set of the modes has no order to get wrong, and its
  empty case is the same failure from the other side: `pure_python`
  cleared and no extension in the wheel. Verified by planting
  `{True, False}` before the check and watching the build stop, with a
  control build before and after.
- **The dynamic-wheel command documents its deployment target.** A
  dynamic wheel compiles no extension, so nothing derives its platform
  tag from a toolchain: without `MACOSX_DEPLOYMENT_TARGET`,
  `hatch_build.py` falls back to `platform.mac_ver()` and the documented
  command produces `macosx_26_0_arm64` on a macOS 26 machine — a tag pip
  refuses on every older macOS the file would in fact have loaded on.
  Documented rather than defaulted in `hatch_build.py`, and the reason
  is that the tag is not the only thing the variable decides: CMake
  reads it too, so a default applied to the tag alone would claim a
  floor the vendored library was not built for, which is worse than the
  narrow tag. Left unset the two agree. Measured both ways on macOS 26
  arm64: `macosx_26_0_arm64` without it, `macosx_11_0_arm64` with
  `MACOSX_DEPLOYMENT_TARGET=11.0`.

### Packaging metadata

- **The classifiers say what the package is.** `Operating System :: OS
  Independent` said the opposite of a package whose whole purpose is
  platform-specific compiled wheels; it is replaced by the three systems
  they are built for, `POSIX`, `MacOS` and `Microsoft :: Windows`.
  `Typing :: Typed` was absent although `btclib_libsecp256k1/py.typed`
  is in every wheel and the typed cffi boundary is the design point
  README.md leads with; it is the classifier PyPI users filter on.
  Checked on the built sdist, which is what the `check-dist` job rates:
  `twine check --strict` passes and `pyroma --min 10` still says 10/10,
  so the ratchet is unmoved.

### External vectors

- **The vendored-vector re-checker reports a path upstream has deleted,
  rather than raising on it** (#75). `repos/{repo}/commits?path=` answers
  `[]` with a 200 when no commit touches that path any more -- renamed,
  moved or deleted -- and `(commit,) = json.loads(...)` unpacked one
  commit out of that. The `ValueError` took `find_drift` down with it and
  `report` was never reached: the monthly run turned red and no issue was
  opened, which is the one outcome the workflow exists to prevent, on the
  one drift a vendored file nobody re-reads would otherwise hide.
  `_latest_commit` answers None there now, `Drift` carries a
  `path_is_gone` reading that encoding in one place, and the issue body
  and stdout say GONE with the reason instead of naming a tip that does
  not exist. Called with no README, or two, it prints its usage on stderr
  and exits 2, where `Path(args[0])` had answered `IndexError: list index
  out of range` about a list the caller never saw. btclib's copy of this
  script is the same code and has the same fix, with the tests: this
  repository has no test module for it, `.github/scripts` being outside
  the coverage source here, so what holds it is btclib's suite and the
  hand check in the session log.

- **ellswift is held to BIP324's published vectors.** The tests encoded,
  decoded and agreed with themselves, which says nothing about the map
  being the one BIP324 defines: two wrong implementations of one
  function agree with themselves too. `ellswift_decode_test_vectors.csv`
  pins every published `(ellswift, x)` pair, the degenerate cases among
  them — `u` or `t` zero, `u**3 + t**2 + 7` zero, and the vectors landing
  on x2 or x3 rather than x1. Only x is compared: BIP324 defines the map
  into a field element, so the y libsecp256k1 recovers with it is a fact
  about the library, and the prefix comes out `02` for some vectors and
  `03` for others. `packet_encoding_test_vectors.csv` pins
  `ellswift.xdh`, the path this module exists for and the one nothing
  independent checked: `in_priv_ours` and the two encodings to
  `mid_shared_secret`, with `in_initiating` settling the argument order
  — ours first with `party = 0`, theirs first with `party = 1` — and the
  same rows pinning `decode` again through `mid_x_ours` and
  `mid_x_theirs`. Bitcoin Core's own `ellswift_xdh` vectors were not
  needed for it. `xswiftec_inv_test_vectors.csv` is deliberately not
  vendored: libsecp256k1 exposes no entry point for the inverse map,
  `secp256k1_ellswift_encode` choosing its case from the randomness it
  is handed, so there is nothing here those vectors could be compared
  against.
- **MuSig2 aggregation is held to BIP327's vectors.** The MuSig2 test
  verified an aggregate signature against an aggregate key these
  bindings computed, which validates the round trip and not the
  aggregation: a wrong-but-self-consistent key or nonce aggregation
  passes it unchanged. Four files pin the four steps — the aggregate key
  with its error cases, the aggregate nonce with three invalid public
  nonces, the published partial signatures, and the aggregate signature
  with the tweaked taproot cases, which is then verified as a plain
  BIP340 signature of the *tweaked* key. Two limits are recorded rather
  than left to be rediscovered. The signing direction is not drivable at
  all: libsecp256k1 has no parser for a serialized secret nonce, by
  design — a secnonce that can be loaded is a secnonce that can be
  reused — so the `sk` and `secnonces` of `sign_verify_vectors.json`
  have no entry point, and what is pinned is the verification, which
  reads the same equation from the other side. And two valid cases are
  an empty message and a 38-byte one, which BIP327 allows and
  `secp256k1_musig_nonce_process`, taking a `msg32`, cannot be handed.
  `key_sort`, `nonce_gen`, `tweak` and `det_sign` are not vendored, each
  for a reason `tests/README.md` gives.
- **`ssa.sign_custom` is signed against the only external values it
  has.** The vendored BIP340 csv gated signing on `len(msg) == 32`, so
  rows 15 to 18 — messages of 0, 1, 17 and 100 octets, each with a
  secret key and an `aux_rand` — were verified and never signed. They
  are exactly the domain of the feature 0.7.1 introduced, and without
  them it was tested only against this package's own output, which
  CONTRIBUTING.md says proves nothing. Every row carrying a secret key
  now goes through `sign_custom`, and the 32-byte ones through `sign` as
  well: that `sign_custom` answers a 32-byte message with the signature
  `sign` returns is itself part of what the vectors check.
- **Recovery ids 2 and 3 are exercised, and so is a high-s signature
  through recovery.** `recovery.py` accepts `recid in range(4)` and
  every test fed it 0 or 1, so half the accepted domain reached
  libsecp256k1 from no test. The high bit says the x coordinate of the
  nonce point was reduced modulo the order on the way into r, and that
  recovery has to add the order back before decompressing it. No search
  finds such a signature — `x(kG)` lands in `[n, p)` with probability
  about `2**-128`, and aiming a `k` there is the discrete logarithm
  problem — so the point comes first and the signature is built around
  it, which needs no `k`: recovery is `r**-1 (sR - eG)`, an equation in
  R and not in its logarithm. The x is `n + 2`, the smallest on-curve
  value above the order, which the test proves rather than asserts, `n`
  itself being on the curve and giving `r = 0` while `n + 1` is a
  quadratic non-residue. Nobody holds the private key of that signature
  and nothing needs to: nothing publishes recid 2/3 vectors, so the
  recovered key is compared against the same equation computed in
  python, by point arithmetic the test file now does, which is the
  standard `der_decode` already set there. The second half is `to_der`,
  which documents that it does not normalize s and was held to it by
  nothing: negating s is the malleability ECDSA has, giving a second
  valid signature under the same key with the parity of the nonce point
  flipped, so it is the *other* recovery id that answers it; `to_der`
  keeps the high s, `dsa.verify` refuses what it produced, and
  `dsa.normalize` gives back exactly what `dsa.sign` returns.
- Every vendored file is pinned to a commit and a git blob SHA-1 in
  `tests/README.md`, as the ones before them are, so the monthly
  `vendored-vectors` workflow re-checks them.

### Mutation testing

- **The inert third of a session is skipped before it runs, not counted
  after it does** (#70). Every module here opens with
  `from __future__ import annotations`, so a mutant of the `|` inside a
  `bytes | int` signature — `bytes >> int` and ten more — is unreachable
  by any test, nothing ever evaluating the annotation as an expression.
  Unfiltered, a session paid the whole suite for that shape on 352 of 777
  mutants before reaching the 13 that were real: 365 survivors in five
  minutes, against 352 skipped and the same 13 in two once
  `[cosmic-ray.filters.operators-filter]` excluded the `BitOr` family by
  operator — in `bindings.toml` itself, which already says what is
  mutated and what judges it, rather than a `# pragma: no mutate` on each
  of the 26 lines it would otherwise mark and on every one a later
  signature adds. `cr-rate` cannot report a filtered session: its
  `is_killed` counts a skip as a kill, so it divided by every enumerated
  mutant and read 1.67%, where the 13 that survived the 425 that ran are
  3.06% of them. `.github/scripts/mutation_counts.py` prints killed,
  survived and skipped instead, with the rate over what actually ran, and
  fails on a worker outcome that is no verdict at all rather than
  reporting it as either.
- **Two of the three real shapes a session survivor list held are
  answered in the code instead of read past** (#71). Six of the 13 #70
  measured were an output buffer whose size was written more than once —
  a serialization, the capacity handed to libsecp256k1 and the length
  unpacked back, as up to three separate literals where `keys.serialize`
  already wrote it once; the other seven were `secrets.token_bytes(32)`,
  a length not observable in an aux value or a shared secret hashed
  before use. `ffi.sizeof` now derives every buffer size across the
  eighteen call sites in eight modules that used to write it by hand, and
  where the randomness is copied into a fixed-size array instead of hashed
  — `ssa.sign_`'s `char[32]` — the longer half of that pair already died
  on cffi's own bound, `ffi.new` there refusing 33 octets and taking 31.
- **A third, unrelated shape survived a private module's own size
  check.** `_scalar.octets`'s `len(value_bytes) != size` mutated to
  `is not` passed the whole suite, no wrapper here ever asking for a size
  past CPython's cached range for small ints, where an equal pair is the
  same object and the two operators cannot be told apart.
  `test_octets_size_check_compares_by_value` drives the check directly at
  300 octets — past the cache, and past every size a wrapper reaches —
  where `!=` and `is not` stop agreeing.

### The gate

- **The README quickstart is executed again** (#74). Fencing the
  indented blocks put the closing ``` flush against the last line of
  each example, and doctest reads the line after an example as the
  output it expects: three of the ten stopped passing, two of them
  expecting `True` followed by a fence. A blank line before each closing
  fence is what says an example's output ends there. The suite caught
  it, which is what it is for — `test_the_readme_examples_run` was added
  in this same release because *"an example nobody runs is documentation
  that stops being true silently"* — and this is the first thing it
  caught. `markdownlint-cli2` stays clean over the result: a blank line
  inside a fenced block is not a blank line around one.
- **The benchmark measures btclib's python arithmetic, which it had
  stopped doing** (#75). Two of its eight rows are labelled *"through
  btclib's pure python arithmetic"*, and `dsa.verify_` and `ssa.verify_`
  delegate to these very bindings for secp256k1 with sha256 -- which is
  exactly the fixture the script sets up. Traced, the two rows called
  `btclib_libsecp256k1.dsa.verify` and `.ssa.verify`: the same C as the
  package's own rows with a python wrapper in front, 22.5 and 24.9 us
  against 13.9 and 13.8, where the python path is 1214 and 1270.
  `python_arithmetic_only` turns the dispatch off before the rows run,
  and it does so in three namespaces because `_libsecp256k1_applicable`
  is imported *by name* into `ecc.dsa`, `ecc.ssa` and `curves.curve`:
  patching one leaves the other two delegating, which is a partial patch
  that still measures C and still looks like python -- the first
  measurement taken for this entry was wrong that way. The two rows drop
  to `mult=1`, a thousand calls of a millisecond being a second of clock
  where they had been sized for twenty microseconds, and the loop reads
  `perf_counter` rather than `time`, a wall clock being the one thing a
  benchmark should not use.

- **The entropy detectors of `detect-secrets` run over the tree.**
  `.secrets.baseline` was generated with `HexHighEntropyString` and
  `Base64HighEntropyString` off, and it is the baseline that decides
  which plugins run — so the two were off *everywhere*, not just over
  the two json vector files that motivated turning them off. A
  high-entropy credential in a workflow, in `scripts/` or in a package
  module was seen by nothing, on a repository whose plan gives it no
  generic secret scanning server-side and where this hook is the
  surrogate. The reason not to exclude those files stands — an AWS key
  planted in one of them went unseen while they were excluded — so the
  split is by plugin set rather than by scan, one baseline each, and the
  hook runs twice: `.secrets.baseline` with every plugin over everything
  else, and `.secrets.vectors.baseline` with the entropy pair off over
  `tests/*.csv` and `tests/*.json`, which are 64-character hex and
  nothing else, so with the detectors on a new vector is
  indistinguishable from a new secret. The keyword, private key and
  provider-token detectors — the ones that caught the planted AWS key —
  keep running over them. The first hook's exclusion is the filter its
  own baseline records, so the pattern is stated once, in the second
  hook's `files`; it names the second baseline too, that one being
  40-character hashes by the hundred, and `detect-secrets` skipping only
  the baseline `--baseline` points at. The newly recorded findings were
  reviewed one by one: hex constants written inline in
  `tests/test_vectors.py` and `tests/test_properties.py`, and
  `"-DSECP256K1_BUILD_BENCHMARK=OFF"` <!-- pragma: allowlist secret -->
  in `scripts/cffi_build.py`, which the base64 detector reads as a
  secret. Verified by planting a 64-character hex constant in a test
  module and an AWS access key in a vector file, and watching each hook
  name its own.
- **The copyright-notice hook reads files at all.** Without
  `--enforce-all` the tool intersects the filenames pre-commit hands it
  with `git diff --staged --name-only --diff-filter=A`: newly *added*
  staged files, and nothing else. On a clean checkout that set is empty,
  so `pre-commit run --all-files` — the run the `lint` workflow makes,
  and the one that gates a pull request — was checking **no file at
  all**, whatever the pattern matched. The hook had been green since it
  was added because it never read a file. `files` is `\.pyi?$` now, one
  extension wider, `stubs/_btclib_libsecp256k1.pyi` being a source file
  of this project — named in `mypy_path`, force-included in the sdist.
  With both fixed exactly one file failed: that stub, whose header was
  still the pre-MIT btclib one, five lines about copying and propagating
  where `COPYRIGHT` has two about the MIT license. The two commits that
  shortened the header and lowercased the `(c)` moved every `.py` and
  could not have moved this one, which is the whole argument for the
  hook. Verified by stripping the notice from the stub and from
  `btclib_libsecp256k1/mult.py` and watching it name both.

### The release path

- **A release tag that is not on `master` fails before anything is
  built.** CONTRIBUTING.md and RELEASING.md both say a release is a tag
  on the merge commit on `master`, and nothing enforced it. The
  deployment tag policy of the `pypi` environment does not: it admits
  the ref pattern `v*`, so a tag on a branch head, on an old `dev` state
  or on a fork-synced commit reaches the environment exactly as the
  release tag does, and the reviewer approving sees the tag name rather
  than its ancestry. GitHub matches a ref pattern and not an ancestry,
  so there is nothing to tighten there; `version-check` refuses a tagged
  commit that is not an ancestor of `origin/master` instead. Its
  checkout takes the whole history for it, and the step reads
  `origin/master` rather than fetching one of its own, so a missing
  `origin/master` fails the step, which is the safe way round.
  REPOSITORY.md and RELEASING.md both stated the tag policy without
  saying what it does not cover, which is how it comes to read as this
  check; both now say which one holds which half.
- **The `HISTORY.md` section is checked before the matrix builds.**
  Three of the release invariants were checked in `version-check`; the
  fourth was discovered in `github-release`, after PyPI had accepted the
  upload, as a `::warning::` with generated notes as the fallback —
  correct there, there being nothing left to stop, and no use at all as
  the place an omission is found. The same `awk`, on the same push path
  as the tag comparison. The fallback downstream stays: it covers a
  release deleted by hand and recreated.
- **Every attempt of a rehearsal gets a version of its own.** The
  suffix was `.dev<run number>`, unique per dispatch and identical
  across the re-runs of one, and the collision surfaced as a TestPyPI
  400 after the three-quarters of an hour the matrix takes.
  `github.run_id` does not help — GitHub's own wording is *"This number
  does not change if you re-run the workflow run"* — so it is
  `run_number * 100 + run_attempt`, computed in `version-check` rather
  than in the `with:` expression, expressions having no arithmetic and
  concatenation being unique only while the two digit counts line up.
  The two digits reserved for the attempt are checked in the same step
  rather than assumed. The discipline that stood in for the fix,
  *"dispatch a fresh run instead"*, is deleted from `release.yml` and
  from RELEASING.md.
- **The release path stays out of the branch concurrency groups.**
  `github.ref` inside a called workflow is the *caller's* ref, so a
  rehearsal — a `workflow_dispatch` of `release.yml` on a branch, which
  is what RELEASING.md prescribes — computed the very groups a push to
  that branch or a direct dispatch of `test.yml` computes, and with
  `cancel-in-progress` one killed the other either way round. Both
  reusable workflows take a `concurrency-suffix` input now and
  `release.yml` passes one. A tag run was already unique and stays so; a
  second rehearsal of the same branch still supersedes the first.

### CI

- **`PYTHON_VERSION` and `OS_NAME` are gone from the two test jobs.**
  Nothing read either one, and in a workflow where every choice carries
  its reasoning, dead configuration reads as load-bearing: the next
  person to refactor those jobs preserves it because it looks
  deliberate. Both values are already in the job name, which is where a
  reader of a failed run looks for them.
- **The matrix was cut to `ubuntu-latest` and CPython 3.14 for the
  duration of this work, and restored at the end.** GitHub Actions was
  degraded on the day, and the pull requests of this release were merged
  without waiting for it; the cut kept the runs that did start cheap and
  the red cells attributable. The restoring pull request is the first
  one that runs the matrix over any of it, which is why it is the one
  that has to be read rather than merged on sight.

### Issues closed without a change

- **#23, `ssa.verify` and the parity of a 33- or 65-byte key**, and
  **#24, entropy arguments left-padded**: both were fixed by `9563ebb`,
  the 0.7.1 release, which landed after the issues were filed.
  `ssa.verify` takes the 32-byte x-only key and only that; the four
  entropy arguments are 32 bytes or `None`, with `is None` rather than
  truthiness, so `b""` raises where it used to mean "not supplied". Both
  are pinned by tests.
- **#22, the per-platform test jobs as required status checks**: the
  aggregating `tests-passed` job exists and is on `master`, and the
  required contexts are `tests-passed`, `Lint and type-check` and
  `CodeQL`, each bound to an `app_id`. The five matrix-derived contexts
  are gone, and REPOSITORY.md carries the `gh api` call that restores
  the set.
