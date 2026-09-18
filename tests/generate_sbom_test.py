# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Tests for the bill of materials generator of `.github/scripts`.

What the release publishes is one document per tag, and the release is
where it is written: nothing else in this repository runs the script, so
what a wrong reading of an archive or of a gitlink would cost is a signed
description of the wrong thing. The document the real tree produces is
built by `build-sdist` and attested beside the sdist; the archives here
are built by hand, PKG-INFO by PKG-INFO, so that the shapes a release
never reaches -- a requirement nothing can parse, a submodule url that is
not GitHub's, a dist directory holding two archives -- are answered here
rather than on release day.

`git` is stubbed rather than run, as `.github/scripts`'s other tests stub
it: what the script needs from it is the one line `git ls-tree` prints
for a gitlink, and that line is written out here.

The script is loaded by path, `.github/scripts` being no package, and
once: `monkeypatch` undoes what each test does to it.
"""

from __future__ import annotations

import gzip
import importlib.util
import io
import json
import runpy
import sys
import tarfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_EPOCH = 1_700_000_000
_PINNED = "6e2c8bc4ecdc6e71dbe7a368f360d8d453ce435d"
_ZKP_PINNED = "9912c3e49b012c91967315395d046be4836c2e34"

_METADATA = """Metadata-Version: 2.5
Name: btclib-secp256k1
Version: 0.8.0.7
Summary: Simple python bindings to libsecp256k1
Project-URL: homepage, https://btclib-secp256k1.readthedocs.io
Project-URL: pull_requests, https://github.com/btclib-org/btclib-secp256k1/pulls
License-Expression: MIT
Requires-Python: >=3.10
Requires-Dist: cffi>=1.6; python_version < '3.13'
Requires-Dist: cffi>=2.0; python_version >= '3.14'

the long description
"""

_GITMODULES = """[submodule "secp256k1"]
\tpath = secp256k1
\turl = https://github.com/bitcoin-core/secp256k1.git
[submodule "secp256k1-zkp"]
\tpath = secp256k1-zkp
\turl = https://github.com/fametrano/secp256k1-zkp.git
"""


def _load() -> ModuleType:
    """Import the generator by path.

    Returns:
        The module.
    """
    path = Path(__file__).parents[1] / ".github" / "scripts" / "generate_sbom.py"
    spec = importlib.util.spec_from_file_location("generate_sbom", path)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sbom = _load()


def write_sdist(
    directory: Path,
    *,
    name: str = "btclib_secp256k1-0.8.0.7.tar.gz",
    metadata: str | None = _METADATA,
    stem: str = "btclib_secp256k1-0.8.0.7",
    directory_member: bool = False,
) -> Path:
    """Write an sdist carrying the given core metadata.

    Args:
        directory: where to write the archive.
        name: the archive's file name, which the output is named after.
        metadata: the PKG-INFO to carry, or None for an archive with
            none.
        stem: the top-level directory inside the archive, whose depth is
            what tells the distribution's own PKG-INFO from a vendored
            one.
        directory_member: whether to add the PKG-INFO as a directory
            instead of a file, which is what `extractfile` answers None
            for.

    Returns:
        The archive's path.
    """
    path = directory / name
    with tarfile.open(path, "w:gz") as archive:
        if directory_member:
            member = tarfile.TarInfo(f"{stem}/PKG-INFO")
            member.type = tarfile.DIRTYPE
            archive.addfile(member)
        elif metadata is not None:
            content = metadata.encode()
            member = tarfile.TarInfo(f"{stem}/PKG-INFO")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        content = b"print()\n"
        source = tarfile.TarInfo(f"{stem}/module.py")
        source.size = len(content)
        archive.addfile(source, io.BytesIO(content))
    return path


def stub_git(monkeypatch: pytest.MonkeyPatch, answers: dict[str, str]) -> list[Any]:
    """Answer `git ls-tree` from a mapping of path to stdout.

    Args:
        monkeypatch: the fixture `subprocess.run` is replaced through.
        answers: the stdout to give for each path asked about.

    Returns:
        The argument list of every call, in order.
    """
    calls: list[Any] = []

    class _Result:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_run(args: list[str], **kwargs: Any) -> _Result:
        calls.append({"args": args, "cwd": kwargs.get("cwd")})
        return _Result(answers[args[-1]])

    monkeypatch.setattr(sbom.subprocess, "run", fake_run)
    return calls


def repository(tmp_path: Path, *, gitmodules: str | None = _GITMODULES) -> Path:
    """Write a repository root holding a `.gitmodules`.

    Args:
        tmp_path: the directory to make the root.
        gitmodules: its content, or None for a tree declaring no
            submodule.

    Returns:
        The root.
    """
    if gitmodules is not None:
        (tmp_path / ".gitmodules").write_text(gitmodules, encoding="utf-8")
    return tmp_path


def test_the_document_names_the_sdist_its_digest_and_its_licence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The root component is the distribution the archive declares.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture `git` is stubbed through.
    """
    sdist = write_sdist(tmp_path)
    stub_git(monkeypatch, {"secp256k1": "", "secp256k1-zkp": ""})
    monkeypatch.setattr(sbom, "submodule_components", lambda _root: [])

    document = sbom.build_sbom(sdist, _EPOCH, repository(tmp_path))

    root = document["metadata"]["component"]
    assert root["purl"] == "pkg:pypi/btclib-secp256k1@0.8.0.7"
    assert root["licenses"] == [{"expression": "MIT"}]
    assert root["description"] == "Simple python bindings to libsecp256k1"
    assert root["properties"] == [{"name": "btclib:requires-python", "value": ">=3.10"}]
    archive = root["externalReferences"][0]
    assert archive["url"] == sdist.name
    assert archive["hashes"][0]["content"] == sbom.file_hash(sdist)
    assert document["metadata"]["timestamp"] == "2023-11-14T22:13:20Z"


def test_a_project_url_with_no_cyclonedx_type_is_kept_as_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A label the vocabulary has no word for is recorded, not dropped.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture the submodule scan is stubbed through.
    """
    sdist = write_sdist(tmp_path)
    monkeypatch.setattr(sbom, "submodule_components", lambda _root: [])

    document = sbom.build_sbom(sdist, _EPOCH, repository(tmp_path))

    references = document["metadata"]["component"]["externalReferences"]
    labelled = {entry.get("comment"): entry["type"] for entry in references}
    assert labelled["homepage"] == "website"
    assert labelled["pull_requests"] == "other"


def test_metadata_the_archive_leaves_out_leaves_the_field_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A document states what the metadata says and invents no default.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture the submodule scan is stubbed through.
    """
    monkeypatch.setattr(sbom, "submodule_components", lambda _root: [])
    sdist = write_sdist(
        tmp_path,
        metadata="Metadata-Version: 2.5\nName: btclib-secp256k1\nVersion: 0.8.0.7\n",
    )

    root = sbom.build_sbom(sdist, _EPOCH, repository(tmp_path))["metadata"]["component"]

    assert "description" not in root
    assert "licenses" not in root
    assert "properties" not in root


def test_an_archive_declaring_no_version_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A document with no version is worse than no document.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture the submodule scan is stubbed through.
    """
    monkeypatch.setattr(sbom, "submodule_components", lambda _root: [])
    sdist = write_sdist(
        tmp_path, metadata="Metadata-Version: 2.5\nName: btclib-secp256k1\n"
    )

    with pytest.raises(SystemExit, match="declares no Name or no Version"):
        sbom.build_sbom(sdist, _EPOCH, repository(tmp_path))


def test_an_archive_with_no_pkg_info_is_refused(tmp_path: Path) -> None:
    """Reading the metadata out of the archive is what makes it describable.

    Args:
        tmp_path: pytest's own.
    """
    sdist = write_sdist(tmp_path, metadata=None)

    with pytest.raises(SystemExit, match="carries 0 PKG-INFO members"):
        sbom.sdist_metadata(sdist)


def test_a_vendored_pkg_info_is_not_the_distributions(tmp_path: Path) -> None:
    """Depth is what tells them apart, a vendored tree carrying its own.

    Args:
        tmp_path: pytest's own.
    """
    path = tmp_path / "btclib_secp256k1-0.8.0.7.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name in ("pkg/PKG-INFO", "pkg/vendored/PKG-INFO"):
            content = _METADATA.encode()
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))

    assert sbom.sdist_metadata(path)["Name"] == "btclib-secp256k1"


def test_a_pkg_info_that_is_not_a_file_is_refused(tmp_path: Path) -> None:
    """A member of that name with nothing to read is named, not skipped.

    Args:
        tmp_path: pytest's own.
    """
    sdist = write_sdist(tmp_path, directory_member=True)

    with pytest.raises(SystemExit, match="is not a regular file"):
        sbom.sdist_metadata(sdist)


def test_the_lines_naming_one_dependency_are_one_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`cffi` is three lines and one node of the graph.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture the submodule scan is stubbed through.
    """
    monkeypatch.setattr(sbom, "submodule_components", lambda _root: [])
    sdist = write_sdist(tmp_path)

    document = sbom.build_sbom(sdist, _EPOCH, repository(tmp_path))

    (cffi,) = document["components"]
    assert cffi["bom-ref"] == "pkg:pypi/cffi"
    assert "version" not in cffi, "a floor is not a version the archive pins"
    assert cffi["scope"] == "required"
    assert [entry["value"] for entry in cffi["properties"]] == [
        "cffi>=1.6; python_version < '3.13'",
        "cffi>=2.0; python_version >= '3.14'",
    ]
    assert document["dependencies"][0]["dependsOn"] == ["pkg:pypi/cffi"]


def test_a_pinned_requirement_gets_the_version_it_pins() -> None:
    """`==` is the one specifier naming a version rather than a range."""
    assert sbom.component([sbom.reading("cffi==1.17")])["version"] == "1.17"


def test_a_requirement_under_an_extra_alone_is_optional() -> None:
    """The scope is what says a dependency the archive asks for sometimes."""
    optional = sbom.component([sbom.reading('rich>=13; extra == "pretty"')])
    assert optional["scope"] == "optional"

    both = sbom.component([
        sbom.reading('rich>=13; extra == "pretty"'),
        sbom.reading("rich>=13"),
    ])
    assert both["scope"] == "required"


def test_a_direct_reference_is_recorded_as_a_vcs_reference() -> None:
    """The url a `@` requirement carries is where that dependency comes from."""
    reference = sbom.component([
        sbom.reading("btclib[dev] @ git+https://github.com/btclib-org/btclib@main")
    ])
    assert reference["externalReferences"] == [
        {"type": "vcs", "url": "git+https://github.com/btclib-org/btclib@main"}
    ]
    assert reference["purl"].endswith(
        "?vcs_url=git%2Bhttps%3A%2F%2Fgithub.com%2Fbtclib-org%2Fbtclib%40main"
    )
    assert {"name": "btclib:extras", "value": "dev"} in reference["properties"]


def test_lines_disagreeing_on_a_field_state_none_of_it() -> None:
    """A fact about one environment is not a fact about the distribution."""
    disagreeing = sbom.component([
        sbom.reading('cffi==1.17; python_version < "3.14"'),
        sbom.reading("cffi==2.0"),
    ])
    assert "version" not in disagreeing


def test_a_requirement_nothing_can_read_is_refused() -> None:
    """A dependency the document would omit in silence is the one failure.

    A line with no name at all is the shape here, an extras group and a
    direct reference standing where PEP 508 asks for a distribution: a
    name with a trailing specifier this cannot make sense of is read as
    the name plus an unpinned specifier rather than refused, which is
    what keeps the refusal to the lines nothing could describe.
    """
    with pytest.raises(SystemExit, match="cannot read the requirement"):
        sbom.reading("[dev] @ https://example.invalid/x.tar.gz")


def test_every_submodule_is_a_component_at_the_commit_it_is_pinned_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pin `Requires-Dist` cannot state is what the gitlink states.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture `git` is stubbed through.
    """
    calls = stub_git(
        monkeypatch,
        {
            "secp256k1": f"160000 commit {_PINNED}\tsecp256k1\n",
            "secp256k1-zkp": f"160000 commit {_ZKP_PINNED}\tsecp256k1-zkp\n",
        },
    )
    root = repository(tmp_path)

    components = sbom.submodule_components(root)

    assert [entry["purl"] for entry in components] == [
        f"pkg:github/bitcoin-core/secp256k1@{_PINNED}",
        f"pkg:github/fametrano/secp256k1-zkp@{_ZKP_PINNED}",
    ]
    assert components[0]["version"] == _PINNED
    assert components[0]["externalReferences"] == [
        {"type": "vcs", "url": "https://github.com/bitcoin-core/secp256k1.git"}
    ]
    assert components[1]["properties"] == [
        {"name": "btclib:submodule-path", "value": "secp256k1-zkp"}
    ]
    assert [call["args"][1:] for call in calls] == [
        ["ls-tree", "HEAD", "--", "secp256k1"],
        ["ls-tree", "HEAD", "--", "secp256k1-zkp"],
    ]
    assert {call["cwd"] for call in calls} == {root}


def test_the_pin_is_read_from_the_tree_and_not_from_a_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`git ls-tree HEAD` answers for a submodule nobody initialized.

    The release checks its submodules out and the sdist carries them, so
    what this holds is the other direction: nothing in the scan opens the
    submodule's own directory, which is what lets the document describe a
    pin without a clone of it.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture `git` is stubbed through.
    """
    stub_git(monkeypatch, {"secp256k1": f"160000 commit {_PINNED}\tsecp256k1\n"})
    root = repository(
        tmp_path,
        gitmodules='[submodule "secp256k1"]\n'
        "\tpath = secp256k1\n"
        "\turl = git@github.com:bitcoin-core/secp256k1\n",
    )

    (component,) = sbom.submodule_components(root)

    assert component["purl"] == f"pkg:github/bitcoin-core/secp256k1@{_PINNED}"
    assert not (root / "secp256k1").exists()


def test_a_path_that_is_no_gitlink_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ordinary file where a submodule was declared is a stale tree.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture `git` is stubbed through.
    """
    stub_git(monkeypatch, {"secp256k1": f"100644 blob {_PINNED}\tsecp256k1\n"})

    with pytest.raises(SystemExit, match="is not a pinned submodule"):
        sbom.submodule_commit(tmp_path, "secp256k1")


def test_a_submodule_url_that_is_not_githubs_is_refused() -> None:
    """A submodule the purl cannot name is one the document would omit."""
    with pytest.raises(SystemExit, match="cannot read the submodule url"):
        sbom.submodule_component("vendor", "https://gitlab.com/x/y.git", _PINNED)


def test_a_tree_declaring_no_submodule_contributes_no_component(
    tmp_path: Path,
) -> None:
    """The scan is a no-op where there is no `.gitmodules` to read.

    Args:
        tmp_path: pytest's own.
    """
    assert sbom.submodule_components(repository(tmp_path, gitmodules=None)) == []


def test_the_serial_number_is_the_archives_digest_and_not_the_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rebuild of a tag writes this file too, which is what signs it.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture the submodule scan is stubbed through.
    """
    monkeypatch.setattr(sbom, "submodule_components", lambda _root: [])
    sdist = write_sdist(tmp_path)
    root = repository(tmp_path)

    first = sbom.build_sbom(sdist, _EPOCH, root)
    later = sbom.build_sbom(sdist, _EPOCH + 86_400, root)

    assert first["serialNumber"] == later["serialNumber"]
    assert first["metadata"]["timestamp"] != later["metadata"]["timestamp"]

    # the same archive rewritten: one byte of content, and the serial
    # number is another document
    with gzip.open(sdist, "ab") as appended:
        appended.write(b"\n")
    assert sbom.build_sbom(sdist, _EPOCH, root)["serialNumber"] != first["serialNumber"]


def test_a_dist_directory_holding_two_archives_is_refused(tmp_path: Path) -> None:
    """Which of them the document describes is not a question to guess at.

    Args:
        tmp_path: pytest's own.
    """
    write_sdist(tmp_path)
    write_sdist(tmp_path, name="btclib_secp256k1-0.8.0.8.tar.gz")

    with pytest.raises(SystemExit, match=r"expected one .*, found .*0\.8\.0\.7"):
        sbom.one_of(tmp_path, "*.tar.gz")


def test_a_dist_directory_holding_none_says_so(tmp_path: Path) -> None:
    """The message names the directory, an empty one being the likelier slip.

    Args:
        tmp_path: pytest's own.
    """
    with pytest.raises(SystemExit, match="found none"):
        sbom.one_of(tmp_path, "*.tar.gz")


def test_main_writes_the_document_named_after_the_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The success path: the caller needs to know neither name nor version.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture the environment and `git` are set
            through.
        capsys: the fixture the written path is read back from.
    """
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(_EPOCH))
    monkeypatch.setattr(sbom, "submodule_components", lambda _root: [])
    dist = tmp_path / "dist"
    dist.mkdir()
    write_sdist(dist)
    output = tmp_path / "sbom"

    assert sbom.main(["prog", str(dist), str(output)]) == 0

    written = output / "btclib_secp256k1-0.8.0.7.cdx.json"
    assert f"wrote {written}" in capsys.readouterr().out
    assert json.loads(written.read_text(encoding="utf-8"))["specVersion"] == "1.6"
    assert written.read_text(encoding="utf-8").endswith("}\n")


def test_main_says_how_to_be_called_when_it_is_not(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One directory, or three, is the usage rather than a crash.

    Args:
        capsys: the fixture the usage line is read back from.
    """
    assert sbom.main(["prog", "dist"]) == 2
    assert capsys.readouterr().err == (
        "usage: prog <dist directory> <output directory>\n"
    )


def test_main_refuses_to_default_source_date_epoch_to_now(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unset is a failure: a document differing from the released one.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture the environment is cleared through.
        capsys: the fixture the message is read back from.
    """
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)

    assert sbom.main(["prog", str(tmp_path), str(tmp_path)]) == 1
    assert "SOURCE_DATE_EPOCH is not set" in capsys.readouterr().err


def test_the_main_guard_runs_the_script_as___main__(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover `if __name__ == "__main__":` without a subprocess.

    This project collects no coverage from a child interpreter, so a real
    subprocess would leave the guard as uncovered as it is in
    `mutation_counts.py`. `runpy.run_path` executes the file fresh with
    `__name__` set to `"__main__"` in this one.

    Args:
        tmp_path: pytest's own.
        monkeypatch: the fixture `sys.argv` is set through.
    """
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    monkeypatch.setattr(sys, "argv", ["prog", str(tmp_path), str(tmp_path)])

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(
            str(Path(__file__).parents[1] / ".github" / "scripts" / "generate_sbom.py"),
            run_name="__main__",
        )

    assert excinfo.value.code == 1
