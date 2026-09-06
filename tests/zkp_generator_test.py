# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`zkp.generator`'s own python logic, driven with a stand-in.

This build carries no `BTCLIB_LIBSECP256K1_ZKP`, so `_btclib_secp256k1_zkp`
is unbuilt and `secp256k1_generator` and `secp256k1_pedersen_commitment`
are types no `ffi` in this process declares: `zkp_test.py`'s own
`STAND_IN` trick, mainline's already-resolved `ffi`/`lib`, only reaches
the calls the two libraries share (context creation, the callbacks), not
these two struct types or any function named for them. So what drives
this module's control flow here is a second, hand-declared `cffi.FFI()`
-- `_FakeFFI` below -- naming only the two structs, and `_FakeLib`, a
plain-python stand-in for every `secp256k1_generator_*` and
`secp256k1_pedersen_*` entry point this module calls, both installed
through the same seam `zkp_test.py` already monkeypatches,
`zkp._import_extension`.

The fakes carry no cryptography: they move bytes as the real calls'
signatures require. Six of them below carry a failure branch at all --
`pedersen_blind_sum`, among others, always succeeds -- and four of
those six answer failure on one shared convention, `FAIL` (a 0xFF byte)
somewhere in the input; the other two, `pedersen_commit` and
`generate_blinded`, instead read an all-zero blind as the refusal, each
named in its own test's docstring rather than here. Both are stricter
there than the library, but not by the same margin: `generate_blinded`
refuses unconditionally what the library always accepts, an all-zero
blind never overflowing the check `secp256k1_generator_generate_blinded`
makes of it, while `pedersen_commit` refuses it regardless of `value`,
where the library only refuses it too when `value` is also zero -- the
point at infinity that combination commits to. For the all-zero blind
each refuses at least as much as the library, which is what the tests
built on them can rely on: a fake refusing more than the library cannot
hide a wrapper bound that is too loose there. Over the rest of the
domain the guarantee does not hold -- both accept a blind at or above
the group order, which `secp256k1_scalar_set_b32`'s own overflow flag,
in `src/modules/generator/main_impl.h` at the pin, makes each of the two
library entry points answer 0 on. `tests/zkp_generator_vectors_test.py`,
marked `zkp`, is where the real library and its own fixed vectors are
exercised instead.
"""

from __future__ import annotations

import types
from collections.abc import Iterator
from typing import Any

import cffi
import pytest

from btclib_secp256k1 import zkp
from btclib_secp256k1.zkp import context as zkp_context
from btclib_secp256k1.zkp import generator as g

FAIL = 0xFF

_fake_ffi = cffi.FFI()
_fake_ffi.cdef("""
typedef struct { unsigned char data[64]; } secp256k1_generator;
typedef struct { unsigned char data[64]; } secp256k1_pedersen_commitment;
""")


def _put(struct: Any, payload: bytes) -> None:
    """Copy `payload` into the front of a fake struct's own `data`."""
    buf = _fake_ffi.buffer(struct.data)
    buf[: len(payload)] = payload


def _get(struct: Any, n: int) -> bytes:
    """Read the front `n` bytes of a fake struct's own `data`."""
    return bytes(_fake_ffi.buffer(struct.data))[:n]


class _FakeLib:
    """A pure-python stand-in for every generator/pedersen entry point."""

    def __init__(self) -> None:
        self.secp256k1_generator_h = _fake_ffi.new("secp256k1_generator *")
        _put(self.secp256k1_generator_h, bytes([0x0B]) + bytes(range(1, 33)))

    # the four context-management calls btclib_secp256k1.zkp.context's own
    # __getattr__ makes to build `ctx`: not shared with mainline's real
    # lib the way zkp_test.py's own STAND_IN reuses it for, because this
    # stand-in is not mainline's lib at all -- what it takes as `context`
    # is never read, only ever passed back to a generator/pedersen call
    # below, which ignores it just the same
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

    def secp256k1_generator_serialize(self, _ctx: Any, output: Any, gen: Any) -> int:
        _fake_ffi.buffer(output)[:] = _get(gen, 33)
        return 1

    def secp256k1_generator_generate(self, _ctx: Any, gen: Any, seed32: bytes) -> int:
        if seed32[0] == FAIL:
            return 0
        _put(gen, bytes([0x0A]) + bytes(seed32))
        return 1

    def secp256k1_generator_generate_blinded(
        self, _ctx: Any, gen: Any, seed32: bytes, blind32: bytes
    ) -> int:
        if blind32 == bytes(32):
            return 0
        _put(gen, bytes([0x0B]) + bytes(seed32))
        return 1

    def secp256k1_pedersen_commitment_parse(
        self, _ctx: Any, commit: Any, input33: bytes
    ) -> int:
        if input33[0] == FAIL:
            return 0
        _put(commit, bytes(input33))
        return 1

    def secp256k1_pedersen_commitment_serialize(
        self, _ctx: Any, output: Any, commit: Any
    ) -> int:
        _fake_ffi.buffer(output)[:] = _get(commit, 33)
        return 1

    def secp256k1_pedersen_commit(
        self, _ctx: Any, commit: Any, blind: bytes, value: int, gen: Any
    ) -> int:
        if blind == bytes(32):
            return 0
        payload = (
            bytes([0x08])
            + bytes(blind[:16])
            + value.to_bytes(8, "big")
            + bytes(_fake_ffi.buffer(gen.data)[0:8])
        )
        _put(commit, payload)
        return 1

    def secp256k1_pedersen_blind_sum(
        self, _ctx: Any, blind_out: Any, blinds: Any, n: int, npositive: int
    ) -> int:
        total = 0
        for i in range(n):
            value = int.from_bytes(_fake_ffi.buffer(blinds[i], 32), "big")
            total = total + value if i < npositive else total - value
        total %= 2**256
        _fake_ffi.buffer(blind_out)[:] = total.to_bytes(32, "big")
        return 1

    def secp256k1_pedersen_verify_tally(
        self, _ctx: Any, commits: Any, pcnt: int, ncommits: Any, ncnt: int
    ) -> int:
        pos = sum(sum(_get(commits[i], 33)) for i in range(pcnt))
        neg = sum(sum(_get(ncommits[i], 33)) for i in range(ncnt))
        return int(pos == neg)

    def secp256k1_pedersen_blind_generator_blind_sum(
        self,
        _ctx: Any,
        _value: Any,
        generator_blind: Any,
        blinding_factor: Any,
        n_total: int,
        _n_inputs: int,
    ) -> int:
        # never called with n_total == 0: the wrapper's own
        # `0 <= n_inputs < n_total` refuses every call the library's
        # ARG_CHECK(n_total > n_inputs) would too, src/modules/generator
        # /main_impl.h at the pin -- strict, the `0, 0` case included,
        # not the special case the header's own NULL-array prose could
        # be misread as
        if _fake_ffi.buffer(generator_blind[0], 1)[:] == bytes([FAIL]):
            return 0
        _fake_ffi.buffer(blinding_factor[n_total - 1], 32)[:] = bytes(range(32))
        return 1


def _install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route `zkp._import_extension` to the fake ffi/lib pair above."""
    stand_in = types.SimpleNamespace(ffi=_fake_ffi, lib=_FakeLib())
    monkeypatch.setattr(zkp, "_import_extension", lambda: stand_in)


def _forget_cached_extension() -> None:
    """Drop whatever `zkp` and `zkp.context` cached of the extension.

    `zkp.ffi`, `zkp.lib` and `zkp.context`'s own `ctx` are written into
    their module globals on first read and stay there, so `context._bindings()`
    finds a plain attribute and the fake above is never consulted:
    whichever library answered first is the one the test runs against.
    Under a flagged build the other zkp test modules read the real one,
    and `pytest-randomly` draws the order.

    Removed with `pop` on each module's own `__dict__` rather than
    tested for with `hasattr`: `zkp.ffi` unset raises `ImportError` out
    of its own `__getattr__` instead of `AttributeError`, which
    `hasattr` does not answer False for. `zkp.context`'s `ffi` and
    `lib` are module-scope names whose default is `None`, so they are
    put back to that rather than removed.
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

    Every test in this file calls a wrapper function and every one of
    those calls `context._bindings()` first, so each needs the fake and leaves a
    cache of its own behind. Clearing on the way in as well as on the
    way out is what makes the order `pytest-randomly` draws not matter
    (btclib-org/btclib-secp256k1#646);
    `tests/zkp_ecdsa_s2c_test.py`'s own `_clean_extension_cache` is the
    same fixture for the same reason.
    """
    _forget_cached_extension()
    _install(monkeypatch)
    yield
    _forget_cached_extension()


def test_generator_parse_and_serialize_round_trip() -> None:
    """`parse` and `serialize` are inverse over a well-formed generator."""
    payload = bytes([0x0B]) + bytes(range(1, 33))
    assert g.serialize(g.parse(payload)) == payload


def test_generator_parse_rejects_the_wrong_length() -> None:
    """A generator that is not 33 bytes is refused before parsing."""
    with pytest.raises(ValueError, match="generator must be 33 bytes"):
        g.parse(b"\x0b" * 10)


def test_generator_parse_rejects_what_the_library_refuses() -> None:
    """A 33-byte string that is not a valid generator is refused."""
    with pytest.raises(ValueError, match="invalid generator"):
        g.parse(bytes([FAIL]) * 33)


def test_h_is_the_static_generator() -> None:
    """`h()` serializes the fake's own `secp256k1_generator_h`."""
    assert g.h() == bytes([0x0B]) + bytes(range(1, 33))


def test_generate() -> None:
    """`generate` returns a 33-byte generator."""
    gen = g.generate(b"\x01" * 32)
    assert len(gen) == 33


def test_generate_rejects_what_the_library_refuses() -> None:
    """The library's own refusal of a seed becomes a `RuntimeError`."""
    with pytest.raises(RuntimeError, match="generator generation failed"):
        g.generate(bytes([FAIL]) + bytes(31))


def test_generate_blinded() -> None:
    """`generate_blinded` returns a 33-byte generator."""
    gen = g.generate_blinded(b"\x01" * 32, 5)
    assert len(gen) == 33


def test_generate_blinded_rejects_an_out_of_range_blind() -> None:
    """An all-zero `blind32` is the fake's own library-refusal marker."""
    with pytest.raises(ValueError, match="invalid blind32"):
        g.generate_blinded(b"\x01" * 32, bytes(32))


def test_pedersen_commitment_parse_and_serialize_round_trip() -> None:
    """`pedersen_commitment_parse`/`_serialize` are inverse, well-formed."""
    payload = bytes([0x08]) + bytes(range(1, 33))
    assert (
        g.pedersen_commitment_serialize(g.pedersen_commitment_parse(payload)) == payload
    )


def test_pedersen_commitment_parse_rejects_the_wrong_length() -> None:
    """A commitment that is not 33 bytes is refused before parsing."""
    with pytest.raises(ValueError, match="Pedersen commitment must be 33 bytes"):
        g.pedersen_commitment_parse(b"\x08" * 10)


def test_pedersen_commitment_parse_rejects_what_the_library_refuses() -> None:
    """A 33-byte string that is not a valid commitment is refused."""
    with pytest.raises(ValueError, match="invalid Pedersen commitment"):
        g.pedersen_commitment_parse(bytes([FAIL]) * 33)


def test_pedersen_commit_with_the_default_generator() -> None:
    """`pedersen_commit` with no `gen_bytes` commits under `h()`."""
    commit = g.pedersen_commit(1, 42)
    assert len(commit) == 33


def test_pedersen_commit_with_an_explicit_generator() -> None:
    """`pedersen_commit` accepts a caller-supplied generator."""
    gen_bytes = g.generate(b"\x02" * 32)
    commit = g.pedersen_commit(1, 42, gen_bytes)
    assert len(commit) == 33


def test_pedersen_commit_rejects_a_value_out_of_range() -> None:
    """A value that does not fit in 8 bytes is refused."""
    with pytest.raises(ValueError, match=r"value must be an int in \[0, 2\*\*64\)"):
        g.pedersen_commit(1, 2**64)


def test_pedersen_commit_rejects_a_bool_value() -> None:
    """A bool is not accepted where an int is asked for."""
    with pytest.raises(ValueError, match=r"value must be an int"):
        g.pedersen_commit(1, True)


def test_pedersen_commit_rejects_a_non_int_value() -> None:
    """A value that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="value must be an int, not str"):
        g.pedersen_commit(1, "42")  # type: ignore[arg-type]


def test_pedersen_commit_rejects_an_invalid_generator() -> None:
    """An invalid `gen_bytes` is refused before the library commits to it."""
    with pytest.raises(ValueError, match="invalid gen"):
        g.pedersen_commit(1, 42, bytes([FAIL]) * 33)


def test_pedersen_commit_rejects_what_the_library_refuses() -> None:
    """An all-zero blind is what the fake reads as the library's own refusal."""
    with pytest.raises(RuntimeError, match="Pedersen commitment failed"):
        g.pedersen_commit(bytes(32), 42)


def test_pedersen_blind_sum() -> None:
    """`pedersen_blind_sum` returns a 32-byte sum."""
    total = g.pedersen_blind_sum([1, 2, 3], 2)
    assert len(total) == 32


def test_pedersen_blind_sum_of_nothing() -> None:
    """An empty sequence sums to 32 zero bytes."""
    total = g.pedersen_blind_sum([], 0)
    assert total == bytes(32)


def test_pedersen_blind_sum_rejects_an_out_of_range_npositive() -> None:
    """`npositive` outside `[0, len(blinds)]` is refused."""
    with pytest.raises(ValueError, match=r"npositive must be in \[0, 2\]"):
        g.pedersen_blind_sum([1, 2], 3)


def test_pedersen_blind_sum_rejects_a_non_int_npositive() -> None:
    """An `npositive` that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="the npositive must be an int, not str"):
        g.pedersen_blind_sum([1, 2], "1")  # type: ignore[arg-type]


def test_pedersen_blind_sum_names_the_bad_element() -> None:
    """A malformed blinding factor is named by its position in the sequence."""
    with pytest.raises(ValueError, match="blinding factor at index 1"):
        g.pedersen_blind_sum([1, b"\x01" * 10], 1)


def test_pedersen_verify_tally_agrees() -> None:
    """A commitment tallies against itself."""
    commit = g.pedersen_commit(1, 42)
    assert g.pedersen_verify_tally([commit], [commit]) is True


def test_pedersen_verify_tally_disagrees() -> None:
    """Two different commitments do not tally."""
    a = g.pedersen_commit(1, 1)
    b = g.pedersen_commit(2, 2)
    assert g.pedersen_verify_tally([a], [b]) is False


def test_pedersen_verify_tally_of_nothing() -> None:
    """Two empty sequences tally, vacuously."""
    assert g.pedersen_verify_tally([], []) is True


def test_pedersen_verify_tally_names_the_bad_commitment() -> None:
    """A malformed negative commitment is named by its position."""
    with pytest.raises(ValueError, match="negative commitment at index 0"):
        g.pedersen_verify_tally([], [b"\x08" * 10])


def test_pedersen_blind_generator_blind_sum() -> None:
    """The corrected last blinding factor is 32 bytes."""
    last = g.pedersen_blind_generator_blind_sum([10, 20], [1, 2], [3, 4], 1)
    assert len(last) == 32


def test_pedersen_blind_generator_blind_sum_rejects_the_empty_case() -> None:
    """`n_inputs == len(values)` is refused even at `0, 0`.

    The library's own `ARG_CHECK(n_total > n_inputs)` is strict, so the
    fully empty call is illegal rather than a trivial success.
    """
    with pytest.raises(ValueError, match=r"n_inputs must be in \[0, len\(values\)\)"):
        g.pedersen_blind_generator_blind_sum([], [], [], 0)


def test_pedersen_blind_generator_blind_sum_rejects_mismatched_lengths() -> None:
    """The three sequences must be the same length."""
    with pytest.raises(ValueError, match="must match in length"):
        g.pedersen_blind_generator_blind_sum([10], [1, 2], [3], 0)


def test_pedersen_blind_generator_blind_sum_rejects_an_out_of_range_n_inputs() -> None:
    """`n_inputs` outside `[0, len(values))` is refused."""
    with pytest.raises(ValueError, match=r"n_inputs must be in \[0, len\(values\)\)"):
        g.pedersen_blind_generator_blind_sum([10], [1], [3], 2)


def test_pedersen_blind_generator_blind_sum_rejects_a_non_int_n_inputs() -> None:
    """An `n_inputs` that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="n_inputs must be an int, not str"):
        g.pedersen_blind_generator_blind_sum([10], [1], [3], "0")  # type: ignore[arg-type]


def test_pedersen_blind_generator_blind_sum_rejects_a_value_out_of_range() -> None:
    """A value that does not fit in 8 bytes is named by its position."""
    with pytest.raises(
        ValueError, match=r"value at index 0 must be an int in \[0, 2\*\*64\)"
    ):
        g.pedersen_blind_generator_blind_sum([2**64], [1], [3], 0)


def test_pedersen_blind_generator_blind_sum_rejects_a_bool_value() -> None:
    """A bool is not accepted where an int is asked for.

    `ffi.new("uint64_t[1]", [True])` answers the value 1, so nothing
    below this check refuses one: the correction would be computed for a
    value the caller did not name.
    """
    with pytest.raises(ValueError, match="value at index 0 must be an int"):
        g.pedersen_blind_generator_blind_sum([True], [1], [3], 0)


def test_pedersen_blind_generator_blind_sum_rejects_a_non_int_value() -> None:
    """A value that is not an int at all is a `TypeError`."""
    with pytest.raises(TypeError, match="value at index 0 must be an int, not str"):
        g.pedersen_blind_generator_blind_sum(["10"], [1], [3], 0)  # type: ignore[list-item]


def test_pedersen_blind_generator_blind_sum_names_the_bad_generator_blind() -> None:
    """A malformed generator blind is named by its position."""
    with pytest.raises(ValueError, match="generator blind at index 0"):
        g.pedersen_blind_generator_blind_sum([10], [b"\x01" * 10], [3], 0)


def test_pedersen_blind_generator_blind_sum_names_the_bad_blinding_factor() -> None:
    """A malformed blinding factor is named by its position."""
    with pytest.raises(ValueError, match="blinding factor at index 0"):
        g.pedersen_blind_generator_blind_sum([10], [1], [b"\x01" * 10], 0)


def test_pedersen_blind_generator_blind_sum_rejects_what_the_library_refuses() -> None:
    """A generator blind starting with the fake's own failure marker."""
    with pytest.raises(RuntimeError, match="blinding factor correction failed"):
        g.pedersen_blind_generator_blind_sum([10], [bytes([FAIL]) + bytes(31)], [3], 0)
