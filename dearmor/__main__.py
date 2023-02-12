import sys
import shutil
from pathlib import Path
import subprocess
import time
import sys
import psutil
import argparse
from pyinjector import inject


def dearmor_main(file: Path):
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

    print("success!")
    print("Output at: ", file.parent / "dump")


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
    dearmor_main(parser.parse_args().file)


if __name__ == "__main__":
    main_cli()
