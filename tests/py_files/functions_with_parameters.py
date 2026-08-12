# Functions taking arguments: dearmor has to synthesise placeholder arguments
# for the calls it makes to trigger decryption.
import time

time.sleep(2)


def identity(first):
    return first


def increments_second(first, second):
    second += 1
    return first


identity(99)
increments_second(1, 5)
