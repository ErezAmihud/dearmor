import time

time.sleep(2)


def a(param1):
    return param1


def b(param1, param2):
    param2 += 1
    return param1


a(99)
b(1, 5)
