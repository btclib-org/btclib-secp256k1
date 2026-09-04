# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests of btclib_secp256k1.zkp.ecdsa_s2c.

Two kinds, for the reason `tests/zkp_test.py`'s own module docstring
gives for the subpackage: the entry points `secp256k1_ecdsa_s2c.h`
declares exist only in secp256k1-zkp, so unlike that file's own
`STAND_IN` -- the primary package's real, always-built extension,
sharing context creation and the two callbacks with secp256k1-zkp's own
header -- nothing here can borrow a real implementation of them. What
stands in for the extension below is therefore hand-written rather than
borrowed: `_FakeLib` answers those calls (the three ordinary ones this
module also reaches, `secp256k1_ec_pubkey_parse` and the two
compact-signature calls, and the four `zkp.context` itself makes to
build a context through this same stand-in) with just enough behaviour
to drive every branch `ecdsa_s2c.py` has of its own -- an invalid
private key or an unparsable object failing exactly where the real
library would -- without computing anything cryptographic. It is not a
second implementation to trust, and nothing here is validated against
it: the `zkp`-marked tests below are.

Those are the ones that need the real thing: `test_ecdsa_s2c_fixed_vectors`
of secp256k1-zkp's own `tests_impl.h`, reproduced here against this
package's wrapper rather than against a bare `ctypes` call, and the full
anti-exfil protocol run end to end. `pytest.importorskip` is what lets
them skip cleanly rather than fail where `_btclib_secp256k1_zkp` was
never built -- the `zkp` marker on them is `-m zkp`'s own selection for
the CI job that builds it, orthogonal to that skip and not a substitute
for it: pyproject.toml's own comment on the marker says it names the
requirement rather than granting one.
"""

from __future__ import annotations

import secrets
import types
from collections.abc import Iterator
from typing import Any

import cffi
import pytest

from btclib_secp256k1 import keys, zkp
from btclib_secp256k1.zkp import context as zkp_context
from btclib_secp256k1.zkp import ecdsa_s2c

# the three structs this extension's own header set declares that
# ecdsa_s2c.py allocates: all three are `unsigned char data[64]`
# underneath (secp256k1.h's own secp256k1_pubkey and
# secp256k1_ecdsa_signature, secp256k1_ecdsa_s2c.h's own opening), which
# is what makes one cdef answer for all three rather than three
_fake_ffi = cffi.FFI()
_fake_ffi.cdef("""
typedef struct { unsigned char data[64]; } secp256k1_ecdsa_signature;
typedef struct { unsigned char data[64]; } secp256k1_ecdsa_s2c_opening;
typedef struct { unsigned char data[64]; } secp256k1_pubkey;
""")

# sentinels this file's own tests pass to provoke the library reporting
# failure -- not a real point or a real invalid signature, only bytes
# _FakeLib recognizes as such
_INVALID_PUBKEY = b"\x00" * 33
_INVALID_SIGNATURE = b"\xff" * 64
_INVALID_OPENING = b"\x00" * 33
_ZERO_PRVKEY = b"\x00" * 32


class _FakeLib:
    """Just enough of libsecp256k1-zkp to drive `ecdsa_s2c.py`'s own branches.

    Every method's signature is the one it is called with: `ecdsa_s2c.py`
    calls most of them directly, and `secp256k1_context_create`, the two
    callback setters and `secp256k1_context_randomize` are called by
    `zkp/context.py` instead, itself driven through this same stand-in.
    None reads `ctx`, which is why `secp256k1_context_create` below can
    hand back an object with nothing behind it. Where the real library
    would compute a point or a hash, this writes a fixed, recognizable
    pattern instead -- enough for the caller's own post-processing (a
    `bytes` of the right length) to run, and nothing that could be
    mistaken for a real commitment.
    """

    def secp256k1_context_create(self, flags: int) -> object:  # noqa: ARG002
        return object()

    def secp256k1_context_set_illegal_callback(
        self, ctx: object, fn: Any, data: Any
    ) -> None:
        pass

    def secp256k1_context_set_error_callback(
        self, ctx: object, fn: Any, data: Any
    ) -> None:
        pass

    def secp256k1_context_randomize(self, ctx: object, seed32: bytes) -> int:  # noqa: ARG002
        return 1

    def secp256k1_ec_pubkey_parse(
        self,
        ctx: object,  # noqa: ARG002
        pubkey: Any,
        input_: bytes,
        inputlen: int,
    ) -> int:
        # 33 only: nothing here drives a 65-byte uncompressed input, and
        # honoring one would write past this fake's own 64-byte `data`
        if inputlen != 33 or input_ == _INVALID_PUBKEY:
            return 0
        pubkey.data[0:inputlen] = input_[0:inputlen]
        return 1

    def secp256k1_ecdsa_signature_parse_compact(
        self,
        ctx: object,  # noqa: ARG002
        signature: Any,
        input64: bytes,
    ) -> int:
        if input64 == _INVALID_SIGNATURE:
            return 0
        signature.data[0:64] = input64
        return 1

    def secp256k1_ecdsa_signature_serialize_compact(
        self,
        ctx: object,  # noqa: ARG002
        output64: Any,
        signature: Any,
    ) -> int:
        output64[0:64] = bytes(signature.data[0:64])
        return 1

    def secp256k1_ecdsa_s2c_opening_parse(
        self,
        ctx: object,  # noqa: ARG002
        opening: Any,
        input33: bytes,
    ) -> int:
        if input33 == _INVALID_OPENING:
            return 0
        opening.data[0:33] = input33
        return 1

    def secp256k1_ecdsa_s2c_opening_serialize(
        self,
        ctx: object,  # noqa: ARG002
        output33: Any,
        opening: Any,
    ) -> int:
        output33[0:33] = bytes(opening.data[0:33])
        return 1

    def secp256k1_ecdsa_s2c_sign(  # noqa: PLR0913, PLR0917
        self,
        ctx: object,  # noqa: ARG002
        signature: Any,
        opening: Any,
        msg32: bytes,  # noqa: ARG002
        seckey: bytes,
        s2c_data32: bytes,  # noqa: ARG002
    ) -> int:
        if seckey == _ZERO_PRVKEY:
            return 0
        signature.data[0:32] = b"\x01" * 32
        signature.data[32:64] = b"\x02" * 32
        opening.data[0] = 2
        opening.data[1:33] = b"\x03" * 32
        return 1

    def secp256k1_ecdsa_s2c_verify_commit(
        self,
        ctx: object,  # noqa: ARG002
        signature: Any,  # noqa: ARG002
        data32: bytes,
        opening: Any,  # noqa: ARG002
    ) -> int:
        # the one call whose two answers this file's own tests choose
        # between directly, there being no failing library call behind
        # either: True is data32 == b"\x01" * 32, chosen by the caller
        return 1 if data32 == b"\x01" * 32 else 0

    def secp256k1_ecdsa_anti_exfil_host_commit(
        self,
        ctx: object,  # noqa: ARG002
        output32: Any,
        rand32: bytes,
    ) -> int:
        output32[0:32] = rand32
        return 1

    def secp256k1_ecdsa_anti_exfil_signer_commit(
        self,
        ctx: object,  # noqa: ARG002
        opening: Any,
        msg32: bytes,  # noqa: ARG002
        seckey: bytes,  # noqa: ARG002
        rand_commitment32: bytes,  # noqa: ARG002
    ) -> int:
        opening.data[0] = 3
        opening.data[1:33] = b"\x04" * 32
        return 1

    def secp256k1_anti_exfil_sign(
        self,
        ctx: object,  # noqa: ARG002
        signature: Any,
        msg32: bytes,  # noqa: ARG002
        seckey: bytes,
        host_data32: bytes,  # noqa: ARG002
    ) -> int:
        if seckey == _ZERO_PRVKEY:
            return 0
        signature.data[0:32] = b"\x05" * 32
        signature.data[32:64] = b"\x06" * 32
        return 1

    def secp256k1_anti_exfil_host_verify(  # noqa: PLR0913, PLR0917
        self,
        ctx: object,  # noqa: ARG002
        signature: Any,  # noqa: ARG002
        msg32: bytes,  # noqa: ARG002
        pubkey: Any,  # noqa: ARG002
        host_data32: bytes,
        opening: Any,  # noqa: ARG002
    ) -> int:
        return 1 if host_data32 == b"\x07" * 32 else 0


_FAKE = types.SimpleNamespace(ffi=_fake_ffi, lib=_FakeLib())


def _forget_cached_extension() -> None:
    """Drop whatever `zkp.context.ctx` and `zkp`'s own `ffi`/`lib` cached.

    `pytest-randomly` interleaves this file's `zkp`-marked tests -- which
    build a real context when the extension is built -- with the
    stand-in ones below, in whichever order it draws. `zkp.context.ctx`
    caches itself as a plain attribute on first read, real or fake, so a
    real context built by one ordering is what the *next* test's own
    `_bindings()` would silently reuse without this: called both before
    the stand-in is installed and after it is removed, so neither
    direction of that leak survives one test.

    `vars(...)`, not `hasattr`: `zkp_context.ctx` unset raises
    `ImportError` through its own `__getattr__` wherever the extension is
    not built, which `hasattr` does not tolerate -- it swallows
    `AttributeError` alone, the same trap `tests/all_test.py`'s own
    docstring names. Checking the module's own `__dict__` answers whether
    `ctx` was ever cached without reading it.
    """
    for name in ("ctx", "_illegal_callback", "_error_callback"):
        if name in vars(zkp_context):
            delattr(zkp_context, name)
    zkp_context.ffi = None
    zkp_context.lib = None
    for name in ("ffi", "lib"):
        if name in vars(zkp):
            delattr(zkp, name)


@pytest.fixture(autouse=True)
def _clean_extension_cache() -> Iterator[None]:
    """Guarantee every test here a fresh `zkp.context.ctx` to build.

    Autouse and unconditional, because the leak `_forget_cached_extension`
    guards against reaches both directions and every test in this file:
    one of the `zkp`-marked tests below, run for real where the
    extension is built, would otherwise cache a real context the very
    next test -- a stand-in one, or a plain argument-validation one that
    imports nothing -- inherits; `tests/zkp_test.py`, sharing the same
    module-level cache, is exposed to it too where both files run in one
    session. Clearing before and after is what makes the order
    `pytest-randomly` draws not matter.
    """
    _forget_cached_extension()
    yield
    _forget_cached_extension()


@pytest.fixture
def stand_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install `_FAKE` in place of the real, flagged extension.

    The same substitution `tests/zkp_test.py` drives with its own
    `STAND_IN`, one level lower, and the same `monkeypatch.setattr`
    rather than a hand-saved-and-restored assignment: `zkp._import_extension`
    is what `zkp.context`'s own `ctx` lazily calls, so patching it here is
    what makes `ecdsa_s2c.py`'s own `_bindings()` -- which reads
    `zkp.context.ctx` -- build a working context out of `_FakeLib` instead
    of failing for want of a real build. `_clean_extension_cache` above is
    what the cache is clear for on entry.
    """
    monkeypatch.setattr(zkp, "_import_extension", lambda: _FAKE)


# ---------------------------------------------------------------------------
# Argument validation: no extension needed for any of these, `_bindings()`
# sitting after every octets()/scalar() call in ecdsa_s2c.py rather than
# before it -- proved here by the plain absence of the `stand_in` fixture.
# ---------------------------------------------------------------------------


def test_sign_rejects_a_short_message_hash() -> None:
    """A wrong-length message hash is refused before the extension is used."""
    with pytest.raises(ValueError, match="message hash must be 32 bytes"):
        ecdsa_s2c.sign(bytes(31), 1, bytes(32))


def test_sign_rejects_a_private_key_out_of_range() -> None:
    """A private key that does not fit in 32 bytes is refused the same way."""
    with pytest.raises(ValueError, match="private key must fit in 32 bytes"):
        ecdsa_s2c.sign(bytes(32), 2**256, bytes(32))


def test_sign_rejects_a_non_bytes_s2c_data() -> None:
    """A non-bytes argument raises TypeError, not the extension's own error."""
    with pytest.raises(TypeError, match="s2c_data32 must be bytes"):
        ecdsa_s2c.sign(bytes(32), 1, 12)  # type: ignore[arg-type]


def test_verify_commit_rejects_a_short_signature() -> None:
    """A wrong-length signature is refused before the extension is touched."""
    with pytest.raises(ValueError, match="signature must be 64 bytes"):
        ecdsa_s2c.verify_commit(bytes(63), bytes(32), bytes(33))


def test_verify_commit_rejects_a_short_opening() -> None:
    """A wrong-length opening is refused before the extension is touched."""
    with pytest.raises(ValueError, match="opening must be 33 bytes"):
        ecdsa_s2c.verify_commit(bytes(64), bytes(32), bytes(32))


def test_opening_parse_rejects_the_wrong_length() -> None:
    """A wrong-length opening is refused before the extension is used."""
    with pytest.raises(ValueError, match="opening must be 33 bytes"):
        ecdsa_s2c.opening_parse(bytes(10))


def test_anti_exfil_host_commit_rejects_a_short_argument() -> None:
    """A wrong-length rand32 is refused before the extension is touched."""
    with pytest.raises(ValueError, match="rand32 must be 32 bytes"):
        ecdsa_s2c.anti_exfil_host_commit(bytes(31))


def test_anti_exfil_signer_commit_rejects_a_bool_private_key() -> None:
    """A bool private key is refused, the way scalar() refuses one elsewhere."""
    # a bool is an int in python; scalar() refuses it anyway, the same
    # rejection _scalar_test.py already covers for the primary package
    with pytest.raises(TypeError, match="private key must be bytes or an int"):
        ecdsa_s2c.anti_exfil_signer_commit(bytes(32), True, bytes(32))


def test_anti_exfil_sign_rejects_a_short_host_data() -> None:
    """A wrong-length host_data32 is refused before the extension is touched."""
    with pytest.raises(ValueError, match="host_data32 must be 32 bytes"):
        ecdsa_s2c.anti_exfil_sign(bytes(32), 1, bytes(31))


def test_anti_exfil_host_verify_rejects_a_short_signature() -> None:
    """A wrong-length signature is refused before the extension is touched."""
    # the public key's own length is not checked here at all, the way
    # `keys.parse` does not check it either: only the C call does, which
    # is what test_anti_exfil_host_verify_reports_an_invalid_public_key
    # below drives with the stand-in
    with pytest.raises(ValueError, match="signature must be 64 bytes"):
        ecdsa_s2c.anti_exfil_host_verify(
            bytes(10), bytes(32), bytes(33), bytes(32), bytes(33)
        )


# ---------------------------------------------------------------------------
# Every branch that does reach the extension, driven with the stand-in.
# ---------------------------------------------------------------------------


def test_opening_parse_and_serialize_round_trip(stand_in: None) -> None:  # noqa: ARG001
    """opening_serialize(opening_parse(x)) answers x back, via the stand-in."""
    opening_bytes = bytes([2]) + b"\x09" * 32
    opening = ecdsa_s2c.opening_parse(opening_bytes)
    assert ecdsa_s2c.opening_serialize(opening) == opening_bytes


def test_opening_parse_reports_an_invalid_opening(stand_in: None) -> None:  # noqa: ARG001
    """The stand-in's own refusal reaches the caller as ValueError."""
    with pytest.raises(ValueError, match="invalid opening"):
        ecdsa_s2c.opening_parse(_INVALID_OPENING)


def test_sign_answers_a_signature_and_an_opening(stand_in: None) -> None:  # noqa: ARG001
    """A successful call answers a 64-byte signature and a 33-byte opening."""
    signature, opening = ecdsa_s2c.sign(bytes(32), 1, bytes(32))
    assert len(signature) == 64
    assert len(opening) == 33


def test_sign_reports_an_invalid_private_key(stand_in: None) -> None:  # noqa: ARG001
    """A private key the stand-in refuses reaches the caller as ValueError."""
    with pytest.raises(ValueError, match="invalid private key"):
        ecdsa_s2c.sign(bytes(32), _ZERO_PRVKEY, bytes(32))


def test_verify_commit_true_and_false(stand_in: None) -> None:  # noqa: ARG001
    """Both of verify_commit's answers, chosen by the stand-in on data32."""
    signature, opening = ecdsa_s2c.sign(bytes(32), 1, bytes(32))
    # _FakeLib's own verify_commit answers True for exactly the data32
    # `secp256k1_ecdsa_s2c_sign` above wrote into the signature it faked
    assert ecdsa_s2c.verify_commit(signature, b"\x01" * 32, opening) is True
    assert ecdsa_s2c.verify_commit(signature, bytes(32), opening) is False


def test_verify_commit_reports_an_invalid_signature(stand_in: None) -> None:  # noqa: ARG001
    """An unparsable signature reaches the caller as ValueError."""
    opening_bytes = bytes([2]) + b"\x09" * 32
    with pytest.raises(ValueError, match="invalid compact signature"):
        ecdsa_s2c.verify_commit(_INVALID_SIGNATURE, bytes(32), opening_bytes)


def test_anti_exfil_host_commit(stand_in: None) -> None:  # noqa: ARG001
    """The stand-in's own commitment is what anti_exfil_host_commit answers."""
    rand32 = b"\x08" * 32
    assert ecdsa_s2c.anti_exfil_host_commit(rand32) == rand32


def test_anti_exfil_signer_commit(stand_in: None) -> None:  # noqa: ARG001
    """A successful call answers a 33-byte opening."""
    opening = ecdsa_s2c.anti_exfil_signer_commit(bytes(32), 1, bytes(32))
    assert len(opening) == 33


def test_anti_exfil_sign_answers_a_signature(stand_in: None) -> None:  # noqa: ARG001
    """A successful call answers a 64-byte signature."""
    signature = ecdsa_s2c.anti_exfil_sign(bytes(32), 1, bytes(32))
    assert len(signature) == 64


def test_anti_exfil_sign_reports_an_invalid_private_key(stand_in: None) -> None:  # noqa: ARG001
    """A private key the stand-in refuses reaches the caller as ValueError."""
    with pytest.raises(ValueError, match="invalid private key"):
        ecdsa_s2c.anti_exfil_sign(bytes(32), _ZERO_PRVKEY, bytes(32))


def test_anti_exfil_host_verify_true_and_false(stand_in: None) -> None:  # noqa: ARG001
    """Both of anti_exfil_host_verify's answers, chosen on host_data32."""
    pubkey_bytes = bytes([2]) + b"\x0a" * 32
    signature, opening = ecdsa_s2c.sign(bytes(32), 1, bytes(32))
    assert ecdsa_s2c.anti_exfil_host_verify(
        signature, bytes(32), pubkey_bytes, b"\x07" * 32, opening
    )
    assert not ecdsa_s2c.anti_exfil_host_verify(
        signature, bytes(32), pubkey_bytes, bytes(32), opening
    )


def test_anti_exfil_host_verify_reports_an_invalid_public_key(stand_in: None) -> None:  # noqa: ARG001
    """An unparsable public key reaches the caller as ValueError."""
    signature, opening = ecdsa_s2c.sign(bytes(32), 1, bytes(32))
    with pytest.raises(ValueError, match="invalid public key"):
        ecdsa_s2c.anti_exfil_host_verify(
            signature, bytes(32), _INVALID_PUBKEY, b"\x07" * 32, opening
        )


# ---------------------------------------------------------------------------
# The real thing: secp256k1-zkp's own two fixed vectors, and the protocol
# run end to end. Skipped cleanly wherever BTCLIB_LIBSECP256K1_ZKP was not
# set at build time -- the marker names the requirement for `-m zkp`'s own
# selection, `importorskip` is what actually skips.
# ---------------------------------------------------------------------------

# src/modules/ecdsa_s2c/tests_impl.h's own `ecdsa_s2c_tests`, at the pin
# CHANGELOG.md names: the key of 0x55 repeated, the message of 0x88
# repeated, and for each entry the s2c_data committed to, the opening
# `secp256k1_ecdsa_s2c_sign` answers, and the opening
# `secp256k1_ecdsa_anti_exfil_signer_commit` answers for the same
# s2c_data used as a host commitment
_PRVKEY = bytes([0x55]) * 32
_MESSAGE = bytes([0x88]) * 32
_FIXED_VECTORS = [
    (
        bytes.fromhex(
            "1bf6fb42f41eb876c4d7aa0d67242b00baab99dc2084493e4e63277fa1f77f22"
        ),
        bytes.fromhex(
            "03f030def3188c0f56fcea87435b307643f45dafe22cbc82fd56034fae97417d3a"
        ),
        bytes.fromhex(
            "02df63755d1f3292bffed82986b106497c93b1f8bdc0454b6b0b0a4779c0ef7188"
        ),
    ),
    (
        bytes.fromhex(
            "35199a8fbf84ad6ef69a184c1b19285befbe06e60b6264e6d373893f6855e24a"
        ),
        bytes.fromhex(
            "03901717ce7c7484a2ce1b7dc7403b14e0354971393ec092a7f3e0c8e4e2d2639d"
        ),
        bytes.fromhex(
            "02c04ac7f771e8ebdbf315ff5e58b7fe9516102103500066172c4fac5b20f9e0ea"
        ),
    ),
]


@pytest.mark.zkp
def test_ecdsa_s2c_fixed_vectors() -> None:
    """secp256k1-zkp's own `test_ecdsa_s2c_fixed_vectors`, one wrapper over.

    Pins `sign`'s opening against the real library's own answer, and
    that `verify_commit` accepts what `sign` just produced -- the two
    checks `tests_impl.h` itself makes for each vector.
    """
    pytest.importorskip("_btclib_secp256k1_zkp")
    for s2c_data32, expected_opening, _expected_exfil_opening in _FIXED_VECTORS:
        signature, opening = ecdsa_s2c.sign(_MESSAGE, _PRVKEY, s2c_data32)
        assert opening == expected_opening
        assert ecdsa_s2c.verify_commit(signature, s2c_data32, opening) is True


@pytest.mark.zkp
def test_ecdsa_anti_exfil_signer_commit_fixed_vectors() -> None:
    """secp256k1-zkp's own `test_ecdsa_anti_exfil_signer_commit`, wrapped.

    The signer's original public nonce is a function of the message, the
    key and the host's commitment alone -- `anti_exfil_signer_commit`
    reaching the same opening `sign` would for the same three, is what
    the anti-exfil protocol needs to hold the two to the same nonce.
    """
    pytest.importorskip("_btclib_secp256k1_zkp")
    for s2c_data32, _expected_opening, expected_exfil_opening in _FIXED_VECTORS:
        opening = ecdsa_s2c.anti_exfil_signer_commit(_MESSAGE, _PRVKEY, s2c_data32)
        assert opening == expected_exfil_opening


@pytest.mark.zkp
def test_ecdsa_s2c_sign_rejects_invalid_private_keys() -> None:
    """`secp256k1_ecdsa_s2c_sign` refuses the zero and the overflowing key.

    `tests_impl.h`'s own `test_ecdsa_s2c_sign_verify` checks the same
    two, which the fixed vectors above never exercise -- both of those
    use a private key already known valid.
    """
    pytest.importorskip("_btclib_secp256k1_zkp")
    with pytest.raises(ValueError, match="invalid private key"):
        ecdsa_s2c.sign(_MESSAGE, bytes(32), bytes(32))
    with pytest.raises(ValueError, match="invalid private key"):
        ecdsa_s2c.sign(_MESSAGE, b"\xff" * 32, bytes(32))


@pytest.mark.zkp
def test_anti_exfil_protocol_end_to_end() -> None:
    """The five steps `secp256k1_ecdsa_s2c.h`'s own module docstring lays out.

    Run against real keys and real randomness rather than the fixed
    vectors, which use no host commitment at all: this is what proves
    the four anti-exfil calls compose into the protocol they are for,
    not only that each answers its own fixed input correctly.
    """
    pytest.importorskip("_btclib_secp256k1_zkp")
    prvkey = secrets.token_bytes(32)
    pubkey = keys.pubkey_from_prvkey(prvkey)
    msg = secrets.token_bytes(32)
    rho = secrets.token_bytes(32)

    # 1. host commits to rho
    host_commitment = ecdsa_s2c.anti_exfil_host_commit(rho)
    # 2. signer answers its original public nonce, committing to the
    #    host's commitment
    opening = ecdsa_s2c.anti_exfil_signer_commit(msg, prvkey, host_commitment)
    # 3. host reveals rho (nothing to call: it is passed directly below)
    # 4. signer signs, committing to rho for real
    signature = ecdsa_s2c.anti_exfil_sign(msg, prvkey, rho)
    # 5. host checks the signature's nonce matches the opening from step 2
    assert (
        ecdsa_s2c.anti_exfil_host_verify(signature, msg, pubkey, rho, opening) is True
    )

    # a host verifying against the wrong opening -- one from a different
    # rho -- is the one thing the protocol exists to catch
    other_opening = ecdsa_s2c.anti_exfil_signer_commit(
        msg, prvkey, ecdsa_s2c.anti_exfil_host_commit(secrets.token_bytes(32))
    )
    assert (
        ecdsa_s2c.anti_exfil_host_verify(signature, msg, pubkey, rho, other_opening)
        is False
    )
