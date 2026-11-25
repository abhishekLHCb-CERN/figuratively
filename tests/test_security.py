"""Safety tests: untrusted configuration, untrusted ROOT files, no shell, no network."""
import os
import signal
import subprocess
from pathlib import Path

import numpy as np
import pytest
import uproot

import figuratively as fg
from figuratively import auto
from figuratively.style import use_style


@pytest.fixture
def clean_config():
    saved, loaded, path = dict(auto.CONFIG), auto._state["loaded"], auto._state["path"]
    yield
    auto.CONFIG.clear()
    auto.CONFIG.update(saved)
    auto._state.update(loaded=loaded, path=path)


def write(path: Path, text: str, mode=0o644):
    path.write_text(text)
    path.chmod(mode)
    return path


# ------------------------------------------------------------------ a configuration file cannot run anything
def test_a_preset_cannot_call_arbitrary_methods(tmp_path, clean_config):
    f = write(tmp_path / "figuratively.toml", '[presets.evil]\nsave = "/tmp/overwritten.pdf"\n')
    with pytest.raises(ValueError, match="not a documented option"):
        auto.load_config(f)
    for bad in ("rc", "annotate", "show", "_where", "close"):
        with pytest.raises(ValueError, match="not a documented option"):
            auto._check_preset("x", {bad: 1}, "test")


def test_a_preset_set_in_code_is_checked_too(clean_config):
    fg.configure(presets={"bad": {"save": "/tmp/x.pdf"}})
    with pytest.raises(ValueError, match="not a documented option"):
        auto._preset_options("bad", auto.CONFIG["presets"])


def test_documented_presets_still_work(clean_config):
    fg.configure(presets={"ok": {"size": "column", "palette": "r4", "formats": ("pdf",)}})
    assert auto._preset_options("ok", auto.CONFIG["presets"])["palette"] == "r4"


def test_a_config_cannot_write_outside_the_project(tmp_path):
    for bad in ('outdir = "/etc"', 'outdir = "../../elsewhere"'):
        f = write(tmp_path / "figuratively.toml", bad + "\n")
        with pytest.raises(ValueError, match="relative folder inside the project"):
            auto.load_config(f)
    f = write(tmp_path / "figuratively.toml", '[presets.p]\noutdir = "/tmp"\n')
    with pytest.raises(ValueError, match="relative folder"):
        auto.load_config(f)


def test_a_style_can_never_be_a_url(tmp_path):
    with pytest.raises(ValueError, match="URLs are not accepted"):
        use_style("https://example.com/evil.mplstyle")
    f = write(tmp_path / "figuratively.toml", 'style = "http://example.com/x.mplstyle"\n')
    with pytest.raises(ValueError, match="must not be a URL"):
        auto.load_config(f)


# ------------------------------------------------------------------ which configuration files are trusted
@pytest.mark.skipif(not hasattr(os, "getuid"), reason="needs POSIX permissions")
def test_a_config_others_can_write_is_ignored(tmp_path, monkeypatch, clean_config):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "figuratively.toml", 'label = "Planted"\n', mode=0o666)
    auto.CONFIG["label"] = None
    with pytest.warns(UserWarning, match="was ignored"):
        assert auto.load_config() is None
    assert auto.CONFIG["label"] is None
    (tmp_path / "figuratively.toml").chmod(0o644)
    assert auto.load_config() == tmp_path / "figuratively.toml" and auto.CONFIG["label"] == "Planted"


def test_configuration_is_never_searched_above_the_home_folder(tmp_path, monkeypatch, clean_config):
    home = tmp_path / "home"
    project = home / "proj" / "sub"
    project.mkdir(parents=True)
    write(tmp_path / "figuratively.toml", 'label = "Above home"\n')       # outside home: must be invisible
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(project)
    auto.CONFIG["label"] = None
    assert auto.load_config() is None
    write(home / "proj" / "figuratively.toml", 'label = "Project"\n')      # inside home: found
    assert auto.load_config() == home.resolve() / "proj" / "figuratively.toml"


# ------------------------------------------------------------------ no shell, no network
def test_viewing_a_file_never_goes_through_a_shell(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: calls.append((args, kw)))
    nasty = tmp_path / "a; touch INJECTED && echo $(id).png"
    auto._view(nasty)
    (args, kw), = calls
    assert isinstance(args, list) and args[-1] == str(nasty) and not kw.get("shell")
    assert not (tmp_path / "INJECTED").exists()


def test_the_package_makes_no_network_calls():
    import re

    src = "\n".join(p.read_text() for p in Path(auto.__file__).parent.glob("*.py"))
    for forbidden in ("import socket", "import requests", "urllib.request", "http.client", "os.system(", "shell=True",
                      "pickle"):
        assert forbidden not in src, forbidden
    # eval/exec as calls (the safe ast.literal_eval is fine)
    assert not re.search(r"(?<![A-Za-z_.])(eval|exec)\(", src)


def test_cli_values_are_parsed_without_evaluating_code():
    from figuratively.cli import _value

    assert _value("xlim", "__import__('os').system('touch X')") == "__import__('os').system('touch X')"   # a string
    assert _value("xlim", "(1, 2)") == (1, 2)


# ------------------------------------------------------------------ untrusted ROOT files
def _damage(blob: bytes, rng: np.random.Generator, how: int) -> bytes:
    b = bytearray(blob)
    if how == 0:                                   # flip a handful of bytes anywhere
        for _ in range(8):
            b[int(rng.integers(len(b)))] ^= int(rng.integers(1, 256))
    elif how == 1:                                 # truncate
        b = b[: int(rng.integers(8, len(b)))]
    elif how == 2:                                 # zero a block
        i = int(rng.integers(len(b) - 64))
        b[i:i + 64] = bytes(64)
    elif how == 3:                                 # corrupt the header
        for i in range(4, 60):
            b[i] = int(rng.integers(256))
    else:                                          # random bytes with a ROOT magic
        b = bytearray(b"root" + bytes(rng.integers(0, 256, 2000, dtype=np.uint8)))
    return bytes(b)


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="needs POSIX alarms")
def test_corrupted_root_files_fail_cleanly_and_quickly(tmp_path):
    good = tmp_path / "good.root"
    with uproot.recreate(good) as f:
        f["h"] = np.histogram(np.random.default_rng(1).normal(0, 1, 2000), bins=20, range=(-4, 4))
        f["h2"] = np.histogram2d(np.random.default_rng(2).normal(0, 1, 500), np.random.default_rng(3).normal(0, 1, 500),
                                 bins=(8, 8))
    blob = good.read_bytes()
    rng = np.random.default_rng(2024)

    def on_alarm(*_):
        raise TimeoutError("took more than 20 s")

    signal.signal(signal.SIGALRM, on_alarm)
    outcomes = {"ok": 0, "error": 0}
    for i in range(60):
        bad = tmp_path / f"bad{i}.root"
        bad.write_bytes(_damage(blob, rng, i % 5))
        signal.alarm(20)
        try:
            p = fg.plot(f"{bad}:h", save=False)
            p.draw()
            p.close()
            outcomes["ok"] += 1
        except (TimeoutError, MemoryError):
            raise
        except Exception:                          # a clean, ordinary error is the right answer to a broken file
            outcomes["error"] += 1
        finally:
            signal.alarm(0)
        try:
            signal.alarm(20)
            fg.list_objects(str(bad))
        except (TimeoutError, MemoryError):
            raise
        except Exception:
            pass
        finally:
            signal.alarm(0)
    assert outcomes["error"] > 0                   # the damage was real, and every case ended quickly


def test_a_file_that_is_not_root_is_refused_politely(tmp_path):
    f = tmp_path / "x.root"
    f.write_bytes(b"#!/bin/sh\nrm -rf ~\n")
    with pytest.raises(ValueError, match="not a readable ROOT file"):
        fg.plot(f"{f}:h", save=False)
    assert f.read_bytes().startswith(b"#!/bin/sh")  # and it was neither run nor modified
