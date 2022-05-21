# dearmor
This is a repo to deobfuscate pyarmor files.

Right now I can obfuscate functions in the obfuscated file.

### Method
I assume you have an obfuscated py and the pytransform module+dll in the same place

1. Put code.py in the same directory as the obfuscated py
1. Run the obfuscated file with your python
1. Inject the dll from [PyInjector](https://github.com/call-042PE/PyInjector) to the running process

The files will be created in a folder called "dump" in the same directory

To change the files from pyc to py, use the amazing [docompyle++](https://github.com/zrax/pycdc) repository

### TODO
[ ] Automatically inject the dll to the process
[ ] Use a nicer way to inject the code - I don't like that I have to compile the dll
[ ] obfuscate entire module and not just single functions
[ ] check if it works __pyarmor_exit__ is called before we inject the dll
[ ] check on advanced modes


### Desclaimer
This repo is for educational perpused only.