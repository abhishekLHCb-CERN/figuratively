"""figly FILE.root                         plot every object in the file
figly FILE.root:NAME [FILE.root:NAME2]   one plot (several objects are overlaid)
figly ls FILE.root                       list the objects
figly inspect FILE.root:NAME             show the components and a call to copy and edit
figly init FILE.root:NAME [-o FILE.toml] write a figuratively.toml with the detected names
figly check FILE.root:NAME [-s nparams=10]   sanity numbers: data vs curve, chi2, empty bins, large pulls
figly summary FILE.root ... [-s fmt=csv]     one row per panel (entries, chi2, component yields)
figly tree FILE.root:TREE BRANCH [-s bins=60 -s cut='pt > 2']   histogram a TTree branch and plot it
figly options                            list every option
figly header [figuratively.h]            the C++ header for ROOT macros (Figuratively::Plot(canvas))
Extras: -s key=value (any fg.plot keyword), e.g. -s logy=True -s "xlim=(1800,1900)"."""
from __future__ import annotations

import argparse
import ast
import sys
import warnings
from pathlib import Path

from . import data as D
from .auto import load_config, plot
from .explore import init, inspect
from .options import options

_TEXT_OPTIONS = {"label", "info", "title", "unit", "exp", "com", "lumi", "outdir", "style", "data_label",
                 "total_label", "ylabel", "data_pattern", "palette", "kind", "formats_text"}


def _value(key: str, v: str):
    """-s values are Python literals (True, 3, (1, 2)), except for options that hold text."""
    if key in _TEXT_OPTIONS and not v.strip().startswith(("[", "(", "{")):
        return v
    try:
        return ast.literal_eval(v)
    except (ValueError, SyntaxError):
        return v


def header_text() -> str:
    """The C++ header (figuratively.h) shipped with the package."""
    return (Path(__file__).parent / "figuratively.h").read_text()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="figuratively", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    from . import __author__, __version__

    ap.add_argument("--version", action="version", version=f"figuratively {__version__} (c) 2026 {__author__}, MIT licence")
    ap.add_argument("targets", nargs="+")
    ap.add_argument("-o", "--out", help="output file or stem (default: plots/ next to the ROOT file)")
    ap.add_argument("-c", "--config", help="figuratively.toml to use")
    ap.add_argument("-s", "--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--force", action="store_true", help="overwrite in `init`")
    ap.add_argument("--strict", action="store_true", help="turn warnings about unmatched names into errors")
    ap.add_argument("--debug", action="store_true", help="show the full traceback on errors")
    a = ap.parse_args(argv)
    cmd = a.targets[0]
    if cmd == "ls":
        for f in a.targets[1:]:
            for k, v in D.list_objects(f).items():
                print(f"{v:14s} {f}:{k}")
        return
    if cmd == "header":  # the C++ header for ROOT macros
        text = header_text()
        if len(a.targets) > 1:
            Path(a.targets[1]).write_text(text)
            print("wrote", a.targets[1])
        else:
            print(text, end="")
        return
    if cmd in ("check", "summary"):
        from .checks import check, summary

        nparams = next((int(kv.split("=")[1]) for kv in a.set if kv.startswith("nparams=")), None)
        targets = a.targets[1:]
        if cmd == "check":
            for t in targets:
                check(t, nparams=nparams)
        else:
            fmt = next((kv.split("=")[1] for kv in a.set if kv.startswith("fmt=")), "text")
            summary(targets, nparams=nparams, fmt=fmt)
        return
    if cmd == "tree":
        from .extras import tree as _tree

        if len(a.targets) != 3:
            ap.error("tree expects FILE.root:TREE and a branch or expression: figly tree f.root:T D0_M -s bins=60")
        tk = {}
        rest = []
        for kv in a.set:
            k, sep, v = kv.partition("=")
            if not sep or not k:
                ap.error(f"-s expects KEY=VALUE, got '{kv}'")
            if k in ("bins", "range", "cut", "weight", "name", "xtitle", "entry_stop"):
                tk[k] = v if k in ("cut", "weight", "name", "xtitle") else _value(k, v)
            else:
                rest.append(kv)
        h = _tree(a.targets[1], a.targets[2], **tk)
        opts = {"strict": True} if a.strict else {}
        for kv in rest:
            k, _, v = kv.partition("=")
            opts[k] = _value(k, v)
        plot(h, out=a.out or f"plots/{h.name}_{a.targets[2]}", **opts)
        return
    if cmd == "options":
        options()
        return
    if cmd == "inspect":
        for t in a.targets[1:]:
            inspect(t)
        return
    if cmd == "init":
        print("wrote", init(a.targets[1], a.out or "figuratively.toml", force=a.force))
        return
    if a.config:
        load_config(a.config)
    opts = {"strict": True} if a.strict else {}
    for kv in a.set:
        k, sep, v = kv.partition("=")
        if not sep or not k:
            ap.error(f"-s expects KEY=VALUE, got '{kv}'")
        opts[k] = _value(k, v)
    if all(":" in t for t in a.targets):
        plot(*a.targets, out=a.out, **opts)
    else:
        for t in a.targets:
            plot(t, **opts)


def _one_line_warning(message, category, filename, lineno, file=None, line=None):
    print(f"figuratively: warning: {message}", file=file or sys.stderr)


def console(argv=None):
    """Entry point of the `figuratively` and `figly` commands: one clean line for expected errors, exit code 1.

    `--debug` (or FIGURATIVELY_DEBUG=1) restores the full traceback. `main` itself still raises, for use from Python.
    """
    import os

    args = sys.argv[1:] if argv is None else list(argv)
    debug = "--debug" in args or bool(os.environ.get("FIGURATIVELY_DEBUG"))
    if not debug:
        warnings.showwarning = _one_line_warning
    try:
        main(argv)
    except (KeyError, ValueError, OSError) as e:
        if debug:
            raise
        msg = e.args[0] if isinstance(e, KeyError) and e.args else str(e)
        print(f"figuratively: error: {msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    console()
