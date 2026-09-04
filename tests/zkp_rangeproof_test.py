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


def _install(monkeypatch: pytest.MonkeyPatch) -> None:
    stand_in = types.SimpleNamespace(ffi=_fake_ffi, lib=_FakeLib())
    monkeypatch.setattr(zkp, "_import_extension", lambda: stand_in)


@pytest.fixture(autouse=True)
def _fake_extension(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Install the fake, and clear every cache it and the context build.

    `tests/zkp_generator_test.py`'s own fixture of the same name has the
    reasoning, including for why this is unconditional.
    """
    _install(monkeypatch)
    yield
    for name in ("ctx", "_illegal_callback", "_error_callback"):
        delattr(zkp_context, name)
    zkp_context.ffi = None
    zkp_context.lib = None
    for name in ("ffi", "lib"):
        delattr(zkp, name)


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
