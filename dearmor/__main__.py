import os
import shutil
from pathlib import Path
import subprocess
import time
import sys
import psutil
import argparse
from pyinjector import inject


def main(file:Path=None, pyinjector:Path=None, error_file:Path=None, print_user_messages:bool=False):
    assert file
    assert pyinjector
    assert error_file
    file= file.resolve()
    pyinjector = pyinjector.resolve()
    error_file = error_file.resolve()
    shutil.copy(Path(__file__).parent.resolve() / "code.py", file.parent / "code.py")
    with open(str(error_file), 'w') as f:
        try:
            p = subprocess.Popen([sys.executable, str(file)], cwd=str(file.parent), stdout=f, stderr=f)
            time.sleep(1) # this is used to allow the python process to create it's child process
            current_process = psutil.Process(p.pid)
            child = current_process.children(recursive=True)
            inject(child[0].pid, str(pyinjector))
            p.communicate()
            if p.poll() != 0:
                raise ValueError("running file itself failed.")
            if print_user_messages:
                print("success!")
                print("Output at: ", str(file.parent / "dump"))
        finally:
            (file.parent / "code.py").unlink()

def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", help="The file the program should run. The file should block atleast for 1 second", required=True, type=Path, dest="file")
    parser.add_argument("-n", "--injector", help="The path to the pyinjector dll", type=Path, required=True, dest="pyinjector")
    parser.add_argument("-f", "--fail-file", help="The file the output of the process will be saved to (useful in case of errors)", type=Path, default="out.txt", dest="error_file")
    main(print_user_messages=True, **parser.parse_args().__dict__)

if __name__ == "__main__":
    main_cli()