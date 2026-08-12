"""Prepare PyInstaller extracted files so a decompiler can read them.

``pyinstxtractor`` strips part of the ``.pyc`` header from the files it
extracts, which makes decompilers such as decompyle++ reject them. This helper
walks over an extraction directory and rebuilds a usable header for every file:

* the main script keeps no header at all, so it gets the magic number of the
  running interpreter plus twelve zero bytes;
* the modules inside ``PYZ-00.pyz_extracted`` keep the first twelve bytes but
  miss one 32-bit field, which is filled with zeroes.

The rebuilt files are written to a fresh ``pycfile_tmp`` directory next to the
current working directory. Run the script and answer the two prompts.
"""

import os
import shutil

# Directory pyinstxtractor creates inside the extraction folder for the modules
# that were bundled in the PYZ archive.
PYZ_DIR_NAME = "PYZ-00.pyz_extracted"

# Where the fixed up .pyc files are written.
OUTPUT_DIR_NAME = "pycfile_tmp"

# Size of the interpreter magic number at the start of a .pyc header.
MAGIC_NUMBER_SIZE = 4

# Number of header bytes the main script is missing after its magic number
# (timestamp, source size and, from 3.7 onwards, the bit field).
MAIN_FILE_MISSING_HEADER_SIZE = 12

# The module files keep this many header bytes and miss a single 32-bit field.
MODULE_KEPT_HEADER_SIZE = 12
MODULE_MISSING_HEADER_SIZE = 4


def find_main(extraction_dir):
    """Guess the name of the extracted main script.

    PyInstaller leaves a ``<name>.exe.manifest`` next to the extracted main
    script, so the manifest that does not belong to PyInstaller itself (those
    are prefixed with ``pyi-``) names the file we are after.

    Returns:
        The file name of the main script, or None if no candidate was found.
    """
    for extracted_file in os.listdir(extraction_dir):
        if not extracted_file.startswith("pyi-") and extracted_file.endswith(
            "manifest"
        ):
            main_file_name = extracted_file.replace(".exe.manifest", "")
            if os.path.exists(f"{extraction_dir}{os.sep}{main_file_name}"):
                return main_file_name


def read_magic_number(pyz_dir):
    """Read the interpreter magic number from any module in ``pyz_dir``.

    The extracted modules still start with their magic number, so any of them
    tells us which interpreter version the bundle was built for -- which is
    exactly the header the main script is missing.
    """
    for extracted_file in os.listdir(pyz_dir):
        if extracted_file.endswith(".pyc"):
            with open(f"{pyz_dir}{os.sep}{extracted_file}", "rb") as module_file:
                return module_file.read(MAGIC_NUMBER_SIZE)
    raise ValueError(f"No .pyc file to read the magic number from in {pyz_dir}")


def create_output_dir():
    """Create an empty output directory, replacing a leftover one."""
    if os.path.exists(OUTPUT_DIR_NAME):
        shutil.rmtree(OUTPUT_DIR_NAME)
    os.mkdir(OUTPUT_DIR_NAME)


def restore_main_file(extraction_dir, main_file_name, magic_number):
    """Write the main script with a complete .pyc header into the output dir."""
    output_path = f"{OUTPUT_DIR_NAME}{os.sep}{main_file_name}.pyc"
    with open(f"{extraction_dir}{os.sep}{main_file_name}", "rb") as source_file, open(
        output_path, "wb"
    ) as output_file:
        output_file.write(magic_number)
        output_file.write(b"\0" * MAIN_FILE_MISSING_HEADER_SIZE)
        output_file.write(source_file.read())


def restore_modules(pyz_dir):
    """Write every bundled module with a complete .pyc header into the output dir."""
    for extracted_file in os.listdir(pyz_dir):
        source_path = f"{pyz_dir}{os.sep}{extracted_file}"
        output_path = f"{OUTPUT_DIR_NAME}{os.sep}{extracted_file}"
        print(source_path, output_path)
        with open(source_path, "rb") as source_file, open(
            output_path, "wb"
        ) as output_file:
            output_file.write(source_file.read(MODULE_KEPT_HEADER_SIZE))
            output_file.write(b"\0" * MODULE_MISSING_HEADER_SIZE)
            output_file.write(source_file.read())


def main():
    extraction_dir = input("pyc dir>")
    # The detected name is only a suggestion; the user confirms it, or types a
    # different one when the manifest based guess is wrong.
    detected_main_file = find_main(extraction_dir)
    main_file_name = input(f"main file>[{detected_main_file}]") or detected_main_file
    print(main_file_name)

    pyz_dir = f"{extraction_dir}{os.sep}{PYZ_DIR_NAME}"
    magic_number = read_magic_number(pyz_dir)

    create_output_dir()
    restore_main_file(extraction_dir, main_file_name, magic_number)
    restore_modules(pyz_dir)


if __name__ == "__main__":
    main()
