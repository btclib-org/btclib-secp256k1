# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the
documentation: https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

import posixpath
import re
import tomllib
from pathlib import Path

from docutils import nodes
from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.transforms.post_transforms import SphinxPostTransform

# the repository root, two levels up from this file, and the one place
# below that is allowed to name it
ROOT = Path(__file__).parents[2].resolve()
# read once and read twice from: the version below and the github url the
# transform at the bottom builds its links on
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "btclib_secp256k1"
# no __copyright__ in this package to read back: LICENSE is the only
# place the holder is declared, so this reads that file instead, minus
# the "Copyright (c) " sphinx prepends itself.
# What comes out carries no year, section 14 of the organization's
# standard having LICENSE name the holder and no range, so the footer
# dates nothing
project_copyright = re.search(
    r"^Copyright \(c\) (.+)$",
    (ROOT / "LICENSE").read_text(encoding="utf-8"),
    re.MULTILINE,
)[1]
author = "The btclib developers"
# read from pyproject.toml, the one place the version is declared, rather
# than from importlib.metadata, so the value does not depend on whether
# this package happens to be installed in the environment building the
# documentation (btclib-org/.github#1098)
release = PYPROJECT["project"]["version"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.intersphinx",
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.coverage",
    "sphinx.ext.githubpages",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

# no sphinx.ext.todo, for the reason a sibling repository's own conf.py
# gives: a ``.. todo::`` left at the default renders as nothing at all,
# and without the extension it is an unknown directive that -W turns
# into a failed build instead

source_suffix = [".rst", ".md"]

# -n on the build (CONTRIBUTING.md's documented command, and docs.yml)
# turns an unresolved cross-reference into a warning for -W to fail on.
# Without an inventory to resolve against, a name from outside this tree
# -- collections.abc.Sequence, collections.abc.Mapping, types.TracebackType,
# the stdlib names this package's own annotations reach -- reports as
# this tree's own broken link; sphinx's own domain answers for the
# builtins (int, bytes, str), so no mapping is needed for those. cffi's
# own ffi and lib are out of scope of intersphinx, cffi publishing no
# inventory to map them against, but neither draws a reference here:
# CData, the boundary's own name for cffi's cdata objects, is declared in
# this package (__init__.py) rather than imported from cffi
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", (None, "_inventories/python.inv")),
}
# `_inventories/python.inv` is a copy of Python 3.14's inventory and no
# cache: sphinx reads it only when `docs.python.org` fails, so a live site
# always wins. It is the Wayback Machine's capture of 2026-08-28,
# https://web.archive.org/web/20260828181213id_/https://docs.python.org/3/objects.inv
# To refresh it, run this from the repository root and rewrite the version
# and source above:
# curl -fsSL -o docs/source/_inventories/python.inv https://docs.python.org/3/objects.inv

# CONTRIBUTING.md links to "README.md#build", an anchor into a markdown
# heading rather than a whole file, and myst generates no heading ids at
# all unless told to. 6 is every level a markdown heading reaches, which
# section 2 of the organization's standard makes the value here: a depth
# read off the headings a root file links to is re-derived every time one
# of them moves, and part of what it would read belongs to no one tree --
# section 14 ports CONTRIBUTING.md's shared half into every repository,
# so a heading added there moves the number in each of them at once
myst_heading_anchors = 6

# no suppress_warnings, matching a sibling repository's own choice: the
# transform at the bottom resolves every link the included root files
# carry, so a myst target still missing is a link with nowhere to go
# and -W is what says so

exclude_patterns: list[str] = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"

# no html_static_path, matching a sibling repository's own conf.py and
# for the same reason: neither an overridden stylesheet nor a shipped
# image exists here, and sphinx warns about a declared "_static"
# directory that has never existed

# -- Links out of the included root markdown files ----------------------------

# Some of the toctree's pages are this repository's own root markdown,
# each pulled into a *_link.md shim by a myst {include}. Which ones is
# what the include fences of docs/source/*.md name, and INCLUDED below
# reads those same fences, so the set is derived in one place and this
# comment does not become a second copy of it the next time a shim is
# added or dropped. What is not shimmed is a root file no page renders,
# which is a fact about this repository rather than a rule. Those root
# files are written for the places that read them unrendered: the GitHub
# file view and, for README.md, the PyPI long description. So a root
# file links another as "./SECURITY.md", which myst cannot resolve once
# the file is lifted into this tree. README.md links it as BLOB plus its
# path, PyPI resolving no relative link against the tree (section 2 of
# the organization's standard, Root files), and myst renders that as a
# link to GitHub.
#
# What myst emits for a relative link is the reason this needs code
# rather than a warning filter, exactly as a sibling repository's own
# conf.py explains: a target myst cannot resolve becomes an anchor on the
# page it is already on, href="#SECURITY.md", an id nothing has. The
# transform below answers each link from the repository rather than from
# a table that would have to be kept in step with this directory: a path
# a page of docs/source includes, or a page of docs/source itself,
# becomes a reference to that page, whether written relative or as BLOB
# plus the path; any other relative path that exists in the tree becomes
# a link to the file on GitHub, and a relative path that exists nowhere
# is left to myst -- which reports it, and -W then fails.

# the branch, not a permalink pinned to a commit: these are navigation
# links to files that keep changing, and a reader following one wants the
# file as it stands
BLOB = f"{PYPROJECT['project']['urls']['repository']}/blob/main/"


# a line opening or closing a fence: the spaces before it, its marker, and
# the info string after it. Behind four spaces, a line at the top level of
# a page is no fence
FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})\s*(.*?)\s*$")

# the info string of an include fence; its argument runs to the end of the line
INCLUDE = re.compile(r"^\{include\}\s+(.+)$")

# the name of the directive an info string opens
DIRECTIVE = re.compile(r"^\{([^}]+)\}")

# the directives whose body this reads as markup, among them the
# admonitions, containers and version notes of docutils and sphinx. Every
# directive not named here is read as code, so an include inside it is
# not read: {code-block}, {eval-rst} and {toctree}, and also some that
# do parse their body, as {figure}, {list-table} and {glossary}. The list
# names only directives MyST renders by parsing their body, and grows
# when a page needs an include inside another one
PARSED = (
    "admonition",
    "attention",
    "caution",
    "danger",
    "error",
    "hint",
    "important",
    "note",
    "tip",
    "warning",
    "seealso",
    "topic",
    "sidebar",
    "epigraph",
    "highlights",
    "pull-quote",
    "compound",
    "container",
    "only",
    "hlist",
    "acks",
    "deprecated",
    "versionadded",
    "versionchanged",
    "versionremoved",
    "version-deprecated",
    "version-added",
    "version-changed",
    "version-removed",
)


def includes(text: str) -> list[str]:
    """Return the paths of the include fences of a page, in page order.

    A fence opening a directive of `PARSED` holds markdown, which myst
    parses, so a fence inside it is read. Any other fence is code, and
    what it holds is shown, not parsed. A fence closes at a bare marker
    of its own character, at least as long as the one that opened it.
    A marker behind spaces may close a fence but opens none: it may sit
    in a list item, which this does not read.

    :param text: the page.
    :returns: the paths, as the fences write them.
    """
    paths: list[str] = []
    # the open fences, innermost last: marker, and whether it is code
    open_fences: list[tuple[str, bool]] = []
    for line in text.splitlines():
        fence = FENCE.match(line)
        if fence is None:
            continue
        indent, marker, info = fence.groups()
        if open_fences:
            top, _ = open_fences[-1]
            if not info and marker[0] == top[0] and len(marker) >= len(top):
                open_fences.pop()
                continue
            if open_fences[-1][1]:
                continue
        if indent:
            continue
        if include := INCLUDE.match(info):
            paths.append(include[1])
        directive = DIRECTIVE.match(info)
        open_fences.append((marker, directive is None or directive[1] not in PARSED))
    return paths


def included(page: Path) -> tuple[str, str] | None:
    """Map the file a page of docs/source includes to the page's docname.

    A page with no include fence renders no file, and maps nothing. One
    with more than one stops the build: a relative link on it would have
    two files to start from, and which one is not a question this can
    answer.
    """
    paths = includes(page.read_text(encoding="utf-8"))
    if len(paths) > 1:
        err_msg = f"{page.name}: {len(paths)} include fences, expected at most one"
        raise ValueError(err_msg)
    if not paths:
        return None
    return str((page.parent / paths[0]).resolve().relative_to(ROOT)), page.stem


# repository-relative path -> the docname whose page renders it
INCLUDED = dict(
    entry
    for entry in map(included, sorted(Path(__file__).parent.glob("*.md")))
    if entry is not None
)


class RootFileLinks(SphinxPostTransform):
    """Resolve the links naming a file of this tree."""

    # ahead of myst's own resolver, which runs at 9 and is what turns an
    # unresolved target into that anchor
    default_priority = 5

    @staticmethod
    def _to_page(node: pending_xref, page: str, anchor: str | None) -> None:
        """Point a myst xref at `page`, a docname."""
        node["refdomain"] = "doc"
        node["reftarget"] = page
        node["reftargetid"] = anchor or None

    def _broken_doc_target(self, node: pending_xref) -> tuple[Path, str | None] | None:
        """Recover the file behind a "doc" xref `path2doc` resolved wrong.

        myst already thinks this resolves; a real docname is a working
        cross-reference and none of this file's business. Anything else is
        `Project.path2doc` stripping a matching suffix off *any* file that
        exists on disk, docs or not (sphinx/project.py), so a link climbing
        out of srcdir into a real file -- a page under docs/source
        linking into README.md -- reads as resolved when it is not.
        Recover the file it actually named: reftarget is that path with
        its suffix gone, and only one of the two the tree parses still
        fits.
        """
        if node["reftarget"] in self.env.all_docs:
            return None
        candidates = (Path(f"{node['reftarget']}{suffix}") for suffix in source_suffix)
        found = next((c for c in candidates if c.is_file()), None)
        return None if found is None else (found, node.get("reftargetid"))

    def _unbound_target(
        self, node: pending_xref, refdoc: str
    ) -> tuple[Path, str | None]:
        """Resolve a link myst left with no domain at all.

        A page that includes a file holds links written relative to that
        file; any other page's links are written relative to wherever the
        page sits in the source tree -- doc2path is what answers that
        without assuming every docname sits flat under docs/source.
        """
        raw, _, anchor = node["reftarget"].partition("#")
        rendered = [path for path, page in INCLUDED.items() if page == refdoc]
        origin = (
            (ROOT / rendered[0]).parent
            if rendered
            else Path(self.env.doc2path(refdoc)).parent
        )
        return origin / raw, anchor or None

    def _source_page(self, target: str) -> str | None:
        """Return the docname of `target` where it is a page of docs/source."""
        stem, suffix = posixpath.splitext(target)
        docname = stem.removeprefix("docs/source/")
        if docname == stem or suffix not in source_suffix:
            return None
        # the file itself, and not only its docname: a missing page.rst
        # would otherwise read as page.md
        if not (ROOT / target).is_file():
            return None
        return docname if docname in self.env.found_docs else None

    def run(self, **_kwargs: object) -> None:
        """Rewrite every link naming a file of this repository."""
        # the list is taken before the tree is edited: replace_self on a
        # node the generator is standing on reparents its children under it
        for node in list(self.document.findall(pending_xref)):
            if node.get("reftype") != "myst":
                continue
            refdomain = node.get("refdomain")
            if refdomain == "doc":
                resolved = self._broken_doc_target(node)
            elif refdomain is None:
                refdoc = node.get("refdoc", self.env.docname)
                resolved = self._unbound_target(node, refdoc)
            else:
                resolved = None
            if resolved is None:
                continue
            found, anchor = resolved
            try:
                # "./tests/README.md" from a shim resolves to
                # "tests/README.md"; a page's own "../../README.md"
                # resolves to "README.md" the same way, against the real
                # filesystem, so a path climbing above ROOT raises rather
                # than reading as one of its own
                target = str(found.resolve().relative_to(ROOT))
            except ValueError:
                # outside the repository: nothing this can answer
                continue
            if target in INCLUDED:
                # handed back to myst as the link it would have been
                # written as, so the page title and the caption are its
                # business and not this file's
                self._to_page(node, INCLUDED[target], anchor)
            elif (ROOT / target).is_file():
                fragment = f"#{anchor}" if anchor else ""
                reference = nodes.reference(
                    "", "", refuri=f"{BLOB}{target}{fragment}", internal=False
                )
                reference.extend(node.children)
                node.replace_self(reference)
        self._blob_links()

    def _blob_links(self) -> None:
        """Turn a BLOB link to a file the docs render into a link to its page.

        myst made each BLOB link an external reference: one naming an
        included file or a page of docs/source becomes the xref myst makes
        from a relative link, which myst's resolver then renders alike.
        """
        for node in list(self.document.findall(nodes.reference)):
            url, _, anchor = node.get("refuri", "").partition("#")
            # the path ends at a query, as `?plain=1`, which the page drops
            url = url.partition("?")[0]
            target = url.removeprefix(BLOB)
            if target == url:
                continue
            page = INCLUDED.get(target) or self._source_page(target)
            if page is None:
                continue
            xref = pending_xref(
                "",
                nodes.inline("", "", *node.children, classes=["xref", "myst"]),
                reftype="myst",
                refexplicit=True,
                refdoc=self.env.docname,
            )
            xref.source, xref.line = node.source, node.line
            self._to_page(xref, page, anchor)
            node.replace_self(xref)


def setup(app: Sphinx) -> None:
    """Register the transform above; sphinx calls this."""
    app.add_post_transform(RootFileLinks)
