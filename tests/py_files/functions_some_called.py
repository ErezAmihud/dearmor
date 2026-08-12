# Only one of the two functions is called. The other one is still encrypted
# when the dump starts, so it exercises the code path that invokes untouched
# code objects to force their decryption.
import time

time.sleep(2)


def greeting():
    return "hi"


def farewell():
    return "bye"


greeting()
