# dearmor
This is a repo to deobfuscate pyarmor files.

Right now I can get an obfuscated file source, only if this is the only file.
For now working only on windows

### Method
I assume you have an obfuscated py and the pytransform module+dll in the same place. To extract it you can use [python-exe-unpacker](https://github.com/countercept/python-exe-unpacker) to make runable pyc files. Then you need to delete all the files that are not the main ones. This may not be the full process, open an issue if you want me to write the full one.

I inject code into the running process that gets the loaded python dll, then I use it to run python code in the same context of the obfuscated code

- Run `dearmor -i {file_path}`

The files will be created in a folder called "dump" in the same directory

To change the files from pyc to py, use the amazing [docompyle++](https://github.com/zrax/pycdc) repository

### Usage
* `python setup.py install`
* `dearmor -h`
* Use file names and not full paths - I still have some things in the user interface to improve

### TODO
- [X] obfuscate entire module and not just single functions
- [X] adding a nice user interface
- [X] Tests
- [X] Trigger functions to load to unobfuscate them
- [X] figure out a way to resolve the functions without invoking their actual code (maybe run the code in a subinterpreter where we can close after the call to __armor_enter__  ?)
- [X] Use a nicer way to inject the code - I don't like that I have to compile the dll, and we can just use ctypes to disable the gil.
- [X] Compile automatically on install
- [ ] Adding automatic testing to different python versions
- [ ] Figure out a way to not force the code to be compatible to EVERY python version
- [ ] add black formatting
- [ ] Find out how to include `code.py` as package data
- [ ] make the code work on versions other than >3.6 (changes are both in the cpp and the syntax of the python in the code.py file)
- [ ] check on advanced modes
- [ ] automatically run tests on pull requests
- [ ] make scripts to automatically extract an exe
- [ ] in decompile remove libraries that are not original of the programmer code
- [ ] Add a compile version for linux

### Contribute
Just ask away or make a pull request.
If something is unclear open an issue

It was done in the last week, so there might be some bugs I haven't saw yet. Open issues!

### Desclaimer
This repo is for educational purposes only. I take no responsibility for its usage. 

### Tested versions:
- 3.7

### Installation
You need to install cmake in order for this repo to compile it's c extension. To install cmake you can use `pip install cmake`