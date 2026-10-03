# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Every `fuzz/corpus/` seed is an input its harness's entry point accepts.

The seeds are what libFuzzer starts from, and a seed the entry point
refuses is a start inside the domain the target already declines: a
parser narrowed under one -- by a fix here, or by a bump of the vendored
library -- would leave the sentinel starting from nothing, with no red
anywhere. What is held here is that every seed is still accepted, and
that `fuzz_ssa_verify_message`'s seeds still verify, in milliseconds
and with no container built.

Each harness imports `atheris` at module level, which is pre-installed
in ClusterFuzzLite's builder image and declared in no dependency group
here, so what each harness's `fuzz_target` calls is restated in
`_ACCEPTS` below, keyed by the harness's file name, and the first test
is what keeps that restatement complete in both directions. A harness
that pads, cuts or splits its input does it in a function `arguments`,
which `_split` loads under a stand-in for `atheris`, so `_ACCEPTS` reads
the layout from the harness rather than restating it. The key and the signature
`fuzz/fuzz_ssa_verify_message.py` fixes are read off its source with
`ast`, so the seed is checked against what the harness verifies with.

A crash the sentinel finds does not come here. Section 10 of the
organization standard makes its regression an ordinary test naming the
input and what the entry point now does with it: a seed a hardened
parser refuses is exactly what this module turns red on.
"""

from __future__ import annotations

import ast
import csv
import importlib.util
import sys
import types
from collections.abc import Callable
from pathlib import Path

import pytest

from btclib_secp256k1 import (
    dsa,
    ellswift,
    hashes,
    keys,
    musig,
    recovery,
    silentpayments,
    ssa,
    xonly,
)

_ROOT = Path(__file__).parents[1]
_FUZZ = _ROOT / "fuzz"
_CORPUS = _FUZZ / "corpus"
_BIP340_VECTORS = Path(__file__).parent / "bip340_test_vectors.csv"


def _hex_constants(harness: str) -> dict[str, bytes]:
    """Return every module-level `NAME = bytes.fromhex("...")` of a harness.

    Read off the source rather than imported, for the reason the module
    docstring gives.
    """
    path = _FUZZ / f"{harness}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants: dict[str, bytes] = {}
    for node in tree.body:
        match node:
            case ast.Assign(
                targets=[ast.Name(id=name)],
                value=ast.Call(
                    func=ast.Attribute(attr="fromhex"),
                    args=[ast.Constant(value=str(text))],
                ),
            ):
                constants[name] = bytes.fromhex(text)
            case _:
                pass
    return constants


def _split(harness: str) -> Callable[[bytes], tuple[object, ...]]:
    """Return the `arguments` function of a harness, loaded without `atheris`.

    The stand-in is in `sys.modules` for the import alone and removed
    after it, so that nothing else sees it.
    """
    path = _FUZZ / f"{harness}.py"
    spec = importlib.util.spec_from_file_location(harness, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["atheris"] = types.ModuleType("atheris")
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules["atheris"]
    arguments: Callable[[bytes], tuple[object, ...]] = module.arguments
    return arguments


def _calls(entry: Callable[..., object], harness: str) -> Callable[[bytes], object]:
    """Return the call `harness` makes of `entry` for a given input."""
    arguments = _split(harness)
    return lambda data: entry(*arguments(data))


_SCHNORR = _hex_constants("fuzz_ssa_verify_message")

# what each harness's fuzz_target calls, keyed by the harness's file
# name: every seed under fuzz/corpus/<name>/ is handed to this
_ACCEPTS: dict[str, Callable[[bytes], object]] = {
    "fuzz_xonly_parse": xonly.parse,
    "fuzz_keys_parse": keys.parse,
    "fuzz_dsa_parse_der": dsa.parse_der,
    "fuzz_ssa_verify_message": lambda msg: ssa.verify(
        msg, _SCHNORR["PUBKEY"], _SCHNORR["SIGNATURE"]
    ),
    "fuzz_tagged_sha256": lambda msg: hashes.tagged_sha256(b"BIP0340/challenge", msg),
    "fuzz_dsa_parse_compact": _calls(dsa.parse_compact, "fuzz_dsa_parse_compact"),
    "fuzz_dsa_verify": _calls(
        lambda msg, pubkey, signature, normalize, compact: dsa.verify(
            msg, pubkey, signature, normalize=normalize, compact=compact
        ),
        "fuzz_dsa_verify",
    ),
    "fuzz_ssa_verify": _calls(ssa.verify, "fuzz_ssa_verify"),
    "fuzz_recovery_recover": _calls(recovery.recover, "fuzz_recovery_recover"),
    "fuzz_ellswift_decode": _calls(ellswift.decode, "fuzz_ellswift_decode"),
    "fuzz_ellswift_xdh": _calls(ellswift.xdh, "fuzz_ellswift_xdh"),
    "fuzz_musig_pubnonce_parse": _calls(
        musig.pubnonce_parse, "fuzz_musig_pubnonce_parse"
    ),
    "fuzz_musig_aggnonce_parse": _calls(
        musig.aggnonce_parse, "fuzz_musig_aggnonce_parse"
    ),
    "fuzz_musig_partial_sig_parse": _calls(
        musig.partial_sig_parse, "fuzz_musig_partial_sig_parse"
    ),
    "fuzz_silentpayments_parse_label": _calls(
        silentpayments.parse_label, "fuzz_silentpayments_parse_label"
    ),
    "fuzz_silentpayments_scan_outputs": _calls(
        silentpayments.scan_outputs, "fuzz_silentpayments_scan_outputs"
    ),
}

_HARNESSES = tuple(sorted(path.stem for path in _FUZZ.glob("fuzz_*.py")))
_SEEDS = tuple(
    seed for name in _HARNESSES for seed in sorted((_CORPUS / name).glob("*.bin"))
)


def _seed_id(seed: Path) -> str:
    return str(seed.relative_to(_CORPUS))


def test_every_harness_has_a_corpus_directory_and_an_entry_above() -> None:
    """The harnesses, the corpus directories and `_ACCEPTS` name one set.

    Every other assertion here quantifies over `_HARNESSES` and `_SEEDS`,
    so an empty `fuzz/` is refused rather than vacuously passed.
    """
    assert _HARNESSES, f"{_FUZZ} holds no fuzz_*.py"
    directories = tuple(sorted(path.name for path in _CORPUS.iterdir()))
    assert directories == _HARNESSES, (
        f"fuzz/corpus/ holds {directories} where fuzz/ holds {_HARNESSES}"
    )
    assert tuple(sorted(_ACCEPTS)) == _HARNESSES, (
        f"_ACCEPTS names {tuple(sorted(_ACCEPTS))} where fuzz/ holds {_HARNESSES}"
    )


@pytest.mark.parametrize("name", _HARNESSES)
def test_every_corpus_directory_holds_a_seed(name: str) -> None:
    """A harness with no seed is one this module has never checked."""
    assert any(seed.parent.name == name for seed in _SEEDS), (
        f"fuzz/corpus/{name}/ holds no *.bin"
    )


@pytest.mark.parametrize("seed", _SEEDS, ids=_seed_id)
def test_every_seed_is_accepted(seed: Path) -> None:
    """The harness's entry point takes the seed without refusing it."""
    _ACCEPTS[seed.parent.name](seed.read_bytes())


@pytest.mark.parametrize("seed", _SEEDS, ids=_seed_id)
def test_no_seed_ends_in_a_newline(seed: Path) -> None:
    """A fixer that appends one turns a seed into a different input."""
    assert not seed.read_bytes().endswith(b"\n"), f"{seed} ends with a newline"


def test_the_schnorr_seeds_verify_under_the_vector_the_harness_fixes() -> None:
    """The key and the signature are BIP340 vector 18's, and each seed verifies.

    `fuzz_ssa_verify_message.py` names that vector; this is what holds
    its constants to it, and its seeds to being messages it signs.
    """
    with _BIP340_VECTORS.open(encoding="ascii", newline="") as file:
        vector = next(row for row in csv.DictReader(file) if row["index"] == "18")
    assert _SCHNORR["PUBKEY"] == bytes.fromhex(vector["public key"])
    assert _SCHNORR["SIGNATURE"] == bytes.fromhex(vector["signature"])
    for seed in (_CORPUS / "fuzz_ssa_verify_message").glob("*.bin"):
        assert ssa.verify(seed.read_bytes(), _SCHNORR["PUBKEY"], _SCHNORR["SIGNATURE"])
