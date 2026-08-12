# Two functions that are both called, so pyarmor decrypts both of them on its
# own before the dump happens.
import time

time.sleep(2)


def greeting():
    return "hi"


def farewell():
    return "bye"


greeting()
farewell()
