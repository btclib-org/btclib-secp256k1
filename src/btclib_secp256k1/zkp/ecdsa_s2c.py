# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""ECDSA sign-to-contract, and the anti-exfil protocol built on it.

This module wraps every entry point `secp256k1_ecdsa_s2c.h` declares,
one for one. Sign-to-contract lets a signer commit to 32 bytes of data
inside an ECDSA signature's own nonce, by offsetting the nonce point
with `hash(R, data) * G`; `opening_parse` and `opening_serialize` carry
that commitment's opening across a process boundary, `sign` is what
makes it, and `verify_commit` is what checks it.

The anti-exfil half is the reason this module exists rather than being
deferred: a hardware wallet could claim to produce RFC6979 nonces and
instead bias them to leak the private key one signature at a time, with
nothing on the host side able to tell the two apart, and
`anti_exfil_host_commit`, `anti_exfil_signer_commit`, `anti_exfil_sign`
and `anti_exfil_host_verify` are the commit-reveal protocol the
header's own module docstring lays out -- host commits to randomness,
signer's public nonce commits to that commitment, host reveals the
randomness, signer signs committing to it for real, host checks the
signature's nonce matches what was committed to at each step. Nothing
here drives the protocol itself, which needs two round trips with a
signing device this package has no notion of; those are the calls the
steps that need one are made of -- the host's own reveal, step 3, needs
none from this module.

This module reads `context._bindings()` -- `btclib_secp256k1.zkp.context`'s
own `ffi`, `lib` and `ctx`, forced together -- inside each function
rather than at its own top level: `zkp.context`'s own docstring has the
reasoning, and importing this module alone stays safe with no flagged
build, which is what lets `docs/source/btclib_secp256k1.rst` document
it.

Signatures cross this boundary in the 64-byte compact form only, `r ||
s`; a caller wanting DER has `btclib_secp256k1.dsa.to_der`, which is a
serialization detail unrelated to the commitment this module is for. An
opening is the 33-byte compressed form `opening_serialize` writes and
`opening_parse` reads back; `sign` and `anti_exfil_signer_commit` answer
it directly, there being no reason to make a caller round-trip through
the parsed object for the common case.
"""

from __future__ import annotations

from typing import Any

from btclib_secp256k1 import BytesLike, CData
from btclib_secp256k1._scalar import octets, scalar

from . import context

__all__ = [
    "anti_exfil_host_commit",
    "anti_exfil_host_verify",
    "anti_exfil_sign",
    "anti_exfil_signer_commit",
    "opening_parse",
    "opening_serialize",
    "sign",
    "verify_commit",
]

_OPENING_SIZE = 33
_SIGNATURE_SIZE = 64


def _pubkey_parse(ffi: Any, lib: Any, ctx: CData, pubkey_bytes: BytesLike) -> CData:
    """Parse a public key, using zkp's own context rather than the primary one.

    `btclib_secp256k1.keys.parse` is the same call against the wrong
    library: a `secp256k1_pubkey` it builds is not pointer-compatible
    with what this extension's own `secp256k1_ec_pubkey_parse` expects,
    two independently built cffi extensions never sharing a struct type
    -- so `anti_exfil_host_verify`, the one function here that takes a
    public key, parses it again rather than reusing that module.

    Args:
        ffi: this extension's `ffi`.
        lib: this extension's `lib`.
        ctx: the shared context.
        pubkey_bytes: the public key, 33 or 65 bytes.

    Returns:
        The libsecp256k1-zkp public key object.

    Raises:
        ValueError: if the bytes are not a valid point in either
            serialization.
    """
    pubkey_bytes = octets(pubkey_bytes, "public key")
    pubkey = ffi.new("secp256k1_pubkey *")
    if not lib.secp256k1_ec_pubkey_parse(ctx, pubkey, pubkey_bytes, len(pubkey_bytes)):
        raise ValueError("invalid public key")
    return pubkey


def _signature_parse(
    ffi: Any, lib: Any, ctx: CData, signature_bytes: BytesLike
) -> CData:
    """Parse a compact signature, the one form this module reads.

    Args:
        ffi: this extension's `ffi`.
        lib: this extension's `lib`.
        ctx: the shared context.
        signature_bytes: the 64 bytes of `r || s`.

    Returns:
        The libsecp256k1-zkp signature object.

    Raises:
        ValueError: if the value is not 64 bytes, or if r or s is not
            below the group order.
    """
    signature_bytes = octets(signature_bytes, "signature", _SIGNATURE_SIZE)
    signature = ffi.new("secp256k1_ecdsa_signature *")
    if not lib.secp256k1_ecdsa_signature_parse_compact(ctx, signature, signature_bytes):
        raise ValueError("invalid compact signature")
    return signature


def _signature_serialize(ffi: Any, lib: Any, ctx: CData, signature: CData) -> bytes:
    """Serialize a signature to its 64-byte compact form.

    Args:
        ffi: this extension's `ffi`.
        lib: this extension's `lib`.
        ctx: the shared context.
        signature: the libsecp256k1-zkp signature object.

    Returns:
        The 64 bytes of `r || s`, each big endian and zero padded.

    Raises:
        RuntimeError: if libsecp256k1-zkp fails to serialize it, which
            no signature it produced can make it do.
    """
    sig_bytes = ffi.new(f"char[{_SIGNATURE_SIZE}]")
    if not lib.secp256k1_ecdsa_signature_serialize_compact(ctx, sig_bytes, signature):
        raise RuntimeError("signature serialization failed")
    return bytes(ffi.unpack(sig_bytes, _SIGNATURE_SIZE))


def opening_parse(opening_bytes: BytesLike) -> CData:
    """Parse a serialized sign-to-contract opening.

    Args:
        opening_bytes: the opening's 33-byte compressed serialization, as
            `opening_serialize` returns and `sign` and
            `anti_exfil_signer_commit` already answer.

    Returns:
        The libsecp256k1-zkp opening object, as `verify_commit` and
        `anti_exfil_host_verify` take it -- through their own
        `opening_bytes` argument, which parses it again; this is for a
        caller working with the object directly.

    Raises:
        ValueError: if the bytes are not 33 long, or do not encode a
            point on the curve.
    """
    opening_bytes = octets(opening_bytes, "opening", _OPENING_SIZE)
    ffi, lib, ctx = context._bindings()
    opening = ffi.new("secp256k1_ecdsa_s2c_opening *")
    if not lib.secp256k1_ecdsa_s2c_opening_parse(ctx, opening, opening_bytes):
        raise ValueError("invalid opening")
    return opening


def opening_serialize(opening: CData) -> bytes:
    """Serialize a sign-to-contract opening to its 33-byte compressed form.

    Args:
        opening: the libsecp256k1-zkp opening object, as `opening_parse`
            returns.

    Returns:
        Its 33-byte compressed serialization.

    Raises:
        RuntimeError: if libsecp256k1-zkp refuses the object -- one it
            cannot read -- or fails for any other reason, which an
            opening `opening_parse` produced cannot make it do.
    """
    ffi, lib, ctx = context._bindings()
    output = ffi.new(f"char[{_OPENING_SIZE}]")
    if not lib.secp256k1_ecdsa_s2c_opening_serialize(ctx, output, opening):
        raise RuntimeError("opening serialization failed")
    return bytes(ffi.unpack(output, _OPENING_SIZE))


def sign(
    msg_bytes: BytesLike, prvkey: BytesLike | int, s2c_data32: BytesLike
) -> tuple[bytes, bytes]:
    """Create an ECDSA signature committing to 32 bytes of data.

    The nonce function is fixed to the RFC6979 default: sign-to-contract
    only works with it, `s2c_data32` being mixed into the very nonce it
    derives, and the C entry point itself takes no nonce-function
    argument at all, so no other one can be supplied.

    Args:
        msg_bytes: the 32-byte hash of the message.
        prvkey: the private key, 32 bytes or an int below 2**256.
        s2c_data32: the 32 bytes of data to commit to.

    Returns:
        The signature, as the 64 bytes of `r || s`, and the opening of
        its commitment, as the 33-byte compressed serialization
        `verify_commit` and `opening_parse` take.

    Raises:
        ValueError: if the message hash or the data are not 32 bytes, or
            if the private key is not 32 bytes, does not fit in them, or
            is not in [1, n-1].
        RuntimeError: if libsecp256k1-zkp fails to serialize the
            signature or the opening, which neither it produced can
            make it do.

    Example:
        >>> from btclib_secp256k1.zkp import ecdsa_s2c
        >>> signature, opening = ecdsa_s2c.sign(bytes(32), 1, bytes(32))
        >>> ecdsa_s2c.verify_commit(signature, bytes(32), opening)
        True
    """
    msg_bytes = octets(msg_bytes, "message hash", 32)
    prvkey_bytes = scalar(prvkey, "private key")
    s2c_data32 = octets(s2c_data32, "s2c_data32", 32)
    ffi, lib, ctx = context._bindings()

    signature = ffi.new("secp256k1_ecdsa_signature *")
    opening = ffi.new("secp256k1_ecdsa_s2c_opening *")
    if not lib.secp256k1_ecdsa_s2c_sign(
        ctx, signature, opening, msg_bytes, prvkey_bytes, s2c_data32
    ):
        raise ValueError("invalid private key: not in [1, n-1]")
    return (
        _signature_serialize(ffi, lib, ctx, signature),
        opening_serialize(opening),
    )


def verify_commit(
    signature_bytes: BytesLike, data32: BytesLike, opening_bytes: BytesLike
) -> bool:
    """Verify a sign-to-contract commitment.

    Answers whether the signature's nonce commits to `data32` under the
    given opening -- a property of the signature's own `r`, checked
    without verifying the signature itself. `anti_exfil_host_verify`
    checks both together.

    Args:
        signature_bytes: the signature containing the commitment, the 64
            bytes of `r || s`.
        data32: the 32 bytes of data the opening should commit to.
        opening_bytes: the opening `sign` or `anti_exfil_signer_commit`
            answered, as its 33-byte compressed serialization.

    Returns:
        True if the signature's nonce commits to `data32` under this
        opening -- and False for an incorrect opening, which is not
        necessarily a signature that fails to verify: `verify_commit`
        answers a property of `r` alone.

    Raises:
        ValueError: if the signature is not 64 bytes or is not a valid
            compact signature, if the data are not 32 bytes, or if the
            opening is not 33 bytes or does not encode a point on the
            curve.
    """
    signature_bytes = octets(signature_bytes, "signature", _SIGNATURE_SIZE)
    data32 = octets(data32, "data32", 32)
    opening_bytes = octets(opening_bytes, "opening", _OPENING_SIZE)
    ffi, lib, ctx = context._bindings()
    signature = _signature_parse(ffi, lib, ctx, signature_bytes)
    opening = opening_parse(opening_bytes)
    return bool(lib.secp256k1_ecdsa_s2c_verify_commit(ctx, signature, data32, opening))


def anti_exfil_host_commit(rand32: BytesLike) -> bytes:
    """Create the host's commitment to its randomness.

    The first step of the anti-exfil protocol: the host draws `rand32`
    from a cryptographically secure RNG and sends this commitment to the
    signer, keeping `rand32` itself back until step 3.

    Args:
        rand32: the 32 bytes of randomness to commit to.

    Returns:
        The 32-byte commitment.

    Raises:
        ValueError: if `rand32` is not 32 bytes.
        RuntimeError: if libsecp256k1-zkp fails to compute the
            commitment, which valid arguments cannot make it do.
    """
    rand32 = octets(rand32, "rand32", 32)
    ffi, lib, ctx = context._bindings()
    commitment = ffi.new("char[32]")
    if not lib.secp256k1_ecdsa_anti_exfil_host_commit(ctx, commitment, rand32):
        raise RuntimeError("host commitment failed")
    return bytes(ffi.unpack(commitment, 32))


def anti_exfil_signer_commit(
    msg_bytes: BytesLike, prvkey: BytesLike | int, rand_commitment32: BytesLike
) -> bytes:
    """Compute the signer's original public nonce, step 2 of the protocol.

    The signer answers this opening to the host without yet signing:
    `anti_exfil_sign` is step 4, once the host has revealed the
    randomness this commits to.

    Args:
        msg_bytes: the 32-byte hash of the message to be signed.
        prvkey: the private key that will sign, 32 bytes or an int below
            2**256.
        rand_commitment32: the host's commitment, from
            `anti_exfil_host_commit`.

    Returns:
        The signer's public nonce, as the 33-byte compressed
        serialization of its opening.

    Raises:
        ValueError: if the message hash or the commitment are not 32
            bytes.
        RuntimeError: if libsecp256k1-zkp fails to compute the
            opening, which valid arguments cannot make it do.
    """
    msg_bytes = octets(msg_bytes, "message hash", 32)
    prvkey_bytes = scalar(prvkey, "private key")
    rand_commitment32 = octets(rand_commitment32, "rand_commitment32", 32)
    ffi, lib, ctx = context._bindings()

    opening = ffi.new("secp256k1_ecdsa_s2c_opening *")
    if not lib.secp256k1_ecdsa_anti_exfil_signer_commit(
        ctx, opening, msg_bytes, prvkey_bytes, rand_commitment32
    ):
        raise RuntimeError("signer commitment failed")
    return opening_serialize(opening)


def anti_exfil_sign(
    msg_bytes: BytesLike, prvkey: BytesLike | int, host_data32: BytesLike
) -> bytes:
    """Sign, committing to the host's randomness. Step 4 of the protocol.

    The same call as `sign`, with `host_data32` -- the randomness the
    host revealed at step 3 -- as the data committed to, and no opening
    answered: the host already holds it, from
    `anti_exfil_signer_commit` at step 2.

    Args:
        msg_bytes: the 32-byte hash of the message.
        prvkey: the private key, 32 bytes or an int below 2**256.
        host_data32: the randomness the host revealed.

    Returns:
        The signature, as the 64 bytes of `r || s`.

    Raises:
        ValueError: if the message hash or the data are not 32 bytes, or
            if the private key is not 32 bytes, does not fit in them, or
            is not in [1, n-1].
        RuntimeError: if libsecp256k1-zkp fails to serialize the
            signature, which no signature it produced can make it do.
    """
    msg_bytes = octets(msg_bytes, "message hash", 32)
    prvkey_bytes = scalar(prvkey, "private key")
    host_data32 = octets(host_data32, "host_data32", 32)
    ffi, lib, ctx = context._bindings()

    signature = ffi.new("secp256k1_ecdsa_signature *")
    if not lib.secp256k1_anti_exfil_sign(
        ctx, signature, msg_bytes, prvkey_bytes, host_data32
    ):
        raise ValueError("invalid private key: not in [1, n-1]")
    return _signature_serialize(ffi, lib, ctx, signature)


def anti_exfil_host_verify(
    signature_bytes: BytesLike,
    msg_bytes: BytesLike,
    pubkey_bytes: BytesLike,
    host_data32: BytesLike,
    opening_bytes: BytesLike,
) -> bool:
    """Verify a signature made under the anti-exfil protocol. Step 5.

    True only where both hold: the signature verifies under `pubkey_bytes`
    for `msg_bytes`, and it commits to `host_data32` under `opening_bytes`
    -- the opening the signer answered at step 2, for the same randomness
    the host revealed at step 3. Together they say the signer could not have
    biased this signature's nonce without the host's own randomness
    changing it, which is what the whole protocol is for.

    Args:
        signature_bytes: the signature the signer produced, the 64 bytes
            of `r || s`.
        msg_bytes: the 32-byte hash of the message.
        pubkey_bytes: the signer's public key, 33 or 65 bytes.
        host_data32: the randomness the host revealed at step 3.
        opening_bytes: the opening from `anti_exfil_signer_commit`, step
            2.

    Returns:
        True if the signature is valid for that key and message, and
        commits to `host_data32` under `opening_bytes`.

    Raises:
        ValueError: if the signature is not 64 bytes or is not a valid
            compact signature, if the message hash or the data are not
            32 bytes, if the public key is not a valid point, or if the
            opening is not 33 bytes or does not encode a point on the
            curve.
    """
    signature_bytes = octets(signature_bytes, "signature", _SIGNATURE_SIZE)
    msg_bytes = octets(msg_bytes, "message hash", 32)
    pubkey_bytes = octets(pubkey_bytes, "public key")
    host_data32 = octets(host_data32, "host_data32", 32)
    opening_bytes = octets(opening_bytes, "opening", _OPENING_SIZE)
    ffi, lib, ctx = context._bindings()
    signature = _signature_parse(ffi, lib, ctx, signature_bytes)
    pubkey = _pubkey_parse(ffi, lib, ctx, pubkey_bytes)
    opening = opening_parse(opening_bytes)
    return bool(
        lib.secp256k1_anti_exfil_host_verify(
            ctx, signature, msg_bytes, pubkey, host_data32, opening
        )
    )
