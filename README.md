# dearmor
Deobfuscate [pyarmor](https://pypi.org/project/pyarmor/) encryption.

There are two backends, one per pyarmor generation. `dearmor` picks the right
one by looking at the script, so normally you do not have to care:

| | pyarmor 8 and 9 | pyarmor 5, 6 and 7 |
| --- | --- | --- |
| Python | 3.10 - 3.13 | 3.6 - 3.9 |
| Platform | any | Windows |
| Input | obfuscated `.py` scripts | `.py`, `.pyc`, `.exe` |
| Extra dependencies | none | `pyinjector`, `psutil`, `dearmor.dll` |

- Run `dearmor -i {file_path}`
The files will be created in a folder called "dump" in the same directory

Run it with the same Python version the file was obfuscated for -- pyarmor emits
version specific bytecode.

To change the files from pyc to py, use [docompyle++](https://github.com/zrax/pycdc)

### Usage
```
dearmor -i script.py               # deobfuscate into ./dump
dearmor -i script.py -o out        # write somewhere else
dearmor -i script.py --timeout 30  # for scripts that will not exit on their own
dearmor -i script.py -b legacy     # force a backend instead of detecting one
```

### installation
`pip install dearmor`

For pyarmor 7 and older, install the injection dependencies too:
`pip install dearmor[legacy]`

### Method
A pyarmor protected function only holds its real bytecode while it is running:
the prologue asks the runtime to decrypt it, the epilogue wipes it again. Both
backends work by reading the code object in between, but they get there very
differently, because pyarmor 8 changed every name involved.

| pyarmor 5/6/7 | pyarmor 8/9 |
| --- | --- |
| `pytransform` module | `pyarmor_runtime_00xxxx` package |
| `pyarmor_runtime()` | `__pyarmor__(__name__, __file__, b'PY0000...')` |
| `__armor_enter__` global | `C_ENTER_CO_OBJECT_INDEX` builtin in `co_consts` |
| `__armor_exit__` global | `C_LEAVE_CO_OBJECT_INDEX` builtin in `co_consts` |
| `__armor__` global | `C_ASSERT_ARMORED_INDEX` builtin in `co_consts` |

The names are only half of it. pyarmor 7 emitted `LOAD_GLOBAL __armor_enter__`,
so the legacy backend can inject a DLL that defines a global with that name and
wait to be called back. pyarmor 8 stores the runtime's C functions straight into
`co_consts` and emits `LOAD_CONST`, so there is no name left to shadow.

The pyarmor 8/9 backend uses a trace function instead. It runs the script,
snapshots each protected code object while it is on the stack, calls whatever
the script never called itself (aborting each one the moment its body is
readable, so none of it actually runs), and then blanks pyarmor's prologue,
epilogue and `try`/`finally` out of the recovered bytecode. No injection, no
DLL, no Windows.

### Known limitations
- Code that never runs cannot be recovered. dearmor calls uncalled functions
  itself, but a function reachable only through, say, a conditional import will
  be dumped still encrypted.
- Recovered functions keep an unused `__assert_armored__` local when they also
  have closure variables. It is never assigned; dropping it would renumber the
  closure, which is not worth the risk.
- pyarmor's non-default modes (BCC, RFT, `--mix-str`) are not handled. BCC in
  particular compiles functions to C, so there is no bytecode left to recover.

### Contribute
Just ask away or make a pull request.
If something is unclear open an issue

### Desclaimer
This repo is for educational purposes only. I take no responsibility for its usage. 

```diff
- WARNING
- This Program will end up running your .exe/.pyc file.
- Do not use this program if you don't trust the .exe/.pyc, or run it in a VM
```

### Tested versions:
- pyarmor 9.2, on Python 3.10, 3.11, 3.12 and 3.13
- pyarmor 7, on Python 3.6, 3.7, 3.8 and 3.9
