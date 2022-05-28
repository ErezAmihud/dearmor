import os
import shutil
import subprocess
import logging
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
        name = 'dearmor.so'
    elif system() == 'Darwin':
        name = 'dearmor.dylib'
    elif system() == 'Windows':
        name = 'dearmor.dll'
    return name


def copy_tree(src: str, dst: str) -> None:
    shutil.copytree(src, dst)
    NEED_CLEAN_TREE.add(os.path.abspath(dst))

    
def clean_up() -> None:
    '''Removed copied files.'''
    for path in NEED_CLEAN_TREE:
        shutil.rmtree(path)


class CMakeExtension(Extension):  # pylint: disable=too-few-public-methods
    '''Wrapper for extension'''
    def __init__(self, name: str) -> None:
        super().__init__(name=name, sources=[])


class BuildExt(build_ext.build_ext):  # pylint: disable=too-many-ancestors
    '''Custom build_ext command using CMake.'''

    def build(
        self,
        src_dir: str,
        build_dir: str
    ) -> None:
        '''Build the core library with CMake.'''

        cmake_cmd = ['cmake', src_dir]
        self.announce('Run CMake command: %s'.format(str(cmake_cmd)))
        subprocess.check_call(cmake_cmd, cwd=build_dir)

        cmake_cmd = ['cmake', '--build', '.', '--config', 'Release']
        self.announce('Run CMake command: %s'.format(str(cmake_cmd)))
        subprocess.check_call(cmake_cmd, cwd=build_dir)

    def build_cmake_extension(self) -> None:
        '''Configure and build using CMake'''
        global BUILD_TEMP_DIR
        BUILD_TEMP_DIR = self.build_temp

        libdearmor = os.path.abspath(os.path.join(CURRENT_DIR, 'dearmor-library', 'lib', lib_name()))
        if os.path.exists(libdearmor):
            self.announce('Found shared library, skipping build.')
            return
        
        src_dir = os.path.join(CURRENT_DIR, 'dearmor-library')
        copy_tree(
            src_dir,
            BUILD_TEMP_DIR)
        

        self.announce('Building from source.')
        self.build(src_dir, BUILD_TEMP_DIR)
            
    def build_extension(self, ext: Extension) -> None:
        '''Override the method for dispatching.'''
        if isinstance(ext, CMakeExtension):
            self.build_cmake_extension()
        else:
            super().build_extension(ext)

    def copy_extensions_to_source(self) -> None:
        '''Dummy override.  Invoked during editable installation.  Our binary
        should available in `lib`.

        '''
        if not os.path.exists(
                os.path.join(CURRENT_DIR, 'dearmor-library', 'lib', lib_name())):
            raise ValueError('For using editable installation, please ' +
                             'build the shared object first with CMake.')


class Sdist(sdist.sdist):       # pylint: disable=too-many-ancestors
    '''Copy c++ source into Python directory.'''

    def run(self) -> None:
        libdearmor = os.path.join(
            CURRENT_DIR, 'dearmor-library','lib', lib_name())
        if os.path.exists(libdearmor):
            self.announce(
                'Found shared library, removing to avoid being included in source distribution.'
            )
            os.remove(libdearmor)
        super().run()


class InstallLib(install_lib.install_lib):
    '''Copy shared object into installation directory.'''
    def install(self) -> List[str]:
        outfiles = super().install()
        lib_dir = os.path.join(self.install_dir, 'lib')
        if not os.path.exists(lib_dir):
            os.mkdir(lib_dir)
        dst = os.path.join(lib_dir, lib_name())

        assert BUILD_TEMP_DIR is not None
        dft_lib = os.path.join(CURRENT_DIR, 'dearmor-library', 'lib', lib_name())
        build_lib = os.path.join(BUILD_TEMP_DIR, 'lib', lib_name())

        src = dft_lib if os.path.exists(dft_lib) else build_lib
        
        self.announce('Installing shared library: %s', src)
        dst, _ = self.copy_file(src, dst)
        outfiles.append(dst)
        return outfiles


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
          version='0.0',
          description="Deobfuscate pyarmor files",
          author='Erez Amihud',
            author_email='erezamihud@gmail.com',
            url='https://github.com/ErezAmihud/dearmor',
            packages=['dearmor'],
            requires=['pyinjector', 'psutil'],
            extras_require={"test": ["pytest", 'pytest-timeout']},
      
          ext_modules=[CMakeExtension('dearmor')],
          cmdclass={
              'build_ext': BuildExt,
              'sdist': Sdist,
              'install_lib': InstallLib
          },
          include_package_data=True,
          license='Apache-2.0',
          entry_points={
                        'console_scripts': [
                                'dearmor=dearmor.__main__:main_cli',
                        ]
                },
          )

    clean_up()
