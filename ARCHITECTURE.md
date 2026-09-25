# Architecture

btclib-secp256k1 is bindings, not a library: every entry point is one
libsecp256k1 or secp256k1-zkp call, with its arguments validated first
and its return value checked afterwards. This page is the design behind
that boundary — the two builds a wheel can be, the module layout, the
vendored submodules and how they are compiled, and how a release is
produced and can be checked. What a user can and cannot expect of it in
terms of security is [SECURITY](./SECURITY.md), and why those
expectations hold is the [assurance case](./ASSURANCE_CASE.md).

## The two builds

One thing decides how a wheel behaves at import, and it is decided by
`src/btclib_secp256k1/__init__.py`'s `_load_lib`: it returns `module.lib`
where the extension has libsecp256k1 linked into it (a **static**
build), and otherwise searches beside it for a shared object and
`ffi.dlopen`s it (a **dynamic**, cffi ABI-mode build). Only one of the
two branches exists in a given wheel, which is why `_load_lib` takes the
module as an argument rather than reading it off the enclosing scope:
the branch a build does not have is reachable only through the stand-in
`tests/extension_test.py` drives it with, and that is how coverage
still reaches every line of both. `btclib_secp256k1.zkp`'s own
`_load_lib`, in `src/btclib_secp256k1/zkp/__init__.py`, has one branch
only — the flagged extension is static-only by decision, that module's
own docstring giving the reason — and is kept the same shape regardless,
so a dynamic path for it has one place to grow into rather than a call
site inlined wherever the subpackage is read.

Which of the two a wheel is is a build-time choice
(`BTCLIB_LIBSECP256K1_DYNAMIC`, below), not a run-time one: a caller
never selects a linkage, and every wrapper module calls the same `lib`
regardless of which branch produced it.

## The boundary

Above the dispatch, one module per libsecp256k1 module wrapped: `dsa`,
`ssa`, `ecdh`, `recovery`, `ellswift`, `silentpayments`, `musig`, plus
`keys`, `xonly` and `hashes` for what several of them share, and
`context`, `_scalar`, `_secret` and `_cdata` for what crosses the
boundary itself. No module is one call of another: `mult` had become
exactly that — `pubkey_from_prvkey` with a flag fixed — and was folded
into `keys`. README.md's *Wrapped modules* section has the table of
which libsecp256k1 module each wraps.

Every wrapper's public entry point takes octets and answers octets,
validating a size and a type before a bare pointer reaches C — README's
*What the boundary checks* section states what that validation is and
what it deliberately is not, and SECURITY.md's *What belongs here, and
what belongs upstream* draws the same line the other way round. Where a
wrapper already holds the libsecp256k1 object a call needs — a key a
sibling call just parsed, a signature a sibling call just built — it
has a private half spelled `_foo_`, both underscores load-bearing: the
leading one says the argument is unchecked, and the trailing one says
which kind of private, `_verify_` taking a parsed key where `_parse_der`
is an ordinary helper. `src/btclib_secp256k1/__init__.py`'s module
docstring states the convention once; every wrapper module states its
own direction of it.

Two outposts hold a converted object across several calls, for a caller
that crosses the boundary again and again with the same key rather than
once: `ssa.Signer` holds a keypair, and `keys.PubkeyTweakChain` holds a
parsed point. Both are documented, with the measurements that justify
holding state at all, in README's *Outposts past the boundary* section.

MuSig2 is deliberately *not* wrapped as a stateless call: its two-round
session holds a secret nonce that cannot be reused, which is a property
of an object's lifetime rather than of a function, so `musig.KeyAggCache`
and `musig.Session` are the one place this package holds a libsecp256k1
object with no serialization to be one instead — the exception to
"every wrapper takes octets and answers octets" stated above, and
`musig.py`'s own module docstring carries the reasoning for taking it.
`musig.SecretNonce` is the object that carries the secret itself, guarded
by a lock of its own so that at most one caller, from any thread, ever
receives it (`src/btclib_secp256k1/musig.py`); README's *Thread safety*
section states what each held object promises under concurrent use.

## The zkp subpackage

`btclib_secp256k1.zkp` is the same layout over secp256k1-zkp, under its
own namespace rather than an argument on each call: the fork's `musig`
builds a session incompatible with mainline's, so the two cannot be
confused once a caller has to write `zkp.musig` to reach the second.
`src/btclib_secp256k1/zkp/__init__.py`'s own `__getattr__` loads the
flagged extension only on the first access to `ffi` or `lib`, so
`import btclib_secp256k1` never reaches for it and `import
btclib_secp256k1.zkp` on its own pays nothing either; the subpackage
itself is always importable, and the extension behind it exists only
where `BTCLIB_LIBSECP256K1_ZKP=true` built one, which no published wheel
does (README's *Design* section states when that changes).

The subpackage holds a second, separate libsecp256k1-zkp context of its
own (`src/btclib_secp256k1/zkp/context.py`), built on first use rather
than at import — README's *Thread safety* section states why a lock
around that deferred build is what makes it safe under several threads,
where the primary extension's context needs none, being built at plain
module scope before any thread exists.

## The build

The vendored libraries are git submodules, read from and never written
to: `secp256k1` is Bitcoin Core's own, and `secp256k1-zkp` is
Blockstream Research's fork, vendored through `fametrano/secp256k1-zkp`
for the reason README's *Versioning* section gives.
`scripts/cffi_build.py` builds the one, or both, with CMake, every
optional module turned on by an explicit
`-DSECP256K1_ENABLE_MODULE_*` flag rather than left to upstream's own
defaults — `tests/module_flags_test.py` holds that list to naming every
module the submodule defines, `OFF` included, so a module upstream
defaults on is never built by omission — and then compiles the cffi
extension over the result by one of three paths, chosen by the
environment rather than by an argument: static with MSVC on native
Windows, static with the interpreter's own toolchain everywhere else,
and dynamic (cffi ABI mode) with no C compiled at all, chosen by
`BTCLIB_LIBSECP256K1_DYNAMIC`. `BTCLIB_LIBSECP256K1_CROSS_COMPILE` forces
the dynamic path for a target whose interpreter cannot run on the build
machine, and `CFFI_PLATFORM` names that target platform; the dynamic
Windows wheel is instead cross-compiled on Linux with mingw-w64, through
the vendored CMake toolchain file. `BTCLIB_LIBSECP256K1_ZKP=true` is the
fourth, orthogonal choice: a second, static-only extension over
`secp256k1-zkp`, built beside whichever of the three paths above the
primary extension takes. `stubs/_btclib_secp256k1.pyi` is what lets
strict mypy typecheck a module that exists only after a build.
`scripts/README.md` walks `scripts/cffi_build.py` and
`scripts/hatch_build.py` in turn, the environment variables among them.

Which commit each submodule is pinned to, and how that pin is reviewed
and kept honest, is README's *Versioning* section and the
`submodule-pin` and `vendored-vectors.yml` gates CONTRIBUTING.md's
*The environment and the gates* names.

## The wheel and its reproducibility

`scripts/hatch_build.py` builds one of two kinds of wheel — never both —
tagged so the difference is legible from the file name: a **static**
wheel carries the one compiled extension, tagged for the interpreter
that built it, and a **dynamic** wheel compiles no C at all, carrying the
ABI-mode module and the shared library it `dlopen`s, tagged
`py3-none-<platform>` because neither file is interpreter-specific.
`docs/source/package-content-policy.md` states what each kind of wheel
may and must hold, enforced by `.github/scripts/verify_wheel_contents.py`
and checked against that same page by `tests/wheel_contents_test.py`.

A wheel's archive members carry the timestamp of the commit that built
them, not the clock of the moment: `SOURCE_DATE_EPOCH`, exported from
`git log -1 --pretty=%ct` before every build that publishes or measures
a distribution, is what a build tool with no repair step stamps every
member from directly. Where it is unset, hatchling's own fallback is a
constant of its own rather than the clock, but `auditwheel` and
`delocate`, which do repair a built wheel, take each repaired member's
timestamp from the clock in that case — which is what makes two builds
of one commit differ otherwise, and what pinning the variable removes.
Two builds of one commit then agree byte for byte, which is what
`wheel-reproducibility.yml` measures by building this commit's wheel
twice, in two separate directories, and diffing the two archives
member by member; `.github/scripts/check_wheel_reproducibility.py` is
the script it runs, and CONTRIBUTING.md's *The environment and the
gates* has the command that reproduces it locally, on the wheel forms
that build on the machine at hand. `wheel-reproducibility` is a required
check on a pull request that touches what its builds read, and
CONTRIBUTING.md's *What gates a merge, and what only reports* states why.

## Release provenance

Wheels and the sdist are published to PyPI by the `release` workflow
through [Trusted Publishing](https://docs.pypi.org/trusted-publishers/):
no long-lived token exists, and PyPI hands the workflow a short-lived one
at run time, through GitHub OIDC. Every upload carries a PEP 740
attestation, so a distribution on the index can be traced back to the
workflow run and the commit it was built from, and the sdist attached to
the GitHub release carries a build provenance attestation of its own,
signed in the run that built it. A CycloneDX bill of materials is
attached beside the sdist, naming each vendored C library at the commit
its submodule gitlink pins — the one fact the package's own metadata
cannot state, `Requires-Dist` naming `cffi` and nothing of
libsecp256k1 — and is itself covered by the sdist's attestation.
SECURITY.md's *Supported versions* states what each of these documents
is signed by and gives the commands that verify them; this page states
only how they come to exist.

## The public surface

Every module declares `__all__`, and `stubs/_btclib_secp256k1.pyi` and
`.pre-commit-config.yaml`'s mypy hook hold the whole package, including
what a build produces, to `strict = true`. `tests/all_test.py` walks the
package for every wrapper module and every entry point it exports, so a
new module or a new function is reached by that census whether or not
anything else names it.
