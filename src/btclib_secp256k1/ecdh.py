# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Elliptic Curve Diffie-Hellman (ECDH)."""

from __future__ import annotations

from typing import overload

from . import BytesLike, CData, MutableBytesLike, ffi, keys, lib
from ._scalar import scalar
from ._secret import take, wipe
from .context import ctx

__all__ = ["shared_point", "shared_secret"]

# the SEC1 tags of the two serializations `keys.serialize` answers: the
# compressed one adds the parity of y to the even tag
_EVEN_Y = 0x02
_UNCOMPRESSED = 0x04


@overload
def _shared_secret_(pubkey: CData, prvkey: BytesLike | int) -> bytes: ...
@overload
def _shared_secret_(
    pubkey: CData, prvkey: BytesLike | int, *, into: MutableBytesLike
) -> None: ...
@overload
def _shared_secret_(
    pubkey: CData, prvkey: BytesLike | int, *, into: MutableBytesLike | None
) -> bytes | None: ...
def _shared_secret_(
    pubkey: CData, prvkey: BytesLike | int, *, into: MutableBytesLike | None = None
) -> bytes | None:
    """Compute the ECDH shared secret from an already-parsed public key.

    The private half of `shared_secret`, for a caller who already holds
    the other party's parsed key -- one exchanging with the same
    counterparty more than once, or one that validated the key on
    receipt: see the package docstring for what the two underscores mean
    throughout.

    Args:
        pubkey: the other party's already-parsed public key, as
            `keys.parse` returns.
        prvkey: this party's private key, 32 bytes or an int below
            2**256.
        into: a writable 32-byte buffer to receive the result, instead
            of the `bytes` this otherwise returns. See `_secret.take`
            and SECURITY.md for what that does and does not buy.

    Returns:
        The 32-byte shared secret, the SHA256 of the compressed shared
        point as `shared_secret` documents it -- or None where `into`
        was given and holds it.

        **A key libsecp256k1 cannot read answers 32 bytes here too, and
        they are a shared secret with nobody.** A `secp256k1_pubkey`
        nothing has written to is reported through the illegal callback,
        which this does not read, and the call succeeds: nothing raises
        and nothing about the answer says it is worthless. That is the
        one place in this package where an unusable object produces a
        value a caller could take for a secret, and `context.check`
        immediately after the call is the only thing that says
        otherwise. `shared_secret` parses the octets it is given and so
        has no such case; a caller holding a key of its own has it, and
        proving that key once with `keys.pubkey_verify` is what removes
        it.

    Raises:
        TypeError: if `into` is not a writable bytearray or memoryview
            of octets.
        ValueError: if the private key is not 32 bytes, does not fit in
            them, or is not a valid scalar.
    """
    prvkey_bytes = scalar(prvkey, "private key")

    output = ffi.new("char[32]")
    # a NULL hash function selects secp256k1_ecdh_hash_function_sha256,
    # which writes 32 bytes to output
    computed = lib.secp256k1_ecdh(ctx, output, pubkey, prvkey_bytes, ffi.NULL, ffi.NULL)
    if not computed:
        raise ValueError("invalid private key")
    return take(output, into=into)


@overload
def shared_secret(pubkey_bytes: BytesLike, prvkey: BytesLike | int) -> bytes: ...
@overload
def shared_secret(
    pubkey_bytes: BytesLike, prvkey: BytesLike | int, *, into: MutableBytesLike
) -> None: ...
@overload
def shared_secret(
    pubkey_bytes: BytesLike, prvkey: BytesLike | int, *, into: MutableBytesLike | None
) -> bytes | None: ...
def shared_secret(
    pubkey_bytes: BytesLike,
    prvkey: BytesLike | int,
    *,
    into: MutableBytesLike | None = None,
) -> bytes | None:
    """Compute the ECDH shared secret.

    The result is the SHA256 of the compressed shared point, i.e. the
    libsecp256k1 default hash function; it is computed in constant time.

    The hash function is not configurable, by decision. libsecp256k1
    takes it as a C callback, so exposing it would mean calling back into
    python from the middle of the computation, with the shared point
    passing through python objects; and it would buy nothing, the point
    being available as `shared_point(pubkey_bytes, prvkey)`, through
    this same call and its constant-time `secp256k1_ecmult_const`. A
    protocol needing another derivation applies it to that: SHA256 of
    its compressed form is what this function returns. Wanting both of
    them is where the private halves earn their keep -- one
    `keys.parse`, then `_shared_secret_` and `_shared_point_` of it --
    the two public halves parsing the same key twice.

    Args:
        pubkey_bytes: the other party's public key, 33 or 65 bytes.
        prvkey: this party's private key, 32 bytes or an int below
            2**256.
        into: a writable 32-byte buffer to receive the result, instead
            of the `bytes` this otherwise returns. See `_secret.take`
            and SECURITY.md for what that does and does not buy.

    Returns:
        The 32-byte shared secret -- or None where `into` was given and
        holds it.

    Raises:
        TypeError: if `into` is not a writable bytearray or memoryview
            of octets.
        ValueError: if the public key is not a valid point, if the
            private key is not 32 bytes or does not fit in them, or if
            it is not a valid scalar.
    """
    return _shared_secret_(keys.parse(pubkey_bytes), prvkey, into=into)


@overload
def _shared_point_(
    pubkey: CData, prvkey: BytesLike | int, compressed: bool = True
) -> bytes: ...
@overload
def _shared_point_(
    pubkey: CData,
    prvkey: BytesLike | int,
    compressed: bool = True,
    *,
    into: MutableBytesLike,
) -> None: ...
@overload
def _shared_point_(
    pubkey: CData,
    prvkey: BytesLike | int,
    compressed: bool = True,
    *,
    into: MutableBytesLike | None,
) -> bytes | None: ...
def _shared_point_(
    pubkey: CData,
    prvkey: BytesLike | int,
    compressed: bool = True,
    *,
    into: MutableBytesLike | None = None,
) -> bytes | None:
    """Compute the ECDH shared point from an already-parsed public key.

    The private half of `shared_point`, for a caller who already holds
    the other party's parsed key: see the package docstring for what the
    two underscores mean throughout.

    Args:
        pubkey: the other party's already-parsed public key, as
            `keys.parse` returns.
        prvkey: this party's private key, 32 bytes or an int below
            2**256.
        compressed: whether to return 33 bytes rather than 65.
        into: a writable buffer of 33 bytes, or of 65 where `compressed`
            is False, to receive the result instead of the `bytes` this
            otherwise returns. See `_secret.take` and SECURITY.md for
            what that does and does not buy.

    Returns:
        The serialized shared point, as `shared_point` documents it --
        or None where `into` was given and holds it. An object
        libsecp256k1 cannot read answers octets here too, which are a
        point shared with nobody: `_shared_secret_` says why, and it is
        the same call.

    Raises:
        TypeError: if `into` is not a writable bytearray or memoryview
            of octets.
        ValueError: if the private key is not 32 bytes, does not fit in
            them, or is not a valid scalar, or if `into` is not the
            length of the serialization.
    """
    prvkey_bytes = scalar(prvkey, "private key")

    coordinates = ffi.new("unsigned char[64]")
    computed = lib.secp256k1_ecdh(
        ctx,
        coordinates,
        pubkey,
        prvkey_bytes,
        lib.btclib_secp256k1_ecdh_hash_function_xy,
        ffi.NULL,
    )
    if not computed:
        # libsecp256k1 multiplies by one in place of a scalar it refuses,
        # so what the hash function copied is the public key itself and
        # there is nothing here to wipe
        raise ValueError("invalid private key")

    # the octets `keys.serialize` would write, assembled from x || y
    # rather than through a `keys.parse` of them, which would prove again
    # a point libsecp256k1 has just computed, and with a variable-time
    # validation. cdata to cdata: no `bytes` of the point is made before
    # `take`, and the tag is arithmetic on the parity rather than a
    # branch on it
    if compressed:
        point = ffi.new("unsigned char[33]")
        point[0] = _EVEN_Y | (coordinates[63] & 1)
        ffi.memmove(point + 1, coordinates, 32)
    else:
        point = ffi.new("unsigned char[65]")
        point[0] = _UNCOMPRESSED
        ffi.memmove(point + 1, coordinates, 64)
    wipe(coordinates)
    return take(point, into=into)


@overload
def shared_point(
    pubkey_bytes: BytesLike, prvkey: BytesLike | int, compressed: bool = True
) -> bytes: ...
@overload
def shared_point(
    pubkey_bytes: BytesLike,
    prvkey: BytesLike | int,
    compressed: bool = True,
    *,
    into: MutableBytesLike,
) -> None: ...
@overload
def shared_point(
    pubkey_bytes: BytesLike,
    prvkey: BytesLike | int,
    compressed: bool = True,
    *,
    into: MutableBytesLike | None,
) -> bytes | None: ...
def shared_point(
    pubkey_bytes: BytesLike,
    prvkey: BytesLike | int,
    compressed: bool = True,
    *,
    into: MutableBytesLike | None = None,
) -> bytes | None:
    """Multiply a public key by a private key, in constant time.

    The point `keys.pubkey_tweak_mul` answers, and the one `shared_secret`
    hashes: this is `secp256k1_ecdh`, whose multiplication is
    `secp256k1_ecmult_const`, constant time in the scalar, where
    `pubkey_tweak_mul` runs the variable-time `secp256k1_ecmult`. So a
    secret scalar belongs here -- an ECDH private key, BIP352's scan key
    -- and a public one, a verification equation's, in `keys`.

    `secp256k1_ecdh` answers the point only to a hash function, which
    libsecp256k1 takes as a C callback. This one is C too, compiled into
    the vendored library by this package's build: it copies x and y out,
    and nothing enters python until the call has returned. A python
    callback would run in the middle of the constant-time call, with the
    point in python objects, and is why `shared_secret`'s hash is not
    configurable.

    What the guarantee covers is the multiplication. The serialization is
    assembled in python from the coordinates, and the point is then a
    python object like any other secret answered here: SECURITY.md is
    what that does and does not mean.

    Args:
        pubkey_bytes: the other party's public key, 33 or 65 bytes.
        prvkey: this party's private key, 32 bytes or an int below
            2**256.
        compressed: whether to return 33 bytes rather than 65.
        into: a writable buffer of 33 bytes, or of 65 where `compressed`
            is False, to receive the result instead of the `bytes` this
            otherwise returns. See `_secret.take` and SECURITY.md for
            what that does and does not buy.

    Returns:
        The serialized point kP, as `keys.serialize` writes it -- or None
        where `into` was given and holds it.

    Raises:
        TypeError: if `into` is not a writable bytearray or memoryview
            of octets.
        ValueError: if the public key is not a valid point, if the
            private key is not 32 bytes or does not fit in them, if it
            is zero or at or above the group order, or if `into` is not
            the length of the serialization.

    Example:
        >>> from btclib_secp256k1 import ecdh, keys
        >>> # 3 * (7 * G) is 21 * G
        >>> point = ecdh.shared_point(keys.pubkey_from_prvkey(7), 3)
        >>> point == keys.pubkey_from_prvkey(21)
        True
    """
    return _shared_point_(keys.parse(pubkey_bytes), prvkey, compressed, into=into)
