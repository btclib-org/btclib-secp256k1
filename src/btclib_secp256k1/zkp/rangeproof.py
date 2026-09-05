# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`secp256k1_rangeproof.h`: proving a commitment's value lies in a range.

A Borromean-ring-signature variant of the Back-Maxwell range proofs from
the Confidential Assets paper, over a `zkp.generator.pedersen_commit`
commitment rather than the value itself: `sign` authors a proof that the
committed value lies in `[min_value, min_value + 2**mantissa)`, `verify`
checks one, and `rewind` recovers what `sign`'s own author embedded --
the value, the blinding factor and up to `MAX_MESSAGE_LEN` bytes of
message -- from a proof made with a matching nonce. `info` reads the
public part of a proof without either.

`MAX_MESSAGE_LEN` is the one constant the header itself fixes
(`SECP256K1_RANGEPROOF_MAX_MESSAGE_LEN`); the other size this module
needs, the worst-case proof buffer, has no such `#define` -- it is what
`secp256k1_rangeproof_max_size` answers, and `sign` asks the library for
it rather than carrying a copy of the 5134 the header's own comment and
zkp's `tests_impl.h` state as today's answer, which is not a promise
about tomorrow's. `MAX_MESSAGE_LEN` cannot be asked of the library the
same way: nothing in `secp256k1_rangeproof.h` exposes it as a function,
and cffi's own cdef generation (`generate_def`'s `gcc -P -E`) preprocesses
every `#define` away before `lib` is built from what remains, so no
runtime call could read it even if this module wanted one to. The
literal is what stands in its place, and a submodule bump that moved it
would go unnoticed by anything here.

Every function here needs `BTCLIB_LIBSECP256K1_ZKP`'s extension, and none
of them reaches for it at import time, for the reason
`btclib_secp256k1.zkp.generator`'s own module docstring gives.
"""

from __future__ import annotations

from typing import Any

from btclib_secp256k1 import BytesLike, CData
from btclib_secp256k1._scalar import in_range, octets, scalar

from . import generator

__all__ = ["MAX_MESSAGE_LEN", "info", "max_size", "rewind", "sign", "verify"]

# SECP256K1_RANGEPROOF_MAX_MESSAGE_LEN, the one constant the header
# itself defines
MAX_MESSAGE_LEN = 3968


def _handles() -> tuple[Any, Any, Any]:
    """Return this subpackage's `ffi`, `lib` and `ctx`, deferred to first use.

    The same seam as `zkp.generator._handles`, and its docstring has the
    reasoning.

    Returns:
        `ffi`, `lib` and `ctx` of the flagged secp256k1-zkp extension.

    Raises:
        ImportError: propagated from `btclib_secp256k1.zkp`, if the
            extension was never built.
    """
    from . import ffi, lib  # noqa: PLC0415
    from .context import ctx  # noqa: PLC0415

    return ffi, lib, ctx


def _gen(lib: Any, gen_bytes: BytesLike | None) -> CData:
    """Resolve the generator argument every function below takes.

    `h()` by default.

    Args:
        lib: this subpackage's own `lib`.
        gen_bytes: the generator, 33 bytes, or None for the commitment's
            usual `generator.h()`.

    Returns:
        The parsed libsecp256k1-zkp generator object.

    Raises:
        ValueError: if `gen_bytes` is given and is not a valid generator.
    """
    if gen_bytes is None:
        return lib.secp256k1_generator_h
    return generator.parse(gen_bytes, "gen")


def max_size(max_value: int, min_bits: int) -> int:
    """Return an upper bound on the size of a rangeproof with these parameters.

    An actual proof may be smaller: in particular this always
    overestimates the size of a single-value proof (`exp=-1`), and a
    `min_value` of 0 usually, but not always, gives a proof 8 bytes
    smaller than a nonzero one would.

    Args:
        max_value: the largest value that might be passed as `value` to
            `sign`. `2**64 - 1` gives the size of the largest possible
            proof, which is what `sign` itself asks for.
        min_bits: the `min_bits` that will be passed to `sign`.

    Returns:
        The upper bound, in bytes.

    Raises:
        TypeError: if `max_value` or `min_bits` is not an int.
        ValueError: if `max_value` is a bool or does not fit in 8 bytes,
            or if `min_bits` is out of [0, 64].
    """
    _ffi, lib, ctx = _handles()
    if not isinstance(max_value, int):
        raise TypeError(f"max_value must be an int, not {type(max_value).__name__}")
    if isinstance(max_value, bool) or not 0 <= max_value < 2**64:
        raise ValueError("max_value must be an int in [0, 2**64)")
    min_bits = in_range(min_bits, "min_bits", 64)
    return int(lib.secp256k1_rangeproof_max_size(ctx, max_value, min_bits))


def verify(
    commit_bytes: BytesLike,
    proof: BytesLike,
    extra_commit: BytesLike = b"",
    gen_bytes: BytesLike | None = None,
) -> tuple[int, int] | None:
    """Verify that a committed value lies within the range the proof states.

    Args:
        commit_bytes: the Pedersen commitment being proved, 33 bytes.
        proof: the proof.
        extra_commit: additional data the proof's signature covers, as
            it was passed to `sign`.
        gen_bytes: the generator the commitment was made under, 33
            bytes, or None for `zkp.generator.h()`.

    Returns:
        `(min_value, max_value)`, the range the proof establishes for
        the committed value, or None where the proof does not verify --
        a verdict rather than an exception, `(0, 2**64 - 1)` being a
        range a proof can legitimately establish and so not usable as a
        failure sentinel.

    Raises:
        ValueError: if `commit_bytes` or `gen_bytes` is not a valid
            33-byte generator or commitment.
    """
    ffi, lib, ctx = _handles()
    commit = generator.pedersen_commitment_parse(commit_bytes, "commitment")
    proof_bytes = octets(proof, "proof")
    extra_bytes = octets(extra_commit, "extra_commit")
    gen = _gen(lib, gen_bytes)
    min_value = ffi.new("uint64_t *")
    max_value = ffi.new("uint64_t *")
    ok = lib.secp256k1_rangeproof_verify(
        ctx,
        min_value,
        max_value,
        commit,
        proof_bytes,
        len(proof_bytes),
        extra_bytes or ffi.NULL,
        len(extra_bytes),
        gen,
    )
    if not ok:
        return None
    return int(min_value[0]), int(max_value[0])


def rewind(
    commit_bytes: BytesLike,
    proof: BytesLike,
    nonce: BytesLike,
    extra_commit: BytesLike = b"",
    gen_bytes: BytesLike | None = None,
) -> tuple[bytes, int, bytes, int, int]:
    """Verify a proof and recover what its author embedded in it.

    Args:
        commit_bytes: the Pedersen commitment being proved, 33 bytes.
        proof: the proof.
        nonce: the 32-byte secret nonce `sign` was called with -- knowing
            it is what makes this call, rather than `verify`, possible.
        extra_commit: additional data the proof's signature covers, as
            it was passed to `sign`.
        gen_bytes: the generator the commitment was made under, 33
            bytes, or None for `zkp.generator.h()`.

    Returns:
        `(blind, value, message, min_value, max_value)`: the 32-byte
        blinding factor and the exact value `sign` committed to, the
        message bytes it embedded (trailing zeros beyond what it wrote
        included, up to `MAX_MESSAGE_LEN`), and the range the proof
        establishes -- the same `min_value`/`max_value` `verify` answers.

    Raises:
        ValueError: if `commit_bytes` or `gen_bytes` is not a valid
            33-byte generator or commitment, if `nonce` is not 32 bytes,
            or if the proof does not verify or the rewind fails --
            libsecp256k1-zkp reports both through the same return code.
    """
    ffi, lib, ctx = _handles()
    commit = generator.pedersen_commitment_parse(commit_bytes, "commitment")
    proof_bytes = octets(proof, "proof")
    nonce_bytes = octets(nonce, "nonce", 32)
    extra_bytes = octets(extra_commit, "extra_commit")
    gen = _gen(lib, gen_bytes)

    # char, not unsigned char: ffi.unpack of the latter answers a list of
    # ints rather than bytes, and both of these are read back below
    blind_out = ffi.new(f"char[{generator._BLIND_SIZE}]")
    value_out = ffi.new("uint64_t *")
    message_out = ffi.new(f"char[{MAX_MESSAGE_LEN}]")
    outlen = ffi.new("size_t *", MAX_MESSAGE_LEN)
    min_value = ffi.new("uint64_t *")
    max_value = ffi.new("uint64_t *")

    ok = lib.secp256k1_rangeproof_rewind(
        ctx,
        blind_out,
        value_out,
        message_out,
        outlen,
        nonce_bytes,
        min_value,
        max_value,
        commit,
        proof_bytes,
        len(proof_bytes),
        extra_bytes or ffi.NULL,
        len(extra_bytes),
        gen,
    )
    if not ok:
        raise ValueError("proof does not verify, or rewind failed")
    return (
        ffi.unpack(blind_out, 32),
        int(value_out[0]),
        ffi.unpack(message_out, int(outlen[0])),
        int(min_value[0]),
        int(max_value[0]),
    )


# ten arguments, where PLR0913 allows five. `dsa.sign`'s own such comment
# has the reasoning for keeping them rather than folding them into an
# options object: six of the ten are keyword-only, `commit_bytes`,
# `blind`, `nonce` and `value` being what every call needs and the rest
# being the header's own tuning knobs, none of which groups with another
def sign(  # noqa: PLR0913
    commit_bytes: BytesLike,
    blind: BytesLike | int,
    nonce: BytesLike,
    value: int,
    *,
    min_value: int = 0,
    exp: int = 0,
    min_bits: int = 0,
    message: BytesLike = b"",
    extra_commit: BytesLike = b"",
    gen_bytes: BytesLike | None = None,
) -> bytes:
    """Prove that a committed value lies within a range.

    Args:
        commit_bytes: the Pedersen commitment being proved, as
            `zkp.generator.pedersen_commit` built it from `blind`,
            `value` and `gen_bytes`.
        blind: the 32-byte blinding factor `pedersen_commit` used, or an
            int below 2**256. May be all-zeros only where `min_bits` is
            at least 3, a side effect of the underlying construction
            rather than a deliberate choice.
        nonce: 32 bytes that must be unique to this call and never
            reused, and kept secret except from parties allowed to
            `rewind` the proof: anyone who learns it recovers `value`
            and `blind`, and reusing it across two proofs may expose
            `blind` even to a party that never learns it.
        value: the value being committed to, an int in [0, 2**64). If
            `min_value` or `exp` is nonzero, `value` must be in
            [0, 2**63) so the proven range does not wrap past 2**64.
        min_value: the minimum value the proof states the commitment can
            have. If nonzero, `value` must be in [0, 2**63) for the same
            reason given above.
        exp: the base-10 exponent below which digits are made public, in
            [-1, 18] -- a larger value makes a smaller proof at the cost
            of revealing more of it; -1 reveals `value` itself, and 0 is
            the most private. If nonzero, `value` must be in [0, 2**63)
            for the same reason given above.
        min_bits: how many bits of the value to keep private, in
            [0, 64] -- 0 asks for the library's own minimal choice.
        message: up to `MAX_MESSAGE_LEN` bytes to embed, recoverable by
            `rewind` with the same `nonce`.
        extra_commit: additional data for the proof's signature to
            cover; `verify` and `rewind` need the same bytes back.
        gen_bytes: the generator `commit_bytes` was committed under, 33
            bytes, or None for `zkp.generator.h()`.

    Returns:
        The proof.

    Raises:
        TypeError: if `value`, `min_value`, `exp` or `min_bits` is not
            an int.
        ValueError: if `commit_bytes` or `gen_bytes` is not a valid
            33-byte generator or commitment, if `blind` or `nonce` is
            not 32 bytes or `blind` does not fit in them, if `value` or
            `min_value` is a bool or does not fit in 8 bytes, if `exp`
            or `min_bits` is out of range, if `message` is longer than
            `MAX_MESSAGE_LEN`, or if libsecp256k1-zkp refuses the call --
            which also reports the "one in 2**100" failure the header's
            own docstring names, indistinguishably from a bad argument
            that reached this far.
    """
    ffi, lib, ctx = _handles()
    commit = generator.pedersen_commitment_parse(commit_bytes, "commitment")
    blind_bytes = scalar(blind, "blind")
    nonce_bytes = octets(nonce, "nonce", 32)
    if not isinstance(value, int):
        raise TypeError(f"value must be an int, not {type(value).__name__}")
    if isinstance(value, bool) or not 0 <= value < 2**64:
        raise ValueError("value must be an int in [0, 2**64)")
    if not isinstance(min_value, int):
        raise TypeError(f"min_value must be an int, not {type(min_value).__name__}")
    if isinstance(min_value, bool) or not 0 <= min_value < 2**64:
        raise ValueError("min_value must be an int in [0, 2**64)")
    if not isinstance(exp, int):
        raise TypeError(f"exp must be an int, not {type(exp).__name__}")
    if not -1 <= exp <= 18:
        raise ValueError("exp must be in [-1, 18]")
    min_bits = in_range(min_bits, "min_bits", 64)
    message_bytes = octets(message, "message")
    if len(message_bytes) > MAX_MESSAGE_LEN:
        raise ValueError(f"message must be at most {MAX_MESSAGE_LEN} bytes")
    extra_bytes = octets(extra_commit, "extra_commit")
    gen = _gen(lib, gen_bytes)

    buffer_size = int(lib.secp256k1_rangeproof_max_size(ctx, 2**64 - 1, 0))
    # char, not unsigned char, for the reason blind_out and message_out
    # above are: this is read back with ffi.unpack too
    proof = ffi.new(f"char[{buffer_size}]")
    plen = ffi.new("size_t *", buffer_size)
    ok = lib.secp256k1_rangeproof_sign(
        ctx,
        proof,
        plen,
        min_value,
        commit,
        blind_bytes,
        nonce_bytes,
        exp,
        min_bits,
        value,
        message_bytes or ffi.NULL,
        len(message_bytes),
        extra_bytes or ffi.NULL,
        len(extra_bytes),
        gen,
    )
    if not ok:
        raise ValueError("rangeproof signing failed")
    return bytes(ffi.unpack(proof, int(plen[0])))


def info(proof: BytesLike) -> tuple[int, int, int, int]:
    """Extract the public parameters of a rangeproof, without verifying it.

    Args:
        proof: the proof.

    Returns:
        `(exp, mantissa, min_value, max_value)`: the exponent `sign` was
        called with (-1 meaning the value is public), the number of bits
        the proof covers, and the range it states -- the same
        `min_value`/`max_value` `verify` answers, without checking that
        the commitment matches.

    Raises:
        ValueError: if the proof cannot be decoded.
    """
    ffi, lib, ctx = _handles()
    proof_bytes = octets(proof, "proof")
    exp = ffi.new("int *")
    mantissa = ffi.new("int *")
    min_value = ffi.new("uint64_t *")
    max_value = ffi.new("uint64_t *")
    if not lib.secp256k1_rangeproof_info(
        ctx, exp, mantissa, min_value, max_value, proof_bytes, len(proof_bytes)
    ):
        raise ValueError("invalid proof")
    return int(exp[0]), int(mantissa[0]), int(min_value[0]), int(max_value[0])
