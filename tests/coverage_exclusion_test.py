# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.

"""No raise `exclude_also` excludes sits behind an object the caller holds.

`[tool.coverage.report]`'s RuntimeError pattern excludes a raise by its
text, and the text cannot say whether an input reaches it. A wrapper
taking a libsecp256k1 object the caller holds is the shape that decides
it: a NULL pointer, or an object nothing has written to, is one
libsecp256k1 refuses, and the wrapper then raises
(btclib-org/btclib-secp256k1#1030). So a raise the pattern matches,
inside a function with a `CData` argument, fails here. Such a raise binds
its message to `msg` first, which the pattern does not match, and a test
drives it.

What this does not reach is a function taking octets whose libsecp256k1
call a chosen input still makes fail, as `zkp.generator.pedersen_blind_sum`
does for a blinding factor not below the order: that the raise of such a
function is unreachable is its docstring's claim, which nothing here
checks.
"""

import ast
import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_EXCLUDED = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
    "tool"
]["coverage"]["report"]["exclude_also"]
_PATTERNS = tuple(re.compile(p) for p in _EXCLUDED if "RuntimeError" in p)


def _takes_cdata(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return whether `function` has an argument annotated with `CData`.

    Args:
        function: the function's node.

    Returns:
        True where any of its arguments' annotations names `CData`.
    """
    arguments = (
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    )
    return any(
        argument.annotation is not None and "CData" in ast.unparse(argument.annotation)
        for argument in arguments
    )


def _excluded_raises() -> list[tuple[str, bool]]:
    """Return every raise the pattern excludes, and whether it takes CData.

    Returns:
        One `path:line` per raise, beside whether a function enclosing it
        takes a `CData` argument.
    """
    found: list[tuple[str, bool]] = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for function in ast.walk(ast.parse(source)):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            takes_cdata = _takes_cdata(function)
            found.extend(
                (f"{path.relative_to(_ROOT)}:{node.lineno}", takes_cdata)
                for node in ast.walk(function)
                if isinstance(node, ast.Raise)
                and any(pattern.search(lines[node.lineno - 1]) for pattern in _PATTERNS)
            )
    return found


_FOUND = _excluded_raises()


def test_the_pattern_excludes_some_raise() -> None:
    """A pattern not read, or matching nothing, passes the test below."""
    assert _PATTERNS, "no RuntimeError pattern in [tool.coverage.report]'s exclude_also"
    assert _FOUND, "the RuntimeError pattern excludes no raise under src"


def test_no_excluded_raise_takes_an_object_the_caller_holds() -> None:
    """A raise behind a caller-held object is reachable, so it is counted."""
    reachable = [site for site, takes_cdata in _FOUND if takes_cdata]
    assert not reachable, (
        f"excluded from coverage, and a caller-held object reaches them: {reachable}"
    )
