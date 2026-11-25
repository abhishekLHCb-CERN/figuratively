"""Using Figuratively from ROOT. PyROOT is not installed in CI, so a stand-in `ROOT` module mimics the
tiny part of its API that is used: TFile(path, mode), obj.Write(name), obj.ClassName(), obj.GetName()."""
import subprocess
import sys
import types

import numpy as np
import pytest
import uproot

import figuratively as fg
from figuratively.cli import header_text, main


class FakeFile:
    current = None

    def __init__(self, path, mode="RECREATE"):
        self.path, self.store = path, {}
        FakeFile.current = self

    def Close(self):
        with uproot.recreate(self.path) as f:
            for name, (counts, edges) in self.store.items():
                f[name] = (counts, edges)


class FakeHist:
    def __init__(self, name, seed):
        counts, edges = np.histogram(np.random.default_rng(seed).normal(0, 1, 4000), bins=25, range=(-4, 4))
        self.name, self.data = name, (counts, edges)

    def ClassName(self):
        return "TH1D"

    def GetName(self):
        return self.name

    def Write(self, name=None):
        FakeFile.current.store[name or self.name] = self.data


class FakeOpenFile:
    def __init__(self, path):
        self.path = path

    def ClassName(self):
        return "TFile"

    def GetName(self):
        return self.path

    def Write(self, name=None):  # never called for a TFile
        raise AssertionError


@pytest.fixture
def fake_root(monkeypatch):
    monkeypatch.setitem(sys.modules, "ROOT", types.SimpleNamespace(TFile=FakeFile))


def test_a_live_root_histogram_is_plotted(fake_root, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = fg.plot(FakeHist("h_mass", 1))
    assert (tmp_path / "plots" / "h_mass.pdf").exists() and (tmp_path / "plots" / "h_mass.png").exists()
    p.draw()  # the Plot outlives the temporary file


def test_two_live_objects_are_overlaid(fake_root, tmp_path):
    p = fg.plot(FakeHist("h_data", 1), FakeHist("h_mc", 2), outdir=str(tmp_path), formats=("png",))
    assert (tmp_path / "h_data+h_mc.png").exists()
    assert {s.label for s in p.series} == {"h_data", "h_mc"}


def test_output_folder_and_options_pass_through(fake_root, tmp_path):
    fg.plot(FakeHist("h", 3), outdir=str(tmp_path / "figs"), formats=("png",), logy=True, label="Draft")
    assert (tmp_path / "figs" / "h.png").exists()


def test_a_root_file_handle_is_plotted_by_name(fake_root, tmp_path):
    path = tmp_path / "x.root"
    with uproot.recreate(path) as f:
        f["a"] = np.histogram(np.arange(100.0), bins=10)
    out = fg.plot(FakeOpenFile(str(path)), outdir=str(tmp_path / "o"), formats=("png",))
    assert len(out) == 1 and (tmp_path / "o" / "x_a.png").exists()


def test_helpful_error_without_pyroot(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "ROOT", None)  # makes `import ROOT` fail
    with pytest.raises(ImportError, match="needs PyROOT"):
        fg.plot(FakeHist("h", 1), outdir=str(tmp_path))


# ------------------------------------------------------------------ C++
def test_cpp_header_ships_and_has_the_documented_api(tmp_path, capsys):
    text = header_text()
    for needle in ("Figuratively::Plot", "namespace Figuratively", "figly", "pip install figuratively", "#pragma once"):
        assert needle in text or needle.replace("Figuratively::", "") in text
    assert "inline int Plot(TObject *obj" in text and "inline int Plot(const std::string &rootFile" in text
    main(["header", str(tmp_path / "figuratively.h")])
    assert (tmp_path / "figuratively.h").read_text() == text
    capsys.readouterr()  # discard the "wrote ..." message of the call above
    main(["header"])
    assert capsys.readouterr().out.startswith("// figuratively.h")


def _stand_in_root_headers(stub, exec_runs_shell=False):
    """Tiny headers with just the ROOT API the figuratively.h header uses."""
    stub.mkdir(exist_ok=True)
    (stub / "TObject.h").write_text('#pragma once\n#include <cstdlib>\nclass TObject { public: virtual ~TObject() {} '
                                    'const char *name = "c"; virtual const char *GetName() const { return name; } '
                                    'virtual int Write(const char * = 0, int = 0, int = 0) { return 1; } };\n')
    (stub / "TDirectory.h").write_text("#pragma once\nclass TDirectory { public: void cd() {} };\n"
                                       "inline TDirectory *gDirectory = nullptr;\n")
    (stub / "TFile.h").write_text('#pragma once\n#include "TDirectory.h"\nclass TFile : public TDirectory '
                                  "{ public: TFile(const char *, const char *) {} void Close() {} };\n")
    (stub / "TString.h").write_text('#pragma once\n#include <string>\nclass TString { public: std::string s; '
                                    "const char *Data() const { return s.c_str(); } };\n")
    run = "std::system(c)" if exec_runs_shell else "0"
    (stub / "TSystem.h").write_text(
        '#pragma once\n#include <cstdio>\n#include <cstdlib>\n#include <unistd.h>\n#include "TString.h"\n'
        "class TSystem { public: const char *TempDirectory() { return \"/tmp\"; } int GetPid() { return 1; } "
        f"int Exec(const char *c) {{ return {run}; }} int Unlink(const char *p) {{ return ::unlink(p); }} "
        "FILE *TempFileName(TString &base, const char * = nullptr, const char *suffix = nullptr) "
        '{ std::string t = std::string("/tmp/figtestXXXXXX") + (suffix ? suffix : ""); '
        "int fd = mkstemps(&t[0], suffix ? (int)std::string(suffix).size() : 0); if (fd < 0) return nullptr; "
        "base.s = t; return fdopen(fd, \"w\"); } };\ninline TSystem *gSystem = new TSystem();\n")


def _compiler():
    for c in ("clang++", "g++"):
        if subprocess.run(["which", c], capture_output=True).returncode == 0:
            return c
    return None


@pytest.mark.skipif(_compiler() is None, reason="no C++ compiler")
def test_cpp_header_compiles_against_stand_in_root_headers(tmp_path):
    _stand_in_root_headers(tmp_path / "stub")
    (tmp_path / "figuratively.h").write_text(header_text())
    (tmp_path / "main.cpp").write_text('#include "figuratively.h"\nint main() { TObject o; '
                                       'return Figuratively::Plot(&o, {"logy=True", "label=Work in progress"}, "out") '
                                       '+ Figuratively::Plot(std::string("f.root")); }\n')
    r = subprocess.run([_compiler(), "-std=c++17", "-Wall", "-Wextra", f"-I{tmp_path / 'stub'}", f"-I{tmp_path}",
                        str(tmp_path / "main.cpp"), "-o", str(tmp_path / "t")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert subprocess.run([str(tmp_path / "t")]).returncode == 0


@pytest.mark.skipif(_compiler() is None, reason="no C++ compiler")
def test_hostile_names_cannot_inject_shell_commands(tmp_path):
    """An object name, folder or keyword with quotes and shell syntax must reach figly as plain text."""
    _stand_in_root_headers(tmp_path / "stub", exec_runs_shell=True)
    (tmp_path / "figuratively.h").write_text(header_text())
    log = tmp_path / "args.log"
    fake = tmp_path / "bin" / "figly"
    fake.parent.mkdir()
    fake.write_text(f'#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a" >> "{log}"; done\n')
    fake.chmod(0o755)
    evil = "x'; touch " + str(tmp_path / "INJECTED") + "; echo '"
    (tmp_path / "main.cpp").write_text('#include "figuratively.h"\n#include <string>\nint main(int, char **argv) { TObject o; '
                                       "o.name = argv[1]; return Figuratively::Plot(&o, {argv[2]}, argv[3]); }\n")
    r = subprocess.run([_compiler(), "-std=c++17", f"-I{tmp_path / 'stub'}", f"-I{tmp_path}",
                        str(tmp_path / "main.cpp"), "-o", str(tmp_path / "t")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    env = {"PATH": f"{fake.parent}:/usr/bin:/bin"}
    subprocess.run([str(tmp_path / "t"), evil, "label=" + evil, "dir " + evil], env=env, check=True)
    assert not (tmp_path / "INJECTED").exists()                    # nothing was executed
    received = log.read_text().splitlines()
    assert any(evil in line for line in received) and any(line == "label=" + evil for line in received)
    assert not [p for p in __import__("pathlib").Path("/tmp").glob("figtest*.root")]   # the temporary file is removed
