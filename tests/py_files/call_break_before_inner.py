# The inner function would block for hours if it were really executed. Calling
# it to force decryption must therefore stop right after the pyarmor prologue -
# if the patching is wrong, the test hits its timeout instead of passing.
import time

time.sleep(2)


def sleeps_for_hours():
    time.sleep(20000)
