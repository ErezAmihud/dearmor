import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PYARMOR8 = "pyarmor8"
LEGACY = "legacy"

# Markers the two generations of PyArmor leave in the scripts they emit.  Both
# call a global named ``__pyarmor__``, so that one says nothing on its own; what
# separates them is the runtime they import it from.
LEGACY_MARKERS = (b"pytransform", b"__armor_enter__", b"__armor__")
PYARMOR8_MARKERS = (b"pyarmor_runtime_", b"__pyarmor__")


def detect_backend(file: Path) -> str:
    """Guess which PyArmor generation obfuscated *file*.

    Anything we cannot read as a script (a frozen executable, for instance)
    falls back to the legacy backend, which is the one that knows how to deal
    with those.
    """
    try:
        head = file.read_bytes()[:4096]
    except OSError:
        return LEGACY
    if any(marker in head for marker in LEGACY_MARKERS):
        return LEGACY
    if any(marker in head for marker in PYARMOR8_MARKERS):
        return PYARMOR8
    return LEGACY


def _subprocess_env():
    """Make sure the runner can import dearmor from wherever we were run.

    The runner starts in the obfuscated script's directory, which is unlikely to
    be anywhere near this package when dearmor has not been installed.  Our path
    goes at the end so it cannot shadow the script's own imports.
    """
    env = dict(os.environ)
    root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [env.get("PYTHONPATH"), root]))
    return env


def dearmor_pyarmor8(file: Path, output: Path = None, timeout: float = None):
    """Deobfuscate a PyArmor 8/9 script.

    The script is run in a subprocess of the *current* interpreter -- the
    bytecode PyArmor emits is version specific, so it has to be the same Python
    that the script was obfuscated for.  :mod:`dearmor.runner` does the actual
    work from inside that process.
    """
    file = file.resolve()
    output = Path(output).resolve() if output else file.parent / "dump"
    command = [sys.executable, "-m", "dearmor.runner", str(file), str(output)]
    if timeout is not None:
        command += ["--timeout", str(timeout)]
    result = subprocess.run(command, cwd=str(file.parent), env=_subprocess_env())
    if result.returncode != 0:
        raise ValueError("could not deobfuscate %s" % file)
    return output


def dearmor_legacy(file: Path):
    """Deobfuscate a PyArmor 5/6/7 script or executable (Windows only).

    Injects ``dearmor.dll`` into the running process; the DLL executes
    :mod:`dearmor.code`, which shadows PyArmor's ``__armor_exit__`` global and
    dumps each code object as it is decrypted.
    """
    import psutil
    from pyinjector import inject

    file = file.resolve()
    shutil.copy(
        Path(__file__).parent.resolve() / "code.py",
        file.parent.resolve() / "dearmor.txt",
    )
    command = [sys.executable, str(file)] if file.name.endswith(".py") else str(file)
    shell = sys.version_info.minor < 7
    p = subprocess.Popen(
        command,
        shell=shell,
        cwd=str(file.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(
        1
    )  # this is used to allow the python process to create it's child process
    current_process = psutil.Process(p.pid)
    child = current_process.children()
    inject(child[0].pid, str(Path(__file__).parent / "Release" / "dearmor.dll"))
    out, err = p.communicate()
    if p.wait() != 0:
        raise ValueError(f"running file itself failed. stdout={out} stderr={err}")

    return file.parent / "dump"


def dearmor_main(file: Path, output: Path = None, backend: str = None, timeout=None):
    """Deobfuscate *file*, picking a backend from its contents unless told."""
    file = Path(file)
    backend = backend or detect_backend(file)
    if backend == PYARMOR8:
        output = dearmor_pyarmor8(file, output, timeout)
    else:
        output = dearmor_legacy(file)

    print("success!")
    print("Output at: ", output)
    return output


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input",
        help="The file the program should run. The file should block atleast for 1 second",
        required=True,
        type=Path,
        dest="file",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Where to write the recovered files (default: a 'dump' folder next to the input)",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "-b",
        "--backend",
        help="Which PyArmor generation to assume (default: detect from the file)",
        choices=[PYARMOR8, LEGACY],
        default=None,
    )
    parser.add_argument(
        "--timeout",
        help="Stop a script that will not finish on its own, in seconds",
        type=float,
        default=None,
    )
    args = parser.parse_args()
    dearmor_main(args.file, args.output, args.backend, args.timeout)


if __name__ == "__main__":
    main_cli()
