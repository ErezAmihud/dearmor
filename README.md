# dearmor

Deobfuscate [pyarmor](https://pypi.org/project/pyarmor/) encryption.

It is best to use it with the pyc files extracted from the exe file, but exe file should work.
Working only on windows.

It was not checked with custom pyarmor modes, only with the default configuration.

### Installation

`pip install dearmor`

### Usage

- Run `dearmor -i {file_path}`

The recovered files are created in a folder called "dump" in the same directory as the input file.
The input file has to keep running for at least a second, so that dearmor can attach to it before it exits.

To change the files from pyc to py, use [decompyle++](https://github.com/zrax/pycdc).

You can also call it from python:

```python
from pathlib import Path
from dearmor import deobfuscate_file

deobfuscate_file(Path("obfuscated.py"))
```

If an executable was built with PyInstaller, extract it with
[pyinstxtractor](https://github.com/extremecoders-re/pyinstxtractor) first and run `decompiler.py`
to repair the `.pyc` headers of the extracted files before decompiling them.

### Method

Dearmor injects a dll into the running process, which calls a python function to run custom code.
Using the custom code dearmor calls each function that exists in the file and deobfuscates it.

In more detail:

1. `dearmor/__main__.py` copies the payload (`dearmor/code.py`) next to the target as `dearmor.txt`,
   starts the target and injects `dearmor.dll` into the process that hosts the interpreter.
2. `dearmor-library/` (the dll) resolves the CPython API from the interpreter that is already loaded
   in the target, acquires the GIL and executes the payload with `PyRun_SimpleString`. That runs it in
   the target's `__main__` namespace - the same namespace as the obfuscated script.
3. Because of that, the payload's `__armor_exit__` shadows the one from the pyarmor runtime. pyarmor
   calls it at the end of every obfuscated code object, which hands control to dearmor at a point where
   the bytecode has already been decrypted in memory.
4. The payload walks up to the outermost obfuscated frame and rebuilds its code object: the pyarmor
   prologue and epilogue are patched out, nested functions that were never called are invoked with
   dummy arguments so that pyarmor decrypts them too, and the `__armor*` names are dropped.
5. The result is marshalled back into a `.pyc` file under `dump/`.

### Development

- `pip install -e .[test]` installs dearmor together with the test dependencies.
- `python -m pytest` runs the test suite. It obfuscates the sample files in `tests/py_files` with
  pyarmor and asserts that dearmoring them reproduces the original bytecode, so it only runs on windows.
- `tox` runs the same suite against every supported interpreter.
- `build_binary.bat` rebuilds `dearmor.dll` from `dearmor-library/` and writes it into the package.
- The code is formatted with [black](https://github.com/psf/black); `pre-commit install` sets that up.

### Contribute

Just ask away or make a pull request.
If something is unclear open an issue.

### Disclaimer

This repo is for educational purposes only. I take no responsibility for its usage.

```diff
- WARNING
- This Program will end up running your .exe/.pyc file.
- Do not use this program if you don't trust the .exe/.pyc, or run it in a VM
```

### Tested versions:
- 3.6
- 3.7
- 3.8
- 3.9
