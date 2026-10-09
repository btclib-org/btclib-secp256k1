# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""`zkp.ecdsa_adaptor` against the ECDSA adaptor signature spec's vectors.

Every test here is marked `zkp`: it needs `BTCLIB_LIBSECP256K1_ZKP=true`.

The vectors are the first six of
`secp256k1-zkp/src/modules/ecdsa_adaptor/tests_impl.h`'s
`test_ecdsa_adaptor_spec_vectors`, which lifts them from the DLC
specification, `dlcspecs`,
<https://github.com/discreetlogcontracts/dlcspecs/blob/596a177375932a47306f07e7385f398f52519a83/test/ecdsa_adaptor.json>:
the three verification and the three recovery ones, with the checks the
C test makes on each. The other five are serialization tests of an
internal function this module does not wrap. The adaptor signatures,
keys and signatures come from the specification, so the wrapper's
answers are compared with values it did not produce.
"""

from __future__ import annotations

import pytest

pytest.importorskip("_btclib_secp256k1_zkp")

from btclib_secp256k1.zkp import ecdsa_adaptor

pytestmark = pytest.mark.zkp

_VECTORS: dict[int, dict[str, str]] = {
    0: {  # plain valid adaptor signature
        "adaptor_sig": (
            "03424d14a5471c048ab87b3b83f6085d125d5864249ae4297a57c84e74710bb6"
            "730223f325042fce535d040fee52ec13231bf709ccd84233c6944b90317e6252"
            "8b2527dff9d659a96db4c99f9750168308633c1867b70f3a18fb0f4539a1aece"
            "dcd1fc0148fc22f36b6303083ece3f872b18e35d368b3958efe5fb081f771673"
            "6ccb598d269aa3084d57e1855e1ea9a45efc10463bbf32ae378029f5763ceb40"
            "173f"
        ),
        "message_hash": "8131e6f4b45754f2c90bd06688ceeabc0c45055460729928b4eecf11026a9e2d",
        "pubkey": (
            "035be5e9478209674a96e60f1f037f6176540fd001fa1d64694770c56a7709c42c"
        ),
        "encryption_key": (
            "02c2662c97488b07b6e819124b8989849206334a4c2fbdf691f7b34d2b16e9c293"
        ),
        "decryption_key": "0b2aba63b885a0f0e96fa0f303920c7fb7431ddfa94376ad94d969fbf4109dc8",
        "signature": (
            "424d14a5471c048ab87b3b83f6085d125d5864249ae4297a57c84e74710bb673"
            "29e80e0ee60e57af3e625bbae1672b1ecaa58effe613426b024fa1621d903394"
        ),
    },
    1: {  # verification test
        "adaptor_sig": (
            "036035c89860ec62ad153f69b5b3077bcd08fbb0d28dc7f7f6df4a05cca35455"
            "be037043b63c56f6317d9928e8f91007335748c49824220db14ad10d80a5d00a"
            "9654af0996c1824c64c90b951bb2734aaecf78d4b36131a47238c3fa2ba25e2c"
            "ed54255b06df696de1483c3767242a3728826e05f79e3981e12553355bba8a01"
            "31cd370e63e3da73106f638576a5aab0ea6d45c042574c0c8d0b14b8c7c01cfe"
            "9072"
        ),
        "message_hash": "8131e6f4b45754f2c90bd06688ceeabc0c45055460729928b4eecf11026a9e2d",
        "pubkey": (
            "035be5e9478209674a96e60f1f037f6176540fd001fa1d64694770c56a7709c42c"
        ),
        "encryption_key": (
            "024eee18be9a5a5224000f916c80b393447989e7194bc0b0f1ad7a03369702bb51"
        ),
        "decryption_key": "db2debddb002473a001dd70b06f6c97bdcd1c46ba1001237fe0ee1aeffb2b6c4",
        "signature": (
            "6035c89860ec62ad153f69b5b3077bcd08fbb0d28dc7f7f6df4a05cca35455be"
            "4ceacf921546c03dd1be596723ad1e7691bdac73d88cc36c421c5e7f08384305"
        ),
    },
    2: {  # proof is wrong
        "adaptor_sig": (
            "03f94dca206d7582c015fb9bffe4e43b14591b30ef7d2b464d103ec5e116595d"
            "ba03127f8ac3533d249280332474339000922eb6a58e3b9bf4fc7e01e4b4df2b"
            "7a4100a1e089f16e5d70bb89f961516f1de0684cc79db978495df2f399b0d01e"
            "d7240fa6e3252aedb58bdc6b5877b0c602628a235dd1ccaebdddcbe96198c0c2"
            "1bead7b05f423b673d14d206fa1507b2dbe2722af792b8c266fc25a2d901d7e2"
            "c335"
        ),
        "message_hash": "8131e6f4b45754f2c90bd06688ceeabc0c45055460729928b4eecf11026a9e2d",
        "pubkey": (
            "035be5e9478209674a96e60f1f037f6176540fd001fa1d64694770c56a7709c42c"
        ),
        "encryption_key": (
            "0214ccb756249ad6e733c80285ea7ac2ee12ffebbcee4e556e6810793a60c45ad4"
        ),
        "decryption_key": "1dfcfc0880e72509768ab46f2545b33168b8b8df8e4f5feb5059aa3750ee59d0",
        "signature": (
            "424d14a5471c048ab87b3b83f6085d125d5864249ae4297a57c84e74710bb673"
            "29e80e0ee60e57af3e625bbae1672b1ecaa58effe613426b024fa1621d903394"
        ),
    },
    3: {  # plain recovery
        "adaptor_sig": (
            "03f2db6e9ed33092cc0b898fd6b282e99bdaeccb3de85c2d2512d8d507f9abab"
            "290210c01b5bed7094a12664aeaab3402d8709a8f362b140328d1b36dd7cb420"
            "d02fb66b1230d61c16d0cd0a2a02246d5ac7848dcd6f04fe627053cd3c7015a7"
            "d4aa6ac2b04347348bd67da43be8722515d99a7985fbfa66f0365c701de76ff0"
            "400dffdc9fa84dddf413a729823b16af60aa6361bc32e7cfd6701e32957c72ac"
            "e67b"
        ),
        "encryption_key": (
            "027ee4f899bc9c5f2b626fa1a9b37ce291c0388b5227e90b0fd8f4fa576164ede7"
        ),
        "decryption_key": "9cf3ea9be594366b78c457162908af3c2ea177058177e9c6bf99047927773a06",
        "signature": (
            "f2db6e9ed33092cc0b898fd6b282e99bdaeccb3de85c2d2512d8d507f9abab29"
            "21811fe7b53becf3b7affa9442abaa93c0ab8a8e45cd7ee2ea8d258bfc25d464"
        ),
    },
    4: {  # the R value of the signature does not match
        "adaptor_sig": (
            "03aa86d78059a91059c29ec1a757c4dc029ff636a1e6c1142fefe1e9d7339617"
            "c003a8153e50c0c8574a38d389e61bbb0b5815169e060924e4b5f2e78ff13aa7"
            "ad858e0c27c4b9eed9d60521b3f54ff83ca4774be5fb3a680f820a35e8840f4a"
            "af2de88e7c5cff38a37b78725904ef97bb82341328d55987019bd38ae1745e3e"
            "fe0f8ea8bdfede0d378fc1f96e944a7505249f41e93781509ee0bade77290d39"
            "cd12"
        ),
        "encryption_key": (
            "035176d24129741b0fcaa5fd6750727ce30860447e0a92c9ebebdeb7c3f93995ed"
        ),
        "signature": (
            "f7f7fe6bd056fc4abd70d335f72d0aa1e8406bba68f3e579e4789475323564a4"
            "52c46176c7fb40aa37d5651341f55697dab27d84a213b30c93011a7790bace8c"
        ),
    },
    5: {  # recovery from high s signature
        "adaptor_sig": (
            "032c637cd797dd8c2ce261907ed43e82d6d1a48cbabbbece801133dd8d70a01b"
            "1403eb615a3e59b1cbbf4f87acaf645be1eda32a066611f35dd5557802802b14"
            "b19c81c04c3fefac5783b2077bd43fa0a39ab8a64d4d78332a5d621ea23eca46"
            "bc011011ab82dda6deb85699f508744d70d4134bea03f784d285b5c6c15a56e4"
            "e1fab4bc356abbdebb3b8fe1e55e6dd6d2a9ea457e91b2e6642fae69f9dbb525"
            "8854"
        ),
        "encryption_key": (
            "02042537e913ad74c4bbd8da9607ad3b9cb297d08e014afc51133083f1bd687a62"
        ),
        "decryption_key": "324719b51ff2474c9438eb76494b0dc0bcceeb529f0a5428fd198ad8f886e99c",
        "signature": (
            "2c637cd797dd8c2ce261907ed43e82d6d1a48cbabbbece801133dd8d70a01b14"
            "b5f24321f550b7b9dd06ee4fcfd82bdad8b142ff93a790cc4d9f7962b38c6a3b"
        ),
    },
}

# vector -> (verify, decrypt reproduces the signature, recover succeeds),
# where None is a check the C test makes on no such vector
_EXPECTED: dict[int, tuple[bool | None, bool | None, bool]] = {
    0: (True, True, True),
    1: (True, True, True),
    2: (False, False, False),
    3: (None, True, True),
    4: (None, None, False),
    5: (None, False, True),
}


def _bytes(vector: int, name: str) -> bytes:
    return bytes.fromhex(_VECTORS[vector][name])


@pytest.mark.parametrize("vector", [0, 1, 2])
def test_spec_verify(vector: int) -> None:
    """`verify` answers what the specification says of the adaptor signature."""
    assert (
        ecdsa_adaptor.verify(
            _bytes(vector, "adaptor_sig"),
            _bytes(vector, "pubkey"),
            _bytes(vector, "message_hash"),
            _bytes(vector, "encryption_key"),
        )
        is _EXPECTED[vector][0]
    )


@pytest.mark.parametrize("vector", [0, 1, 2, 3, 5])
def test_spec_decrypt(vector: int) -> None:
    """`decrypt` gives the specification's signature, or not where it says not.

    Vector 5's signature has a high s, and `decrypt` answers the low-s
    form, so they differ; vector 2's adaptor signature is invalid, and
    `decrypt` does not check that.
    """
    signature = ecdsa_adaptor.decrypt(
        _bytes(vector, "decryption_key"), _bytes(vector, "adaptor_sig")
    )
    assert (signature == _bytes(vector, "signature")) is _EXPECTED[vector][1]


@pytest.mark.parametrize("vector", [0, 1, 2, 3, 4, 5])
def test_spec_recover(vector: int) -> None:
    """`recover` gives the specification's decryption key, or refuses."""
    args = (
        _bytes(vector, "signature"),
        _bytes(vector, "adaptor_sig"),
        _bytes(vector, "encryption_key"),
    )
    if not _EXPECTED[vector][2]:
        with pytest.raises(ValueError, match="does not match"):
            ecdsa_adaptor.recover(*args)
        return
    deckey = _bytes(vector, "decryption_key")
    assert ecdsa_adaptor.recover(*args) == deckey
    into = bytearray(32)
    assert ecdsa_adaptor.recover(*args, into=into) is None
    assert bytes(into) == deckey
