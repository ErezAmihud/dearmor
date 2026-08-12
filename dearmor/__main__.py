"""Command line entry point of dearmor.

The package itself does very little: it starts the obfuscated program, injects
``dearmor.dll`` into it and lets the injected payload (``dearmor/code.py``) do
the actual deobfuscation from inside the running interpreter. See that module
for a description of how the dump is produced.
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil
from pyinjector import inject

# The payload is copied next to the target under this name. The DLL has the
# very same name compiled into it (see the DEARMOR_CODE definition in
# dearmor-library/CMakeLists.txt) and reads it from the working directory.
PAYLOAD_FILE_NAME = "dearmor.txt"

# Name of the directory the payload writes the recovered .pyc files to, created
# next to the target file. Must match DUMP_DIR in dearmor/code.py.
DUMP_DIR_NAME = "dump"

# The DLL that is injected into the target process, shipped inside the package.
INJECTED_LIBRARY_PATH = Path(__file__).parent / "Release" / "dearmor.dll"

# How long to wait for the target to spawn the child process that actually
# hosts the Python interpreter (PyInstaller executables unpack themselves and
# re-exec, and `python file.py` is started through a shell on Python 3.6).
CHILD_PROCESS_STARTUP_SECONDS = 1


def deobfuscate_file(target_file: Path) -> None:
    """Run an obfuscated file and dump the deobfuscated code objects it loads.

    The recovered ``.pyc`` files end up in a ``dump`` directory next to
    ``target_file``.

    Args:
        target_file: The pyarmor obfuscated ``.py``, ``.pyc`` or ``.exe`` to
            run. It has to stay alive for at least a second so the payload can
            be injected before it exits.

    Raises:
        ValueError: if the target itself exits with a non-zero status.

    Warning:
        This *executes* the target file. Only use it on files you trust, or
        inside a virtual machine.
    """
    target_file = target_file.resolve()
    shutil.copy(
        Path(__file__).parent.resolve() / "code.py",
        target_file.parent.resolve() / PAYLOAD_FILE_NAME,
    )

    is_python_source = target_file.name.endswith(".py")
    command = (
        [sys.executable, str(target_file)] if is_python_source else str(target_file)
    )
    # Python 3.6 needs a shell to spawn the interpreter as a separate child
    # process, which is the process we are after below.
    use_shell = sys.version_info.minor < 7

    target_process = subprocess.Popen(
        command,
        shell=use_shell,
        cwd=str(target_file.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # this is used to allow the python process to create it's child process
    time.sleep(CHILD_PROCESS_STARTUP_SECONDS)

    child_processes = psutil.Process(target_process.pid).children()
    inject(child_processes[0].pid, str(INJECTED_LIBRARY_PATH))

    stdout, stderr = target_process.communicate()
    if target_process.wait() != 0:
        raise ValueError(f"running file itself failed. stdout={stdout} stderr={stderr}")

    print("success!")
    print("Output at: ", target_file.parent / DUMP_DIR_NAME)


# Backwards compatible alias for the name this function had up to 0.3.1.
dearmor_main = deobfuscate_file


def main_cli() -> None:
    """Parse the command line arguments and deobfuscate the requested file."""
    parser = argparse.ArgumentParser(
        description="Deobfuscate a pyarmor protected file by running it and "
        "dumping the decrypted code objects into a 'dump' directory."
    )
    parser.add_argument(
        "-i",
        "--input",
        help="The file the program should run. The file should block atleast for 1 second",
        required=True,
        type=Path,
        dest="target_file",
    )
    deobfuscate_file(parser.parse_args().target_file)


if __name__ == "__main__":
    main_cli()
