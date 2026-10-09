# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""ECDSA adaptor signatures.

This module wraps every entry point `secp256k1_ecdsa_adaptor.h`
declares: `encrypt`, `verify`, `decrypt` and `recover`. An adaptor
signature is an ECDSA signature that is not yet valid: it is encrypted
under a public key Y, and whoever knows the secret key y of Y can
`decrypt` it into an ordinary signature. Whoever then sees both the
adaptor signature and the decrypted signature can `recover` y, which is
what makes the construction useful for atomic swaps and DLCs.

**WARNING.** The adaptor signature leaks the Diffie-Hellman point of the
signing key and the encryption key: given X = x*G, Y = y*G and the
adaptor signature, x*Y = y*X is easy to compute. Do not use the signing key in
protocols that rely on the hardness of the computational Diffie-Hellman
problem, such as a key exchange or ElGamal encryption. The header says
the same.

An adaptor signature is 162 bytes, `R || R' || s' || e || s`: the
33-byte compressed points R = k*Y and R' = k*G, the scalar
s' = k^-1 (m + R.x * x), and a proof (e, s) that R and R' have the same
discrete logarithm k with respect to Y and G. `verify` checks the proof
and that s' is a signature on the message under R'. Public keys cross
this boundary as SEC bytes and signatures as the 64 bytes of `r || s`,
as in `zkp.ecdsa_s2c`.

The nonce function is fixed to the library's default: the C entry point
accepts another, and this module does not offer one. The default's
auxiliary randomness is `encrypt`'s `aux_rand32`.

This module reads `context._bindings()` inside each function rather than
at its own top level, for the reason `zkp.context`'s docstring gives.
"""

from __future__ import annotations

from typing import overload

from btclib_secp256k1 import BytesLike, MutableBytesLike
from btclib_secp256k1._scalar import octets, scalar
from btclib_secp256k1._secret import take, wipe

from . import context
from .ecdsa_s2c import _signature_parse, _signature_serialize

__all__ = ["decrypt", "encrypt", "recover", "verify"]

_ADAPTOR_SIGNATURE_SIZE = 162
_DECKEY_SIZE = 32
_SIGNATURE_SIZE = 64


def encrypt(
    msg32: BytesLike,
    prvkey: BytesLike | int,
    enckey: BytesLike,
    *,
    aux_rand32: BytesLike | None = None,
    verify: bool = True,
) -> bytes:
    """Create an adaptor signature, encrypted under a public key.

    With `verify`, the result is checked by `verify` under the public
    key of `prvkey` before it is returned, as `ecdsa_s2c.sign` checks
    its own: what that catches is the computation going wrong.

    Args:
        msg32: the 32-byte hash of the message.
        prvkey: the private key, 32 bytes or an int below 2**256.
        enckey: the encryption public key, SEC compressed or
            uncompressed.
        aux_rand32: 32 bytes of auxiliary randomness for the nonce, as
            BIP340 recommends, or None for none.
        verify: whether to check the adaptor signature before returning
            it.

    Returns:
        The 162-byte adaptor signature.

    Raises:
        TypeError: if an argument is not of a type its name allows.
        ValueError: if the message hash or `aux_rand32` is not 32 bytes,
            if the private key is not 32 bytes, does not fit in them, or
            is not in [1, n-1], or if the encryption key is not a valid
            point.
        RuntimeError: if `verify` asks and the adaptor signature does
            not verify, which no input can make happen.

    Example:
        >>> from btclib_secp256k1 import keys
        >>> from btclib_secp256k1.zkp import ecdsa_adaptor
        >>> enckey = keys.pubkey_from_prvkey(2)
        >>> adaptor_sig = ecdsa_adaptor.encrypt(bytes(32), 1, enckey)
        >>> ecdsa_adaptor.verify(
        ...     adaptor_sig, keys.pubkey_from_prvkey(1), bytes(32), enckey
        ... )
        True
    """
    msg_bytes = octets(msg32, "message hash", 32)
    prvkey_bytes = scalar(prvkey, "private key")
    aux_bytes = None if aux_rand32 is None else octets(aux_rand32, "aux_rand32", 32)
    ffi, lib, ctx = context._bindings()
    enckey_obj = context._pubkey_parse(ffi, lib, ctx, enckey, "encryption key")
    adaptor_sig = ffi.new(f"char[{_ADAPTOR_SIGNATURE_SIZE}]")
    if not lib.secp256k1_ecdsa_adaptor_encrypt(
        ctx,
        adaptor_sig,
        prvkey_bytes,
        enckey_obj,
        msg_bytes,
        ffi.NULL,
        ffi.NULL if aux_bytes is None else aux_bytes,
    ):
        raise ValueError("invalid private key: not in [1, n-1]")
    if verify:
        pubkey = ffi.new("secp256k1_pubkey *")
        if not lib.secp256k1_ec_pubkey_create(
            ctx, pubkey, prvkey_bytes
        ) or not lib.secp256k1_ecdsa_adaptor_verify(
            ctx, adaptor_sig, pubkey, msg_bytes, enckey_obj
        ):
            raise RuntimeError(
                "encryption produced an adaptor signature that does not verify"
            )
    return bytes(ffi.unpack(adaptor_sig, _ADAPTOR_SIGNATURE_SIZE))


def verify(
    adaptor_sig162: BytesLike,
    pubkey: BytesLike,
    msg32: BytesLike,
    enckey: BytesLike,
) -> bool:
    """Verify an adaptor signature.

    Answers whether the decryption key can be extracted from the
    adaptor signature and the signature completed from it, which is
    what the adaptor signature's proof and its signature on the message
    under the signer's key establish together.

    Args:
        adaptor_sig162: the 162-byte adaptor signature.
        pubkey: the signer's public key, SEC compressed or uncompressed.
        msg32: the 32-byte hash of the message.
        enckey: the encryption public key, SEC compressed or
            uncompressed.

    Returns:
        True if the adaptor signature verifies, False if it does not,
        a malformed one included.

    Raises:
        TypeError: if an argument is not of a type its name allows.
        ValueError: if the adaptor signature is not 162 bytes or the
            message hash is not 32, or if a public key is not a valid
            point.
    """
    adaptor_bytes = octets(adaptor_sig162, "adaptor signature", _ADAPTOR_SIGNATURE_SIZE)
    msg_bytes = octets(msg32, "message hash", 32)
    ffi, lib, ctx = context._bindings()
    pubkey_obj = context._pubkey_parse(ffi, lib, ctx, pubkey, "public key")
    enckey_obj = context._pubkey_parse(ffi, lib, ctx, enckey, "encryption key")
    return bool(
        lib.secp256k1_ecdsa_adaptor_verify(
            ctx, adaptor_bytes, pubkey_obj, msg_bytes, enckey_obj
        )
    )


def decrypt(deckey: BytesLike | int, adaptor_sig162: BytesLike) -> bytes:
    """Complete an adaptor signature into an ECDSA signature.

    The adaptor signature is not verified here, and a signature
    decrypted from an unverified one may be invalid: call `verify` first.
    The result is the low-s form.

    Args:
        deckey: the decryption key, the private key of the encryption
            public key: 32 bytes or an int below 2**256.
        adaptor_sig162: the 162-byte adaptor signature.

    Returns:
        The signature, as the 64 bytes of `r || s`.

    Raises:
        TypeError: if an argument is not of a type its name allows.
        ValueError: if the decryption key is not 32 bytes, does not fit
            in them, or is not in [1, n-1], or if the adaptor signature
            is not 162 bytes, its s' is not in [1, n-1], or its R.x is 0
            modulo n.
        RuntimeError: if libsecp256k1-zkp fails to serialize the
            signature, which no signature it produced can make it do.
    """
    deckey_bytes = scalar(deckey, "decryption key")
    adaptor_bytes = octets(adaptor_sig162, "adaptor signature", _ADAPTOR_SIGNATURE_SIZE)
    ffi, lib, ctx = context._bindings()
    signature = ffi.new("secp256k1_ecdsa_signature *")
    if not lib.secp256k1_ecdsa_adaptor_decrypt(
        ctx, signature, deckey_bytes, adaptor_bytes
    ):
        raise ValueError("invalid decryption key or adaptor signature")
    return _signature_serialize(ffi, lib, ctx, signature)


@overload
def recover(
    sig64: BytesLike, adaptor_sig162: BytesLike, enckey: BytesLike
) -> bytes: ...
@overload
def recover(
    sig64: BytesLike,
    adaptor_sig162: BytesLike,
    enckey: BytesLike,
    *,
    into: MutableBytesLike,
) -> None: ...
@overload
def recover(
    sig64: BytesLike,
    adaptor_sig162: BytesLike,
    enckey: BytesLike,
    *,
    into: MutableBytesLike | None,
) -> bytes | None: ...
def recover(
    sig64: BytesLike,
    adaptor_sig162: BytesLike,
    enckey: BytesLike,
    *,
    into: MutableBytesLike | None = None,
) -> bytes | None:
    """Recover the decryption key from a signature and its adaptor signature.

    Whoever completes an adaptor signature into `sig64` has revealed the
    decryption key to anyone holding both. Neither is verified here
    beyond what recovery itself checks: that `sig64` and the adaptor
    signature share `r`, and that the key they imply matches `enckey`.

    Args:
        sig64: the 64-byte completed signature, `r || s`.
        adaptor_sig162: the 162-byte adaptor signature it was completed
            from.
        enckey: the encryption public key, SEC compressed or
            uncompressed.
        into: a writable 32-byte buffer to receive the key, instead of
            the `bytes` this otherwise returns. See `_secret.take` and
            SECURITY.md for what that does and does not buy.

    Returns:
        The 32-byte decryption key -- or None where `into` was given and
        holds it.

    Raises:
        TypeError: if an argument is not of a type its name allows, or
            if `into` is not a writable buffer of contiguous
            one-dimensional octets.
        ValueError: if `sig64` is not 64 bytes or is not a valid compact
            signature, if the adaptor signature is not 162 bytes or its
            s' is not in [1, n-1], if the encryption key is not a valid
            point, if the signature and the adaptor signature do not
            match, or if `into` is not 32 bytes.
    """
    sig_bytes = octets(sig64, "signature", _SIGNATURE_SIZE)
    adaptor_bytes = octets(adaptor_sig162, "adaptor signature", _ADAPTOR_SIGNATURE_SIZE)
    ffi, lib, ctx = context._bindings()
    signature = _signature_parse(ffi, lib, ctx, sig_bytes)
    enckey_obj = context._pubkey_parse(ffi, lib, ctx, enckey, "encryption key")
    deckey = ffi.new(f"char[{_DECKEY_SIZE}]")
    if not lib.secp256k1_ecdsa_adaptor_recover(
        ctx, deckey, signature, adaptor_bytes, enckey_obj
    ):
        # recovery may have written a key before refusing it
        wipe(deckey)
        raise ValueError("the signature does not match the adaptor signature")
    return take(deckey, into=into)
