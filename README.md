# dearmor
This is a repo to deobfuscate pyarmor files.

Right now I can obfuscate functions in the obfuscated file.

### Method
I assume you have an obfuscated py and the pytransform module+dll in the same place. To extract it you can use [python-exe-unpacker](https://github.com/countercept/python-exe-unpacker) and the script `decompile.py` in this repository to make runable pyc files. Then you need to delete all the files that are not the main ones. This may not be the full process, open an issue if you want me to write the full one.

1. Put code.py in the same directory as the obfuscated py
1. Run the obfuscated file with your python
1. Inject the dll from [PyInjector](https://github.com/call-042PE/PyInjector) to the running process

The files will be created in a folder called "dump" in the same directory

To change the files from pyc to py, use the amazing [docompyle++](https://github.com/zrax/pycdc) repository

### TODO
[X] obfuscate entire module and not just single functions
[X] adding a nice user interface
[X] Tests
[X] Trigger functions to load to unobfuscate them
[X] automatically close whatever windows the running application may start
[ ] add black formatting
[ ] Find out how to include `code.py` as package data
[ ] Use a nicer way to inject the code - I don't like that I have to compile the dll
[ ] make the code work on versions other than >3.6
[ ] check on advanced modes


### Contribute
Just ask away or make a pull request.
If something is unclear open an issue

It was done in the last week, so there might be some bugs I haven't saw yet. Open issues!

### Desclaimer
This repo is for educational purposes only. I take no responsibility for its usage. 