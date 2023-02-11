import os
import shutil
import subprocess
from typing import List
import sys
from platform import system
from setuptools import setup, find_packages, Extension
from setuptools.command import build_ext, sdist, install_lib

# You can't use `pip install .` as pip copies setup.py to a temporary
# directory, parent directory is no longer reachable (isolated build) .
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, CURRENT_DIR)


NEED_CLEAN_TREE = set()
BUILD_TEMP_DIR = None


def lib_name() -> str:
    '''Return platform dependent shared object name.'''
    if system() == 'Linux' or system().upper().endswith('BSD'):
        return 'dearmor.so'
    elif system() == 'Darwin':
        return 'dearmor.dylib'
    elif system() == 'Windows':
        return 'dearmor.dll'
    raise ValueError()


def copy_tree(src: str, dst: str) -> None:
    shutil.copytree(src, dst)
    NEED_CLEAN_TREE.add(os.path.abspath(dst))

    
def clean_up() -> None:
    '''Removed copied files.'''
    for path in NEED_CLEAN_TREE:
        shutil.rmtree(path)



if __name__ == '__main__':
    # Supported commands:
    # From internet:
    # - pip install dearmor

    # - python setup.py build
    # - python setup.py build_ext
    # - python setup.py install
    # - python setup.py sdist       && pip install <sdist-name>
    # - python setup.py bdist_wheel && pip install <wheel-name>

    setup(name='dearmor',
          version='0.2',
          description="Deobfuscate pyarmor files",
          author='Erez Amihud',
          author_email='erezamihud@gmail.com',
          url='https://github.com/ErezAmihud/dearmor',
          packages=['dearmor'],
          install_requires=['pyinjector', 'psutil'],
          extras_require={"test": ["pytest", 'pytest-timeout', 'pyarmor']},
          include_package_data=True,
          package_data={'dearmor':['*.dll']},
          license='Apache-2.0',
          entry_points={
                        'console_scripts': [
                                'dearmor=dearmor.__main__:main_cli',
                        ]
                },
          )

    clean_up()
