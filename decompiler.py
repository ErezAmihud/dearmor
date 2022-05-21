import os
def find_main(pyc_dir):
        for pyc_file in os.listdir(pyc_dir):
                if not pyc_file.startswith("pyi-") and pyc_file.endswith("manifest"):
                        main_file = pyc_file.replace(".exe.manifest", "")
                        result = f"{pyc_dir}{os.sep}{main_file}"
                        if os.path.exists(result):
                                return main_file

pyc_dir = input("pyc dir>")
main_file = find_main(pyc_dir)
main_file = input("main file>")
print(main_file)
pyz_dir = f"{pyc_dir}{os.sep}PYZ-00.pyz_extracted"
for pyc_file in os.listdir(pyz_dir):
        if pyc_file.endswith(".pyc"):
                file = f"{pyz_dir}{os.sep}{pyc_file}"
                break
with open(file, "rb") as f:
        head = f.read(4)
        list(map(hex, head))

import shutil
if os.path.exists("pycfile_tmp"):
        shutil.rmtree("pycfile_tmp")
os.mkdir("pycfile_tmp")
main_file_result = f"pycfile_tmp{os.sep}{main_file}.pyc"
with open(f"{pyc_dir}{os.sep}{main_file}", "rb") as read, open(main_file_result, "wb") as write:
        write.write(head)
        write.write(b"\0"*12)
        write.write(read.read())

pyz_dir = f"{pyc_dir}{os.sep}PYZ-00.pyz_extracted"
for pyc_file in os.listdir(pyz_dir):
        pyc_file_src = f"{pyz_dir}{os.sep}{pyc_file}"
        pyc_file_dest = f"pycfile_tmp{os.sep}{pyc_file}"
        print(pyc_file_src, pyc_file_dest)
        with open(pyc_file_src, "rb") as read, open(pyc_file_dest, "wb") as write:
                write.write(read.read(12))
                write.write(b"\0"*4)
                write.write(read.read())