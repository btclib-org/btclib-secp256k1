# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Concurrent use of the shared libsecp256k1 context.

The bindings hold one context, created and randomized at import time and
passed to every call. That is safe because a context is only mutated by
secp256k1_context_randomize, which runs once before any thread exists,
and because each call allocates the buffers it writes to; but nothing in
the code says so, and static wheels are built for the free-threaded
interpreters (cp314t and cp315t), where these calls are no longer
serialized by an interpreter lock.

Every operation exercised here is deterministic, ECDSA by RFC6979 and
BIP340 by a fixed aux_rand32, so a result that differs between threads
is a shared buffer, not a legitimate difference.

`ssa.Signer` and `keys.PubkeyTweakChain` are what hold a buffer across
calls, and the second test is the half of the reasoning that does not
follow from the paragraph above: what makes a shared signer safe is that
libsecp256k1 takes a keypair const. A chain is not shared and is not
tested as if it were: `secp256k1_ec_pubkey_tweak_add` takes its key as
in and out, so every `tweak_add` writes the point the chain holds, and
one chain belongs to one thread. What is tested of it here is that a
chain per thread answers what a chain alone answers.

`musig.SecretNonce` is neither of those two shapes. It is not const, like
a keypair, and it is not one-thread-per-object by convention, like a
chain: it is meant to be read exactly once, from whichever thread gets
there first, and refused everywhere else -- the invariant the whole class
exists to hold, a secnonce driving `secp256k1_musig_partial_sign` twice
being how MuSig2 leaks the private key. `SecretNonce._take` makes the
read and the clear one atomic step under a lock private to the instance,
and the last two tests here are what that buys: `WORKERS` threads racing
one `SecretNonce`, of which exactly one may ever sign, and `WORKERS`
threads racing its `_take`, of which exactly one may ever succeed. The
first checks the outcome, which libsecp256k1's own refusal of a reused
secnonce also produces; the second is the one that fails without the lock.
"""

import contextlib
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from btclib_secp256k1 import CData, dsa, ecdh, keys, musig, ssa, xonly

prvkey = 0xB7331FE4A9F79F4A2B79A5BEE4CCA2C6A0A9DCE05C4EB77C1C8AA1CC1EE47ADD
tweak = 0x3F2B1C7D8E9F0A1B2C3D4E5F60718293A4B5C6D7E8F901A2B3C4D5E6F708192A
msg = b"\xa0\xdce\xff\xcay\x98s\xcb\xea\n\xc2t\x01[\x95&P]\xaa\xae\xd3\x85\x15T%\xf73w\x04\x88>"
aux_rand32 = b"\x11" * 32

WORKERS = 8
ROUNDS = 32
WINDOW = 1.0


def test_concurrent_round_trips() -> None:
    """Eight threads repeat every operation and reach one answer each.

    The values are computed once on the main thread and then asserted
    from the pool, so a result that differs is a buffer two calls shared
    rather than a legitimate difference: every operation here is
    deterministic. `map` is consumed rather than discarded, an assertion
    failing in a worker being raised only when its result is read.
    """
    pubkey_bytes = keys.pubkey_from_prvkey(prvkey, compressed=False)
    xonly_bytes, _ = xonly.from_pubkey(pubkey_bytes)
    dsa_sig = dsa.sign(msg, prvkey)
    ssa_sig = ssa.sign(msg, prvkey, aux_rand32)
    secret = ecdh.shared_secret(pubkey_bytes, tweak)
    tweaked = xonly.tweak_add(xonly_bytes, tweak)
    combined = keys.pubkey_combine([
        pubkey_bytes,
        keys.pubkey_from_prvkey(tweak, compressed=False),
    ])

    def round_trip(_: int) -> None:
        assert dsa.sign(msg, prvkey) == dsa_sig
        assert dsa.verify(msg, pubkey_bytes, dsa_sig)
        assert ssa.sign(msg, prvkey, aux_rand32) == ssa_sig
        assert ssa.verify(msg, xonly_bytes, ssa_sig)
        assert keys.pubkey_from_prvkey(prvkey, compressed=False) == pubkey_bytes
        assert ecdh.shared_secret(pubkey_bytes, tweak) == secret
        assert xonly.tweak_add(xonly_bytes, tweak) == tweaked
        assert (
            keys.pubkey_combine([
                pubkey_bytes,
                keys.pubkey_from_prvkey(tweak, compressed=False),
            ])
            == combined
        )

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        # map is lazy: the results have to be consumed for an assertion
        # failing in a worker to be raised here
        list(pool.map(round_trip, range(WORKERS * ROUNDS)))


def test_one_signer_signs_from_every_thread() -> None:
    """Eight threads share one keypair and reach the one signature.

    The keypair a signer holds is one of the two buffers these bindings
    keep across calls, so it is a place the module docstring's reasoning
    does not reach: what makes this safe is that libsecp256k1 takes a
    keypair const, and signing does not write to it. What is not safe is
    wiping it while a thread is inside `sign`, which is why the wipe here
    is after the pool has joined -- the ordering the `with` block gives a
    caller for free.
    """
    expected = ssa.sign(msg, prvkey, aux_rand32)
    signer = ssa.Signer(prvkey)

    def sign_through(_: int) -> None:
        assert signer.sign(msg, aux_rand32) == expected

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(sign_through, range(WORKERS * ROUNDS)))

    signer.wipe()


def test_a_chain_per_thread_walks_the_same_path() -> None:
    """Eight threads each build a chain, and all eight reach one path.

    The other buffer held across calls, and the one that is written by
    the calls that use it: `secp256k1_ec_pubkey_tweak_add` takes its key
    as in and out, so a chain shared between threads would be two writers
    of one point rather than two walkers of one path. A chain per thread
    is what a caller builds, and this is that: what each thread pays for
    it is the parse the chain then saves at every step after the first.
    """
    pubkey_bytes = keys.pubkey_from_prvkey(prvkey, compressed=False)
    tweaks = (tweak, prvkey, tweak)
    expected = [
        keys.pubkey_tweak_add(pubkey_bytes, tweaks[0]),
        keys.pubkey_tweak_add(
            keys.pubkey_tweak_add(pubkey_bytes, tweaks[0]), tweaks[1]
        ),
    ]
    expected.append(keys.pubkey_tweak_add(expected[-1], tweaks[2]))

    def walk(_: int) -> None:
        chain = keys.PubkeyTweakChain(pubkey_bytes)
        assert [chain.tweak_add(each) for each in tweaks] == expected
        assert chain.pubkey() == expected[-1]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(walk, range(WORKERS * ROUNDS)))


def test_exactly_one_thread_signs_a_shared_secret_nonce() -> None:
    """`WORKERS` threads race one `SecretNonce`, and exactly one signs it.

    The outcome `SecretNonce` promises, and no more: libsecp256k1 zeroes
    a secnonce when it loads it, so this passes, in practice, with or
    without `SecretNonce._lock`.
    `test_exactly_one_thread_takes_a_shared_secret_nonce` is the test of
    the lock.

    A single round rather than `ROUNDS`: a secret nonce is spent by the
    first thread to reach it, `ROUNDS` more attempts on the same one
    only exercising the refusal `test_a_wiped_secret_nonce_refuses_to
    _sign` already covers in `tests/musig_test.py`.
    """
    pubkey_bytes = keys.pubkey_from_prvkey(prvkey)
    cache = musig.KeyAggCache([pubkey_bytes])
    secnonce = musig.nonce_gen(pubkey_bytes, prvkey)
    aggnonce = musig.nonce_agg([secnonce.pubnonce])
    session = musig.Session(aggnonce, msg, cache)

    def race(_: int) -> bytes | None:
        try:
            return secnonce.partial_sign(prvkey, cache, session)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(race, range(WORKERS)))

    signed = [result for result in results if result is not None]
    assert len(signed) == 1
    assert results.count(None) == WORKERS - 1


def count_takes(secnonce_type: type[Any], secnonce: Any) -> int:
    """Return how many of `WORKERS` threads `_take` the same secret nonce.

    A subclass makes the read of `_secnonce` that finds a nonce wait,
    for up to `WINDOW` seconds, for a second reader that has found one too.
    With the check and the clear one operation under the lock, the
    second reader never comes and the wait runs out. Without the lock
    the readers meet and all go through to the clear.

    Args:
        secnonce_type: the class under test, mainline or zkp.
        secnonce: the nonce whose native parts the instance takes over,
            unused afterwards.

    Returns:
        The number of `_take` calls that returned the nonce.
    """
    meeting = threading.Barrier(2, timeout=WINDOW)

    class Slow(secnonce_type):  # type: ignore[misc]
        @property
        def _secnonce(self) -> CData | None:
            held: CData | None = self.__dict__.get("held")
            if held is not None:
                with contextlib.suppress(threading.BrokenBarrierError):
                    meeting.wait()
            return held

        @_secnonce.setter
        def _secnonce(self, value: CData | None) -> None:
            self.__dict__["held"] = value

    shared = Slow(secnonce._secnonce, secnonce._pubnonce, secnonce._pubkey)

    def take(_: int) -> bool:
        try:
            shared._take()
        except ValueError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return sum(pool.map(take, range(WORKERS)))


def test_exactly_one_thread_takes_a_shared_secret_nonce() -> None:
    """`WORKERS` threads race one `_take`, and exactly one gets the nonce.

    Several threads take it without `SecretNonce._lock`, and also with a
    `_take` that reads, waits and then clears.
    """
    secnonce = musig.nonce_gen(keys.pubkey_from_prvkey(prvkey), prvkey)
    assert count_takes(musig.SecretNonce, secnonce) == 1


@pytest.mark.zkp
def test_exactly_one_thread_takes_a_shared_zkp_secret_nonce() -> None:
    """The same for `btclib_secp256k1.zkp.musig.SecretNonce`."""
    pytest.importorskip("_btclib_secp256k1_zkp")
    from btclib_secp256k1.zkp import musig as zkp_musig  # noqa: PLC0415

    secnonce = zkp_musig.nonce_gen(keys.pubkey_from_prvkey(prvkey), prvkey)
    assert count_takes(zkp_musig.SecretNonce, secnonce) == 1
