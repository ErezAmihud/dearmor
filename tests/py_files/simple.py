# The most basic case: a module with nothing but a top level assignment.
# Every sample sleeps so the process stays alive long enough for dearmor to
# inject its DLL into it.
import time

time.sleep(2)
result = 1 + 1
