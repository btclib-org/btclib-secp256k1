# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`zkp.rangeproof`'s own python logic, driven with a stand-in.

The same shape `tests/zkp_generator_test.py` uses, and its own module
docstring has the reasoning: a hand-declared `cffi.FFI()` and a
plain-python `_FakeLib`, installed through `zkp._import_extension`. This
one also answers `secp256k1_generator_parse`,
`secp256k1_pedersen_commitment_parse` and `secp256k1_generator_h`,
because `rangeproof.py` calls into `generator.py` for the commitment and
the generator each of `verify`, `rewind` and `sign` takes -- `max_size`
and `info` take neither.
`tests/zkp_rangeproof_vectors_test.py`, marked `zkp`, is where the real
library and zkp's own fixed vectors are exercised instead.
"""

from __future__ import annotations

import inspect
import types
from collections.abc import Iterator
from typing import Any

import cffi
import pytest

from btclib_secp256k1 import zkp
from btclib_secp256k1.zkp import context as zkp_context
from btclib_secp256k1.zkp import rangeproof as r

FAIL = 0xFF

_fake_ffi = cffi.FFI()
_fake_ffi.cdef("""
typedef struct { unsigned char data[64]; } secp256k1_generator;
typedef struct { unsigned char data[64]; } secp256k1_pedersen_commitment;
typedef struct { unsigned char data[64]; } secp256k1_pubkey;
""")


def _put(struct: Any, payload: bytes) -> None:
    _fake_ffi.buffer(struct.data)[: len(payload)] = payload


def _get(struct: Any, n: int) -> bytes:
    return bytes(_fake_ffi.buffer(struct.data))[:n]


class _FakeLib:
    """A pure-python stand-in for every call `rangeproof.py` reaches."""

    def __init__(self) -> None:
        self.secp256k1_generator_h = _fake_ffi.new("secp256k1_generator *")
        _put(self.secp256k1_generator_h, bytes([0x0B]) + bytes(range(1, 33)))

    def secp256k1_context_create(self, _flags: int) -> object:
        return object()

    def secp256k1_context_set_illegal_callback(
        self, _context: Any, _callback: Any, _data: Any
    ) -> None:
        return None

    def secp256k1_context_set_error_callback(
        self, _context: Any, _callback: Any, _data: Any
    ) -> None:
        return None

    def secp256k1_context_randomize(self, _context: Any, _seed32: bytes) -> int:
        return 1

    def secp256k1_generator_parse(self, _ctx: Any, gen: Any, input33: bytes) -> int:
        if input33[0] == FAIL:
            return 0
        _put(gen, bytes(input33))
        return 1

    def secp256k1_pedersen_commitment_parse(
        self, _ctx: Any, commit: Any, input33: bytes
    ) -> int:
        if input33[0] == FAIL:
            return 0
        _put(commit, bytes(input33))
        return 1

    def secp256k1_rangeproof_max_size(
        self, _ctx: Any, max_value: int, min_bits: int
    ) -> int:
        return 64 + min_bits + (max_value % 32)

    def secp256k1_rangeproof_verify(
        self,
        _ctx: Any,
        min_value: Any,
        max_value: Any,
        commit: Any,
        proof: bytes,
        _plen: int,
        _extra_commit: Any,
        _extra_commit_len: int,
        _gen: Any,
    ) -> int:
        if not proof or proof[0] == FAIL or _get(commit, 1)[0] == FAIL:
            return 0
        min_value[0] = 0
        max_value[0] = 63
        return 1

    def secp256k1_rangeproof_rewind(
        self,
        _ctx: Any,
        blind_out: Any,
        value_out: Any,
        message_out: Any,
        outlen: Any,
        nonce: bytes,
        min_value: Any,
        max_value: Any,
        _commit: Any,
        proof: bytes,
        _plen: int,
        _extra_commit: Any,
        _extra_commit_len: int,
        _gen: Any,
    ) -> int:
        if not proof or proof[0] == FAIL or nonce[0] == FAIL:
            return 0
        _fake_ffi.buffer(blind_out, 32)[:] = bytes(range(32))
        value_out[0] = 42
        message = b"hello"
        _fake_ffi.buffer(message_out, r.MAX_MESSAGE_LEN)[: len(message)] = message
        outlen[0] = len(message)
        min_value[0] = 0
        max_value[0] = 63
        return 1

    def secp256k1_rangeproof_sign(
        self,
        _ctx: Any,
        proof: Any,
        plen: Any,
        min_value: int,
        _commit: Any,
        blind: bytes,
        _nonce: bytes,
        exp: int,
        min_bits: int,
        value: int,
        _message: Any,
        _msg_len: int,
        _extra_commit: Any,
        _extra_commit_len: int,
        _gen: Any,
    ) -> int:
        # the one constraint the header states outright: value must fit
        # in [0, 2**63) once min_value or exp asks for a bounded proof
        if (min_value or exp) and value >= 2**63:
            return 0
        if blind == bytes(32):
            return 0
        payload = bytes([min_bits & 0xFF]) + value.to_bytes(8, "big")
        buffer_len = int(plen[0])
        _fake_ffi.buffer(proof, buffer_len)[: len(payload)] = payload
        plen[0] = len(payload)
        return 1

    def secp256k1_rangeproof_info(
        self,
        _ctx: Any,
        exp: Any,
        mantissa: Any,
        min_value: Any,
        max_value: Any,
        proof: bytes,
        _plen: int,
    ) -> int:
        if not proof or proof[0] == FAIL:
            return 0
        exp[0] = 0
        mantissa[0] = 6
        min_value[0] = 0
        max_value[0] = 63
        return 1

    def secp256k1_ec_pubkey_parse(
        self, _ctx: Any, pubkey: Any, input_: bytes, inputlen: int
    ) -> int:
        if inputlen != 33 or input_[0] == FAIL:
            return 0
        _put(pubkey, bytes(input_))
        return 1

    def secp256k1_borromean_verify(
        self,
        _ctx: Any,
        e0: bytes,
        _s: bytes,
        _m: bytes,
        _mlen: int,
        _pubkeys: Any,
        _n_pubkeys: int,
        _rsizes: Any,
        _nrings: int,
    ) -> int:
        # e0's own first byte is this fake's one sentinel, the same shape
        # every other call in this class answers a failure through: never
        # the ring shape, which `borromean_verify`'s own Python-side
        # checks already refuse before any of this is called
        return 0 if e0[0] == FAIL else 1


def _install(monkeypatch: pytest.MonkeyPatch) -> None:
    stand_in = types.SimpleNamespace(ffi=_fake_ffi, lib=_FakeLib())
    monkeypatch.setattr(zkp, "_import_extension", lambda: stand_in)


def _forget_cached_extension() -> None:
    """Drop whatever `zkp` and `zkp.context` cached of the extension.

    `tests/zkp_generator_test.py`'s own function of the same name has
    the reasoning.
    """
    for name in ("ctx", "_illegal_callback", "_error_callback"):
        vars(zkp_context).pop(name, None)
    zkp_context.ffi = None
    zkp_context.lib = None
    for name in ("ffi", "lib"):
        vars(zkp).pop(name, None)


@pytest.fixture(autouse=True)
def _fake_extension(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Install the fake, over caches cleared before it and after it.

    `tests/zkp_generator_test.py`'s own fixture of the same name has the
    reasoning, including for why the clearing runs on the way in
    (btclib-org/btclib-secp256k1#646).
    """
    _forget_cached_extension()
    _install(monkeypatch)
    yield
    _forget_cached_extension()


COMMIT = bytes([0x08]) + bytes(range(1, 33))
PROOF = bytes([0x01, 0x02, 0x03])
FAIL_PROOF = bytes([FAIL, 0x02, 0x03])
FAIL_COMMIT = bytes([FAIL]) + bytes(range(1, 33))


def test_max_size() -> None:
    """`max_size` answers what the fake computes, not the header's formula.

    The real `secp256k1_rangeproof_max_size` (`main_impl.h` at the pin)
    is a mantissa/rings/pubs computation this fake does not reproduce;
    what this asserts is only that the wrapper passes `max_value` and
    `min_bits` through and returns the library's answer unchanged.
    `tests/zkp_rangeproof_vectors_test.py`'s own
    `test_max_size_bounds_a_real_proof`, marked `zkp`, is where the real
    formula is exercised, against the real library.
    """
    assert r.max_size(100, 0) == 64 + 0 + 100 % 32


def test_max_size_rejects_an_out_of_range_max_value() -> None:
    """A `max_value` that does not fit in 8 bytes is refused."""
    with pytest.raises(ValueError, match=r"max_value must be an int in \[0, 2\*\*64\)"):
        r.max_size(2**64, 0)


def test_max_size_rejects_a_bool_max_value() -> None:
    """A bool is not accepted where an int is asked for.

    `True` clears every test a `[0, 2**64)` bound makes on its own, so
    without this one `max_size` answers the bound for 1 and says nothing
    about having been asked for something else.
    """
    with pytest.raises(ValueError, match="max_value must be an int"):
        r.max_size(True, 0)


def test_max_size_rejects_a_non_int_max_value() -> None:
    """A `max_value` that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="max_value must be an int, not str"):
        r.max_size("100", 0)  # type: ignore[arg-type]


def test_max_size_rejects_an_out_of_range_min_bits() -> None:
    """A `min_bits` outside `[0, 64]` is refused."""
    with pytest.raises(ValueError, match=r"min_bits must be in \[0, 64\]"):
        r.max_size(100, 65)


def test_max_size_rejects_a_non_int_min_bits() -> None:
    """A `min_bits` that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="the min_bits must be an int, not str"):
        r.max_size(100, "0")  # type: ignore[arg-type]


def test_verify_succeeds() -> None:
    """`verify` returns the proof's own range for a well-formed proof."""
    assert r.verify(COMMIT, PROOF) == (0, 63)


def test_verify_fails() -> None:
    """A proof the fake reads as invalid makes `verify` answer None."""
    assert r.verify(COMMIT, FAIL_PROOF) is None


def test_verify_with_an_explicit_generator() -> None:
    """`verify` accepts a caller-supplied generator."""
    gen_bytes = bytes([0x0B]) + bytes(range(1, 33))
    assert r.verify(COMMIT, PROOF, gen_bytes=gen_bytes) == (0, 63)


def test_verify_with_extra_commit() -> None:
    """`verify` accepts the same `extra_commit` the proof was signed over."""
    assert r.verify(COMMIT, PROOF, extra_commit=b"context") == (0, 63)


def test_verify_rejects_an_invalid_commitment() -> None:
    """An invalid commitment is refused before the library sees the proof."""
    with pytest.raises(ValueError, match="invalid commitment"):
        r.verify(FAIL_COMMIT, PROOF)


def test_verify_rejects_an_invalid_generator() -> None:
    """An invalid generator is refused before the library sees the proof."""
    with pytest.raises(ValueError, match="invalid gen"):
        r.verify(COMMIT, PROOF, gen_bytes=bytes([FAIL]) * 33)


def test_rewind_succeeds() -> None:
    """`rewind` recovers the blind, value, message and range the fake set."""
    blind, value, message, min_value, max_value = r.rewind(COMMIT, PROOF, b"\x01" * 32)
    assert blind == bytes(range(32))
    assert value == 42
    assert message == b"hello"
    assert (min_value, max_value) == (0, 63)


def test_rewind_fails() -> None:
    """A proof the fake reads as invalid makes `rewind` raise."""
    with pytest.raises(ValueError, match="rewind failed"):
        r.rewind(COMMIT, PROOF, bytes([FAIL]) * 32)


def test_rewind_rejects_a_short_nonce() -> None:
    """A nonce that is not 32 bytes is refused before the library sees it."""
    with pytest.raises(ValueError, match="nonce must be 32 bytes"):
        r.rewind(COMMIT, PROOF, b"\x01" * 10)


def test_sign_succeeds() -> None:
    """`sign` returns a proof encoding the value the fake reads back."""
    proof = r.sign(COMMIT, 1, b"\x01" * 32, 42)
    assert proof[9:] == b""
    assert int.from_bytes(proof[1:9], "big") == 42


def test_sign_with_a_message_and_extra_commit() -> None:
    """`sign` accepts a message and an extra commit alongside the value."""
    proof = r.sign(COMMIT, 1, b"\x01" * 32, 42, message=b"hi", extra_commit=b"ctx")
    assert int.from_bytes(proof[1:9], "big") == 42


def test_sign_with_an_explicit_generator() -> None:
    """`sign` accepts a caller-supplied generator."""
    gen_bytes = bytes([0x0B]) + bytes(range(1, 33))
    proof = r.sign(COMMIT, 1, b"\x01" * 32, 42, gen_bytes=gen_bytes)
    assert int.from_bytes(proof[1:9], "big") == 42


def test_sign_rejects_an_out_of_range_value() -> None:
    """A value that does not fit in 8 bytes is refused."""
    with pytest.raises(ValueError, match=r"value must be an int in \[0, 2\*\*64\)"):
        r.sign(COMMIT, 1, b"\x01" * 32, 2**64)


def test_sign_rejects_a_bool_value() -> None:
    """A bool is not accepted where an int is asked for."""
    with pytest.raises(ValueError, match="value must be an int"):
        r.sign(COMMIT, 1, b"\x01" * 32, True)


def test_sign_rejects_a_non_int_value() -> None:
    """A value that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="value must be an int, not str"):
        r.sign(COMMIT, 1, b"\x01" * 32, "42")  # type: ignore[arg-type]


def test_sign_rejects_an_out_of_range_min_value() -> None:
    """A `min_value` that does not fit in 8 bytes is refused."""
    with pytest.raises(ValueError, match=r"min_value must be an int in \[0, 2\*\*64\)"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, min_value=2**64)


def test_sign_rejects_a_non_int_min_value() -> None:
    """A `min_value` that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="min_value must be an int, not str"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, min_value="0")  # type: ignore[arg-type]


def test_sign_rejects_a_bool_min_value() -> None:
    """A bool is not accepted where `min_value` asks for an int.

    `True` would otherwise pass as `min_value = 1` and silently prove a
    different range than the caller asked for.
    """
    with pytest.raises(ValueError, match="min_value must be an int"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, min_value=True)


def test_sign_rejects_an_out_of_range_exp() -> None:
    """An `exp` outside `[-1, 18]` is refused."""
    with pytest.raises(ValueError, match=r"exp must be in \[-1, 18\]"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, exp=19)


def test_sign_rejects_a_non_int_exp() -> None:
    """An `exp` that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="exp must be an int, not str"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, exp="0")  # type: ignore[arg-type]


def test_sign_rejects_an_out_of_range_min_bits() -> None:
    """A `min_bits` outside `[0, 64]` is refused."""
    with pytest.raises(ValueError, match=r"min_bits must be in \[0, 64\]"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, min_bits=65)


def test_sign_rejects_a_non_int_min_bits() -> None:
    """A `min_bits` that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="the min_bits must be an int, not str"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, min_bits="0")  # type: ignore[arg-type]


def test_sign_rejects_a_message_too_long() -> None:
    """A message longer than `MAX_MESSAGE_LEN` is refused."""
    with pytest.raises(ValueError, match="message must be at most"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, message=b"\x00" * (r.MAX_MESSAGE_LEN + 1))


def test_sign_rejects_what_the_library_refuses() -> None:
    """An all-zero blind is what the fake reads as the library's own refusal."""
    with pytest.raises(ValueError, match="rangeproof signing failed"):
        r.sign(COMMIT, bytes(32), b"\x01" * 32, 42)


def test_sign_rejects_a_bounded_value_that_does_not_fit_in_63_bits() -> None:
    """A bounded value of 2**63 or more is the library's own refusal.

    "If nonzero, value must be in [0, 2**63)", the header's own words for
    `min_value`: this is the library's own constraint, not one the
    wrapper's own argument checks reject first.
    """
    with pytest.raises(ValueError, match="rangeproof signing failed"):
        r.sign(COMMIT, 1, b"\x01" * 32, 2**63, min_value=1)


def test_info() -> None:
    """`info` decodes the exponent, mantissa and range a proof carries."""
    assert r.info(PROOF) == (0, 6, 0, 63)


def test_info_rejects_an_undecodable_proof() -> None:
    """A proof the fake reads as invalid makes `info` raise."""
    with pytest.raises(ValueError, match="invalid proof"):
        r.info(FAIL_PROOF)


PUBKEY = bytes([0x02]) + bytes(range(1, 33))
FAIL_PUBKEY = bytes([FAIL]) + bytes(range(1, 33))


def test_borromean_verify_succeeds() -> None:
    """A well-formed call the fake reads as verifying answers True."""
    e0 = bytes(32)
    s = bytes(32) * 3
    assert r.borromean_verify(e0, s, b"msg", [PUBKEY, PUBKEY, PUBKEY], [2, 1]) is True


def test_borromean_verify_fails() -> None:
    """A signature the fake reads as not verifying answers False, not a raise.

    `e0`'s own first byte is this file's `FAIL` sentinel -- the same
    "well-formed but does not verify" case a scalar at or above the
    curve order is, in the real library.
    """
    e0 = bytes([FAIL]) + bytes(31)
    s = bytes(32) * 3
    assert r.borromean_verify(e0, s, b"msg", [PUBKEY, PUBKEY, PUBKEY], [2, 1]) is False


def test_borromean_verify_rejects_a_short_e0() -> None:
    """A wrong-length e0 is refused before the extension is touched."""
    with pytest.raises(ValueError, match="e0 must be 32 bytes"):
        r.borromean_verify(bytes(31), bytes(32), b"msg", [PUBKEY], [1])


def test_borromean_verify_rejects_a_wrong_length_s() -> None:
    """`s` must be exactly 32 bytes per pubkey, ring-major."""
    with pytest.raises(ValueError, match="s must be 64 bytes"):
        r.borromean_verify(bytes(32), bytes(32), b"msg", [PUBKEY, PUBKEY], [2])


def test_borromean_verify_rejects_an_invalid_pubkey() -> None:
    """An unparsable public key is refused before the library sees anything."""
    with pytest.raises(ValueError, match="invalid public key at index 0"):
        r.borromean_verify(bytes(32), bytes(32), b"msg", [FAIL_PUBKEY], [1])


def test_borromean_verify_rejects_a_mismatched_ring_shape() -> None:
    """`sum(rsizes) != len(pubkeys)` is the ring-shape ARG_CHECK, refused first.

    `secp256k1_borromean_verify` itself would refuse this same shape
    through its illegal callback (btclib-org/btclib-secp256k1#828's own
    issue body has the ARG_CHECK); this wrapper never reaches it, the
    fake's own `secp256k1_borromean_verify` above having no branch for
    it at all.
    """
    with pytest.raises(ValueError, match=r"sum\(rsizes\) must equal len\(pubkeys\)"):
        r.borromean_verify(bytes(32), bytes(32) * 2, b"msg", [PUBKEY, PUBKEY], [1])


def test_borromean_verify_rejects_an_empty_pubkeys() -> None:
    """`n_pubkeys` must be at least 1, the header's own ARG_CHECK."""
    with pytest.raises(ValueError, match="pubkeys must hold between 1 and 128"):
        r.borromean_verify(bytes(32), b"", b"msg", [], [])


def test_borromean_verify_rejects_too_many_pubkeys() -> None:
    """`n_pubkeys` must be at most 128, the header's own ARG_CHECK."""
    with pytest.raises(ValueError, match="pubkeys must hold between 1 and 128"):
        r.borromean_verify(
            bytes(32), bytes(32) * 129, b"msg", [PUBKEY] * 129, [1] * 129
        )


def test_borromean_verify_rejects_too_many_rings() -> None:
    """`nrings` must be at most 32, the header's own ARG_CHECK."""
    with pytest.raises(ValueError, match="rsizes must hold between 1 and 32"):
        r.borromean_verify(bytes(32), bytes(32) * 33, b"msg", [PUBKEY] * 33, [1] * 33)


# the ends of a `uint64_t`, and one step past each: what every amount the
# module takes is held to. Past either end cffi's own answer is an
# `OverflowError`, for a negative number and for one too big alike, and
# the documented refusal is a `ValueError`. `2**64 + 1` is there as well
# as `2**64` because a check that stops at `!= 2**64` refuses the one and
# lets the other through
OUTSIDE_A_UINT64 = [-1, 2**64, 2**64 + 1]
INSIDE_A_UINT64 = [0, 2**63, 2**64 - 1]


@pytest.mark.parametrize("max_value", OUTSIDE_A_UINT64)
def test_max_size_refuses_a_max_value_outside_a_uint64(max_value: int) -> None:
    """A `max_value` outside [0, 2**64) is a `ValueError`, whichever side."""
    with pytest.raises(ValueError, match=r"max_value must be an int in \[0, 2\*\*64\)"):
        r.max_size(max_value, 0)


@pytest.mark.parametrize("value", OUTSIDE_A_UINT64)
def test_sign_refuses_a_value_outside_a_uint64(value: int) -> None:
    """A `value` that is not in [0, 2**64) is a `ValueError`, whichever side."""
    with pytest.raises(ValueError, match=r"value must be an int in \[0, 2\*\*64\)"):
        r.sign(COMMIT, 1, b"\x01" * 32, value)


@pytest.mark.parametrize("value", INSIDE_A_UINT64)
def test_sign_takes_a_value_up_to_the_last_uint64(value: int) -> None:
    """The first and the last value a `uint64_t` holds are signed for."""
    proof = r.sign(COMMIT, 1, b"\x01" * 32, value)
    assert int.from_bytes(proof[1:9], "big") == value


@pytest.mark.parametrize("min_value", OUTSIDE_A_UINT64)
def test_sign_refuses_a_min_value_outside_a_uint64(min_value: int) -> None:
    """A `min_value` outside [0, 2**64) is a `ValueError`, whichever side."""
    with pytest.raises(ValueError, match=r"min_value must be an int in \[0, 2\*\*64\)"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, min_value=min_value)


@pytest.mark.parametrize("exp", [-2, 19])
def test_sign_refuses_an_exp_either_side_of_the_range(exp: int) -> None:
    """`exp` is in [-1, 18], and -2 is as much out of it as 19 is."""
    with pytest.raises(ValueError, match=r"exp must be in \[-1, 18\]"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, exp=exp)


@pytest.mark.parametrize("exp", [-1, 18])
def test_sign_takes_both_ends_of_the_exp_range(exp: int) -> None:
    """The smallest and the largest `exp` the header documents are signed."""
    assert r.sign(COMMIT, 1, b"\x01" * 32, 42, exp=exp)


def test_sign_takes_a_message_of_3968_bytes_and_no_more() -> None:
    """`MAX_MESSAGE_LEN` is 3968, `SECP256K1_RANGEPROOF_MAX_MESSAGE_LEN`.

    The literal is the one `secp256k1_rangeproof.h` defines, which
    `MAX_MESSAGE_LEN` restates. `tests/zkp_rangeproof_vectors_test.py`
    has the real library take exactly this much.
    """
    assert r.MAX_MESSAGE_LEN == 3968
    assert r.sign(COMMIT, 1, b"\x01" * 32, 42, message=bytes(3968))
    with pytest.raises(ValueError, match="message must be at most 3968 bytes"):
        r.sign(COMMIT, 1, b"\x01" * 32, 42, message=bytes(3969))


def test_sign_takes_everything_after_the_value_by_keyword() -> None:
    """`min_value`, `exp`, `min_bits`, `message` and the rest are keyword-only.

    The header's own tuning knobs, as the comment above `sign` calls
    them: passed by position, `min_value` would be an argument nothing at
    the call site names.
    """
    parameters = inspect.signature(r.sign).parameters
    names = list(parameters)
    tuning = names[names.index("value") + 1 :]
    assert tuning
    for name in tuning:
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY, name


def test_borromean_verify_refuses_more_in_the_rings_than_there_are_keys() -> None:
    """`sum(rsizes)` above `len(pubkeys)` is refused as much as below it.

    The other direction of the ring-shape check above. The real library
    refuses it too, through its illegal callback, and answers a bare 0
    -- a `False`, which reads as a signature that does not verify; the
    check here is what makes it a `ValueError`.
    """
    with pytest.raises(ValueError, match=r"sum\(rsizes\) must equal len\(pubkeys\)"):
        r.borromean_verify(bytes(32), bytes(32), b"msg", [PUBKEY], [2])


def test_borromean_verify_rejects_no_rings_over_some_keys() -> None:
    """An empty `rsizes` is a ring-count refusal, not a sum that is off."""
    with pytest.raises(ValueError, match="rsizes must hold between 1 and 32"):
        r.borromean_verify(bytes(32), bytes(32), b"msg", [PUBKEY], [])
