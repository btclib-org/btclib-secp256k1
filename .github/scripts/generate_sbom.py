# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Write the CycloneDX bill of materials of an sdist, or of a wheel.

A release says where its files came from: PEP 740 attestations on the
index, and a build provenance attestation over the sdist the GitHub
release attaches. What is *in* them is the other half, and this writes
it -- one CycloneDX 1.6 document naming the distribution, its licence,
the sdist and its digest, every dependency the metadata declares, and
every vendored submodule at the commit it is pinned to.

**The sdist beside it, and each wheel from inside.** The document `main()`
writes describes the file the `attest` job signs and `github-release`
attaches, which is the sdist alone: a wheel's only public copy is the one
PyPI already attests under PEP 740. Section 12 of the organization
standard puts the compiled wheels outside the property that a released
file rebuilds from its tag, and RELEASING.md's "Rebuild a release from
its tag" is where this repository states which of them a stranger can
rebuild at all -- so a document whose serial number derived from their
digests would be a document nobody could rebuild either, where the same
section asks that one can. That recipe rebuilds the sdist, and this
document with it.

A wheel carries its own document instead, at `.dist-info/sboms/` as PEP
770 places it, which `scripts/hatch_build.py` has `write_wheel_sbom`
below write while the wheel is built. It reads the core metadata and the
gitlinks as the sdist's does, narrowed to the wheel: the vendored
libraries this build compiled rather than every submodule the tree
holds, and how they are linked. It carries no digest, a document inside
an archive being unable to name the archive's own, and no
`vulnerabilities`: an entry of `.github/vex.toml` may name a library a
given wheel did not compile, which `vulnerabilities` refuses rather than
skips. Nothing in it comes from the clock or from the compiled files, so
two builds of one commit write it byte for byte alike, whatever
toolchain compiled the extension beside it.

**The archive's own metadata is the source, not pyproject.toml.** They
agree on a release and not in a rehearsal, where `version-check` computes
a `.dev<run*100+attempt>` suffix that `dev-version` writes into the tree
before the build: the document has to describe the file beside it, so it
reads the `PKG-INFO` of the archive it is given. Which also means the
only version it can report for a dependency is the one the metadata pins,
and that is deliberate -- what a user's installer resolves is not a fact
about this file, so a resolved version recorded here would be a claim the
sdist does not make. A requirement pinned with `==` gets a `version`;
anything else gets the specifier as a property and no version.

**It is reproducible, like the file it describes.** The timestamp is
`SOURCE_DATE_EPOCH`, which `build-sdist` exports from the commit date for
the sdist normalizer, and the serial number is a UUID5 over the purl and
the digest -- so a rebuild of a tag writes the same bytes here too, and
the attestation over the release assets covers this file as well. Nothing
is read from the clock, and nothing is random: `uuid4` would make a
rebuild differ in the one field nobody could check.

**`Requires-Dist` is not the only source.** It says what a distribution
*declares*, and this one declares `cffi` alone, where what the archive
carries is the vendored C libraries `.gitmodules` names -- trees git
records as a gitlink and the sdist builder copies in, named in no
metadata. `.gitmodules` and the gitlink `git ls-tree` reads off the tree
are what name them, so each submodule is reported as its own component:
a `library` with a `pkg:github/<owner>/<repo>@<sha>` purl, a `vcs`
externalReference naming the upstream repository, and `version` set to
that sha. A commit is a narrower pin than any `==` this script otherwise
grants a version to, so withholding one here would be the stricter rule
protecting the weaker case; the sha rather than an upstream tag name,
because the sha is what the gitlink actually stores and every commit has
one, where resolving a tag would be a network call this script otherwise
makes none of, for a result that may not exist
(issue btclib-org/btclib#1280).

**The tree's not-affected findings are a second input.** The script reads
`.github/vex.toml` from the tree the archive was built from and writes its
entries as the document's `vulnerabilities`; a tree with no such file gets no
such key, and a file it cannot read as section 12 states it stops the run.

Run it on a freshly built dist directory, after the sdist normalizer,
whose rewrite changes the digest this records:

    uv run --no-project --python 3.15 \
        .github/scripts/generate_sbom.py dist/ sbom/

The output is named `<distribution>-<version>.cdx.json` after the sdist,
so the workflow does not have to know the version -- which in a rehearsal
it does not. RELEASING.md has the command that regenerates it from a tag
and verifies it against the attestation.
"""

from __future__ import annotations

import configparser
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tomllib
from email import message_from_bytes, message_from_string
from email.message import Message
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

# PEP 508, cut down to the two forms a distribution's `Requires-Dist` takes
# here: a name with a version specifier, and a name with a direct
# reference. Anything else is refused rather than guessed at -- a
# requirement this cannot read is a dependency the document would omit in
# silence, which is the one failure a bill of materials must not have
REQUIREMENT = re.compile(
    r"""
    ^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)   # the name
    (?:\[(?P<extras>[^][]+)\])?                             # its extras
    (?:\s*@\s*(?P<url>[^\s;]+)                              # a direct reference
      |(?P<specifier>[^;]*))                                # or a specifier
    (?:\s*;\s*(?P<marker>.+))?$                             # its environment marker
    """,
    re.VERBOSE,
)

# one `==` and one version, which is the only specifier that names a
# version rather than a range of them
PINNED = re.compile(r"^==\s*(?P<version>[^,\s]+)$")

# how the labels of pyproject.toml's `[project.urls]` map onto the
# externalReference types CycloneDX defines. A label with no mapping is
# recorded as "other" rather than dropped: the document is a description,
# and losing a url because the vocabulary has no word for it is worse than
# saying "other"
REFERENCE_TYPES = {
    "changelog": "release-notes",
    "documentation": "documentation",
    "download": "distribution",
    "homepage": "website",
    "issues": "issue-tracker",
    "repository": "vcs",
}

# the two forms `git submodule add` writes into `.gitmodules` for a GitHub
# url, https and ssh, with or without the `.git` suffix -- anything else
# is refused, for the same reason an unreadable `Requires-Dist` line is:
# a submodule this cannot name is one the document would omit in silence
GITHUB_SUBMODULE_URL = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)"
    r"(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)

# a gitlink, which is what a submodule is recorded as in the tree that
# carries it, whether or not the submodule was ever checked out
GITLINK = re.compile(r"^160000 commit (?P<sha>[0-9a-f]{40})\t")

# where a tree records the findings it has judged not to affect its
# release, relative to the repository root. TOML because a finding is a
# judgement and the reason is what makes it one: a comment can carry the
# evidence beside the entry, which JSON has no place for
VEX = Path(".github") / "vex.toml"

# the keys of one `[[not_affected]]` table, all required: a finding
# without its justification or its detail is a claim nobody can check
VEX_KEYS = frozenset({"id", "source", "component", "justification", "detail"})

# CycloneDX 1.6's `impactAnalysisJustification`, the whole enumeration
JUSTIFICATIONS = frozenset({
    "code_not_present",
    "code_not_reachable",
    "requires_configuration",
    "requires_dependency",
    "requires_environment",
    "protected_by_compiler",
    "protected_at_runtime",
    "protected_at_perimeter",
    "protected_by_mitigating_control",
})

# resolved once: S607 is what a bare "git" in a subprocess list would be,
# a partial executable path relying on PATH's own search order rather
# than naming what actually runs
_GIT = shutil.which("git") or "git"


def canonical_name(name: str) -> str:
    """Return the PEP 503 normalized form of a distribution name.

    Args:
        name: the distribution name as the metadata spells it.

    Returns:
        The name lowercased, with each run of `-`, `_` and `.` collapsed
        to a single `-`.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def file_hash(path: Path) -> str:
    """Return the SHA-256 of a file, read a megabyte at a time.

    Args:
        path: the file to digest.

    Returns:
        The hex digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sdist_metadata(sdist: Path) -> Message:
    """Return the parsed PKG-INFO of a source distribution.

    The archive's own copy of the core metadata, which is what the wheels
    built from this tree carry too -- measured equal, field for field, on
    a build of this repository. Reading it here is what lets the document
    describe a rehearsal's `.dev` version rather than the one
    pyproject.toml declares.

    Args:
        sdist: the `.tar.gz` to read.

    Returns:
        The parsed `<distribution>-<version>/PKG-INFO` member.

    Raises:
        SystemExit: where the archive carries no such member, or more
            than one.
    """
    with tarfile.open(sdist) as archive:
        names = [
            name
            for name in archive.getnames()
            if name.count("/") == 1 and name.endswith("/PKG-INFO")
        ]
        if len(names) != 1:
            msg = f"{sdist.name} carries {len(names)} PKG-INFO members"
            raise SystemExit(msg)
        member = archive.extractfile(names[0])
        if member is None:
            msg = f"{sdist.name}: {names[0]} is not a regular file"
            raise SystemExit(msg)
        return message_from_bytes(member.read())


def purl(name: str, version: str | None, url: str | None) -> str:
    """Return the package url of a PyPI distribution, qualified by its vcs.

    Args:
        name: the distribution name.
        version: the version to pin the reference to, or None.
        url: the direct reference the requirement carries, or None.

    Returns:
        The package url.
    """
    reference = f"pkg:pypi/{canonical_name(name)}"
    if version is not None:
        reference += f"@{version}"
    if url is not None:
        # percent-encoded, the qualifier value being part of a url itself:
        # the `git+https://...@main` of a direct reference carries the two
        # characters that would otherwise end the qualifier
        reference += f"?vcs_url={quote(url, safe='')}"
    return reference


class Reading(NamedTuple):
    """What one `Requires-Dist` line says about the dependency it names."""

    name: str
    version: str | None
    url: str | None
    extras: str | None
    optional: bool
    line: str


def reading(requirement: str) -> Reading:
    """Return the reading of one `Requires-Dist` line.

    Args:
        requirement: the line as the metadata carries it.

    Returns:
        What the line says about the dependency it names.

    Raises:
        SystemExit: where the line is neither of the two PEP 508 forms
            `REQUIREMENT` reads.
    """
    match = REQUIREMENT.match(requirement.strip())
    if match is None:
        msg = f"cannot read the requirement {requirement!r}"
        raise SystemExit(msg)

    specifier = (match["specifier"] or "").strip()
    pinned = PINNED.match(specifier)
    marker = match["marker"]
    return Reading(
        name=canonical_name(match["name"]),
        version=pinned["version"] if pinned is not None else None,
        url=match["url"],
        extras=match["extras"],
        # an extra names a dependency the archive asks for only when the
        # extra is; nothing else in a marker makes a requirement optional
        # to a bill of materials, an interpreter version being a condition
        # on where it installs rather than on whether it is needed
        optional=marker is not None and "extra ==" in marker,
        line=requirement,
    )


def agreed(values: list[str | None]) -> str | None:
    """Return the value every line carries, or None where they differ.

    A field one line answers differently from the next is a fact about
    one installation environment and not about the distribution, so the
    document states none of it -- the lines are kept below as properties,
    where each answer is read beside the marker it holds under.

    Args:
        values: one line's answer each.

    Returns:
        The answer they all give, or None.
    """
    first = values[0]
    return first if all(value == first for value in values) else None


def component(readings: list[Reading]) -> dict[str, Any]:
    """Return the component the lines naming one dependency describe.

    One component per dependency and not per `Requires-Dist` line. A
    floor widened across interpreter versions is several lines differing
    only by marker -- which is what `cffi` is here -- and each reads as
    the same package url: a component per line would give the document
    several sharing one `bom-ref`, which CycloneDX 1.6 requires to be
    unique, and would leave `dependencies` standing one package in the
    graph as several nodes. Minting a unique reference per line instead
    -- a suffix, a qualifier -- satisfies the schema and keeps that
    graph, at the price of a `bom-ref` that is no longer the purl a
    consumer resolves the package by; the document is read to resolve a
    dependency graph, so the graph is what has to be right, and the lines
    survive as properties either way (issue btclib-org/btclib#1194).

    Args:
        readings: every line naming one dependency, in the order the
            metadata declares them.

    Returns:
        The CycloneDX component.
    """
    version = agreed([entry.version for entry in readings])
    url = agreed([entry.url for entry in readings])
    reference = purl(readings[0].name, version, url)

    properties: list[dict[str, str]] = []
    for entry in readings:
        # the line as the metadata carries it, which is the whole of what
        # this document knows about the dependency: the fields above are a
        # reading of it, and the reading is checkable against it
        properties.append({"name": "btclib:requires-dist", "value": entry.line})
        if entry.extras is not None:
            properties.append({"name": "btclib:extras", "value": entry.extras})

    # optional only where every line naming it is under an extra: one line
    # asking for it unconditionally is the distribution asking for it
    optional = all(entry.optional for entry in readings)
    result: dict[str, Any] = {
        "type": "library",
        "bom-ref": reference,
        "name": readings[0].name,
        "purl": reference,
        "scope": "optional" if optional else "required",
        "properties": properties,
    }
    if version is not None:
        result["version"] = version
    # deduplicated and in the order the metadata declares them, a
    # reference repeated once per line being noise rather than a second
    # place to look
    urls = dict.fromkeys(entry.url for entry in readings if entry.url is not None)
    if urls:
        result["externalReferences"] = [{"type": "vcs", "url": each} for each in urls]
    return result


def timestamp(epoch: int) -> str:
    """Return the epoch as the UTC ISO 8601 instant CycloneDX asks for.

    Args:
        epoch: `SOURCE_DATE_EPOCH`, as an integer.

    Returns:
        The instant, spelled with the `Z` the schema's own examples use.
    """
    # `isoformat` spells the zone "+00:00" and the schema's own examples
    # end in "Z"; both are valid ISO 8601 and one of them is what every
    # other tool writes
    when = datetime.datetime.fromtimestamp(epoch, datetime.UTC)
    return when.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def distribution_reference(path: Path) -> dict[str, Any]:
    """Return the externalReference for the distribution file.

    Args:
        path: the archive the document describes.

    Returns:
        A `distribution` reference carrying the file's name and digest.
    """
    return {
        "type": "distribution",
        # the name alone, and no url: the file is published to PyPI and
        # attached to a GitHub release, so a url here would name one of
        # the two copies and read as the authoritative one
        "url": path.name,
        "hashes": [{"alg": "SHA-256", "content": file_hash(path)}],
    }


def submodule_commit(repo_root: Path, path: str) -> str:
    """Return the commit a gitlink in the tree pins a submodule path to.

    Read with `git ls-tree` rather than from a checkout of the submodule,
    which need not exist: a gitlink is recorded in the parent repository's
    own tree regardless of whether `git submodule update` ever ran.

    Args:
        repo_root: the checked-out tree holding the gitlink.
        path: the submodule's path, as `.gitmodules` gives it.

    Returns:
        The 40-hex commit the gitlink pins.

    Raises:
        SystemExit: where the path is no gitlink in that tree.
    """
    result = subprocess.run(  # noqa: S603
        [_GIT, "ls-tree", "HEAD", "--", path],
        cwd=repo_root,
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    match = GITLINK.match(result.stdout)
    if match is None:
        msg = f"{path} is declared in .gitmodules but is not a pinned submodule"
        raise SystemExit(msg)
    return match["sha"]


def submodule_component(path: str, url: str, sha: str) -> dict[str, Any]:
    """Return the component a vendored, commit-pinned submodule describes.

    Args:
        path: the submodule's path in this repository.
        url: the upstream repository `.gitmodules` names.
        sha: the commit the gitlink pins it to.

    Returns:
        The CycloneDX component.

    Raises:
        SystemExit: where the url is neither GitHub form
            `GITHUB_SUBMODULE_URL` reads.
    """
    match = GITHUB_SUBMODULE_URL.match(url)
    if match is None:
        msg = f"cannot read the submodule url {url!r}"
        raise SystemExit(msg)
    reference = f"pkg:github/{match['owner']}/{match['repo']}@{sha}"
    return {
        "type": "library",
        "bom-ref": reference,
        "name": match["repo"],
        "purl": reference,
        # the sha, not an upstream tag name: see the module docstring for
        # why a network call to resolve one buys nothing a rebuild can
        # check, where the sha is what the gitlink already states
        "version": sha,
        "scope": "required",
        "externalReferences": [{"type": "vcs", "url": url}],
        "properties": [{"name": "btclib:submodule-path", "value": path}],
    }


def submodule_components(repo_root: Path) -> list[dict[str, Any]]:
    """Return one component per git submodule pinned to a commit.

    `.gitmodules` names the path and the upstream url of every submodule
    the repository declares; `submodule_commit` reads the commit each is
    pinned to straight from the tree. A repository with no `.gitmodules`
    makes this a no-op.

    Args:
        repo_root: the checked-out tree to read.

    Returns:
        One component per submodule, in the order `.gitmodules` declares
        them.
    """
    gitmodules = repo_root / ".gitmodules"
    if not gitmodules.is_file():
        return []

    config = configparser.ConfigParser()
    config.read(gitmodules, encoding="utf-8")
    return [
        submodule_component(
            config[section]["path"],
            config[section]["url"],
            submodule_commit(repo_root, config[section]["path"]),
        )
        for section in config.sections()
    ]


def vex_findings(repo_root: Path) -> list[dict[str, Any]]:
    """Return the entries of the tree's not-affected list, empty where none.

    A file it cannot read as section 12 states it stops the run with a
    message naming the file, and so does one with no entry: a tree with
    none has no file.

    Args:
        repo_root: the checked-out tree holding `.github/vex.toml`.

    Returns:
        The `[[not_affected]]` tables, or an empty list where the tree
        keeps no file.

    Raises:
        SystemExit: where the file does not parse, is not a list of
            tables, or holds none.
    """
    path = repo_root / VEX
    if not path.is_file():
        return []
    try:
        with path.open("rb") as stream:
            findings = tomllib.load(stream).get("not_affected", [])
    except tomllib.TOMLDecodeError as error:
        msg = f"{VEX}: does not parse: {error}"
        raise SystemExit(msg) from error
    if not isinstance(findings, list) or not all(
        isinstance(finding, dict) for finding in findings
    ):
        msg = f"{VEX}: `not_affected` must be a list of `[[not_affected]]` tables"
        raise SystemExit(msg)
    if not findings:
        msg = f"{VEX}: holds no `[[not_affected]]` entry; a tree with none has no file"
        raise SystemExit(msg)
    return findings


def vulnerabilities(
    repo_root: Path, components: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the tree's not-affected findings, as CycloneDX says them.

    Refused rather than skipped where an entry is not one this can state
    whole, or names a component the document does not carry: a finding
    about a package that is not in the files is either a typo, and so an
    answer that silently answers nothing, or a dependency that left, and
    the entry is then stale. A tree with no file states none, and the
    document has no `vulnerabilities` key at all: an empty array would say
    the tree looked and found nothing to report, which is a claim about the
    tree's process this script cannot check. A file with no entry is
    refused, section 12 giving a tree with none no file.

    Args:
        repo_root: the checked-out tree holding `.github/vex.toml`.
        components: every component the document carries, the
            distribution's own among them.

    Returns:
        One CycloneDX vulnerability per finding, sorted by id and
        component.

    Raises:
        SystemExit: where an entry is malformed or names a component the
            document does not carry.
    """
    findings = vex_findings(repo_root)

    references: dict[str, str] = {}
    for entry in components:
        # a submodule's name is its upstream repository's, so a dependency
        # and a submodule can spell one name: an entry naming it would be
        # ambiguous, and is refused below rather than resolved by order
        key = canonical_name(str(entry["name"]))
        if key in references:
            references[key] = ""
        else:
            references[key] = str(entry["bom-ref"])
    result = []
    for finding in findings:
        if set(finding) != VEX_KEYS or not all(
            isinstance(value, str) and value for value in finding.values()
        ):
            msg = f"{VEX}: an entry needs exactly {sorted(VEX_KEYS)}, got {finding!r}"
            raise SystemExit(msg)
        if finding["justification"] not in JUSTIFICATIONS:
            msg = (
                f"{VEX}: {finding['id']} has the justification "
                f"{finding['justification']!r}"
            )
            raise SystemExit(msg)
        name = canonical_name(finding["component"])
        if name not in references:
            msg = (
                f"{VEX}: {finding['id']} names {name}, "
                "which this document does not carry"
            )
            raise SystemExit(msg)
        if not references[name]:
            msg = (
                f"{VEX}: {finding['id']} names {name}, which the document carries twice"
            )
            raise SystemExit(msg)
        result.append({
            "id": finding["id"],
            "source": {"name": finding["source"]},
            "affects": [{"ref": references[name]}],
            "analysis": {
                "state": "not_affected",
                "justification": finding["justification"],
                "detail": finding["detail"],
            },
        })
    return sorted(result, key=lambda entry: (entry["id"], entry["affects"][0]["ref"]))


def distribution_component(
    metadata: Message, source: str, references: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return the component the core metadata describes, the document's subject.

    Args:
        metadata: the parsed core metadata.
        source: the file the metadata was read from, for the message.
        references: the externalReferences to put ahead of the project
            urls the metadata declares.

    Returns:
        The CycloneDX component.

    Raises:
        SystemExit: where the metadata declares no name or no version.
    """
    name = metadata["Name"]
    version = metadata["Version"]
    if name is None or version is None:
        msg = f"{source} declares no Name or no Version"
        raise SystemExit(msg)
    reference = purl(name, version, None)

    references = list(references)
    for entry in metadata.get_all("Project-URL", []):
        label, _, url = entry.partition(", ")
        references.append({
            "type": REFERENCE_TYPES.get(label, "other"),
            "url": url,
            "comment": label,
        })

    root: dict[str, Any] = {
        "type": "library",
        "bom-ref": reference,
        "name": canonical_name(name),
        "version": version,
        "purl": reference,
        # no component-level `hashes`: the digest belongs on the
        # reference above, where a verifier can check it against the file
        # it has
        "externalReferences": references,
    }
    summary = metadata["Summary"]
    if summary is not None:
        root["description"] = summary
    # PEP 639, which is what pyproject.toml's `license = "MIT"` writes:
    # a SPDX expression, and CycloneDX takes one as such rather than as a
    # licence name it would have to match against a list
    expression = metadata["License-Expression"]
    if expression is not None:
        root["licenses"] = [{"expression": expression}]
    requires_python = metadata["Requires-Python"]
    if requires_python is not None:
        root["properties"] = [
            {"name": "btclib:requires-python", "value": requires_python}
        ]
    return root


def dependency_components(metadata: Message) -> list[dict[str, Any]]:
    """Return one component per dependency the core metadata declares.

    Args:
        metadata: the parsed core metadata.

    Returns:
        The components, in the order the metadata first names each.
    """
    # grouped by the name the lines normalize to, which is what makes the
    # references distinct: the dict keeps each dependency's lines in the
    # order the metadata declares them
    by_name: dict[str, list[Reading]] = {}
    for requirement in metadata.get_all("Requires-Dist", []):
        declared = reading(requirement)
        by_name.setdefault(declared.name, []).append(declared)
    return [component(readings) for readings in by_name.values()]


def document(
    serial: str, root: dict[str, Any], components: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return the CycloneDX document around its subject and its components.

    Args:
        serial: what the serial number is derived from.
        root: the component the document describes.
        components: every other component, in the order to write them.

    Returns:
        The document, with no timestamp and no vulnerabilities.
    """
    reference = root["bom-ref"]
    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        # derived and not random, so that a rebuild writes this file byte
        # for byte as the first build did
        "serialNumber": f"urn:uuid:{uuid5(NAMESPACE_URL, serial)}",
        "version": 1,
        "metadata": {
            "tools": {
                "components": [
                    {"type": "application", "name": ".github/scripts/generate_sbom.py"}
                ]
            },
            "component": root,
        },
        "components": components,
        "dependencies": [
            {"ref": reference, "dependsOn": [entry["bom-ref"] for entry in components]},
            *({"ref": entry["bom-ref"], "dependsOn": []} for entry in components),
        ],
    }


def build_sbom(sdist: Path, epoch: int, repo_root: Path) -> dict[str, Any]:
    """Return the CycloneDX document describing one source distribution.

    Args:
        sdist: the archive to describe.
        epoch: `SOURCE_DATE_EPOCH`, the document's own timestamp.
        repo_root: the checked-out tree the archive was built from.

    Returns:
        The document, as the object `json.dumps` is given below.
    """
    metadata = sdist_metadata(sdist)
    root = distribution_component(metadata, sdist.name, [distribution_reference(sdist)])
    components = sorted(
        dependency_components(metadata) + submodule_components(repo_root),
        key=lambda dependency: str(dependency["bom-ref"]),
    )
    findings = vulnerabilities(repo_root, [root, *components])
    result = document(f"{root['bom-ref']}:{file_hash(sdist)}", root, components)
    result["metadata"]["timestamp"] = timestamp(epoch)
    if findings:
        result["vulnerabilities"] = findings
    return result


def build_wheel_sbom(
    metadata: Message, repo_root: Path, compiled: list[str], linkage: str
) -> dict[str, Any]:
    """Return the CycloneDX document a wheel carries about itself.

    The subject and its dependencies are read as `build_sbom` reads them,
    and of the submodules only those `compiled` names: a wheel carries
    what its build compiled, and a vendored library it did not compile is
    not in it. The serial number is derived from the document's own
    content, the archive holding the document having no digest yet, and
    there is no timestamp and no `vulnerabilities` key.

    Args:
        metadata: the core metadata the wheel carries.
        repo_root: the checked-out tree the wheel is built from.
        compiled: the path of each submodule the build compiled.
        linkage: how the build links them, `static` or `dynamic`.

    Returns:
        The document, as the object `json.dumps` is given below.

    Raises:
        SystemExit: where a compiled path is no submodule `.gitmodules`
            declares.
    """
    root = distribution_component(metadata, "the wheel's METADATA", [])
    root.setdefault("properties", []).append({
        "name": "btclib:linkage",
        "value": linkage,
    })
    vendored = {
        entry["properties"][0]["value"]: entry
        for entry in submodule_components(repo_root)
    }
    unknown = sorted(set(compiled) - set(vendored))
    if unknown:
        msg = f"{unknown} compiled, and not declared in .gitmodules"
        raise SystemExit(msg)
    components = sorted(
        dependency_components(metadata) + [vendored[path] for path in compiled],
        key=lambda dependency: str(dependency["bom-ref"]),
    )
    content = json.dumps([root, components], sort_keys=True)
    digest = hashlib.sha256(content.encode()).hexdigest()
    return document(f"{root['bom-ref']}:{digest}", root, components)


def write_document(sbom: dict[str, Any], output: Path) -> None:
    """Write a document as every one of them is written.

    Args:
        sbom: the document.
        output: the file to write, its directory created if missing.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(sbom, indent=2, sort_keys=True)
    output.write_text(f"{text}\n", encoding="utf-8")


def write_wheel_sbom(
    metadata: str, repo_root: Path, compiled: list[str], linkage: str, directory: Path
) -> Path:
    """Write the document a wheel carries, for the build hook to hand over.

    Named `<distribution>.cdx.json` after the wheel's own distribution
    field, which is what `.github/scripts/verify_wheel_contents.py` looks
    for under `sboms/`.

    Args:
        metadata: the text of the METADATA file the wheel carries.
        repo_root: the checked-out tree the wheel is built from.
        compiled: the path of each submodule the build compiled.
        linkage: how the build links them, `static` or `dynamic`.
        directory: where to write the file.

    Returns:
        The file written.
    """
    parsed = message_from_string(metadata)
    sbom = build_wheel_sbom(parsed, repo_root, compiled, linkage)
    # the wheel filename's escaping of the distribution name, PEP 427's
    distribution = canonical_name(sbom["metadata"]["component"]["name"])
    output = directory / f"{distribution.replace('-', '_')}.cdx.json"
    write_document(sbom, output)
    return output


def one_of(directory: Path, pattern: str) -> Path:
    """Return the single file in the directory matching the pattern.

    Args:
        directory: the dist directory to look in.
        pattern: the glob to match.

    Returns:
        The one file matching it.

    Raises:
        SystemExit: where the directory holds none, or several.
    """
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        found = ", ".join(match.name for match in matches) if matches else "none"
        msg = f"{directory}: expected one {pattern}, found {found}"
        raise SystemExit(msg)
    return matches[0]


# the script name plus the two positional arguments
_EXPECTED_ARGC = 3


def main(argv: list[str]) -> int:
    """Write the bill of materials of one dist directory into another.

    Args:
        argv: `sys.argv`, the dist directory and the output directory
            after the script's own name.

    Returns:
        0 where the document was written, 1 where `SOURCE_DATE_EPOCH` is
        unset, 2 where the arguments are not the two expected.
    """
    if len(argv) != _EXPECTED_ARGC:
        print(f"usage: {argv[0]} <dist directory> <output directory>", file=sys.stderr)
        return 2

    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is None:
        # not a default of "now", for normalize_sdist.py's reason: a
        # default makes the document differ from the released one, and
        # whoever finds that out is the one person who cannot fix it
        print("SOURCE_DATE_EPOCH is not set", file=sys.stderr)
        return 1

    sdist = one_of(Path(argv[1]), "*.tar.gz")
    # this file's own location within the checked-out tree, so the
    # submodule scan finds the repository root regardless of the caller's
    # working directory
    repo_root = Path(__file__).resolve().parents[2]
    sbom = build_sbom(sdist, int(epoch), repo_root)

    # named after the sdist's own two fields, {distribution} and
    # {version}, so the caller needs to know neither -- which in a
    # rehearsal, where the version carries a `.dev<run*100+attempt>` the
    # workflow patched in, it does not
    output = Path(argv[2]) / f"{sdist.name.removesuffix('.tar.gz')}.cdx.json"
    write_document(sbom, output)
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
