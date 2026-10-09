# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests of btclib_secp256k1.zkp.ecdsa_adaptor.

Three kinds. Argument validation needs no extension: it raises before
`context._bindings()` is read. The stand-in tests drive the wrapper's own
branches through `_FakeLib`, a hand-written substitute for the flagged
extension that computes nothing cryptographic and is trusted for nothing,
as `tests/zkp_ecdsa_s2c_test.py`'s own docstring explains. The `zkp`
tests below them run the real library, and
`tests/zkp_ecdsa_adaptor_vectors_test.py` holds the specification's
vectors.
"""

from __future__ import annotations

import hashlib
import types
from collections.abc import Iterator
from typing import Any

import cffi
import pytest

from btclib_secp256k1 import dsa, keys, zkp
from btclib_secp256k1.zkp import context as zkp_context
from btclib_secp256k1.zkp import ecdsa_adaptor

_fake_ffi = cffi.FFI()
_fake_ffi.cdef("""
typedef struct { unsigned char data[64]; } secp256k1_ecdsa_signature;
typedef struct { unsigned char data[64]; } secp256k1_pubkey;
""")

# bytes `_FakeLib` recognizes as ones libsecp256k1-zkp refuses
_INVALID_PUBKEY = b"\x00" * 33
_PUBKEY = b"\x02" * 33
_INVALID_SIGNATURE = b"\xff" * 64
_INVALID_ADAPTOR_SIGNATURE = b"\xee" * 162
_ZERO_KEY = b"\x00" * 32
# secp256k1's group order, the smallest 32 octets that are not a valid
# private key
_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

_MESSAGE = hashlib.sha256(b"btclib_secp256k1 zkp ecdsa_adaptor").digest()
_SIGNING_KEY = hashlib.sha256(b"signing key").digest()
_DECRYPTION_KEY = hashlib.sha256(b"decryption key").digest()


def _octets(value: Any) -> bytes:
    """Read an argument the wrapper passed as bytes or as a cffi buffer."""
    return value if isinstance(value, bytes) else bytes(_fake_ffi.buffer(value))


class _FakeLib:
    """Just enough of libsecp256k1-zkp to drive `ecdsa_adaptor.py`."""

    def __init__(self) -> None:
        self.recover_buffers: list[Any] = []
        self.ndata: list[Any] = []

    def secp256k1_context_create(self, flags: int) -> object:  # noqa: ARG002
        return object()

    def secp256k1_context_set_illegal_callback(
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
        if inputlen != 33 or input_ == _INVALID_PUBKEY:
            return 0
        pubkey.data[0:inputlen] = input_[0:inputlen]
        return 1

    def secp256k1_ec_pubkey_create(
        self,
        ctx: object,  # noqa: ARG002
        pubkey: Any,
        seckey: bytes,
    ) -> int:
        pubkey.data[0:32] = seckey
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

    def secp256k1_ecdsa_adaptor_encrypt(  # noqa: PLR0913, PLR0917
        self,
        ctx: object,  # noqa: ARG002
        adaptor_sig162: Any,
        seckey32: bytes,
        enckey: Any,  # noqa: ARG002
        msg32: bytes,  # noqa: ARG002
        noncefp: Any,  # noqa: ARG002
        ndata: Any,
    ) -> int:
        if seckey32 == _ZERO_KEY:
            return 0
        self.ndata.append(ndata)
        adaptor_sig162[0:162] = b"\x02" * 162
        return 1

    def secp256k1_ecdsa_adaptor_verify(
        self,
        ctx: object,  # noqa: ARG002
        adaptor_sig162: bytes,
        pubkey: Any,  # noqa: ARG002
        msg32: bytes,  # noqa: ARG002
        enckey: Any,  # noqa: ARG002
    ) -> int:
        return 0 if _octets(adaptor_sig162) == _INVALID_ADAPTOR_SIGNATURE else 1

    def secp256k1_ecdsa_adaptor_decrypt(
        self,
        ctx: object,  # noqa: ARG002
        signature: Any,
        deckey32: bytes,
        adaptor_sig162: bytes,  # noqa: ARG002
    ) -> int:
        if deckey32 == _ZERO_KEY:
            return 0
        signature.data[0:64] = b"\x05" * 64
        return 1

    def secp256k1_ecdsa_adaptor_recover(
        self,
        ctx: object,  # noqa: ARG002
        deckey32: Any,
        signature: Any,  # noqa: ARG002
        adaptor_sig162: bytes,
        enckey: Any,  # noqa: ARG002
    ) -> int:
        # the real function writes a key even where it then refuses it
        deckey32[0:32] = b"\x09" * 32
        self.recover_buffers.append(deckey32)
        return 0 if _octets(adaptor_sig162) == _INVALID_ADAPTOR_SIGNATURE else 1


_FAKE = types.SimpleNamespace(ffi=_fake_ffi, lib=_FakeLib())


def _forget_cached_extension() -> None:
    """Drop whatever `zkp.context` and `zkp` cached of an extension.

    `tests/zkp_ecdsa_s2c_test.py`'s function of the same name has the
    reasoning: the cache is a plain attribute, and a context built by a
    real test must not serve a stand-in one, or the other way round.
    """
    for name in ("ctx", "_illegal_callback"):
        if name in vars(zkp_context):
            delattr(zkp_context, name)
    zkp_context.ffi = None
    zkp_context.lib = None
    for name in ("ffi", "lib"):
        if name in vars(zkp):
            delattr(zkp, name)


@pytest.fixture(autouse=True)
def _clean_extension_cache() -> Iterator[None]:
    """Guarantee every test here a fresh `zkp.context.ctx` to build."""
    _forget_cached_extension()
    yield
    _forget_cached_extension()


@pytest.fixture
def stand_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install `_FAKE` in place of the real, flagged extension."""
    monkeypatch.setattr(zkp, "_import_extension", lambda: _FAKE)
    _FAKE.lib.recover_buffers.clear()
    _FAKE.lib.ndata.clear()


# ---------------------------------------------------------------------------
# Argument validation: no extension, no `stand_in`.
# ---------------------------------------------------------------------------


def test_encrypt_rejects_a_short_message_hash() -> None:
    """A wrong-length message hash is refused before the extension is used."""
    with pytest.raises(ValueError, match="message hash must be 32 bytes"):
        ecdsa_adaptor.encrypt(bytes(31), 1, bytes(33))


def test_encrypt_rejects_a_private_key_out_of_range() -> None:
    """A private key that does not fit in 32 bytes is refused the same way."""
    with pytest.raises(ValueError, match="private key must fit in 32 bytes"):
        ecdsa_adaptor.encrypt(bytes(32), 2**256, bytes(33))


def test_encrypt_rejects_a_short_aux_rand() -> None:
    """Auxiliary randomness of the wrong length is refused, not padded."""
    with pytest.raises(ValueError, match="aux_rand32 must be 32 bytes"):
        ecdsa_adaptor.encrypt(bytes(32), 1, bytes(33), aux_rand32=bytes(31))


def test_verify_rejects_a_short_adaptor_signature() -> None:
    """A wrong-length adaptor signature is refused before the extension."""
    with pytest.raises(ValueError, match="adaptor signature must be 162 bytes"):
        ecdsa_adaptor.verify(bytes(161), bytes(33), bytes(32), bytes(33))


def test_decrypt_rejects_a_bool_decryption_key() -> None:
    """A bool decryption key is refused, as `scalar` refuses one elsewhere."""
    with pytest.raises(TypeError, match="decryption key must be bytes or an int"):
        ecdsa_adaptor.decrypt(True, bytes(162))


def test_recover_rejects_a_short_signature() -> None:
    """A wrong-length signature is refused before the extension is used."""
    with pytest.raises(ValueError, match="signature must be 64 bytes"):
        ecdsa_adaptor.recover(bytes(63), bytes(162), bytes(33))


# ---------------------------------------------------------------------------
# The wrapper's own branches, through the stand-in.
# ---------------------------------------------------------------------------


def test_encrypt_answers_162_bytes(stand_in: None) -> None:  # noqa: ARG001
    """A successful call answers the adaptor signature the library wrote."""
    adaptor_sig = ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, b"\x02" * 33)
    assert adaptor_sig == b"\x02" * 162


def test_encrypt_reports_an_invalid_private_key(stand_in: None) -> None:  # noqa: ARG001
    """A private key the library refuses reaches the caller as ValueError."""
    with pytest.raises(ValueError, match="invalid private key"):
        ecdsa_adaptor.encrypt(_MESSAGE, _ZERO_KEY, b"\x02" * 33)


def test_encrypt_reports_an_invalid_encryption_key(stand_in: None) -> None:  # noqa: ARG001
    """An encryption key the library refuses is a ValueError."""
    with pytest.raises(ValueError, match="invalid encryption key"):
        ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _INVALID_PUBKEY)


def test_encrypt_passes_the_aux_rand_or_null(stand_in: None) -> None:  # noqa: ARG001
    """`aux_rand32` reaches the library as `ndata`, and none as NULL."""
    ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, b"\x02" * 33)
    ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, b"\x02" * 33, aux_rand32=bytes(32))
    null, aux = _FAKE.lib.ndata
    assert null == _fake_ffi.NULL
    assert bytes(aux) == bytes(32)


@pytest.mark.parametrize(
    "call", ["secp256k1_ec_pubkey_create", "secp256k1_ecdsa_adaptor_verify"]
)
def test_encrypt_verifies_by_default(
    monkeypatch: pytest.MonkeyPatch,
    stand_in: None,  # noqa: ARG001
    call: str,
) -> None:
    """An adaptor signature that does not verify is never returned."""
    monkeypatch.setattr(_FAKE.lib, call, lambda *_args: 0)
    with pytest.raises(RuntimeError, match="does not verify"):
        ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, b"\x02" * 33)


def test_encrypt_verify_false_skips_the_check(
    monkeypatch: pytest.MonkeyPatch,
    stand_in: None,  # noqa: ARG001
) -> None:
    """verify=False reaches neither call, both of which would fail."""
    monkeypatch.setattr(_FAKE.lib, "secp256k1_ec_pubkey_create", lambda *_a: 0)
    monkeypatch.setattr(_FAKE.lib, "secp256k1_ecdsa_adaptor_verify", lambda *_a: 0)
    adaptor_sig = ecdsa_adaptor.encrypt(
        _MESSAGE, _SIGNING_KEY, b"\x02" * 33, verify=False
    )
    assert len(adaptor_sig) == 162


def test_verify_true_and_false(stand_in: None) -> None:  # noqa: ARG001
    """Both of verify's answers, chosen by the stand-in."""
    args = (_PUBKEY, _MESSAGE, _PUBKEY)
    assert ecdsa_adaptor.verify(b"\x02" * 162, args[0], args[1], args[2]) is True
    assert (
        ecdsa_adaptor.verify(_INVALID_ADAPTOR_SIGNATURE, args[0], args[1], args[2])
        is False
    )


def test_verify_reports_an_invalid_public_key(stand_in: None) -> None:  # noqa: ARG001
    """A public key the library refuses is a ValueError, not False."""
    with pytest.raises(ValueError, match="invalid public key"):
        ecdsa_adaptor.verify(bytes(162), _INVALID_PUBKEY, _MESSAGE, _PUBKEY)
    with pytest.raises(ValueError, match="invalid encryption key"):
        ecdsa_adaptor.verify(bytes(162), _PUBKEY, _MESSAGE, _INVALID_PUBKEY)


def test_decrypt_answers_a_signature(stand_in: None) -> None:  # noqa: ARG001
    """A successful call answers the 64 bytes the library wrote."""
    assert ecdsa_adaptor.decrypt(_DECRYPTION_KEY, bytes(162)) == b"\x05" * 64


def test_decrypt_reports_an_invalid_key(stand_in: None) -> None:  # noqa: ARG001
    """A decryption key the library refuses reaches the caller as ValueError."""
    with pytest.raises(ValueError, match="invalid decryption key"):
        ecdsa_adaptor.decrypt(_ZERO_KEY, bytes(162))


def test_recover_answers_the_key_or_fills_into(stand_in: None) -> None:  # noqa: ARG001
    """The key the library wrote comes back, and `into` receives it instead."""
    args = (bytes(64), bytes(162), _PUBKEY)
    assert ecdsa_adaptor.recover(*args) == b"\x09" * 32
    into = bytearray(32)
    assert ecdsa_adaptor.recover(*args, into=into) is None
    assert bytes(into) == b"\x09" * 32
    # the buffer the library wrote into is wiped either way
    assert all(_octets(buf) == bytes(32) for buf in _FAKE.lib.recover_buffers)


def test_recover_wipes_a_key_it_refuses(stand_in: None) -> None:  # noqa: ARG001
    """A refused recovery leaves no key in the buffer the library wrote."""
    with pytest.raises(ValueError, match="does not match"):
        ecdsa_adaptor.recover(bytes(64), _INVALID_ADAPTOR_SIGNATURE, _PUBKEY)
    (buffer,) = _FAKE.lib.recover_buffers
    assert _octets(buffer) == bytes(32)


def test_recover_reports_an_invalid_signature_or_key(stand_in: None) -> None:  # noqa: ARG001
    """What the library refuses to parse reaches the caller as ValueError."""
    with pytest.raises(ValueError, match="invalid compact signature"):
        ecdsa_adaptor.recover(_INVALID_SIGNATURE, bytes(162), _PUBKEY)
    with pytest.raises(ValueError, match="invalid encryption key"):
        ecdsa_adaptor.recover(bytes(64), bytes(162), _INVALID_PUBKEY)


# ---------------------------------------------------------------------------
# The real library.
# ---------------------------------------------------------------------------

_SIGNING_PUBKEY = keys.pubkey_from_prvkey(_SIGNING_KEY)
_ENCRYPTION_KEY = keys.pubkey_from_prvkey(_DECRYPTION_KEY)


@pytest.mark.zkp
def test_the_round_trip() -> None:
    """Encrypt, verify, decrypt, verify as ECDSA, and recover the key.

    `dsa.verify` is the primary package's own library, which shares
    nothing with the zkp extension: the decrypted signature is accepted
    by an implementation that never saw the adaptor signature.
    """
    pytest.importorskip("_btclib_secp256k1_zkp")
    adaptor_sig = ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)
    assert len(adaptor_sig) == 162
    assert ecdsa_adaptor.verify(adaptor_sig, _SIGNING_PUBKEY, _MESSAGE, _ENCRYPTION_KEY)
    signature = ecdsa_adaptor.decrypt(_DECRYPTION_KEY, adaptor_sig)
    assert dsa.verify(_MESSAGE, _SIGNING_PUBKEY, signature, compact=True)
    assert ecdsa_adaptor.recover(signature, adaptor_sig, _ENCRYPTION_KEY) == (
        _DECRYPTION_KEY
    )


@pytest.mark.zkp
def test_verify_refuses_what_it_was_not_made_for() -> None:
    """A wrong message, signer or encryption key each fail `verify`."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    adaptor_sig = ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)
    other_pubkey = keys.pubkey_from_prvkey(2)
    assert not ecdsa_adaptor.verify(
        adaptor_sig, _SIGNING_PUBKEY, bytes(32), _ENCRYPTION_KEY
    )
    assert not ecdsa_adaptor.verify(
        adaptor_sig, other_pubkey, _MESSAGE, _ENCRYPTION_KEY
    )
    assert not ecdsa_adaptor.verify(
        adaptor_sig, _SIGNING_PUBKEY, _MESSAGE, other_pubkey
    )
    assert not ecdsa_adaptor.verify(
        bytes(162), _SIGNING_PUBKEY, _MESSAGE, _ENCRYPTION_KEY
    )


@pytest.mark.zkp
def test_the_aux_rand_changes_the_signature_and_nothing_else_does() -> None:
    """Without `aux_rand32` the call is deterministic; with it, keyed on it."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    plain = ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)
    assert plain == ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)
    assert plain == ecdsa_adaptor.encrypt(
        _MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY, verify=False
    )
    aux = ecdsa_adaptor.encrypt(
        _MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY, aux_rand32=bytes(32)
    )
    assert aux != plain
    assert aux == ecdsa_adaptor.encrypt(
        _MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY, aux_rand32=bytes(32)
    )
    assert ecdsa_adaptor.verify(aux, _SIGNING_PUBKEY, _MESSAGE, _ENCRYPTION_KEY)


@pytest.mark.zkp
def test_an_uncompressed_encryption_key_is_the_same_key() -> None:
    """Uncompressed and compressed encryption keys are the same key."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    uncompressed = keys.pubkey_from_prvkey(_DECRYPTION_KEY, compressed=False)
    assert ecdsa_adaptor.encrypt(
        _MESSAGE, _SIGNING_KEY, uncompressed
    ) == ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)


@pytest.mark.zkp
@pytest.mark.parametrize(
    "prvkey",
    [0, _ORDER, b"\xff" * 32],
    ids=["zero", "the order", "above the order"],
)
def test_encrypt_rejects_invalid_private_keys(prvkey: bytes | int) -> None:
    """The library refuses a private key outside [1, n-1]."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    with pytest.raises(ValueError, match="invalid private key"):
        ecdsa_adaptor.encrypt(_MESSAGE, prvkey, _ENCRYPTION_KEY)


@pytest.mark.zkp
def test_encrypt_rejects_an_invalid_encryption_key() -> None:
    """A point not on the curve is refused."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    with pytest.raises(ValueError, match="invalid encryption key"):
        ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, b"\x02" + b"\xff" * 32)


@pytest.mark.zkp
def test_decrypt_rejects_what_the_library_refuses() -> None:
    """A zero decryption key and an unparsable adaptor signature."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    adaptor_sig = ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)
    with pytest.raises(ValueError, match="invalid decryption key"):
        ecdsa_adaptor.decrypt(0, adaptor_sig)
    with pytest.raises(ValueError, match="invalid decryption key"):
        ecdsa_adaptor.decrypt(_DECRYPTION_KEY, bytes(162))


@pytest.mark.zkp
def test_recover_refuses_a_signature_of_another_adaptor() -> None:
    """A signature that does not complete this adaptor signature is refused."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    adaptor_sig = ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)
    other = ecdsa_adaptor.decrypt(
        _DECRYPTION_KEY,
        ecdsa_adaptor.encrypt(bytes(32), _SIGNING_KEY, _ENCRYPTION_KEY),
    )
    with pytest.raises(ValueError, match="does not match"):
        ecdsa_adaptor.recover(other, adaptor_sig, _ENCRYPTION_KEY)


@pytest.mark.zkp
def test_recover_into_a_caller_s_buffer() -> None:
    """With `into` the key lands there, not in a returned `bytes` (#640)."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    adaptor_sig = ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)
    signature = ecdsa_adaptor.decrypt(_DECRYPTION_KEY, adaptor_sig)
    into = bytearray(32)
    args = (signature, adaptor_sig, _ENCRYPTION_KEY)
    assert ecdsa_adaptor.recover(*args, into=into) is None
    assert bytes(into) == _DECRYPTION_KEY
    with pytest.raises(ValueError, match="must be 32 bytes"):
        ecdsa_adaptor.recover(*args, into=bytearray(31))


@pytest.mark.zkp
def test_decrypt_and_recover_read_only_r_x_and_s_prime() -> None:
    """Only R.x and s' of the adaptor signature are read by either.

    The `Raises:` sections say so: an R prefix, R' and the proof can be
    changed and both calls answer as before, while an s' outside
    [1, n-1] or an R.x of zero is refused.
    """
    pytest.importorskip("_btclib_secp256k1_zkp")
    adaptor_sig = ecdsa_adaptor.encrypt(_MESSAGE, _SIGNING_KEY, _ENCRYPTION_KEY)
    signature = ecdsa_adaptor.decrypt(_DECRYPTION_KEY, adaptor_sig)
    altered = (
        b"\x05" + adaptor_sig[1:],  # R prefix
        adaptor_sig[:33] + b"\xff" * 33 + adaptor_sig[66:],  # R'
        adaptor_sig[:130] + b"\xff" * 32,  # the proof's s, above n
    )
    for sig in altered:
        assert ecdsa_adaptor.decrypt(_DECRYPTION_KEY, sig) == signature
        assert ecdsa_adaptor.recover(signature, sig, _ENCRYPTION_KEY) == (
            _DECRYPTION_KEY
        )
    for bad in (
        adaptor_sig[:66] + bytes(32) + adaptor_sig[98:],  # s' = 0
        adaptor_sig[:66] + b"\xff" * 32 + adaptor_sig[98:],  # s' >= n
        adaptor_sig[:1] + bytes(32) + adaptor_sig[33:],  # R.x = 0
    ):
        with pytest.raises(ValueError, match="invalid decryption key"):
            ecdsa_adaptor.decrypt(_DECRYPTION_KEY, bad)
