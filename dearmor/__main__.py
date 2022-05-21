import shutil
from pathlib import Path
import subprocess
import time
import sys
import psutil
import argparse
from pyinjector import inject


def main(file:Path, pyinjector:Path):
    file= file.resolve()
    pyinjector = pyinjector.resolve()
    shutil.copy(Path(__file__).parent.resolve() / "code.py", file.parent / "code.py")
    try:
        p = subprocess.Popen([sys.executable, str(file)], cwd=str(file.parent))
        time.sleep(1) # this is used to allow the python process to create it's child process
        current_process = psutil.Process(p.pid)
        child = current_process.children(recursive=True)
        inject(child[0].pid, str(pyinjector))
        p.communicate()
        if p.poll() != 0:
            raise ValueError(f"running file itself failed: {stdout}")
        print("success!")
        print("Output at: ", str(file.parent / "dump"))
    finally:
        (file.parent / "code.py").unlink()

def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", help="The file the program should run. The file should block atleast for 1 second", required=True, type=Path, dest="file")
    parser.add_argument("-n", "--injector", help="The path to the pyinjector dll", type=Path, required=True, dest="pyinjector")
    main(**parser.parse_args().__dict__)

if __name__ == "__main__":
    main_cli()