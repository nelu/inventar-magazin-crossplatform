"""Nuitka build entrypoint for containers and native CI."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


APP_DIR = Path("C:/app" if os.name == "nt" else "/app")
OUTPUT = Path("C:/out" if os.name == "nt" else "/out")
SOURCE = APP_DIR / "src" / "main.py"
WINDOWS_SEED = Path("C:/nuitka-seed")
QT_PROBE = "import shiboken6\nfrom PySide6 import QtCore, QtGui, QtWidgets\n"


def invoke_nuitka(args, *, env=None):
    return subprocess.run([sys.executable, "-m", "nuitka", *args], env=env).returncode


def build_app(mode, extra=(), *, app_dir=APP_DIR, output=OUTPUT, env=None):
    options = [
        f"--{mode}",
        "--enable-plugin=pyside6",
        "--lto=no",
        "--assume-yes-for-downloads",
        f"--output-dir={output.as_posix()}",
    ]
    if os.name == "nt":
        options += [
            "--include-qt-plugins=platforms,styles",
            "--windows-console-mode=disable",
            "--msvc=latest",
            "--output-filename=Magazin.exe",
        ]
    else:
        options += [
            "--include-qt-plugins=platforms",
            # The Essentials wheel lacks dependencies for optional PDF and
            # embedded EGLFS plugins; the desktop app uses neither.
            "--noinclude-qt-plugins=egldeviceintegrations",
            "--noinclude-dlls=*/libqeglfs.so",
            "--noinclude-dlls=*/libqpdf.so",
        ]
        if mode == "onefile":
            options.append("--output-filename=Magazin-linux-x64")
    source = app_dir / "src" / "main.py"
    return invoke_nuitka([*options, *extra, source.as_posix()], env=env)


def warm_windows_cache():
    # Use the same paths as the application build so DLL scan keys are reusable.
    WINDOWS_SEED.mkdir()
    SOURCE.parent.mkdir()
    try:
        OUTPUT.mkdir()
        try:
            SOURCE.write_text(QT_PROBE, encoding="utf-8", newline="\n")
            return build_app("standalone", env={**os.environ, "NUITKA_CACHE_DIR": str(WINDOWS_SEED)})
        finally:
            shutil.rmtree(OUTPUT)
    finally:
        shutil.rmtree(SOURCE.parent)
        compiler_cache = WINDOWS_SEED / "clcache"
        if compiler_cache.is_dir():
            shutil.rmtree(compiler_cache)


def merge_windows_seed(source, target):
    if target.is_dir():
        if source.is_dir():
            for child in source.iterdir():
                merge_windows_seed(child, target / child.name)
        return
    if os.path.lexists(target):
        return

    # Stage on the cache volume. On Windows, rename never replaces an existing
    # destination. If a concurrent container wins, merge any missing children.
    with TemporaryDirectory(prefix=".seed-", dir=target.parent) as scratch:
        staged = Path(scratch) / "entry"
        if source.is_dir():
            shutil.copytree(source, staged)
        else:
            shutil.copy2(source, staged)
        try:
            staged.rename(target)
        except OSError:
            if not os.path.lexists(target):
                raise
            merge_windows_seed(source, target)


def merge_default_windows_seed():
    if os.name == "nt" and WINDOWS_SEED.is_dir():
        cache_dir = os.environ.get("NUITKA_CACHE_DIR")
        if not cache_dir:
            sys.exit("NUITKA_CACHE_DIR is required to merge the cache seed")
        cache = Path(cache_dir)
        cache.mkdir(parents=True, exist_ok=True)
        merge_windows_seed(WINDOWS_SEED, cache)


def main(args):
    if args[:1] == ["--warm-cache"]:
        if os.name != "nt" or len(args) != 1:
            sys.exit("Usage (Windows only): --warm-cache")
        return warm_windows_cache()

    modes = {"--build-app": "onefile", "--build-standalone": "standalone"}
    mode = modes.get(args[0]) if args else None
    if mode:
        parser = argparse.ArgumentParser(
            prog=f"{Path(sys.argv[0]).name} {args[0]}", allow_abbrev=False
        )
        parser.add_argument("--app-dir", type=Path, default=APP_DIR)
        parser.add_argument("--output-dir", type=Path, default=OUTPUT)
        paths, extra = parser.parse_known_args(args[1:])
        app_dir = paths.app_dir.resolve()
        output = paths.output_dir.resolve()
        test_result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=app_dir,
        )
        if test_result.returncode:
            return test_result.returncode
        merge_default_windows_seed()
        return build_app(mode, extra, app_dir=app_dir, output=output)

    merge_default_windows_seed()
    return invoke_nuitka(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
