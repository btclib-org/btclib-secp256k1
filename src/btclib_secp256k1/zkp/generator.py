# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`secp256k1_generator.h`: generators, and Pedersen commitments.

A generator is a second base point, unrelated to `G` by any known
discrete logarithm, that a Pedersen commitment `x*G + v*gen` blinds a
value `v` under. `h()` is the static one the header itself fixes and
`generate`/`generate_blinded` are the two ways to make another; `parse`
and `serialize` are the octet boundary for either, and
`pedersen_commitment_parse`/`pedersen_commitment_serialize` are the same
boundary for the 33-byte commitment `pedersen_commit` builds.

`ISS 608 <https://github.com/btclib-org/btclib-secp256k1/issues/608>`_'s
own body names a downstream consumer already pinned against the
x-coordinate of `secp256k1_generator_h`, independently of this library:
`h()` is what turns that pin into an assertion against the library
itself rather than against a copied literal.

Every function here needs `BTCLIB_LIBSECP256K1_ZKP`'s extension, and none
of them reaches for it at import time: `_handles` is where each defers
to it, on the first call rather than on `import
btclib_secp256k1.zkp.generator`, the same reason
`btclib_secp256k1.zkp.context`'s own `__getattr__` docstring gives for
deferring its own `ctx` -- so that importing that module never reaches
for the extension on its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from btclib_secp256k1 import BytesLike, CData
from btclib_secp256k1._scalar import in_range, octets, scalar

__all__ = [
    "generate",
    "generate_blinded",
    "h",
    "parse",
    "pedersen_blind_generator_blind_sum",
    "pedersen_blind_sum",
    "pedersen_commit",
    "pedersen_commitment_parse",
    "pedersen_commitment_serialize",
    "pedersen_verify_tally",
    "serialize",
]

_GENERATOR_SIZE = 33
_COMMITMENT_SIZE = 33
_BLIND_SIZE = 32


def _handles() -> tuple[Any, Any, Any]:
    """Return this subpackage's `ffi`, `lib` and `ctx`, deferred to first use.

    Every public function below calls this rather than importing `ffi`,
    `lib` or `ctx` at module scope, which is what keeps `import
    btclib_secp256k1.zkp.generator` free of the flagged extension --
    only a call into one of these functions reaches for it, and the
    module docstring says why that boundary is drawn here.

    Returns:
        `ffi`, `lib` and `ctx` of the flagged secp256k1-zkp extension.

    Raises:
        ImportError: propagated from `btclib_secp256k1.zkp`, if the
            extension was never built.
    """
    from . import ffi, lib  # noqa: PLC0415
    from .context import ctx  # noqa: PLC0415

    return ffi, lib, ctx


def _ptr_array(ffi: Any, cdecl: str, items: Sequence[CData]) -> CData:
    """Build the pointer array some calls require to be non-NULL.

    Never `btclib_secp256k1._cdata.array`: that helper's own `ffi.new`
    is mainline's, which has no `secp256k1_generator` or
    `secp256k1_pedersen_commitment` in its cdef at all -- an
    "undefined type name" `ffi.error`, measured rather than assumed, for
    any array of either struct built through it. This subpackage's own
    `ffi`, `_handles` already resolved, is what every array here goes
    through instead, whichever of the two element types it holds.

    Unlike `_array_or_null` below, this never answers NULL for an empty
    sequence: `secp256k1_pedersen_blind_sum`'s own header marks its
    `blinds` array "(cannot be NULL)" with no exception for a zero
    count, unlike `secp256k1_pedersen_verify_tally`'s `commits`, which
    explicitly allows NULL where its count is zero. `ffi.new` of a
    zero-length array is a real, non-NULL pointer to nothing, which is
    what this needs.

    Args:
        ffi: this subpackage's own `ffi`, `_handles` already resolved.
        cdecl: the cffi declaration of the array type.
        items: the objects to point at, which the caller keeps alive.

    Returns:
        The array, never NULL.
    """
    return ffi.new(cdecl, list(items))


def _array_or_null(ffi: Any, cdecl: str, items: Sequence[CData]) -> CData:
    """Build the pointer array some calls require NULL for, when empty.

    The counterpart of `_ptr_array` above, and its own docstring has the
    reason neither of these is `btclib_secp256k1._cdata.array`: the same
    NULL-for-empty behaviour that helper gives, through this
    subpackage's own `ffi` rather than mainline's.

    Args:
        ffi: this subpackage's own `ffi`, `_handles` already resolved.
        cdecl: the cffi declaration of the array type.
        items: the objects to point at, which the caller keeps alive.

    Returns:
        The array, or NULL where there is nothing to point at.
    """
    return ffi.new(cdecl, list(items)) if items else ffi.NULL


def parse(generator_bytes: BytesLike, name: str = "generator") -> CData:
    """Parse a 33-byte generator into its internal representation.

    Args:
        generator_bytes: the generator, 33 bytes, as `serialize`,
            `generate`, `generate_blinded` or `h` answered it.
        name: what the generator is, as the exception should call it.

    Returns:
        The libsecp256k1-zkp generator object.

    Raises:
        ValueError: if it is not 33 bytes, or not a valid generator.
    """
    ffi, lib, ctx = _handles()
    generator_bytes = octets(generator_bytes, name, _GENERATOR_SIZE)
    gen = ffi.new("secp256k1_generator *")
    if not lib.secp256k1_generator_parse(ctx, gen, generator_bytes):
        raise ValueError(f"invalid {name}")
    return gen


def serialize(gen: CData) -> bytes:
    """Serialize a parsed generator.

    Args:
        gen: the libsecp256k1-zkp generator object, as `parse` returns.

    Returns:
        Its 33 bytes.
    """
    ffi, lib, ctx = _handles()
    output = ffi.new(f"char[{_GENERATOR_SIZE}]")
    lib.secp256k1_generator_serialize(ctx, output, gen)
    return bytes(ffi.unpack(output, _GENERATOR_SIZE))


def h() -> bytes:
    """Return the static generator the header calls `h`, serialized.

    "Static constant generator 'h' maintained for historical reasons",
    in the header's own words: `secp256k1_generator_h`, read once rather
    than parsed from a literal, is what lets a caller pin their own copy
    of it against this library instead of against a copy of the bytes.

    Returns:
        Its 33 bytes.
    """
    _ffi, lib, _ctx = _handles()
    return serialize(lib.secp256k1_generator_h)


def generate(seed32: BytesLike) -> bytes:
    """Generate a generator, distributed uniformly over the curve.

    The result has no known discrete logarithm with respect to any other
    generator this produces, or to the base generator `G`.

    Args:
        seed32: 32 bytes seeding the generator.

    Returns:
        Its 33-byte serialization.

    Raises:
        ValueError: if `seed32` is not 32 bytes.
        RuntimeError: if libsecp256k1-zkp refuses the seed, which is
            "highly unlikely" in the header's own words and cannot
            happen for a seed this package generated.
    """
    ffi, lib, ctx = _handles()
    seed_bytes = octets(seed32, "seed32", 32)
    gen = ffi.new("secp256k1_generator *")
    if not lib.secp256k1_generator_generate(ctx, gen, seed_bytes):
        raise RuntimeError("generator generation failed")
    return serialize(gen)


def generate_blinded(seed32: BytesLike, blind32: BytesLike | int) -> bytes:
    """Generate a generator, blinded by a secret tweak.

    Equivalent to `generate` followed by a plain EC tweak of the result
    read as a public key, and back -- computed directly instead, in one
    call.

    Args:
        seed32: 32 bytes seeding the generator.
        blind32: the secret value to blind it with, 32 bytes or an int
            below 2**256.

    Returns:
        Its 33-byte serialization.

    Raises:
        ValueError: if `seed32` is not 32 bytes, if `blind32` is not 32
            bytes or does not fit in them, if `blind32` is out of range,
            or if libsecp256k1-zkp refuses the seed -- "highly unlikely"
            in the header's own words and cannot happen for a seed this
            package generated. The two failures share one return code
            and are not told apart.
    """
    ffi, lib, ctx = _handles()
    seed_bytes = octets(seed32, "seed32", 32)
    blind_bytes = scalar(blind32, "blind32")
    gen = ffi.new("secp256k1_generator *")
    if not lib.secp256k1_generator_generate_blinded(ctx, gen, seed_bytes, blind_bytes):
        raise ValueError("invalid blind32, or seed generation failed")
    return serialize(gen)


def pedersen_commitment_parse(
    commitment_bytes: BytesLike, name: str = "Pedersen commitment"
) -> CData:
    """Parse a 33-byte Pedersen commitment into its internal representation.

    Args:
        commitment_bytes: the commitment, 33 bytes, as
            `pedersen_commitment_serialize` or `pedersen_commit`
            answered it.
        name: what the commitment is, as the exception should call it.

    Returns:
        The libsecp256k1-zkp Pedersen commitment object.

    Raises:
        ValueError: if it is not 33 bytes, or not a valid commitment.
    """
    ffi, lib, ctx = _handles()
    commitment_bytes = octets(commitment_bytes, name, _COMMITMENT_SIZE)
    commit = ffi.new("secp256k1_pedersen_commitment *")
    if not lib.secp256k1_pedersen_commitment_parse(ctx, commit, commitment_bytes):
        raise ValueError(f"invalid {name}")
    return commit


def pedersen_commitment_serialize(commit: CData) -> bytes:
    """Serialize a parsed Pedersen commitment.

    Args:
        commit: the libsecp256k1-zkp commitment object, as
            `pedersen_commitment_parse` returns.

    Returns:
        Its 33 bytes.
    """
    ffi, lib, ctx = _handles()
    output = ffi.new(f"char[{_COMMITMENT_SIZE}]")
    lib.secp256k1_pedersen_commitment_serialize(ctx, output, commit)
    return bytes(ffi.unpack(output, _COMMITMENT_SIZE))


def pedersen_commit(
    blind: BytesLike | int, value: int, gen_bytes: BytesLike | None = None
) -> bytes:
    """Commit to a value, `blind*G + value*gen`.

    Args:
        blind: the blinding factor, 32 bytes or an int below 2**256.
            Generated and verified the same way as an ordinary
            libsecp256k1 private key.
        value: the value to commit to, an int in [0, 2**64).
        gen_bytes: the generator `gen`, 33 bytes, or None for `h()` --
            the plain, unblinded Pedersen commitment most callers want.

    Returns:
        The 33-byte serialized commitment.

    Raises:
        TypeError: if `value` is not an int.
        ValueError: if `blind` is not 32 bytes, does not fit in them, or
            is out of range; if `value` is a bool or does not fit in 8
            bytes; or if `gen_bytes` is given and is not 33 bytes or not
            a valid generator.
        RuntimeError: if libsecp256k1-zkp refuses the blinding factor,
            which is a ~2**-127 event for a random one and cannot happen
            for a factor already verified.
    """
    ffi, lib, ctx = _handles()
    blind_bytes = scalar(blind, "blind")
    if not isinstance(value, int):
        raise TypeError(f"value must be an int, not {type(value).__name__}")
    if isinstance(value, bool) or not 0 <= value < 2**64:
        raise ValueError("value must be an int in [0, 2**64)")
    gen_obj = (
        lib.secp256k1_generator_h if gen_bytes is None else parse(gen_bytes, "gen")
    )
    commit = ffi.new("secp256k1_pedersen_commitment *")
    if not lib.secp256k1_pedersen_commit(ctx, commit, blind_bytes, value, gen_obj):
        raise RuntimeError("Pedersen commitment failed")
    return pedersen_commitment_serialize(commit)


def pedersen_blind_sum(blinds: Sequence[BytesLike | int], npositive: int) -> bytes:
    """Sum blinding factors, first `npositive` positive, the rest negative.

    Args:
        blinds: the blinding factors, 32 bytes or an int below 2**256
            each.
        npositive: how many of `blinds`, from the start, are summed with
            a positive sign; the rest are summed with a negative one.

    Returns:
        The 32-byte sum.

    Raises:
        TypeError: if `npositive` is not an int.
        ValueError: if one of `blinds` is not 32 bytes, does not fit in
            them, or is out of range -- named by its position in the
            sequence, `blinds[0]` being "blinding factor at index 0" --
            or if `npositive` is out of [0, len(blinds)].
        RuntimeError: if libsecp256k1-zkp refuses one of the factors,
            which is a ~2**-127 event for a random one.
    """
    ffi, lib, ctx = _handles()
    npositive = in_range(npositive, "npositive", len(blinds))
    blind_buffers = [
        ffi.new(
            f"unsigned char[{_BLIND_SIZE}]",
            scalar(blind, f"blinding factor at index {i}"),
        )
        for i, blind in enumerate(blinds)
    ]
    # char, not unsigned char: ffi.unpack of the latter answers a list of
    # ints rather than bytes, and this is the buffer read back below
    blind_out = ffi.new(f"char[{_BLIND_SIZE}]")
    blinds_array = _ptr_array(ffi, "unsigned char *[]", blind_buffers)
    if not lib.secp256k1_pedersen_blind_sum(
        ctx, blind_out, blinds_array, len(blind_buffers), npositive
    ):
        raise RuntimeError("blinding factor sum failed")
    return bytes(ffi.unpack(blind_out, _BLIND_SIZE))


def pedersen_verify_tally(
    commits_bytes: Sequence[BytesLike], ncommits_bytes: Sequence[BytesLike]
) -> bool:
    """Verify `commits` sums to `ncommits`, factors and values alike.

    `sum(commits) - sum(ncommits) == 0`, for the generator each was
    committed under: every commitment mixing more than one generator
    must sum to zero for each of them separately, which is the caller's
    to arrange by grouping commitments per generator before calling
    this.

    Args:
        commits_bytes: the positive commitments, 33 bytes each.
        ncommits_bytes: the negative commitments, 33 bytes each.

    Returns:
        True if they sum to zero.

    Raises:
        ValueError: if one of the commitments is not 33 bytes or not a
            valid one -- named by its position in whichever sequence it
            came from.
    """
    ffi, lib, ctx = _handles()
    commits = [
        pedersen_commitment_parse(commit_bytes, f"commitment at index {i}")
        for i, commit_bytes in enumerate(commits_bytes)
    ]
    ncommits = [
        pedersen_commitment_parse(commit_bytes, f"negative commitment at index {i}")
        for i, commit_bytes in enumerate(ncommits_bytes)
    ]
    return bool(
        lib.secp256k1_pedersen_verify_tally(
            ctx,
            _array_or_null(ffi, "secp256k1_pedersen_commitment *[]", commits),
            len(commits),
            _array_or_null(ffi, "secp256k1_pedersen_commitment *[]", ncommits),
            len(ncommits),
        )
    )


def pedersen_blind_generator_blind_sum(
    values: Sequence[int],
    generator_blinds: Sequence[BytesLike | int],
    blinding_factors: Sequence[BytesLike | int],
    n_inputs: int,
) -> bytes:
    """Correct the last blinding factor so every sum cancels.

    For blinded generators `A' = A + r*G`, a Pedersen commitment
    `P = v*A' + r'*G` really has the form `v*A + (v*r + r')*G`: this
    subtracts the sum of `v*r + r'` over every element but the last from
    the last element of `blinding_factors`, so that the total sum of
    `(v*r + r')` over all of them is zero.

    Args:
        values: the asset values, one per commitment, an int in
            [0, 2**64) each.
        generator_blinds: the asset (generator) blinding factors, `r` in
            the equation above, one per commitment, 32 bytes or an int
            below 2**256 each.
        blinding_factors: the commitment blinding factors, `r'` in the
            equation above, one per commitment, 32 bytes or an int below
            2**256 each -- every one but the last is used as given, and
            only the last is what this recomputes.
        n_inputs: how many of the initial elements, across all three
            sequences, are negated in the final sum. Strictly less than
            `len(values)`: the library's own `ARG_CHECK(n_total >
            n_inputs)` refuses `n_inputs == len(values)`, the `0, 0` case
            -- empty sequences included -- among them.

    Returns:
        The corrected last blinding factor, 32 bytes -- the caller's own
        `blinding_factors` with its last element replaced by this is the
        array libsecp256k1-zkp's own in/out semantics describe.

    Raises:
        TypeError: if `n_inputs` is not an int, or if one of `values` is
            not an int.
        ValueError: if the three sequences are not the same length, if
            `n_inputs` is not in [0, len(values)), if one of `values` is
            a bool or does not fit in 8 bytes, or if one of the blinding
            factors is not 32 bytes, does not fit in them, or is out of
            range. A bad element is named by its position in its own
            sequence, `values[0]` being "value at index 0".
        RuntimeError: if libsecp256k1-zkp refuses one of the factors,
            which is a ~2**-127 event for random ones.
    """
    ffi, lib, ctx = _handles()
    n_total = len(values)
    if len(generator_blinds) != n_total or len(blinding_factors) != n_total:
        raise ValueError(
            "values, generator_blinds and blinding_factors must match in length"
        )
    if not isinstance(n_inputs, int):
        raise TypeError(f"n_inputs must be an int, not {type(n_inputs).__name__}")
    if not 0 <= n_inputs < n_total:
        raise ValueError("n_inputs must be in [0, len(values))")

    # checked here rather than beside the two argument-wide checks above
    # so that a bad element is reported in the order the signature
    # declares the three sequences, the blinds' own `scalar` calls
    # running as each array is built below
    for i, value in enumerate(values):
        if not isinstance(value, int):
            raise TypeError(
                f"value at index {i} must be an int, not {type(value).__name__}"
            )
        if isinstance(value, bool) or not 0 <= value < 2**64:
            raise ValueError(f"value at index {i} must be an int in [0, 2**64)")
    value_array = ffi.new(f"uint64_t[{n_total}]", list(values))
    generator_blind_buffers = [
        ffi.new(
            f"unsigned char[{_BLIND_SIZE}]",
            scalar(blind, f"generator blind at index {i}"),
        )
        for i, blind in enumerate(generator_blinds)
    ]
    # char, not unsigned char, for the reason pedersen_blind_sum's own
    # blind_out is: only the last element is read back with ffi.unpack
    blinding_factor_buffers = [
        ffi.new(
            f"char[{_BLIND_SIZE}]",
            scalar(blind, f"blinding factor at index {i}"),
        )
        for i, blind in enumerate(blinding_factors)
    ]
    # never NULL: n_total is at least 1 here, `0 <= n_inputs < n_total`
    # having already refused the only n_total for which the library's
    # own arrays may be NULL
    generator_blind_array = _ptr_array(
        ffi, "unsigned char *[]", generator_blind_buffers
    )
    blinding_factor_array = _ptr_array(
        ffi, "unsigned char *[]", blinding_factor_buffers
    )
    if not lib.secp256k1_pedersen_blind_generator_blind_sum(
        ctx,
        value_array,
        generator_blind_array,
        blinding_factor_array,
        n_total,
        n_inputs,
    ):
        raise RuntimeError("blinding factor correction failed")
    return bytes(ffi.unpack(blinding_factor_buffers[-1], _BLIND_SIZE))
