"""Run a PyArmor 8/9 obfuscated script and dump what it decrypts.

This is the module the PyArmor 8/9 backend executes in a subprocess.  It has to
run inside the obfuscated process because the only moment a protected function's
bytecode exists in memory is while that function is on the stack.

    python -m dearmor.runner <script> <output directory>
"""

import argparse
import runpy
import sys
import threading
from pathlib import Path

from . import pyarmor8
from .pyc import marshal_to_pyc


class Watchdog:
    """Interrupts the main thread so a hanging script still gets dumped."""

    def __init__(self, timeout):
        self.timeout = timeout
        self._timer = None

    def __enter__(self):
        if self.timeout:
            import _thread

            self._timer = threading.Timer(self.timeout, _thread.interrupt_main)
            self._timer.daemon = True
            self._timer.start()
        return self

    def __exit__(self, *exc_info):
        if self._timer is not None:
            self._timer.cancel()
        return False


def collect(script, timeout=None):
    """Run *script* under a :class:`~dearmor.pyarmor8.Collector`.

    The collector is returned whatever the script does -- the interesting code
    objects are usually captured long before a script that crashes or blocks
    gets to misbehave.
    """
    script = Path(script).resolve()
    collector = pyarmor8.Collector()
    argv, path = sys.argv[:], sys.path[:]
    sys.argv = [str(script)]
    sys.path.insert(0, str(script.parent))
    try:
        with collector, Watchdog(timeout):
            try:
                runpy.run_path(str(script), run_name="__main__")
            except BaseException as error:  # the script is not ours to trust
                print("dearmor: script stopped with %r" % (error,), file=sys.stderr)
    finally:
        sys.argv, sys.path = argv, path

    collector.force_all()
    return collector


def dump(collector, output):
    """Write every recovered module to *output* as a ``.pyc`` file."""
    output = Path(output)
    written = []
    for name, code in pyarmor8.recovered_modules(collector).items():
        written.append(marshal_to_pyc(output / (name.replace(".", "/") + ".pyc"), code))
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m dearmor.runner")
    parser.add_argument("script", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args(argv)

    collector = collect(args.script, args.timeout)
    if not collector.captured:
        print(
            "dearmor: no PyArmor 8/9 protected code found in %s" % args.script,
            file=sys.stderr,
        )
        return 1

    for path in dump(collector, args.output):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
