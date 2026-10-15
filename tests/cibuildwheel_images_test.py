# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""The Linux images `pyproject.toml` pins are the ones cibuildwheel ships.

`[tool.cibuildwheel.linux]` names each image by digest, and its comment
says cibuildwheel's own `manylinux_2_28` and `musllinux_1_2` aliases
resolve to the same objects. cibuildwheel resolves them through
`resources/pinned_docker_images.cfg`, a table inside the release `uv.lock`
pins, so a bump of cibuildwheel alone can make that sentence false. A pull
request builds only a few interpreters, so its wheel builds can pass where
the push run on `main` fails (btclib-org/btclib-secp256k1#1190).

This module compares each `*-image` key with the digest that table gives
for the key's architecture and for the alias the pinned image name
carries. It reads the table only from the cibuildwheel that `uv.lock`
pins, the one the builds use: the image tests are skipped where
cibuildwheel is not installed, where another version is, where `uv.lock`
is absent, and where it records a resolution other than the highest, as
`deps-oldest.yml` writes. Another version or resolution is a cibuildwheel
the pins were not chosen for.
"""

import configparser
import importlib.metadata
import re
import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).parents[1]
_LINUX: dict[str, str] = tomllib.loads(
    (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
)["tool"]["cibuildwheel"]["linux"]

# "x86_64" out of `manylinux-x86_64-image`, the architecture's name in the table
_IMAGE_KEY = re.compile(r"^(?P<family>manylinux|musllinux)-(?P<arch>[^-]+)-image$")
_PINNED = [key for key in _LINUX if key.endswith("-image")]


def _skip_reason(lock: str | None, installed: str | None) -> str | None:
    """Return why the table read is not the locked one, or None if it is.

    Args:
        lock: the text of `uv.lock`, or None where there is none.
        installed: the version of cibuildwheel installed, or None.

    Returns:
        The reason to skip, or None where the installed cibuildwheel is the
        one a highest resolution of `lock` pins.
    """
    if lock is None:
        return "uv.lock is not here, so no version of cibuildwheel is locked"
    data: dict[str, Any] = tomllib.loads(lock)
    mode = data.get("options", {}).get("resolution-mode", "highest")
    if mode != "highest":
        return f"uv.lock records a {mode} resolution, not the highest"
    locked = [p["version"] for p in data["package"] if p["name"] == "cibuildwheel"]
    assert len(locked) == 1, "uv.lock does not resolve cibuildwheel once"
    if installed is None:
        return "cibuildwheel is not installed"
    if installed != locked[0]:
        return f"cibuildwheel {installed} is installed, uv.lock pins {locked[0]}"
    return None


def _installed(name: str) -> str | None:
    """Return the version of the distribution `name`, or None if absent."""
    return next(
        (
            d.version
            for d in importlib.metadata.distributions()
            if (d.metadata["Name"] or "").lower() == name
        ),
        None,
    )


_LOCK = _ROOT / "uv.lock"
_SKIP = _skip_reason(
    _LOCK.read_text(encoding="utf-8") if _LOCK.is_file() else None,
    _installed("cibuildwheel"),
)
_LOCKED_CIBUILDWHEEL = pytest.mark.skipif(_SKIP is not None, reason=_SKIP or "")


def _table() -> configparser.ConfigParser:
    """Return the digests cibuildwheel resolves its aliases to, per arch."""
    parser = configparser.ConfigParser(inline_comment_prefixes=("#",))
    cfg = files("cibuildwheel") / "resources" / "pinned_docker_images.cfg"
    parser.read_string(cfg.read_text(encoding="utf-8"))
    return parser


def test_an_installed_distribution_is_found_by_its_name() -> None:
    """A lookup that finds nothing skips the image tests silently."""
    assert _installed("pytest") is not None
    assert _installed("no-such-distribution") is None


def test_the_image_keys_were_read() -> None:
    """A list that parsed to nothing is one every comparison passes on."""
    assert sorted(_PINNED) == [
        "manylinux-aarch64-image",
        "manylinux-x86_64-image",
        "musllinux-aarch64-image",
        "musllinux-x86_64-image",
    ]


_SAMPLE = """\
version = 1
{options}
[[package]]
name = "cibuildwheel"
version = "4.3.0"
"""
_HIGHEST = _SAMPLE.format(options="")
_LOWEST = _SAMPLE.format(options='[options]\nresolution-mode = "lowest-direct"\n')


@pytest.mark.parametrize(
    "lock, installed, reason",
    [
        (None, "4.3.0", "uv.lock is not here"),
        (_LOWEST, "4.3.0", "lowest-direct resolution"),
        (_HIGHEST, None, "cibuildwheel is not installed"),
        (_HIGHEST, "4.2.0", "4.2.0 is installed, uv.lock pins 4.3.0"),
        (_HIGHEST, "4.3.0", None),
    ],
    ids=["no-lock", "lowest", "absent", "other-version", "locked"],
)
def test_the_table_is_read_only_from_the_locked_cibuildwheel(
    lock: str | None, installed: str | None, reason: str | None
) -> None:
    """Each way the table read is not the locked one has its own reason."""
    got = _skip_reason(lock, installed)
    assert (got is None) if reason is None else (reason in (got or ""))


@_LOCKED_CIBUILDWHEEL
@pytest.mark.parametrize("key", _PINNED)
def test_every_image_pin_is_the_one_cibuildwheel_ships(key: str) -> None:
    """The digest is the one the locked cibuildwheel ships for its alias."""
    match = _IMAGE_KEY.fullmatch(key)
    assert match, f"{key} is not an image key of the shape this module reads"
    arch = match["arch"]
    pinned = _LINUX[key]
    repository = pinned.split("@", 1)[0].removeprefix("quay.io/pypa/")
    suffix = f"_{arch}"
    assert repository.endswith(suffix), f"{key} names {repository}, not {arch}"
    alias = repository.removesuffix(suffix)
    assert alias.startswith(match["family"]), f"{key} names the image {alias}"
    table = _table()
    assert table.has_option(arch, alias), f"cibuildwheel ships no {alias} for {arch}"
    shipped = table[arch][alias]
    assert pinned == shipped, (
        f"[tool.cibuildwheel.linux]'s {key} is {pinned} where cibuildwheel's"
        f" {alias} for {arch} is {shipped}"
    )
