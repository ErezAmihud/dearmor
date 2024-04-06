# dearmor
Deobfuscate [pyarmor](https://pypi.org/project/pyarmor/) encryption.

It is best to use it with the pyc files extracted from the exe file, but exe file should work.
Working only on windows.

It was not checked with custom pyarmor modes, only with the default configuration.

### Method
Dearmor injects a dll into the running process, which calls a python function to run custom code. Using the custom code dearmor calls each function the exists in the file and deobfuscate it.

- Run `dearmor -i {file_path}`
The files will be created in a folder called "dump" in the same directory

To change the files from pyc to py, use [docompyle++](https://github.com/zrax/pycdc)

### installation
`pip install dearmor`

### Contribute
Just ask away or make a pull request.
If something is unclear open an issue

### Desclaimer
```diff
- WARNING
- This Program will end up running your .exe/.pyc file.
- Do not use this program if you don't trust the .exe/.pyc, or run it in a VM
```
This repo is for educational purposes only. I take no responsibility for its usage. 

### Tested versions:
- 3.6
- 3.7
- 3.8
- 3.9
