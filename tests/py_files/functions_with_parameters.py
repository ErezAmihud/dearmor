import time

time.sleep(2)


def a(param1):
    return param1


def b(param1, param=4):
    return param1 + param

b(1)
b(1,5)
a(99)
