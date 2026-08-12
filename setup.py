"""Packaging script for dearmor.

The injected library is *not* built from here: run ``build_binary.bat`` to
produce ``dearmor/Release/dearmor.dll`` with cmake first, the wheel then ships
that dll as package data.
"""

import os
import sys
from platform import system

from setuptools import setup

# You can't use `pip install .` as pip copies setup.py to a temporary
# directory, parent directory is no longer reachable (isolated build) .
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, CURRENT_DIR)


def shared_library_name() -> str:
    """Return platform dependent shared object name."""
    if system() == "Linux" or system().upper().endswith("BSD"):
        return "dearmor.so"
    elif system() == "Darwin":
        return "dearmor.dylib"
    elif system() == "Windows":
        return "dearmor.dll"
    raise ValueError()


if __name__ == "__main__":
    setup(
        name="dearmor",
        version="0.3.1",
        description="Deobfuscate pyarmor files",
        long_description=open("README.md", "r").read(),
        long_description_content_type="text/markdown",
        author="Erez Amihud",
        author_email="erezamihud@gmail.com",
        url="https://github.com/ErezAmihud/dearmor",
        packages=["dearmor"],
        install_requires=["pyinjector", "psutil"],
        extras_require={"test": ["pytest", "pytest-timeout", "pyarmor"]},
        include_package_data=True,
        package_data={"dearmor": ["Release\\*.dll"]},
        license="Apache-2.0",
        entry_points={
            "console_scripts": [
                "dearmor=dearmor.__main__:main_cli",
            ]
        },
    )
