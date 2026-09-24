# Assurance case

[SECURITY](./SECURITY.md) states what a user can and cannot expect of
these bindings in terms of security. This page argues why those
expectations hold: the threat model, the trust boundaries, how secure
design principles are applied, and how common implementation weaknesses
are countered. Each argument below names the file, the test or the
workflow that supports it; where SECURITY.md already states a fact, this
page points at it instead of repeating it. The components named here are
the ones [ARCHITECTURE](./ARCHITECTURE.md) describes.

## What is claimed

- **The answer is libsecp256k1's, or secp256k1-zkp's.** Every wrapper is
  one C call, with its arguments validated first and its return value
  checked afterwards; none reimplements, extends or second-guesses the
  cryptography, and README.md's *Design* section states so.
- **Malformed input is refused before it reaches C.** A size or a type
  that a bare pointer cannot carry safely is checked here, because no
  return code or callback of the library can report it once the call is
  made; README.md's *What the boundary checks* section states what else
  is checked and what is deliberately left to libsecp256k1.
- **An illegal argument cannot take the caller's process down.** The
  vendored build replaces libsecp256k1's abort()ing default callbacks
  with do-nothing stubs, so a violated precondition is recorded on
  `context.check()` and never crashes the interpreter that reached it —
  `tests/core_test.py::test_safe_abort` drives that replacement with
  deliberately illegal arguments.
- **A secret this package produces is read out and overwritten once.**
  Wherever a wrapper returns a tweaked key, a nonce or a shared secret,
  the buffer libsecp256k1 or secp256k1-zkp wrote it into is wiped before
  it is dropped, and an `into` buffer moves the last copy to memory the
  caller can overwrite in turn; SECURITY.md's *Limitations of the
  binding layer* states exactly what this does and does not buy.
- **A published distribution is what this tree built.** SECURITY.md's
  *Supported versions* states how that is verified and what the files
  may hold.

## Threat model

This package is a boundary in its caller's process, not a service: it
opens no socket, starts no subprocess, and reads no file whose path a
caller supplies. The command below lists the top-level name of every
module `src/` imports, at any depth and in any spelling of the
statement — `cffi`, the one runtime dependency `pyproject.toml`
declares, is absent from it because nothing under `src/` imports it by
name: the compiled extension provides `ffi` and `lib` already built,
and `src/btclib_secp256k1/__init__.py` reads them off that extension
rather than off the `cffi` package.

```shell
python3 - <<'EOF'
import ast, pathlib
names = set()
for p in pathlib.Path("src").rglob("*.py"):
    for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            names.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            names.add(n.module.split(".")[0])
print(sorted(names))
EOF
```

What it prints is `__future__`, `_btclib_secp256k1`, `btclib_secp256k1`,
`collections`, `importlib`, `pathlib`, `secrets`, `threading`, `types`
and `typing`. `__future__` is every module's own `from __future__ import
annotations`, a language pragma rather than a dependency; `btclib_secp256k1`
is the `zkp` subpackage reaching its parent's own `BytesLike`, `CData`
and `_scalar`/`_secret` helpers through an absolute rather than a
relative import (`src/btclib_secp256k1/zkp/musig.py` and its siblings),
self-referential rather than third-party. `_btclib_secp256k1` is the
compiled extension `_load_lib` returns the handle of. `_btclib_secp256k1_zkp`
is not in the list despite being loaded: `zkp/__init__.py` reaches it
through `importlib.import_module("_btclib_secp256k1_zkp")`, a name built
at run time and passed to a function call, which an `ast.Import` walk
does not see as an import statement. `os` is not among them either:
nothing under `src/` reads an environment variable at run time. The four
variables that choose a build path (*Architecture*'s *The build*) are
read only under `scripts/`, before any wheel exists to run —
`scripts/cffi_build.py` reads all four, and `CFFI_PLATFORM` alone is
read a second time, by `scripts/hatch_build.py`, to compute the wheel's
own platform tag.

**What is defended.**

- Private keys, nonces and shared secrets, against a short buffer
  reading adjacent memory, against recovery from what the buffer they
  passed through still holds once a call returns, and, where
  libsecp256k1's own call carries that guarantee, from the timing of the
  call itself.
- The caller's process, against an argument that violates a
  precondition libsecp256k1 or secp256k1-zkp checks internally: what
  answers for it is `context.check()`, never an abort().
- The correctness of the answer, against an adversary who chooses the
  input: a signature accepted that should be refused, a key parsed that
  is not one, a scalar treated as valid outside `[1, n-1]`.

**The adversaries.**

- A caller passing octets it does not control on to a wrapper: a
  signature, a key or a message received from a remote party, with no
  parsing of its own in front of it.
- An observer of timing on the same machine, for the calls whose
  libsecp256k1 or secp256k1-zkp implementation is constant-time.
- A party tampering with a distribution between this tree and the user,
  or with a vendored submodule's history before it is pinned here.

**What is not defended**, each stated in SECURITY.md's *Limitations of
the binding layer*:

- memory disclosure of a secret held in a Python object — an `int`, a
  `bytes` — which is neither mutable nor zeroized
- the variable-time multiplication `keys.pubkey_tweak_mul` and
  `keys.pubkey_tweak_mul_sum` run, `secp256k1_ec_pubkey_tweak_mul` being
  timed by the scalar rather than constant; `ecdh.shared_point` is the
  same product through the constant-time `secp256k1_ecdh`, and is where
  a secret scalar belongs
- a nonce read back through `dsa.nonce_rfc6979` or `ssa.nonce_bip340`,
  which exists to check a derivation against libsecp256k1's own and is
  the private key given the signature it made
- a private key or a tweak passed as an `int` rather than as octets,
  whose magnitude the serialization crossing the boundary takes a
  variable time over
- the operating system's random number generator, which this package
  uses through `secrets` rather than seeding one of its own

Nor is the interpreter or the operating system this package runs on: a
binding shares its caller's process and has no defence against it.

## Trust boundaries

**The caller and every public entry point.** Octets and scalars cross
from the caller at every wrapper, and each is validated there before a
pointer reaches C: README.md's *What the boundary checks* section states
the rule, and `tests/core_test.py` and `tests/module_flags_test.py`
drive it. The caller is trusted with the choices the API offers: which
serialization a key or a signature arrives in, `grind=True` on
`dsa.sign`, or a private half taking a libsecp256k1 object already
proved.

**This package and libsecp256k1 or secp256k1-zkp.** Past this boundary
is C code this package does not own. A private half spelled `_foo_`
does not read the illegal-argument callback, so what it answers for an
object the library refuses is whatever that call itself answers —
`tests/callbacks_test.py` drives every shape that can take.
`context.check()` is what reports a violated precondition, on the thread
that triggered it. A flaw on the far side is reported upstream, as
SECURITY.md's *What belongs here, and what belongs upstream* states.

**The vendored submodules.** `secp256k1` and `secp256k1-zkp` are read
from and never written to: `scripts/cffi_build.py` builds them out of
tree, and `.pre-commit-config.yaml`'s `submodule-pin` and
`submodules-checked-out` hooks refuse a commit whose pin or whose
checkout disagrees with what README.md's *Versioning* section names.
`vendored-vectors.yml`'s `pin` job verifies the mainline tag against a
libsecp256k1 maintainer's signature, and its `zkp-pin` job verifies
every commit in the fork's delta against a recognized signer, both on a
schedule and on a pull request touching the pin.

**Files.** This package opens no file a caller names: what a dynamic
build reads is its own installed directory, globbing for the shared
library shipped beside it, and what every build reads is its own
distribution metadata, for `__version__`. Neither path is one a caller
supplies.

**The environment.** Nothing under `src/` reads one, as the *Threat
model* census above shows; the four variables that choose a build path
are read only at build time, by `scripts/cffi_build.py`.

## Secure design principles

Saltzer and Schroeder's principles, and the boundary *Architecture*
describes beside them.

- **Economy of mechanism.** One dispatch decides which library handle a
  wrapper calls through (`_load_lib`, *Architecture*'s *The two
  builds*), and one context is shared by every call into a given
  library, randomized once before any thread exists rather than per
  call.
- **Fail-safe defaults.** An argument of the wrong size or type is
  refused rather than padded or reinterpreted into a valid one, README's
  *What the boundary checks* section stating the rule and its one
  deliberate exception, `dsa.verify(..., normalize=True)`, being an
  explicit choice rather than a default.
- **Complete mediation.** Every public entry point validates its
  arguments before calling; a private `_foo_` half defers that check
  because its caller already made it, by parsing the object or by
  building it through a call that already proved it.
- **Open design.** The code, the vendored submodules and their pins, and
  the limitations are all published; the suite is checked against
  vectors BIP340, RFC6979 and trezor-firmware publish, not against a
  second implementation of the arithmetic
  (`tests/vectors_test.py`, `tests/nonces_test.py`).
- **Least privilege.** The *Threat model* census above is the whole of
  what this package imports, no network client or subprocess launcher
  among them, and the only files it opens are its own.
- **Psychological acceptability.** A verdict function —
  `keys.prvkey_verify`, `keys.pubkey_verify`, `xonly.pubkey_verify`,
  `dsa.signature_verify` — answers `False` for input that does not hold
  and never raises, where every entry point that goes on to *use* the
  value raises instead: a caller can tell "not valid" from "cannot be
  used" (README.md's *What the boundary checks* section).
- **Layering.** A public entry point speaks in octets, and the private
  half beneath it in libsecp256k1 objects, never the other way round
  (`src/btclib_secp256k1/__init__.py`'s module docstring); the fork's
  `zkp` subpackage is reached only under its own namespace, never
  through a flag on a mainline call.

**Constant time where it is claimed.** It is claimed of libsecp256k1 and
secp256k1-zkp, not of this package's own boundary code, which branches
on a type, a length or a magnitude and never on a secret's content
(README.md's *What the boundary checks* section, its closing paragraph).
Which calls carry the guarantee and which do not is
SECURITY.md's *Limitations of the binding layer*.

## Common implementation weaknesses

Weaknesses from MITRE's CWE list that a binding layer of this kind is
exposed to, and what counters each.

- **Out-of-bounds read or write (CWE-125, CWE-787).** Every wrapper
  checks a bare pointer's declared length against what the caller
  supplied before the call is made, README.md's *What the boundary
  checks* section stating why this is the one check that cannot be left
  to the caller. `tests/core_test.py`'s
  `test_size_checks_refuse_both_sides` drives a short and a long
  argument against every entry point that takes one, and
  `tests/bytes_like_test.py` holds the same boundary to the three
  buffer types it accepts.
- **Reachable assertion (CWE-617).** The vendored build's callback stubs
  replace libsecp256k1's abort()ing defaults, so a violated precondition
  is reported rather than crashing the process; `tests/core_test.py`'s
  `test_safe_abort` drives libsecp256k1 with deliberately illegal
  arguments to prove the replacement holds.
- **Improper input validation (CWE-20).** The tests under *Trust
  boundaries*, and `tests/properties_test.py`'s invariants over inputs
  derived from a chain of SHA256 rather than chosen by hand.
- **Uncaught exceptions on hostile input (CWE-248, CWE-755).** The
  targets under `fuzz/` run under ClusterFuzzLite in
  `.github/workflows/fuzz.yml`, each parsing octets it does not control
  through the entry point it names, and `tests/fuzz_corpus_test.py`
  checks that every seed of their corpus still parses.
- **Observable timing (CWE-208).** The constant-time calls and what is
  not, stated in SECURITY.md and pointed at from *What is not defended*
  above.
- **Weak randomness (CWE-330, CWE-338).** Randomness comes from
  `secrets.token_bytes`
  (SECURITY.md), and ruff's flake8-bandit rules, selected with the rest
  of `ALL` in `pyproject.toml` and unmodified by its `ignore` list, flag
  a call into the `random` module.
- **Improper verification of a signature (CWE-347).** A scheme whose
  specification publishes vectors is checked against them —
  `tests/vectors_test.py` for BIP340, BIP324, BIP327 and BIP352 — and
  `tests/nonces_test.py` checks a nonce derivation by recomputing `r`
  from the `k` it returns.
- **Exposure of sensitive information (CWE-209) and cleartext storage of
  sensitive information in memory (CWE-316).** The buffers a secret
  passes through are overwritten before being dropped
  (`tests/secret_test.py`), and an `into` argument moves the last
  un-zeroizable copy to memory the caller owns; what neither reaches is
  stated in SECURITY.md's *Limitations of the binding layer*.
- **Race condition (CWE-362).** `musig.SecretNonce` is read and cleared
  under a lock of its own, and `btclib_secp256k1.zkp`'s deferred context
  build is guarded the same way, so two threads racing either cannot
  both proceed; `tests/concurrency_test.py`'s
  `test_exactly_one_thread_signs_a_shared_secret_nonce` asserts the
  first, and `tests/zkp_test.py`'s
  `test_racing_threads_build_the_context_once` the second.
- **Type confusion (CWE-843).** mypy runs with `strict = true`
  (`pyproject.toml`) over the package, the suite and the build scripts,
  as a hook of the lint gate in `.pre-commit-config.yaml`.
- **Code that is wrong and still passes.** Line and branch coverage is
  held at 100% by `fail_under` in `pyproject.toml`, and mutation
  testing, profiled under `.github/mutation/` and run by
  `.github/workflows/mutation.yml`, asks whether the suite notices a
  bound written with the wrong comparison or the wrong constant — the
  shape `.github/mutation/bindings.toml`'s own header gives as this
  package's own gap between statement coverage and a wrapper's actual
  claim.
- **Supply chain.** SECURITY.md's *Supported versions* describes the
  attestations and the bill of materials; *Trust boundaries* above
  states how the vendored submodules are pinned and verified. `uv.lock`
  pins every dependency, and CONTRIBUTING.md's *The environment and the
  gates* states that every job installs with `--locked`. Every
  third-party action is pinned to a commit sha, the organization's own
  reusable workflows excepted; `actionlint`, `zizmor` and
  `detect-secrets` run as hooks in `.pre-commit-config.yaml`.
