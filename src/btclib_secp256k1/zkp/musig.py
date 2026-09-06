# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""zkp's MuSig2: BIP327 plus adaptor signatures, the whole header wrapped.

`btclib_secp256k1.musig` wraps every entry point of mainline
libsecp256k1's `secp256k1_musig.h`. This wraps secp256k1-zkp's own
header instead, which adds `nonce_parity`, `adapt` and
`extract_adaptor` beyond mainline's, and gives `nonce_process` itself a
sixth argument, an optional adaptor point. #283's structural finding is
why this is a second module rather than a few extra functions bolted
onto the first: zkp's `nonce_process` cannot be called with mainline's
five-argument signature, `adapt` needs the `nonce_parity` a session
built by *this* `nonce_process` reports, and `secp256k1_musig_session`,
`secp256k1_musig_keyagg_cache` and `secp256k1_musig_secnonce` are opaque
structs of a different build from mainline's -- so a caller starting a
session on `btclib_secp256k1.musig` has nothing to adapt, and there is
no shared session to hand between the two modules. `KeyAggCache`,
`SecretNonce` and `Session` below are that module's own classes, shaped
the same way and for the reasons its docstring gives -- a keyagg cache
and a session hold nothing secret and have no serialization, so they
are held rather than round-tripped through octets, and a secret nonce
is wiped on the way out of `partial_sign` and by the `with` block that
holds a `SecretNonce`.

**Nothing here is `btclib_secp256k1.musig`'s code reused.** Two
statically linked cores share no cffi type identity: a
`secp256k1_pubkey` this module's own `_pubkey_parse` builds and one
`btclib_secp256k1.keys.parse` builds are both named `secp256k1_pubkey *`
and are not interchangeable -- passing one to a call compiled against
the other's `ffi` raises `TypeError: ... the types are different
(check that you are not e.g. mixing up different ffi instances)`,
measured directly before this module was written this way. So every
struct this needs -- a public key, an x-only public key, a keypair, in
addition to the five `secp256k1_musig_*` structs the header already
declares -- is parsed and serialized locally, through zkp's own `ffi`
and `lib`, rather than through `btclib_secp256k1.keys` or
`btclib_secp256k1.xonly`. What *is* shared, and safely, is
`_scalar.py`'s `octets`, `scalar` and `in_range`: they take and return
plain bytes and ints, or a bare `unsigned char[32]`-shaped cdata view
that cffi treats structurally rather than nominally, measured to cross
the same boundary without complaint -- and `_secret.wipe`, which
overwrites through `ffi.buffer(buffer)` and asks that buffer for its
own length rather than typing it, so it too does not care which `ffi`
built what it is wiping. `_secret.keypair` is not shared for the same
reason `keys.parse` is not: it returns a `secp256k1_keypair *` built
through mainline's own `lib.secp256k1_keypair_create`, and this module's
`_keypair` is the local equivalent, over zkp's own `ctx` and `lib`.

**Every entry point here defers `ffi`, `lib` and `ctx` to its own call,
through `context._bindings()`, rather than importing any of the three
at module scope.** `btclib_secp256k1.musig` imports its `ffi` and `lib`
eagerly and may, because mainline's extension is never flag-gated; this
module's is, and `docs/source/btclib_secp256k1.rst` documents every
class and function below with `:members:` in a build that never sets
`BTCLIB_LIBSECP256K1_ZKP` -- so importing this module, which Sphinx's
autodoc does to read the docstrings and signatures, must not itself
reach for the extension. `btclib_secp256k1.zkp.context`'s own
`__getattr__` already makes this trade for `ctx` alone; `_bindings` is
the same trade for `ffi` and `lib` too, shared by every module wrapping
a zkp-only entry point so that none of them repeats the two lines that
make it.

**Validation**: BIP327's own vectors -- `tests/bip327_*_vectors.json`,
the files `tests/vectors_test.py` already reads for
`btclib_secp256k1.musig` -- run unchanged against this module in
`tests/zkp_musig_vectors_test.py`, which is the API-compatibility check
secp256k1-zkp#330 was opened to make possible and this package can run
without waiting for that split. The adaptor path has no published
vector -- zkp's own tests draw the adaptor secret with `testrand256`,
and a downstream caller checked for one to lift and found none -- so it
is checked by round trip instead, in `tests/zkp_musig_test.py`:
pre-sign, adapt with a known secret, extract the secret back out of the
two signatures.
"""

from __future__ import annotations

import secrets
import threading
from collections.abc import Sequence
from types import TracebackType
from typing import Any

from btclib_secp256k1 import BytesLike, CData
from btclib_secp256k1._scalar import in_range, octets, scalar
from btclib_secp256k1._secret import wipe

from . import context

__all__ = [
    "KeyAggCache",
    "SecretNonce",
    "Session",
    "adapt",
    "aggnonce_parse",
    "aggnonce_serialize",
    "extract_adaptor",
    "nonce_agg",
    "nonce_gen",
    "nonce_gen_counter",
    "partial_sig_parse",
    "partial_sig_serialize",
    "pubnonce_parse",
    "pubnonce_serialize",
]

# the widths this module has fixed sizes for: BIP327's own for a public
# and an aggregate nonce (33 octets per point, two points each),
# libsecp256k1's compact 32-byte partial signature, the 64-byte plain
# BIP340 signature `Session.partial_sig_agg` and `adapt` both answer, and
# the two serializations `_pubkey_parse`/`_pubkey_serialize` use, which
# `btclib_secp256k1.keys` has no cross-ffi-safe equivalent of here
_PUBNONCE_SIZE = 66
_AGGNONCE_SIZE = 66
_PARTIAL_SIG_SIZE = 32
_SIGNATURE_SIZE = 64
_COMPRESSED_SIZE = 33
_UNCOMPRESSED_SIZE = 65
_XONLY_SIZE = 32
_ADAPTOR_SIZE = 32

# SECP256K1_EC_COMPRESSED and SECP256K1_EC_UNCOMPRESSED: the macros do
# not survive the preprocessing of the headers into cffi definitions,
# and `btclib_secp256k1.keys` states the same two literals for the same
# reason
_COMPRESSED_FLAG = 258
_UNCOMPRESSED_FLAG = 2


def _pubkey_parse(
    ffi: Any, lib: Any, ctx: Any, pubkey_bytes: BytesLike, name: str
) -> CData:
    """Parse a public key, through zkp's own `ffi` and `lib`.

    The local equivalent of `btclib_secp256k1.keys.parse`: the module
    docstring explains why that one cannot be called from here instead.

    Args:
        ffi: this module's `ffi`, from `context._bindings()`.
        lib: this module's `lib`, from `context._bindings()`.
        ctx: this module's `ctx`, from `context._bindings()`.
        pubkey_bytes: the public key, 33 or 65 bytes.
        name: what the key is, as the exception should call it.

    Returns:
        The zkp-native `secp256k1_pubkey *` object.

    Raises:
        ValueError: if the bytes are not a valid point in either
            serialization.
    """
    pubkey_bytes = octets(pubkey_bytes, name)
    pubkey = ffi.new("secp256k1_pubkey *")
    if not lib.secp256k1_ec_pubkey_parse(ctx, pubkey, pubkey_bytes, len(pubkey_bytes)):
        raise ValueError(f"invalid {name}")
    return pubkey


def _pubkey_serialize(
    ffi: Any, lib: Any, ctx: Any, pubkey: CData, compressed: bool
) -> bytes:
    """Serialize a zkp-native public key.

    The local equivalent of `btclib_secp256k1.keys.serialize`.

    Args:
        ffi: this module's `ffi`, from `context._bindings()`.
        lib: this module's `lib`, from `context._bindings()`.
        ctx: this module's `ctx`, from `context._bindings()`.
        pubkey: the zkp-native public key object, as `_pubkey_parse` or
            `secp256k1_musig_pubkey_get` returns.
        compressed: whether to return 33 bytes rather than 65.

    Returns:
        The 33-byte compressed serialization, or the 65-byte
        uncompressed one.

    Raises:
        RuntimeError: if libsecp256k1-zkp refuses the object, which one
            it produced cannot make it do.
    """
    size = _COMPRESSED_SIZE if compressed else _UNCOMPRESSED_SIZE
    flags = _COMPRESSED_FLAG if compressed else _UNCOMPRESSED_FLAG
    output = ffi.new(f"char[{size}]")
    length = ffi.new("size_t *", size)
    if not lib.secp256k1_ec_pubkey_serialize(ctx, output, length, pubkey, flags):
        raise RuntimeError("point serialization failed")
    return bytes(ffi.unpack(output, size))


def _xonly_serialize(ffi: Any, lib: Any, ctx: Any, xonly_pubkey: CData) -> bytes:
    """Serialize a zkp-native x-only public key.

    The local equivalent of `btclib_secp256k1.xonly.serialize`.

    Args:
        ffi: this module's `ffi`, from `context._bindings()`.
        lib: this module's `lib`, from `context._bindings()`.
        ctx: this module's `ctx`, from `context._bindings()`.
        xonly_pubkey: the zkp-native x-only public key object, as
            `secp256k1_musig_pubkey_agg` writes it.

    Returns:
        The 32-byte x coordinate.

    Raises:
        RuntimeError: if libsecp256k1-zkp refuses the object, which one
            it produced cannot make it do.
    """
    output = ffi.new(f"char[{_XONLY_SIZE}]")
    if not lib.secp256k1_xonly_pubkey_serialize(ctx, output, xonly_pubkey):
        raise RuntimeError("x-only public key serialization failed")
    return bytes(ffi.unpack(output, _XONLY_SIZE))


def _keypair(ffi: Any, lib: Any, ctx: Any, prvkey: BytesLike | int) -> CData:
    """Build the zkp-native keypair of a private key.

    The local equivalent of `btclib_secp256k1._secret.keypair`: the
    caller of this wipes the buffer it returns, `_secret.wipe` being
    safe to call on it for the reason the module docstring gives.

    Args:
        ffi: this module's `ffi`, from `context._bindings()`.
        lib: this module's `lib`, from `context._bindings()`.
        ctx: this module's `ctx`, from `context._bindings()`.
        prvkey: the private key, 32 bytes or an int below 2**256.

    Returns:
        The zkp-native `secp256k1_keypair *` object, which the caller
        wipes.

    Raises:
        ValueError: if it is not 32 bytes, does not fit in them, or is
            not in [1, n-1].
    """
    buffer = ffi.new("secp256k1_keypair *")
    if not lib.secp256k1_keypair_create(ctx, buffer, scalar(prvkey, "private key")):
        raise ValueError("invalid private key: not in [1, n-1]")
    return buffer


def _array(ffi: Any, cdecl: str, items: Sequence[CData]) -> CData:
    """Build the array of borrowed pointers libsecp256k1-zkp reads.

    The local equivalent of `btclib_secp256k1._cdata.array`, over this
    module's own `ffi`.

    Args:
        ffi: this module's `ffi`, from `context._bindings()`.
        cdecl: the cffi declaration of the array type.
        items: the objects to point at, which the caller keeps alive.

    Returns:
        The array, or NULL where there is nothing to point at.
    """
    return ffi.new(cdecl, list(items)) if items else ffi.NULL


def pubnonce_parse(pubnonce_bytes: BytesLike, name: str = "public nonce") -> CData:
    """Parse a signer's public nonce into its internal representation.

    Args:
        pubnonce_bytes: the public nonce, 66 bytes, as `nonce_gen` or
            `nonce_gen_counter` answered it through the `SecretNonce`
            they built.
        name: what the nonce is, as the exception should call it, for a
            caller parsing more than one array of them.

    Returns:
        The libsecp256k1-zkp public nonce object.

    Raises:
        ValueError: if it is not 66 bytes, or not one BIP327 defines.
    """
    ffi, lib, ctx = context._bindings()
    pubnonce_bytes = octets(pubnonce_bytes, name, _PUBNONCE_SIZE)
    pubnonce = ffi.new("secp256k1_musig_pubnonce *")
    if not lib.secp256k1_musig_pubnonce_parse(ctx, pubnonce, pubnonce_bytes):
        raise ValueError(f"invalid {name}")
    return pubnonce


def pubnonce_serialize(pubnonce: CData) -> bytes:
    """Serialize a parsed public nonce.

    Args:
        pubnonce: the libsecp256k1-zkp public nonce object, as
            `pubnonce_parse` returns.

    Returns:
        Its 66 bytes.

    Raises:
        RuntimeError: if libsecp256k1-zkp refuses the object, which one
            it produced cannot make it do.
    """
    ffi, lib, ctx = context._bindings()
    output = ffi.new(f"char[{_PUBNONCE_SIZE}]")
    if not lib.secp256k1_musig_pubnonce_serialize(ctx, output, pubnonce):
        raise RuntimeError("public nonce serialization failed")
    return bytes(ffi.unpack(output, _PUBNONCE_SIZE))


def aggnonce_parse(aggnonce_bytes: BytesLike, name: str = "aggregate nonce") -> CData:
    """Parse an aggregate public nonce into its internal representation.

    Args:
        aggnonce_bytes: the aggregate nonce, 66 bytes, as `nonce_agg`
            answered it.
        name: what the nonce is, as the exception should call it.

    Returns:
        The libsecp256k1-zkp aggregate nonce object.

    Raises:
        ValueError: if it is not 66 bytes, or not one BIP327 defines.
    """
    ffi, lib, ctx = context._bindings()
    aggnonce_bytes = octets(aggnonce_bytes, name, _AGGNONCE_SIZE)
    aggnonce = ffi.new("secp256k1_musig_aggnonce *")
    if not lib.secp256k1_musig_aggnonce_parse(ctx, aggnonce, aggnonce_bytes):
        raise ValueError(f"invalid {name}")
    return aggnonce


def aggnonce_serialize(aggnonce: CData) -> bytes:
    """Serialize a parsed aggregate public nonce.

    Args:
        aggnonce: the libsecp256k1-zkp aggregate nonce object, as
            `aggnonce_parse` returns.

    Returns:
        Its 66 bytes.

    Raises:
        RuntimeError: if libsecp256k1-zkp refuses the object, which one
            it produced cannot make it do.
    """
    ffi, lib, ctx = context._bindings()
    output = ffi.new(f"char[{_AGGNONCE_SIZE}]")
    if not lib.secp256k1_musig_aggnonce_serialize(ctx, output, aggnonce):
        raise RuntimeError("aggregate nonce serialization failed")
    return bytes(ffi.unpack(output, _AGGNONCE_SIZE))


def partial_sig_parse(
    partial_sig_bytes: BytesLike, name: str = "partial signature"
) -> CData:
    """Parse a partial signature into its internal representation.

    Args:
        partial_sig_bytes: the partial signature, 32 bytes, as
            `SecretNonce.partial_sign` answered it.
        name: what the signature is, as the exception should call it.

    Returns:
        The libsecp256k1-zkp partial signature object.

    Raises:
        ValueError: if it is not 32 bytes, or not one below the curve
            order.
    """
    ffi, lib, ctx = context._bindings()
    partial_sig_bytes = octets(partial_sig_bytes, name, _PARTIAL_SIG_SIZE)
    partial_sig = ffi.new("secp256k1_musig_partial_sig *")
    if not lib.secp256k1_musig_partial_sig_parse(ctx, partial_sig, partial_sig_bytes):
        raise ValueError(f"invalid {name}")
    return partial_sig


def partial_sig_serialize(partial_sig: CData) -> bytes:
    """Serialize a parsed partial signature.

    Args:
        partial_sig: the libsecp256k1-zkp partial signature object, as
            `partial_sig_parse` returns.

    Returns:
        Its 32 bytes.

    Raises:
        RuntimeError: if libsecp256k1-zkp refuses the object, which one
            it produced cannot make it do.
    """
    ffi, lib, ctx = context._bindings()
    output = ffi.new(f"char[{_PARTIAL_SIG_SIZE}]")
    if not lib.secp256k1_musig_partial_sig_serialize(ctx, output, partial_sig):
        raise RuntimeError("partial signature serialization failed")
    return bytes(ffi.unpack(output, _PARTIAL_SIG_SIZE))


def nonce_agg(pubnonces_bytes: Sequence[BytesLike]) -> bytes:
    """Aggregate the signers' public nonces into one, for `Session`.

    Any party can do this, trusted or not: an aggregate nonce computed
    wrong makes the final signature invalid rather than makes it forge,
    so BIP327 lets an untrusted coordinator collect the round-one
    nonces and hand every signer this one value back instead of every
    other signer's.

    Args:
        pubnonces_bytes: the signers' public nonces, 66 bytes each, in
            the order `Session.partial_sig_agg` will later take their
            partial signatures. At least one is required.

    Returns:
        The 66-byte aggregate nonce.

    Raises:
        ValueError: if the sequence is empty, or if one of the nonces is
            not 66 bytes or not one BIP327 defines -- named by its
            position in the sequence, `pubnonces_bytes[0]` being "public
            nonce at index 0".
        RuntimeError: if libsecp256k1-zkp fails to aggregate or
            serialize the result, which no valid input can make it do.
    """
    ffi, lib, ctx = context._bindings()
    if not pubnonces_bytes:
        raise ValueError("at least one public nonce is required")
    # a per-contribution parse loop, not a comprehension calling
    # `pubnonce_parse` with its default name -- `btclib_secp256k1.musig`'s
    # own `nonce_agg` has the same shape and the same reason
    pubnonces = [
        pubnonce_parse(pubnonce_bytes, f"public nonce at index {index}")
        for index, pubnonce_bytes in enumerate(pubnonces_bytes)
    ]
    aggnonce = ffi.new("secp256k1_musig_aggnonce *")
    if not lib.secp256k1_musig_nonce_agg(
        ctx,
        aggnonce,
        _array(ffi, "secp256k1_musig_pubnonce *[]", pubnonces),
        len(pubnonces),
    ):
        raise RuntimeError("nonce aggregation failed")
    return aggnonce_serialize(aggnonce)


class KeyAggCache:
    """The aggregate of a set of signers' public keys, and its tweaks.

    The zkp-native `btclib_secp256k1.musig.KeyAggCache`: what
    `secp256k1_musig_keyagg_cache` holds, and why it is held rather than
    round-tripped through octets, is that class's own docstring, which
    applies unchanged. What differs is only that every call below goes
    through zkp's own `ffi`, `lib` and `ctx` -- the module docstring
    explains why the two cannot share a cache object.

    Building one is `secp256k1_musig_pubkey_agg`, which orders the keys
    exactly as given: `keys.pubkey_sort` first is BIP327's own rule for
    reaching one aggregate key independently of the order the signers'
    public keys arrived in, and is the caller's to apply -- that
    function is a pure re-serialization after a real sort, so
    `btclib_secp256k1.keys.pubkey_sort` is safe to call for this module
    too, unlike `parse` and `serialize`.

    Args:
        pubkeys_bytes: the signers' public keys, 33 or 65 bytes each, in
            aggregation order. At least one is required.

    Raises:
        ValueError: if the sequence is empty, or if one of the keys is
            not a valid point -- named by its position in the sequence,
            `pubkeys_bytes[0]` being "public key at index 0".
        RuntimeError: if libsecp256k1-zkp fails to aggregate or
            serialize the result, which no valid input can make it do.

    Example:
        >>> from btclib_secp256k1 import keys
        >>> from btclib_secp256k1.zkp import musig
        >>> pubkeys = [keys.pubkey_from_prvkey(1), keys.pubkey_from_prvkey(2)]
        >>> cache = musig.KeyAggCache(pubkeys)
        >>> len(cache.agg_pubkey)
        32
    """

    # pydoclint (DOC301) asks that this carry no docstring of its own,
    # the class docstring above being where the constructor is documented
    def __init__(self, pubkeys_bytes: Sequence[BytesLike]) -> None:  # noqa: D107
        ffi, lib, ctx = context._bindings()
        if not pubkeys_bytes:
            raise ValueError("at least one public key is required")
        # a per-contribution parse loop, for the reason nonce_agg's has
        pubkeys = [
            _pubkey_parse(ffi, lib, ctx, pubkey_bytes, f"public key at index {index}")
            for index, pubkey_bytes in enumerate(pubkeys_bytes)
        ]
        cache = ffi.new("secp256k1_musig_keyagg_cache *")
        agg_pk = ffi.new("secp256k1_xonly_pubkey *")
        if not lib.secp256k1_musig_pubkey_agg(
            ctx,
            agg_pk,
            cache,
            _array(ffi, "secp256k1_pubkey *[]", pubkeys),
            len(pubkeys),
        ):
            raise RuntimeError("key aggregation failed")
        self._cache = cache
        # BIP327's Q, before any tweak: pubkey_agg is the only call that
        # answers it, so it is captured now or not at all -- pubkey_get
        # below answers the *current*, possibly tweaked aggregate instead
        self.agg_pubkey = _xonly_serialize(ffi, lib, ctx, agg_pk)

    def pubkey_get(self, compressed: bool = True) -> bytes:
        """Return the current aggregate public key, tweaks included.

        Useful for the non-xonly form of the aggregate key -- plain
        tweaking, or batch-verifying more than one key aggregation, which
        libsecp256k1-zkp does not implement -- where `agg_pubkey` is the
        x-only one and BIP341 taproot tweaking wants the full point.

        Args:
            compressed: whether to return 33 bytes rather than 65.

        Returns:
            The serialized aggregate public key, as it stands after
            every `pubkey_ec_tweak_add` and `pubkey_xonly_tweak_add`
            made so far.

        Raises:
            RuntimeError: if libsecp256k1-zkp fails to read or serialize
                it, which a cache this built cannot make it do.
        """
        ffi, lib, ctx = context._bindings()
        agg_pk = ffi.new("secp256k1_pubkey *")
        if not lib.secp256k1_musig_pubkey_get(ctx, agg_pk, self._cache):
            raise RuntimeError("aggregate public key extraction failed")
        return _pubkey_serialize(ffi, lib, ctx, agg_pk, compressed)

    def pubkey_ec_tweak_add(
        self, tweak: BytesLike | int, compressed: bool = True
    ) -> bytes:
        """Add a plain EC tweak to the aggregate key, e.g. a BIP32 step.

        The MuSig2 counterpart of `keys.pubkey_tweak_add`: the tweaking
        method is the same, and what differs is that it is applied to
        this cache's running aggregate rather than to an argument, so
        that signing for the tweaked key is `SecretNonce.partial_sign`
        against the cache afterwards rather than against a key nobody
        holds the private share of directly.

        Args:
            tweak: the tweak, 32 bytes or an int below 2**256. Callers
                are responsible for deriving it in a way that does not
                reduce MuSig2's security, BIP32 being such a way.
            compressed: whether to return 33 bytes rather than 65.

        Returns:
            The serialized tweaked aggregate public key.

        Raises:
            ValueError: if the tweak is not 32 bytes or does not fit in
                them, or if the tweak or the resulting key is invalid.
            RuntimeError: if libsecp256k1-zkp fails to serialize the
                result, which no valid input can make it do.
        """
        return self._tweak_add("secp256k1_musig_pubkey_ec_tweak_add", tweak, compressed)

    def pubkey_xonly_tweak_add(
        self, tweak: BytesLike | int, compressed: bool = True
    ) -> bytes:
        """Add a BIP341 x-only tweak to the aggregate key, for a taproot output.

        `xonly.tweak_add`'s equation, applied to this cache instead of
        to a bare argument -- the module docstring's reasoning about
        `xonly` not being callable from here does not reach this: what
        is asked of the caller is the same BIP341 equation, not a call
        into `btclib_secp256k1.xonly`. This is required, rather than
        tweaking the x-only key directly, wherever a signature is wanted
        for the tweaked key: that would leave this cache untweaked, so a
        later `SecretNonce.partial_sign` would sign for the untweaked
        aggregate instead.

        Args:
            tweak: the tweak, 32 bytes or an int below 2**256. Callers
                are responsible for deriving it in a way that does not
                reduce MuSig2's security, BIP341 being such a way.
            compressed: whether to return 33 bytes rather than 65.

        Returns:
            The serialized tweaked aggregate public key.

        Raises:
            ValueError: if the tweak is not 32 bytes or does not fit in
                them, or if the tweak or the resulting key is invalid.
            RuntimeError: if libsecp256k1-zkp fails to serialize the
                result, which no valid input can make it do.
        """
        return self._tweak_add(
            "secp256k1_musig_pubkey_xonly_tweak_add", tweak, compressed
        )

    def _tweak_add(
        self, tweak_add_name: str, tweak: BytesLike | int, compressed: bool
    ) -> bytes:
        """Apply the tweak both public methods share, told apart by the C call.

        Args:
            tweak_add_name: `"secp256k1_musig_pubkey_ec_tweak_add"` or
                `"secp256k1_musig_pubkey_xonly_tweak_add"`, read off
                `lib` here rather than passed in already bound -- one
                fewer argument for the same reason `nonce_gen_counter`'s
                own caller has to stay under ruff's limit on how many a
                function may take.
            tweak: the tweak, 32 bytes or an int below 2**256.
            compressed: whether to return 33 bytes rather than 65.

        Returns:
            The serialized tweaked aggregate public key.

        Raises:
            ValueError: if the tweak is not 32 bytes or does not fit in
                them, or if the tweak or the resulting key is invalid.
            RuntimeError: if libsecp256k1-zkp fails to serialize the
                result, which no valid input can make it do.
        """
        ffi, lib, ctx = context._bindings()
        tweak_add = getattr(lib, tweak_add_name)
        tweak_bytes = scalar(tweak, "tweak")
        output = ffi.new("secp256k1_pubkey *")
        if not tweak_add(ctx, output, self._cache, tweak_bytes):
            raise ValueError("invalid tweak or resulting public key")
        return _pubkey_serialize(ffi, lib, ctx, output, compressed)

    def _cache_(self) -> CData:
        """Return the libsecp256k1-zkp keyagg cache object this holds.

        The private half every other entry point of this module reaches
        for: `nonce_gen`, `nonce_gen_counter`, `Session.__init__` and
        `SecretNonce.partial_sign` all take a `KeyAggCache` and read it
        through this rather than through a public attribute, so that
        nothing outside this class can replace what it points at.

        Returns:
            The libsecp256k1-zkp keyagg cache object, mutated in place
            by `pubkey_ec_tweak_add` and `pubkey_xonly_tweak_add`.
        """
        return self._cache


def nonce_gen(
    pubkey_bytes: BytesLike,
    prvkey: BytesLike | int | None = None,
    msg32: BytesLike | None = None,
    keyagg_cache: KeyAggCache | None = None,
    extra_input32: BytesLike | None = None,
) -> SecretNonce:
    """Start a signing session by generating a nonce.

    Round one of BIP327: the public nonce this answers is sent to every
    other signer, or to whoever aggregates them, and the secret nonce is
    kept -- held by the `SecretNonce` this returns, until a matching
    `Session` exists to call its `partial_sign`.

    The 32 bytes of session randomness BIP327 requires, unique to this
    call and never reused, is not a parameter: it is generated here with
    `secrets.token_bytes`, the same source `btclib_secp256k1.musig`'s own
    `nonce_gen` uses, because the one thing a caller could do with it --
    supply their own -- is the one thing the header warns against doing
    twice.

    Args:
        pubkey_bytes: the public key of the signer this nonce is for, 33
            or 65 bytes. The secnonce this answers can only sign for a
            keypair matching it, which `SecretNonce.partial_sign` asks
            libsecp256k1-zkp to check.
        prvkey: this signer's private key, 32 bytes or an int below
            2**256, if already known. Optional, and folded into the
            nonce derivation to increase misuse-resistance where given;
            using the same private key across several MuSig2 sessions is
            fine.
        msg32: the 32-byte message this session will sign, if already
            known. Optional, for the same reason.
        keyagg_cache: the key aggregation this session signs under, if
            already known. Optional, for the same reason.
        extra_input32: 32 bytes that do not repeat in normal use, such as
            the current time, folded into the derivation alongside the
            above. Optional, and no substitute for the session
            randomness above, which is what carries the uniqueness
            requirement.

    Returns:
        The secret nonce, held rather than returned as octets -- the
        module docstring says why, and `SecretNonce` is what a caller
        wipes if this session is abandoned before `partial_sign`.

    Raises:
        ValueError: if the public key is not a valid point, if the
            private key is given and is not 32 bytes, does not fit in
            them, or is not in [1, n-1], or if `msg32` or
            `extra_input32` is given and is not 32 bytes.
    """
    ffi, lib, ctx = context._bindings()
    pubkey = _pubkey_parse(ffi, lib, ctx, pubkey_bytes, "public key")
    prvkey_bytes = None if prvkey is None else scalar(prvkey, "private key")
    msg_bytes = None if msg32 is None else octets(msg32, "message", 32)
    extra_bytes = (
        None if extra_input32 is None else octets(extra_input32, "extra_input32", 32)
    )
    cache = ffi.NULL if keyagg_cache is None else keyagg_cache._cache_()

    secnonce = ffi.new("secp256k1_musig_secnonce *")
    pubnonce = ffi.new("secp256k1_musig_pubnonce *")
    session_secrand = ffi.new("unsigned char[32]", secrets.token_bytes(32))
    try:
        generated = lib.secp256k1_musig_nonce_gen(
            ctx,
            secnonce,
            pubnonce,
            session_secrand,
            ffi.NULL if prvkey_bytes is None else prvkey_bytes,
            pubkey,
            ffi.NULL if msg_bytes is None else msg_bytes,
            cache,
            ffi.NULL if extra_bytes is None else extra_bytes,
        )
    finally:
        # this package's own scratch randomness, owed a wipe whether the
        # call used it or refused it first -- `wipe` is cross-ffi safe,
        # the module docstring explains why
        wipe(session_secrand)
    if not generated:
        raise ValueError("invalid private key: not in [1, n-1]")
    return SecretNonce(secnonce, pubnonce, pubkey)


def nonce_gen_counter(
    prvkey: BytesLike | int,
    nonrepeating_cnt: int,
    msg32: BytesLike | None = None,
    keyagg_cache: KeyAggCache | None = None,
    extra_input32: BytesLike | None = None,
) -> SecretNonce:
    """Start a signing session, deriving the nonce from a counter instead.

    The alternative to `nonce_gen` for a signer with a non-repeating
    counter rather than good randomness available -- a hardware signer
    keeping one in place of an RNG it does not trust, which is what this
    exists for. The counter must never repeat for this private key: two
    calls with the same keypair and the same `nonrepeating_cnt`, on any
    device signing with that key, reuse the nonce.

    Args:
        prvkey: this signer's private key, 32 bytes or an int below
            2**256. Mandatory here, where `nonce_gen`'s is optional: the
            counter's uniqueness is a property of the key it counts for.
        nonrepeating_cnt: the counter value, an int in [0, 2**64 - 1],
            unique to this call for this private key.
        msg32: the 32-byte message this session will sign, if already
            known.
        keyagg_cache: the key aggregation this session signs under, if
            already known.
        extra_input32: 32 bytes that do not repeat in normal use, folded
            into the derivation alongside the above.

    Returns:
        The secret nonce, as `nonce_gen` returns it.

    Raises:
        TypeError: if `nonrepeating_cnt` is not an int.
        ValueError: if the private key is not 32 bytes, does not fit in
            them, or is not in [1, n-1], if `nonrepeating_cnt` is out of
            range, if `extra_input32` is given and is not 32 bytes, or if
            `msg32` is given and is not 32 bytes.
        RuntimeError: if libsecp256k1-zkp fails to extract the public key
            or to generate the nonce, which a private key already
            verified cannot make it do.
    """
    ffi, lib, ctx = context._bindings()
    nonrepeating_cnt = in_range(nonrepeating_cnt, "nonrepeating_cnt", 2**64 - 1)
    msg_bytes = None if msg32 is None else octets(msg32, "message", 32)
    extra_bytes = (
        None if extra_input32 is None else octets(extra_input32, "extra_input32", 32)
    )
    cache = ffi.NULL if keyagg_cache is None else keyagg_cache._cache_()

    keypair_obj = _keypair(ffi, lib, ctx, prvkey)
    try:
        pubkey = ffi.new("secp256k1_pubkey *")
        if not lib.secp256k1_keypair_pub(ctx, pubkey, keypair_obj):
            raise RuntimeError("public key extraction failed")

        secnonce = ffi.new("secp256k1_musig_secnonce *")
        pubnonce = ffi.new("secp256k1_musig_pubnonce *")
        generated = lib.secp256k1_musig_nonce_gen_counter(
            ctx,
            secnonce,
            pubnonce,
            nonrepeating_cnt,
            keypair_obj,
            ffi.NULL if msg_bytes is None else msg_bytes,
            cache,
            ffi.NULL if extra_bytes is None else extra_bytes,
        )
    finally:
        # the keypair carries the private key: overwrite it whether the
        # nonce was made or refused, as `btclib_secp256k1.musig`'s own
        # `nonce_gen_counter` does with its own
        wipe(keypair_obj)
    if not generated:
        raise RuntimeError("nonce generation failed")
    return SecretNonce(secnonce, pubnonce, pubkey)


class SecretNonce:
    """A signer's secret nonce, held between `nonce_gen` and `partial_sign`.

    The zkp-native `btclib_secp256k1.musig.SecretNonce`: that class's own
    docstring has the reasoning -- the lock guarding `_take` against two
    threads racing `partial_sign` on one object, `wipe`'s cases, and why
    a `SecretNonce` told neither `wipe` nor entered as a `with` block is
    dropped holding the secret. All of it applies unchanged; only the
    `ctx`, `ffi` and `lib` this reaches for, through `context._bindings()`,
    differ.

    Args:
        secnonce: the libsecp256k1-zkp secret nonce object `nonce_gen` or
            `nonce_gen_counter` built.
        pubnonce: the matching public nonce object, already parsed.
        pubkey: the signer's already-parsed public key, kept for
            `partial_sign`'s own `verify`.

    Example:
        >>> from btclib_secp256k1 import keys
        >>> from btclib_secp256k1.zkp import musig
        >>> prvkey, pubkey = 1, keys.pubkey_from_prvkey(1)
        >>> with musig.nonce_gen(pubkey, prvkey) as secnonce:
        ...     len(secnonce.pubnonce)
        66
    """

    # pydoclint (DOC301) asks that this carry no docstring of its own,
    # the class docstring above being where the constructor is documented
    def __init__(self, secnonce: CData, pubnonce: CData, pubkey: CData) -> None:  # noqa: D107
        self._secnonce: CData | None = secnonce
        self._pubnonce = pubnonce
        self._pubkey = pubkey
        self.pubnonce = pubnonce_serialize(pubnonce)
        # private to this instance: what it orders is one SecretNonce's
        # own check-and-clear, not calls into libsecp256k1-zkp, so it is
        # not a shared context's lock and does not compete with it
        self._lock = threading.Lock()

    def partial_sign(
        self,
        prvkey: BytesLike | int,
        keyagg_cache: KeyAggCache,
        session: Session,
        *,
        verify: bool = True,
    ) -> bytes:
        """Produce this signer's partial signature, and wipe the secret nonce.

        Whatever the outcome -- a signature, a refusal or an exception --
        the secret nonce this holds does not survive the call.

        Args:
            prvkey: this signer's private key, 32 bytes or an int below
                2**256, matching the public key `nonce_gen` or
                `nonce_gen_counter` built this nonce for.
            keyagg_cache: the key aggregation this session signs under,
                the same one the nonce was generated against if one was.
            session: the session `Session.__init__` built from the
                aggregate nonce this signer's public nonce contributed
                to.
            verify: whether to check the partial signature against this
                signer's public nonce and public key before returning
                it, as `btclib_secp256k1.musig`'s own module docstring
                explains and BIP327's own header recommends.

        Returns:
            The 32-byte partial signature.

        Raises:
            ValueError: if this secret nonce has already been spent or
                wiped, if the private key is not 32 bytes, does not fit
                in them, or is not in [1, n-1], or if it does not match
                this secret nonce, or `keyagg_cache` or `session` do not.
            RuntimeError: if `verify` asks and the partial signature does
                not verify, which no input reaching this far can make
                happen.
        """
        ffi, lib, ctx = context._bindings()
        # _take, not _held: it clears self._secnonce as the one
        # statement that reads it, for the reason
        # `btclib_secp256k1.musig.SecretNonce`'s own docstring gives
        secnonce = self._take()
        keypair_obj: CData | None = None
        partial_sig = ffi.new("secp256k1_musig_partial_sig *")
        try:
            # `_keypair(...)` is inside the try on purpose: it is the one
            # fallible step here that runs before libsecp256k1-zkp ever
            # sees secnonce, and the class docstring's guarantee -- the
            # secret nonce does not survive the call, whatever the
            # outcome -- has to hold even when this raises before that
            # call is made
            keypair_obj = _keypair(ffi, lib, ctx, prvkey)
            signed = lib.secp256k1_musig_partial_sign(
                ctx,
                partial_sig,
                secnonce,
                keypair_obj,
                keyagg_cache._cache_(),
                session._session_(),
            )
        finally:
            # the keypair carries the private key, wiped unconditionally
            # for the reason `btclib_secp256k1.musig`'s own
            # `partial_sign` gives; the secret nonce is spent regardless
            if keypair_obj is not None:
                wipe(keypair_obj)
            wipe(secnonce)
        if not signed:
            msg = (
                "the private key, key aggregation cache or session do not"
                " match this secret nonce"
            )
            raise ValueError(msg)
        if verify and not lib.secp256k1_musig_partial_sig_verify(
            ctx,
            partial_sig,
            self._pubnonce,
            self._pubkey,
            keyagg_cache._cache_(),
            session._session_(),
        ):
            raise RuntimeError(
                "partial signing produced a signature that does not verify"
            )
        return partial_sig_serialize(partial_sig)

    def wipe(self) -> None:
        """Overwrite the secret nonce, ending what this can sign.

        Signing afterwards raises rather than signing with the zeros
        left behind, and there is no reviving it: nothing here keeps the
        nonce anywhere else, so a session abandoned this way is
        restarted with a fresh `nonce_gen` rather than resumed. Takes
        the same lock `partial_sign` does, so a `wipe` racing a
        `partial_sign` call on another thread cannot see the buffer
        between the two.
        """
        with self._lock:
            secnonce = self._secnonce
            self._secnonce = None
        if secnonce is not None:
            wipe(secnonce)

    # PYI034 asks for `typing.Self` here, and that is 3.11 while this
    # package supports 3.10, as `btclib_secp256k1.musig.SecretNonce`'s
    # own comment says
    def __enter__(self) -> SecretNonce:  # noqa: PYI034
        """Return this secret nonce, for the `with` block that wipes it.

        Returns:
            This object, nothing being built here that the constructor
            did not already build.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Wipe the secret nonce, whatever ended the block.

        Args:
            exc_type: the class of the exception ending the block, if
                one is.
            exc_value: that exception.
            traceback: its traceback.
        """
        self.wipe()

    def _take(self) -> CData:
        """Read the secret nonce and clear it, as one atomic step.

        Returns:
            The libsecp256k1-zkp secret nonce object. `self._secnonce`
            is already `None` by the time this returns it, so no other
            call -- from any thread -- can receive the same object
            again.

        Raises:
            ValueError: if `wipe` or a previous `partial_sign` has
                already taken it.
        """
        with self._lock:
            secnonce = self._secnonce
            self._secnonce = None
        if secnonce is None:
            raise ValueError("this secret nonce has been wiped or already spent")
        return secnonce


class Session:
    """A MuSig2 signing session, opened from the signers' aggregate nonce.

    What `secp256k1_musig_nonce_process` produces, over zkp's own
    `ctx`, `ffi` and `lib`: the message, the aggregate nonce and the key
    aggregation are fixed into it, as
    `btclib_secp256k1.musig.Session`'s own docstring explains for the
    17-argument call it wraps. This wraps the 18-argument one instead --
    zkp's own `nonce_process` takes a sixth argument, an optional
    adaptor point -- so the session this builds is a pre-signature
    session where `adaptor_bytes` is given, and an ordinary one where it
    is not; `nonce_parity`, `adapt` and `extract_adaptor` are what tell
    the two apart afterwards.

    Args:
        aggnonce_bytes: the aggregate of the signers' public nonces, 66
            bytes, as `nonce_agg` answered it.
        msg32: the 32-byte message this session signs.
        keyagg_cache: the key aggregation this session signs under.
        adaptor_bytes: an adaptor point, encoded as a public key (33 or
            65 bytes), if this session is part of an adaptor signature
            protocol. `Session.partial_sig_agg` then answers a
            pre-signature rather than a valid one, and `adapt` is what
            turns it into one, given the secret this point commits to.

    Raises:
        ValueError: if `aggnonce_bytes` is not 66 bytes or not one
            BIP327 defines, if the message is not 32 bytes, or if
            `adaptor_bytes` is given and is not a valid point.
        RuntimeError: if libsecp256k1-zkp fails to build the session,
            which no valid input can make it do.

    Example:
        >>> from btclib_secp256k1 import keys
        >>> from btclib_secp256k1.zkp import musig
        >>> pubkeys = [keys.pubkey_from_prvkey(1), keys.pubkey_from_prvkey(2)]
        >>> cache = musig.KeyAggCache(pubkeys)
        >>> secnonces = [
        ...     musig.nonce_gen(pk, i + 1) for i, pk in enumerate(pubkeys)
        ... ]
        >>> pubnonces = [s.pubnonce for s in secnonces]
        >>> aggnonce = musig.nonce_agg(pubnonces)
        >>> session = musig.Session(aggnonce, bytes(32), cache)
    """

    # pydoclint (DOC301) asks that this carry no docstring of its own,
    # the class docstring above being where the constructor is documented
    def __init__(  # noqa: D107
        self,
        aggnonce_bytes: BytesLike,
        msg32: BytesLike,
        keyagg_cache: KeyAggCache,
        adaptor_bytes: BytesLike | None = None,
    ) -> None:
        ffi, lib, ctx = context._bindings()
        aggnonce = aggnonce_parse(aggnonce_bytes)
        msg_bytes = octets(msg32, "message", 32)
        adaptor = (
            ffi.NULL
            if adaptor_bytes is None
            else _pubkey_parse(ffi, lib, ctx, adaptor_bytes, "adaptor")
        )
        session = ffi.new("secp256k1_musig_session *")
        if not lib.secp256k1_musig_nonce_process(
            ctx, session, aggnonce, msg_bytes, keyagg_cache._cache_(), adaptor
        ):
            raise RuntimeError("nonce processing failed")
        self._session = session

    def partial_sig_verify(
        self,
        partial_sig_bytes: BytesLike,
        pubnonce_bytes: BytesLike,
        pubkey_bytes: BytesLike,
        keyagg_cache: KeyAggCache,
    ) -> bool:
        """Verify one signer's partial signature, within this session.

        Not required in a regular session: an aggregate signature that
        fails `ssa.verify` (or, for a pre-signature, `adapt` followed by
        it) was made from at least one bad partial signature, but does
        not say which. This is the call that finds out, at the cost of
        one verification per signer instead of one for the aggregate.

        Args:
            partial_sig_bytes: the partial signature to verify, 32 bytes.
            pubnonce_bytes: the public nonce of the signer it is
                attributed to, 66 bytes, exactly as it went into
                `nonce_agg`.
            pubkey_bytes: the public key of that signer, 33 or 65 bytes,
                exactly as it went into the `KeyAggCache` this session's
                key aggregation came from.
            keyagg_cache: that key aggregation.

        Returns:
            True if the partial signature is valid for that signer's
            nonce and key, within this session.

        Raises:
            ValueError: if any of the three byte arguments is not the
                right length or not one libsecp256k1-zkp will read.
        """
        ffi, lib, ctx = context._bindings()
        partial_sig = partial_sig_parse(partial_sig_bytes)
        pubnonce = pubnonce_parse(pubnonce_bytes)
        pubkey = _pubkey_parse(ffi, lib, ctx, pubkey_bytes, "public key")
        return bool(
            lib.secp256k1_musig_partial_sig_verify(
                ctx,
                partial_sig,
                pubnonce,
                pubkey,
                keyagg_cache._cache_(),
                self._session,
            )
        )

    def partial_sig_agg(self, partial_sigs_bytes: Sequence[BytesLike]) -> bytes:
        """Aggregate the signers' partial signatures into the final one.

        The result is a plain BIP340 signature over the aggregate
        (possibly tweaked) key, unless this session was built with an
        adaptor point, in which case it is a pre-signature: `adapt` is
        what turns it into a valid one, given the secret the adaptor
        point commits to. Either way this answers 1 "which does NOT mean
        the resulting signature verifies", in the header's own words --
        `ssa.verify`, or `adapt` and then `ssa.verify`, is how a caller
        checks it.

        Args:
            partial_sigs_bytes: the signers' partial signatures, 32
                bytes each, one per signer of this session. At least
                one is required.

        Returns:
            The 64-byte aggregate signature, or pre-signature.

        Raises:
            ValueError: if the sequence is empty, or if one of the
                partial signatures is not 32 bytes or not one below the
                curve order -- named by its position in the sequence,
                `partial_sigs_bytes[0]` being "partial signature at
                index 0".
            RuntimeError: if libsecp256k1-zkp fails to aggregate the
                result, which no valid input can make it do.
        """
        ffi, lib, ctx = context._bindings()
        if not partial_sigs_bytes:
            raise ValueError("at least one partial signature is required")
        # a per-contribution parse loop, for the reason nonce_agg's has
        partial_sigs = [
            partial_sig_parse(partial_sig_bytes, f"partial signature at index {index}")
            for index, partial_sig_bytes in enumerate(partial_sigs_bytes)
        ]
        signature = ffi.new(f"char[{_SIGNATURE_SIZE}]")
        if not lib.secp256k1_musig_partial_sig_agg(
            ctx,
            signature,
            self._session,
            _array(ffi, "secp256k1_musig_partial_sig *[]", partial_sigs),
            len(partial_sigs),
        ):
            raise RuntimeError("partial signature aggregation failed")
        return bytes(ffi.unpack(signature, _SIGNATURE_SIZE))

    def nonce_parity(self) -> int:
        """Return this session's aggregate nonce parity, for the adaptor calls.

        `adapt` and `extract_adaptor` both need it, and neither takes
        this session as an argument to read it from directly -- the
        header's own `secp256k1_musig_adapt` and
        `secp256k1_musig_extract_adaptor` do not, so this is the one
        call that connects a session back to either of them.

        Returns:
            0 or 1.

        Raises:
            RuntimeError: if libsecp256k1-zkp fails to extract it, which
                a session this built cannot make it do.
        """
        ffi, lib, ctx = context._bindings()
        parity = ffi.new("int *")
        if not lib.secp256k1_musig_nonce_parity(ctx, parity, self._session):
            raise RuntimeError("nonce parity extraction failed")
        return int(parity[0])

    def _session_(self) -> CData:
        """Return the libsecp256k1-zkp session object this holds.

        Returns:
            The libsecp256k1-zkp session object, read by
            `SecretNonce.partial_sign` and by this class's own methods.
        """
        return self._session


def adapt(
    pre_sig64: BytesLike, sec_adaptor: BytesLike | int, nonce_parity: int
) -> bytes:
    """Turn a pre-signature into a valid signature, given the adaptor secret.

    The other half of the adaptor signature protocol from the secret
    holder's side: `Session.partial_sig_agg`, over a session built with
    an adaptor point, answers the pre-signature this takes.
    `extract_adaptor` is the inverse, run by whoever holds both the
    pre-signature and the completed signature instead of the secret.

    Args:
        pre_sig64: the 64-byte pre-signature, from `Session.partial_sig_agg`.
        sec_adaptor: the 32-byte secret adaptor, or an int below 2**256,
            that the adaptor point given to `Session.__init__` commits
            to.
        nonce_parity: the output of `Session.nonce_parity`, called on the
            session that produced `pre_sig64`.

    Returns:
        The 64-byte signature. An incorrect `sec_adaptor` makes it
        invalid rather than makes this call fail -- `ssa.verify` is what
        a caller checks it with, this function not verifying it.

    Raises:
        TypeError: if `nonce_parity` is not an int.
        ValueError: if `pre_sig64` is not 64 bytes, if `sec_adaptor` is
            not 32 bytes or does not fit in them, if `nonce_parity` is
            not 0 or 1, or if `pre_sig64` or `sec_adaptor` overflow.
    """
    ffi, lib, ctx = context._bindings()
    pre_sig_bytes = octets(pre_sig64, "pre-signature", _SIGNATURE_SIZE)
    sec_adaptor_bytes = scalar(sec_adaptor, "secret adaptor")
    nonce_parity = in_range(nonce_parity, "nonce_parity", 1)
    sig64 = ffi.new(f"char[{_SIGNATURE_SIZE}]")
    if not lib.secp256k1_musig_adapt(
        ctx, sig64, pre_sig_bytes, sec_adaptor_bytes, nonce_parity
    ):
        raise ValueError("invalid pre-signature or secret adaptor")
    return bytes(ffi.unpack(sig64, _SIGNATURE_SIZE))


def extract_adaptor(sig64: BytesLike, pre_sig64: BytesLike, nonce_parity: int) -> bytes:
    """Extract the secret adaptor from a signature and its pre-signature.

    The inverse of `adapt`, and the reason an adaptor signature protocol
    works: whoever completes the pre-signature into `sig64` -- by
    whatever means, not necessarily `adapt` -- has thereby revealed the
    secret to anyone holding both signatures. Neither input is verified
    here: "if it is merely given signatures that do not verify, the
    returned value will be nonsense", the header's own words, and a
    caller is expected to have verified both already.

    Args:
        sig64: the 64-byte completed signature.
        pre_sig64: the 64-byte pre-signature it was completed from, from
            `Session.partial_sig_agg`.
        nonce_parity: the output of `Session.nonce_parity`, called on the
            session that produced `pre_sig64`.

    Returns:
        The 32-byte secret adaptor.

    Raises:
        TypeError: if `nonce_parity` is not an int.
        ValueError: if `sig64` or `pre_sig64` is not 64 bytes, if
            `nonce_parity` is not 0 or 1, or if `sig64` or `pre_sig64`
            grossly overflow.
    """
    ffi, lib, ctx = context._bindings()
    sig_bytes = octets(sig64, "signature", _SIGNATURE_SIZE)
    pre_sig_bytes = octets(pre_sig64, "pre-signature", _SIGNATURE_SIZE)
    nonce_parity = in_range(nonce_parity, "nonce_parity", 1)
    sec_adaptor = ffi.new(f"char[{_ADAPTOR_SIZE}]")
    if not lib.secp256k1_musig_extract_adaptor(
        ctx, sec_adaptor, sig_bytes, pre_sig_bytes, nonce_parity
    ):
        raise ValueError("invalid signature or pre-signature")
    return bytes(ffi.unpack(sec_adaptor, _ADAPTOR_SIZE))
