# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The `repr` and `str` of a class that holds a secret hold none of it.

Section 7 of the btclib-org standard asks, for a class that holds a
secret, for a test that its repr and its str() hold none of it.
`tests/secret_free/__init__.py` reads an exception, so the two texts
are put in one (`Shown`) and the helper's own window rule is applied to
them.

Which classes hold a secret is read off the package: the classes each
module of `btclib_secp256k1` defines, found by `defined_classes`, each
named in `HOLDS_A_SECRET` or in `HOLDS_NONE`. A class added without
being named in one fails `test_every_class_is_classified`, so the answer
is given for it. Each class of `HOLDS_NONE` keeps the `repr` and `str`
of `object`, which show a type and an address.

The zkp flavour of `SecretNonce` is checked in
`tests/zkp_secret_free_reprs_test.py`, which needs the flagged build.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override

import btclib_secp256k1
from btclib_secp256k1 import ffi, keys, musig, ssa

from .secret_free import assert_secret_free

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

    from btclib_secp256k1.zkp import musig as zkp_musig

#: The classes that hold a private key, a nonce, a blind or a keypair.
HOLDS_A_SECRET = frozenset({
    "btclib_secp256k1.musig.SecretNonce",
    "btclib_secp256k1.ssa.Signer",
    "btclib_secp256k1.zkp.musig.SecretNonce",
})

#: The classes that hold public data only, or thread-local error state.
HOLDS_NONE = frozenset({
    "btclib_secp256k1.context._Reported",
    "btclib_secp256k1.keys.PubkeyTweakChain",
    "btclib_secp256k1.musig.KeyAggCache",
    "btclib_secp256k1.musig.Session",
    "btclib_secp256k1.zkp.context._Reported",
    "btclib_secp256k1.zkp.musig.KeyAggCache",
    "btclib_secp256k1.zkp.musig.Session",
})

#: A made-up private key, which no text of the package contains.
PRVKEY = bytes.fromhex(
    "1d2f3e4d5c6b7a8998a7b6c5d4e3f20112233445566778899aabbccddeeff0a1"  # pragma: allowlist secret
)

#: The order of the group, to turn a key into the key BIP340 uses for it.
ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

#: The key negated, which BIP340 signs with where the public key's y is odd.
NEGATED = (ORDER - int.from_bytes(PRVKEY, "big")).to_bytes(32, "big")

MSG = bytes.fromhex("c0ffee" * 10 + "abcd")


class Shown(Exception):  # noqa: N818
    """An exception that shows a text, to hand it to `assert_secret_free`."""

    def __init__(self, text: str) -> None:  # noqa: D107
        super().__init__()
        self.text = text

    @override
    def __str__(self) -> str:
        return self.text

    @override
    def __repr__(self) -> str:
        return self.text


def assert_repr_secret_free(
    obj: object, secrets: list[str | bytes | bytearray]
) -> None:
    """Assert that neither `repr(obj)` nor `str(obj)` holds a piece of a secret.

    Args:
        obj: the object holding the secret.
        secrets: the secret, in each spelling a text could print it.
    """
    assert_secret_free(Shown(f"{obj!r}\n{obj!s}"), secrets)


def spelled(*octets: bytes) -> list[str | bytes | bytearray]:
    """Return the bytes of a secret, their hex and their decimal.

    Args:
        octets: each secret, as bytes.

    Returns:
        The same bytes, their hex, and the decimal of their big-endian int.
    """
    return [
        *octets,
        *(o.hex() for o in octets),
        *(str(int.from_bytes(o, "big")) for o in octets),
    ]


def keypair_secret(signer: ssa.Signer) -> bytes:
    """Return the 32 secret octets of the keypair a signer holds.

    Args:
        signer: a signer that is not wiped.

    Returns:
        The first 32 octets of the `secp256k1_keypair`, the secret key.
    """
    held = signer._keypair
    assert held is not None
    return bytes(ffi.buffer(held))[:32]


def secnonce_secret(secnonce: musig.SecretNonce | zkp_musig.SecretNonce) -> bytes:
    """Return the 64 secret octets of the nonce a `SecretNonce` holds.

    The layout is `secp256k1_musig_secnonce_save`'s: four octets of magic,
    the two nonce scalars, then the public key.

    Args:
        secnonce: a secret nonce that is not wiped.

    Returns:
        The two scalars.
    """
    held = secnonce._secnonce
    assert held is not None
    return bytes(ffi.buffer(held))[4:68]


def defined_classes(package: ModuleType) -> Iterator[type]:
    """Yield each class a module of a package defines, at any depth.

    Args:
        package: the package.

    Yields:
        The classes whose `__module__` is the module that holds them, so
        that a name imported from elsewhere is counted once, where it is
        defined.
    """
    for info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        yield from (
            cls
            for _, cls in inspect.getmembers(module, inspect.isclass)
            if cls.__module__ == module.__name__
        )
        if info.ispkg:
            yield from defined_classes(module)


def qualified(cls: type) -> str:
    """Return the dotted name of a class.

    Args:
        cls: the class.

    Returns:
        Its module and its name.
    """
    return f"{cls.__module__}.{cls.__qualname__}"


def test_every_class_is_classified() -> None:
    """Each class the package defines is named as holding a secret or none."""
    found = {qualified(cls) for cls in defined_classes(btclib_secp256k1)}
    assert found == HOLDS_A_SECRET | HOLDS_NONE


def test_the_two_lists_do_not_overlap() -> None:
    """A class is in one list only."""
    assert not HOLDS_A_SECRET & HOLDS_NONE


@pytest.mark.parametrize("name", sorted(HOLDS_NONE | HOLDS_A_SECRET))
def test_no_class_writes_its_own_repr_or_str(name: str) -> None:
    """A class that writes neither shows a type and an address, like `object`.

    A class of `HOLDS_A_SECRET` that starts to write one, for a debugger
    or a log, moves from here to the tests below, where its text is read
    for the secret.

    Args:
        name: the dotted name of a class the package defines.
    """
    module, _, qualname = name.rpartition(".")
    cls = getattr(importlib.import_module(module), qualname)
    assert cls.__repr__ is object.__repr__
    assert cls.__str__ is object.__str__


def a_signer(prvkey: bytes | int = PRVKEY) -> ssa.Signer:
    """Build a signer, which the caller is to wipe.

    Args:
        prvkey: the private key.

    Returns:
        The signer.
    """
    return ssa.Signer(prvkey)


@pytest.mark.parametrize(
    "prvkey", [PRVKEY, int.from_bytes(PRVKEY, "big")], ids=["bytes", "int"]
)
def test_a_signer_shows_no_key(prvkey: bytes | int) -> None:
    """Neither `repr` nor `str` of a signer holds the key, in any spelling.

    BIP340 signs with the negation of the key where its public key has an
    odd y, so both are looked for.

    Args:
        prvkey: the private key, as bytes and as an int.
    """
    with a_signer(prvkey) as signer:
        held = keypair_secret(signer)
        assert held == PRVKEY
        assert_repr_secret_free(signer, spelled(PRVKEY, NEGATED))


def test_a_wiped_signer_shows_no_key() -> None:
    """A signer shows no key after `wipe`, either."""
    signer = a_signer()
    signer.wipe()
    assert_repr_secret_free(signer, spelled(PRVKEY))


def a_secnonce(
    module: ModuleType = musig,
) -> musig.SecretNonce | zkp_musig.SecretNonce:
    """Build a secret nonce under the key, which the caller is to wipe.

    Args:
        module: `btclib_secp256k1.musig` or `btclib_secp256k1.zkp.musig`.

    Returns:
        The secret nonce.
    """
    pubkey = keys.pubkey_from_prvkey(PRVKEY)
    secnonce: musig.SecretNonce | zkp_musig.SecretNonce = module.nonce_gen(
        pubkey, PRVKEY, msg32=MSG
    )
    return secnonce


def test_a_secret_nonce_shows_no_nonce_and_no_key() -> None:
    """Neither `repr` nor `str` of a secret nonce holds its nonce or the key."""
    with a_secnonce() as secnonce:
        nonce = secnonce_secret(secnonce)
        assert nonce != bytes(64)
        assert_repr_secret_free(secnonce, spelled(nonce[:32], nonce[32:], PRVKEY))


def test_a_wiped_secret_nonce_shows_no_key() -> None:
    """A secret nonce shows no key after `wipe`, either."""
    secnonce = a_secnonce()
    secnonce.wipe()
    assert_repr_secret_free(secnonce, spelled(PRVKEY))


class _KeyInRepr(ssa.Signer):
    """A signer whose `repr` shows the key."""

    @override
    def __repr__(self) -> str:
        return f"Signer({keypair_secret(self).hex()})"


class _KeyInStr(ssa.Signer):
    """A signer whose `str` shows the key."""

    @override
    def __str__(self) -> str:
        return f"Signer({int.from_bytes(keypair_secret(self), 'big')})"


class _NonceInRepr(musig.SecretNonce):
    """A secret nonce whose `repr` shows the first nonce scalar."""

    @override
    def __repr__(self) -> str:
        return f"SecretNonce({secnonce_secret(self)[:32]!r})"


class _NonceInStr(musig.SecretNonce):
    """A secret nonce whose `str` shows the key."""

    @override
    def __str__(self) -> str:
        return f"SecretNonce({PRVKEY.hex()})"


def test_the_helper_fails_on_a_repr_or_str_that_shows_the_key() -> None:
    """A planted `__repr__` or `__str__` that prints a secret is caught.

    The signer's two cases print the key from the keypair, in hex through
    `repr` and in decimal through `str`. The secret nonce's print the
    first scalar as the bytes `repr` writes, and the key in hex.
    """
    signers: list[ssa.Signer] = [_KeyInRepr(PRVKEY), _KeyInStr(PRVKEY)]
    for signer in signers:
        with signer:
            secrets = spelled(PRVKEY, NEGATED, keypair_secret(signer))
            with pytest.raises(AssertionError):
                assert_repr_secret_free(signer, secrets)

    with a_secnonce() as secnonce:
        nonce = secnonce_secret(secnonce)
        held_nonce = secnonce._secnonce
        assert held_nonce is not None
        for cls in (_NonceInRepr, _NonceInStr):
            leaky_nonce = cls(held_nonce, secnonce._pubnonce, secnonce._pubkey)
            with pytest.raises(AssertionError):
                assert_repr_secret_free(
                    leaky_nonce, spelled(nonce[:32], nonce[32:], PRVKEY)
                )
