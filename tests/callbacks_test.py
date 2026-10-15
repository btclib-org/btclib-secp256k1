# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests of what libsecp256k1 reports through the context's illegal callback.

What it records is `context.check`'s to raise, except for the
wrappers that read it through `context._checked`. Three parts are tested
here. That `check` itself reports, clears and attributes per thread;
that a wrapper handed an object libsecp256k1 cannot read answers
*something* -- its own exception where a return code allowed one, and
otherwise a value that means nothing -- while leaving the reason on the
thread for a `check` that follows; and that the sums, the sort and the
ECDH raise the reason instead, leaving the thread as they found it.

The second part is the contract a caller has to know, so each of its
shapes is driven rather than described: a raise whose message is the
wrapper's own, a `False` from a verification, and an ordering from a
comparison. The public entry points are the counter-case, parsing their
octets and so leaving the thread clean.

One of those shapes is not an object the caller handed `lib` but an
argument of a wrapper: the public key `recovery._sign_` compares against
is taken on trust, so an unreadable one is recorded on the thread from
inside a call that answers its own `ValueError` about the key. That the
verdict is right anyway is the reasoning that docstring gives, and the
last test here is it.

An internal error is not among these shapes: libsecp256k1 never returns
one to a caller, its own aborting default applying to it, and
`context.py`'s own comment beside its callback registration has the
reasoning.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import pytest

from btclib_secp256k1 import (
    CData,
    _secret,
    context,
    dsa,
    ecdh,
    ellswift,
    ffi,
    keys,
    lib,
    musig,
    recovery,
    silentpayments,
    ssa,
    xonly,
)
from btclib_secp256k1.context import ctx

# a public key libsecp256k1 is asked to parse into nowhere: the bindings
# always give it a buffer, a call through lib does not have to
NOWHERE_ARGS = (ffi.NULL, b"\x02" + b"\x01" * 32, 33)


def test_check_with_nothing_reported() -> None:
    """With nothing reported, check returns: that is the whole behaviour."""
    # nothing reported is not an error: returning is the whole behaviour
    context.check()


def test_illegal_argument() -> None:
    """An illegal argument reaches the caller as ValueError, with its text.

    Driven through `lib`, which a wrapper taking octets cannot do: it
    gives libsecp256k1 bytes it has already checked. The wrappers taking
    an object the caller holds are the exception, and are driven below.
    """
    assert not lib.secp256k1_ec_pubkey_parse(ctx, *NOWHERE_ARGS)
    with pytest.raises(ValueError, match="illegal argument: pubkey != NULL"):
        context.check()


def test_check_clears_what_it_reported() -> None:
    """A message is reported once, and not attributed to a later call.

    The second `check` returns, so what was raised is gone: left in
    place, it would surface out of whichever call came next and blame it
    for something it did not do.
    """
    assert not lib.secp256k1_ec_pubkey_parse(ctx, *NOWHERE_ARGS)
    with pytest.raises(ValueError, match="pubkey != NULL"):
        context.check()
    # the message is not reported twice, and cannot be attributed to a
    # later call which did not produce one
    context.check()


def test_serialize_raises_its_own_failure() -> None:
    """`keys.serialize` raises a bare failure, and the reason is on the thread.

    It takes the libsecp256k1 object the caller holds, so there is
    nothing to check about it before the call and the precondition is
    libsecp256k1's to violate. What reaches the caller is this wrapper's
    RuntimeError, the return code being all it read; which precondition
    was violated is what `check` answers after it, and a NULL pointer is
    the shortest way there.
    """
    with pytest.raises(RuntimeError, match="point serialization failed"):
        keys.serialize(ffi.NULL)
    with pytest.raises(ValueError, match="illegal argument: pubkey != NULL"):
        context.check()


def test_serialize_leaves_the_reason_on_the_thread() -> None:
    """And it leaves it there whether or not anybody comes to read it.

    A `secp256k1_pubkey` nothing has written to is the reachable form of
    the mistake: the message is about the zero field it finds, not about
    a pointer. Nothing clears it but a `check`, so the next one reports
    this call's message -- which is why `context.check` documents itself
    as belonging immediately after the call it explains.
    """
    with pytest.raises(RuntimeError, match="point serialization failed"):
        keys.serialize(ffi.new("secp256k1_pubkey *"))
    with pytest.raises(ValueError, match="illegal argument: !secp256k1_fe"):
        context.check()


def test_from_keypair_raises_its_own_failure() -> None:
    """`xonly.from_keypair` does as `keys.serialize` does, and for its reason.

    It takes the keypair the caller holds, so the precondition is
    libsecp256k1's to violate here too, and the conversion answering 0
    is all this wrapper reads. A NULL pointer names itself; a wiped
    keypair is the reachable mistake, and what libsecp256k1 reports of it
    is the zero it finds where the x of a point should be.
    """
    with pytest.raises(RuntimeError, match="x-only public key conversion failed"):
        xonly.from_keypair(ffi.NULL)
    with pytest.raises(ValueError, match="illegal argument: keypair != NULL"):
        context.check()

    signer = ssa.Signer(7)
    keypair = signer._keypair
    signer.wipe()
    with pytest.raises(RuntimeError, match="x-only public key conversion failed"):
        xonly.from_keypair(keypair)
    with pytest.raises(ValueError, match="illegal argument: !secp256k1_fe_is_zero"):
        context.check()


def test_verification_of_an_unreadable_key_is_false_not_a_verdict() -> None:
    """`dsa._verify_` answers False for a key libsecp256k1 cannot read.

    The same False a signature that does not verify gets, and the
    difference is on the thread rather than in the answer. This is the
    shape a caller has to know about: nothing raises, so a caller passing
    objects of its own reads a verdict that was never reached.
    """
    prvkey = (7).to_bytes(32, "big")
    msg = bytes(range(32))
    signature = dsa.parse_der(dsa.sign(msg, prvkey))

    assert dsa._verify_(msg, ffi.new("secp256k1_pubkey *"), signature) is False
    with pytest.raises(ValueError, match="illegal argument"):
        context.check()


def test_schnorr_verification_of_an_unreadable_key_is_false_too() -> None:
    """`ssa._verify_` answers False for the same reason `dsa._verify_` does.

    Two entry points and one contract, and the second is driven rather
    than inferred from the first: they read different libsecp256k1 calls
    of different key types, so which of them leaves a reason on the
    thread is a fact about each rather than about the shape they share.
    """
    msg = bytes(range(32))
    signature = ssa.sign(msg, 7)

    assert ssa._verify_(msg, ffi.new("secp256k1_xonly_pubkey *"), signature) is False
    with pytest.raises(ValueError, match="illegal argument"):
        context.check()


def test_a_signature_libsecp256k1_cannot_read_is_low_s_like_any_other() -> None:
    """`dsa._is_low_s_` answers True for a signature it was never shown.

    Which is the True an already-normalized signature gets: the call
    reports the input as unchanged either way, and nothing in the answer
    separates the two.

    NULL is what reaches that shape, and the zeroed object the tests
    above prefer would not: an r and an s of zero are a signature
    libsecp256k1 reads and normalizes -- answering True with the thread
    left clean -- where a zeroed `secp256k1_pubkey` is a point it
    refuses. The reachable mistake is not the same object twice.
    """
    assert dsa._is_low_s_(ffi.NULL) is True
    with pytest.raises(ValueError, match="illegal argument: sigin != NULL"):
        context.check()


def test_a_signature_libsecp256k1_cannot_read_has_no_low_r_to_read() -> None:
    """`dsa._is_low_r_` raises where `_is_low_s_` answers True.

    The two are asked the same way and answer differently, which is what
    the docstring names: `_is_low_s_` reads a return code, and a refused
    object is reported as unchanged exactly as an already-normalized one
    is, where this has to serialize first -- and a serialization that did
    not happen leaves no octet to compare.
    """
    with pytest.raises(RuntimeError, match="signature serialization failed"):
        dsa._is_low_r_(ffi.NULL)
    with pytest.raises(ValueError, match="illegal argument: sig != NULL"):
        context.check()


def test_comparison_of_unreadable_keys_is_an_ordering_like_any_other() -> None:
    """`keys._pubkey_cmp_` answers zero for two objects it could not read.

    Which is what it answers for two keys that are equal.
    """
    blank = ffi.new("secp256k1_pubkey *")

    assert keys._pubkey_cmp_(blank, blank) == 0
    with pytest.raises(ValueError, match="illegal argument"):
        context.check()


def _generator() -> CData:
    """Return the generator, parsed."""
    return keys.parse(keys.pubkey_from_prvkey(1))


# the wrappers that read the illegal callback themselves, each handed a
# `secp256k1_pubkey` nothing has written to or a NULL pointer, and the
# message libsecp256k1 reports for it. The sums and the sort take the
# first beside the generator: libsecp256k1 goes on with the unreadable
# key and answers a point or an ordering. The sort reads no key of a
# list of one, so that case is driven alone. A NULL pointer makes
# `secp256k1_ecdh` return 0, which alone would read as a refused private
# key
_UNREADABLE = "illegal argument: !secp256k1_fe_is_zero"
_RAISING_WRAPPERS: dict[str, tuple[Callable[[], object], str]] = {
    "ecdh._shared_secret_ of NULL": (
        lambda: ecdh._shared_secret_(ffi.NULL, 7),
        "illegal argument: point != NULL",
    ),
    "ecdh._shared_point_": (
        lambda: ecdh._shared_point_(_refused("secp256k1_pubkey"), 7),
        _UNREADABLE,
    ),
    "ecdh._shared_secret_": (
        lambda: ecdh._shared_secret_(_refused("secp256k1_pubkey"), 7),
        _UNREADABLE,
    ),
    "keys._pubkey_combine_": (
        lambda: keys._pubkey_combine_([_refused("secp256k1_pubkey"), _generator()]),
        _UNREADABLE,
    ),
    "keys._pubkey_sort_": (
        lambda: keys._pubkey_sort_([_refused("secp256k1_pubkey"), _generator()]),
        _UNREADABLE,
    ),
    "keys._pubkey_sort_ of one": (
        lambda: keys._pubkey_sort_([_refused("secp256k1_pubkey")]),
        _UNREADABLE,
    ),
    "keys._pubkey_sort_ of NULL": (
        lambda: keys._pubkey_sort_([_generator(), ffi.NULL]),
        r"illegal argument: pubkeys\[i\] != NULL",
    ),
    "keys._pubkey_sum_": (
        lambda: keys._pubkey_sum_([_refused("secp256k1_pubkey"), _generator()]),
        _UNREADABLE,
    ),
    "keys._pubkey_sum_ of NULL": (
        lambda: keys._pubkey_sum_([_generator(), ffi.NULL]),
        r"illegal argument: pubnonces\[i\] != NULL",
    ),
}


@pytest.mark.parametrize("name", sorted(_RAISING_WRAPPERS))
def test_an_unreadable_key_raises_libsecp256k1s_reason(name: str) -> None:
    """The sums, sort and ECDH raise the reason, and leave the thread clean.

    Each of these calls goes on computing with a key it cannot read, so
    the answer it would return looks like any other: a point, an
    ordering or 32 bytes. The raise is what tells the caller, and the
    `check` after it returning shows the message was not also left on
    the thread.
    """
    call, message = _RAISING_WRAPPERS[name]
    with pytest.raises(ValueError, match=message):
        call()
    context.check()


@pytest.mark.parametrize(
    "name, size", [("_shared_secret_", 32), ("_shared_point_", 64)]
)
def test_an_unreadable_key_leaves_no_ecdh_output_behind(
    name: str, size: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The buffer libsecp256k1 wrote into is wiped before the raise.

    The key here has a zero x, which libsecp256k1 refuses, and a y that
    is not zero: what `secp256k1_ecdh` computes from it depends on the
    private key, so it is wiped like any other secret. The real `wipe`
    runs, and the buffer it was given is read back afterwards.
    """
    unreadable = ffi.new("secp256k1_pubkey *")
    # the second half of the 64 octets holds y
    unreadable.data[32] = 5
    wiped: list[bytes] = []

    def recording(buffer: CData) -> None:
        wiped.append(bytes(ffi.buffer(buffer)))
        _secret.wipe(buffer)
        wiped.append(bytes(ffi.buffer(buffer)))

    monkeypatch.setattr(ecdh, "wipe", recording)
    with pytest.raises(ValueError, match=_UNREADABLE):
        getattr(ecdh, name)(unreadable, 7)
    before, after = wiped
    assert before != bytes(size)
    assert after == bytes(size)


def test_checked_keeps_what_the_thread_already_held() -> None:
    """A message recorded before the call is still there after it.

    `context._checked` clears the record to see what the call reports,
    and puts back what was there, so a `check` the caller still owes is
    not answered by a wrapper in between.
    """
    assert not lib.secp256k1_ec_pubkey_parse(ctx, *NOWHERE_ARGS)
    assert keys._pubkey_sum_([_generator(), _generator()]) is not None
    with pytest.raises(ValueError, match="pubkey != NULL"):
        context.check()


@pytest.mark.parametrize("returned", [0, 1])
def test_checked_reads_the_report_and_not_the_return_code(returned: int) -> None:
    """A report raises whatever the call returned.

    libsecp256k1's own sum and ECDH return 1 for a key they cannot read;
    a version that returns 0 for it must raise the same way. A stand-in
    records the report as the callback would, and returns either code.
    """

    def reporting() -> int:
        context._record_illegal(ffi.new("char[]", b"stand-in"), ffi.NULL)
        return returned

    with pytest.raises(ValueError, match="illegal argument: stand-in"):
        context._checked(reporting)
    context.check()


def test_the_public_entry_points_leave_the_thread_clean() -> None:
    """A caller who passes octets cannot reach any of that.

    `verify` and `pubkey_tweak_add` parse what they are given, so the
    objects they hand libsecp256k1 are ones it has just built: a bad key
    is refused by the parse, with this package's own message, and nothing
    is recorded on the thread. That is the whole of why the shapes above
    belong to the private halves alone.
    """
    msg = bytes(range(32))
    not_a_point = b"\x02" + bytes(32)

    with pytest.raises(ValueError, match="invalid public key"):
        keys.pubkey_tweak_add(not_a_point, 7)
    context.check()

    with pytest.raises(ValueError, match="invalid public key"):
        dsa.verify(msg, not_a_point, dsa.sign(msg, 7))
    context.check()


def test_reported_per_thread() -> None:
    """What one thread reports is not another thread's to raise.

    A callback runs on the thread of the call that triggered it, so a
    second thread sees nothing and the first still has its message. This
    is what lets one shared context serve every thread.
    """
    # a callback runs on the thread of the call that triggered it, so
    # what one thread reports is not another thread's to raise
    assert not lib.secp256k1_ec_pubkey_parse(ctx, *NOWHERE_ARGS)

    elsewhere: list[str] = []

    def other_thread() -> None:
        # raises, were the message of the calling thread visible here,
        # and the assertion below then finds nothing appended
        context.check()
        elsewhere.append("nothing reported")

    thread = threading.Thread(target=other_thread)
    thread.start()
    thread.join()

    assert elsewhere == ["nothing reported"]
    # the calling thread still has it
    with pytest.raises(ValueError, match="pubkey != NULL"):
        context.check()


def test_the_key_the_recoverable_check_trusts_is_the_one_nobody_validated() -> None:
    """A wrapper's own argument, unreadable, and a verdict that still holds.

    Every other shape above is an object a caller passed through `lib`.
    This one is an argument of a wrapper: `recovery._sign_` takes the key
    its check compares against on trust -- that being what the private
    half is for -- so a `secp256k1_pubkey` nothing has written to reaches
    `secp256k1_ec_pubkey_cmp`, and the illegal argument is recorded from
    inside a call that raises about the key instead.

    What is pinned here is that the answer is right regardless.
    libsecp256k1 serializes a key it cannot load as 33 zero octets,
    "less than any valid public key" by its own comment, so the readable
    recovered key compares unequal to it: the comparison falls through to
    the derivation, finds the signature is the signer's after all, and
    reports the key handed in. A `RuntimeError` there would have told the
    caller their hardware was faulty because they passed a zeroed struct.
    """
    msg = bytes(range(32))
    unreadable = ffi.new("secp256k1_pubkey *")
    with pytest.raises(ValueError, match="not this private key's"):
        recovery._sign_(msg, 7, pubkey=unreadable)
    with pytest.raises(ValueError, match="secp256k1_fe_is_zero"):
        context.check()


def _refused(type_name: str) -> object:
    """Return an object of `type_name` that nothing has written to."""
    return ffi.new(f"{type_name} *")


# every wrapper here takes an object the caller holds and answers its
# own RuntimeError where libsecp256k1 refuses it, so each of those raises
# is one an input reaches and the coverage ratchet counts
# (btclib-org/btclib-secp256k1#1030). `keys.serialize`,
# `xonly._from_keypair_` and `dsa.serialize_compact` have tests of their
# own above
_REFUSING_WRAPPERS: dict[str, tuple[Callable[[], object], str]] = {
    "dsa.serialize_der": (
        lambda: dsa.serialize_der(ffi.NULL),
        "signature serialization failed",
    ),
    "ellswift._encode_": (
        lambda: ellswift._encode_(_refused("secp256k1_pubkey"), None),
        "ElligatorSwift encoding failed",
    ),
    "keys._pubkey_negate_": (
        lambda: keys._pubkey_negate_(_refused("secp256k1_pubkey")),
        "public key negation failed",
    ),
    "musig.pubnonce_serialize": (
        lambda: musig.pubnonce_serialize(_refused("secp256k1_musig_pubnonce")),
        "public nonce serialization failed",
    ),
    "musig.aggnonce_serialize": (
        lambda: musig.aggnonce_serialize(_refused("secp256k1_musig_aggnonce")),
        "aggregate nonce serialization failed",
    ),
    "musig.partial_sig_serialize": (
        lambda: musig.partial_sig_serialize(_refused("secp256k1_musig_partial_sig")),
        "partial signature serialization failed",
    ),
    "recovery._to_der_": (
        lambda: recovery._to_der_(ffi.NULL),
        "signature conversion failed",
    ),
    "recovery.serialize_compact": (
        lambda: recovery.serialize_compact(ffi.NULL),
        "signature serialization failed",
    ),
    "silentpayments.serialize_label": (
        lambda: silentpayments.serialize_label(
            _refused("secp256k1_silentpayments_label")
        ),
        "label serialization failed",
    ),
    "ssa._sign32": (
        lambda: ssa._sign32(bytes(32), _refused("secp256k1_keypair"), None),
        "schnorr signing failed",
    ),
    "ssa._sign_custom": (
        lambda: ssa._sign_custom(b"msg", _refused("secp256k1_keypair"), None),
        "schnorr signing failed",
    ),
    "xonly._from_pubkey_": (
        lambda: xonly._from_pubkey_(_refused("secp256k1_pubkey")),
        "x-only public key conversion failed",
    ),
    "xonly.serialize": (
        lambda: xonly.serialize(_refused("secp256k1_xonly_pubkey")),
        "x-only public key serialization failed",
    ),
}


@pytest.mark.parametrize("name", sorted(_REFUSING_WRAPPERS))
def test_a_refused_object_raises_the_wrappers_own_failure(name: str) -> None:
    """The wrapper's own message, and libsecp256k1's reason on the thread.

    Each call hands libsecp256k1 a NULL pointer or an object nothing has
    written to, the two ways a caller-held object can be one it will not
    read.
    """
    call, message = _REFUSING_WRAPPERS[name]
    with pytest.raises(RuntimeError, match=message):
        call()
    with pytest.raises(ValueError, match="illegal argument"):
        context.check()


def test_the_static_context_is_not_randomized() -> None:
    """`context._randomize` answers its own failure for a context it refuses.

    `secp256k1_context_static` has no signing precomputation to re-blind,
    and `secp256k1_context_randomize` refuses a context that is not a
    proper one.
    """
    with pytest.raises(RuntimeError, match="context randomization failed"):
        context._randomize(lib.secp256k1_context_static)
