"""figly FILE.root                         plot every object in the file
figly FILE.root:NAME [FILE.root:NAME2]   one plot (several objects are overlaid)
figly ls FILE.root                       list the objects
figly inspect FILE.root:NAME             show the components and a call to copy and edit
figly init FILE.root:NAME [-o FILE.toml] write a figuratively.toml with the detected names
figly check FILE.root:NAME [-s nparams=10]   sanity numbers: data vs curve, chi2, empty bins, large pulls
figly summary FILE.root ... [-s fmt=csv]     one row per panel (entries, chi2, component yields)
figly options                            list every option
figly header [figuratively.h]            the C++ header for ROOT macros (Figuratively::Plot(canvas))
Extras: -s key=value (any fg.plot keyword), e.g. -s logy=True -s "xlim=(1800,1900)"."""
from __future__ import annotations

import argparse
import ast
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


if __name__ == "__main__":
    main()
