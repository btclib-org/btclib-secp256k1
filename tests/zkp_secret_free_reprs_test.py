# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The `repr` and `str` of the zkp `SecretNonce` hold no secret.

The zkp flavour of `tests/secret_free_reprs_test.py`, whose helpers it
uses. It needs the flagged build, so a run against an unflagged one skips
it.
"""

from __future__ import annotations

import pytest
from typing_extensions import override

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1.zkp import musig

from .secret_free_reprs_test import (
    PRVKEY,
    a_secnonce,
    assert_repr_secret_free,
    secnonce_secret,
    spelled,
)

pytestmark = pytest.mark.zkp


def test_a_zkp_secret_nonce_shows_no_nonce_and_no_key() -> None:
    """Neither `repr` nor `str` of a secret nonce holds its nonce or the key."""
    with a_secnonce(musig) as secnonce:
        nonce = secnonce_secret(secnonce)
        assert nonce != bytes(64)
        assert_repr_secret_free(secnonce, spelled(nonce[:32], nonce[32:], PRVKEY))


def test_a_wiped_zkp_secret_nonce_shows_no_key() -> None:
    """A secret nonce shows no key after `wipe`, either."""
    secnonce = a_secnonce(musig)
    secnonce.wipe()
    assert_repr_secret_free(secnonce, spelled(PRVKEY))


class _NonceInRepr(musig.SecretNonce):
    """A secret nonce whose `repr` shows the first nonce scalar."""

    @override
    def __repr__(self) -> str:
        return f"SecretNonce({secnonce_secret(self)[:32]!r})"


class _KeyInStr(musig.SecretNonce):
    """A secret nonce whose `str` shows the key."""

    @override
    def __str__(self) -> str:
        return f"SecretNonce({PRVKEY.hex()})"


def test_the_helper_fails_on_a_repr_or_str_that_shows_the_key() -> None:
    """A planted `__repr__` or `__str__` that prints a secret is caught."""
    with a_secnonce(musig) as secnonce:
        nonce = secnonce_secret(secnonce)
        held = secnonce._secnonce
        assert held is not None
        for cls in (_NonceInRepr, _KeyInStr):
            leaky = cls(held, secnonce._pubnonce, secnonce._pubkey)
            with pytest.raises(AssertionError):
                assert_repr_secret_free(leaky, spelled(nonce[:32], nonce[32:], PRVKEY))
