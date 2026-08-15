"""Deobfuscation backend for PyArmor 8 and 9.

PyArmor 8 dropped every hook name the old backend (:mod:`dearmor.code`) relied
on.  A quick summary of what changed:

===========================  ==================================================
PyArmor 5/6/7                PyArmor 8/9
===========================  ==================================================
``pytransform`` module       ``pyarmor_runtime_00xxxx`` package
``pyarmor_runtime()``        ``__pyarmor__(__name__, __file__, b'PY0000...')``
``__armor_enter__`` global   ``C_ENTER_CO_OBJECT_INDEX`` builtin in ``co_consts``
``__armor_exit__`` global    ``C_LEAVE_CO_OBJECT_INDEX`` builtin in ``co_consts``
``__armor__`` global         ``C_ASSERT_ARMORED_INDEX`` builtin in ``co_consts``
===========================  ==================================================

The important part is not just that the names changed, but *how* they are
referenced.  PyArmor 7 emitted ``LOAD_GLOBAL __armor_enter__``, so the old
backend could inject a module that simply defined a global with that name and
wait to be called back.  PyArmor 8 stores the runtime's C functions directly in
``co_consts`` and emits ``LOAD_CONST``, so there is no name left to shadow.

What did *not* change is the protection scheme itself: a function's real
bytecode is only present in the code object while the function is running.  The
prologue calls ``C_ENTER_CO_OBJECT_INDEX`` which decrypts the body in place, and
the epilogue calls ``C_LEAVE_CO_OBJECT_INDEX`` which wipes it again.  So the
recovery strategy is the same as before -- observe the code object between those
two calls -- only the way we get in position differs.  Instead of injecting a
DLL we install a trace function, which makes this backend pure Python and
platform independent.
"""

import dis
import opcode
import sys
import types

#: Names of the runtime helpers PyArmor 8/9 embeds in ``co_consts``.
ENTER_NAME = "C_ENTER_CO_OBJECT_INDEX"
LEAVE_NAME = "C_LEAVE_CO_OBJECT_INDEX"
ASSERT_NAME = "C_ASSERT_ARMORED_INDEX"
RUNTIME_NAMES = frozenset((ENTER_NAME, LEAVE_NAME, ASSERT_NAME))

#: Local PyArmor binds ``C_ASSERT_ARMORED_INDEX`` to, always last in
#: ``co_varnames``.
ASSERT_LOCAL = "__assert_armored__"

NOP = opcode.opmap["NOP"]
LOAD_CONST = opcode.opmap["LOAD_CONST"]
POP_TOP = opcode.opmap["POP_TOP"]
EXTENDED_ARG = opcode.opmap["EXTENDED_ARG"]

# When to read a frame's bytecode, which is a different answer per version.
#
# From 3.11 on the ``call`` trace event is raised by the ``RESUME`` instruction,
# which PyArmor places *after* its enter call, so the body is already decrypted
# by the time we are handed the frame.  That is the only chance we get: from
# 3.11 on ``co_code`` is rebuilt from the quickened instruction array on first
# access and then cached forever, so one early read would hide the decrypted
# body for good.
#
# Up to 3.10 the event fires on frame creation instead, before the enter call
# has run -- but there ``co_code`` is a plain attribute that always reflects the
# current state, so we can simply wait for an opcode event past the prologue.
CALL_EVENT_IS_POST_ENTER = sys.version_info >= (3, 11)


class NotArmored(Exception):
    """Raised when asked to strip a code object that PyArmor did not touch."""


def _is_runtime_helper(const):
    return getattr(const, "__name__", None) in RUNTIME_NAMES


def runtime_const_indices(co):
    """Return the ``co_consts`` indices holding PyArmor runtime helpers."""
    return {i for i, c in enumerate(co.co_consts) if _is_runtime_helper(c)}


def is_armored(co):
    """Whether *co* is a PyArmor 8/9 protected code object."""
    return any(_is_runtime_helper(c) for c in co.co_consts)


def iter_code_consts(co):
    for const in co.co_consts:
        if isinstance(const, types.CodeType):
            yield const


def module_name_of(co):
    """Recover a module name from the ``<frozen name>`` filename PyArmor uses."""
    filename = co.co_filename or ""
    if filename.startswith("<frozen ") and filename.endswith(">"):
        return filename[len("<frozen ") : -1]
    return None


# --------------------------------------------------------------------------- #
# exception table (3.11+)
# --------------------------------------------------------------------------- #

HAS_EXCEPTION_TABLE = sys.version_info >= (3, 11)


def _parse_varint(it):
    b = next(it)
    val = b & 63
    while b & 64:
        val <<= 6
        b = next(it)
        val |= b & 63
    return val


def _write_varint(val, out):
    chunks = []
    while val:
        chunks.append(val & 63)
        val >>= 6
    if not chunks:
        chunks.append(0)
    chunks.reverse()
    for chunk in chunks[:-1]:
        out.append(chunk | 64)
    out.append(chunks[-1])


def parse_exception_table(table):
    """Decode ``co_exceptiontable`` into ``(start, end, target, depth, lasti)``."""
    entries = []
    it = iter(table)
    while True:
        try:
            start = _parse_varint(it) * 2
        except StopIteration:
            return entries
        length = _parse_varint(it) * 2
        target = _parse_varint(it) * 2
        depth_lasti = _parse_varint(it)
        entries.append(
            (start, start + length, target, depth_lasti >> 1, bool(depth_lasti & 1))
        )


def assemble_exception_table(entries):
    out = bytearray()
    for start, end, target, depth, lasti in entries:
        first = len(out)
        _write_varint(start // 2, out)
        out[first] |= 0x80
        _write_varint((end - start) // 2, out)
        _write_varint(target // 2, out)
        _write_varint((depth << 1) | bool(lasti), out)
    return bytes(out)


# --------------------------------------------------------------------------- #
# bytecode surgery
# --------------------------------------------------------------------------- #


def _instructions(co, code):
    """Disassemble *code* using *co* for its name/const tables."""
    return list(dis.get_instructions(co.replace(co_code=code)))


def _nop_out(buf, start, end):
    for offset in range(start, end, 2):
        buf[offset] = NOP
        buf[offset + 1] = 0


def _runtime_call_regions(insns, runtime_indices):
    """Find the byte ranges occupied by PyArmor's enter/leave/assert calls.

    Every one of them starts at a ``LOAD_CONST`` of a runtime helper and ends at
    the instruction that consumes the call's result -- a ``POP_TOP`` for the
    enter and leave calls, a store for the ``__assert_armored__`` binding 3.13
    keeps around.  A ``PUSH_NULL`` may sit on either side of the ``LOAD_CONST``
    depending on the version, so it is picked up by looking one instruction back
    and by the forward scan.
    """
    regions = []
    i = 0
    while i < len(insns):
        ins = insns[i]
        if ins.opname == "LOAD_CONST" and ins.arg in runtime_indices:
            start = _start_of_runtime_call(insns, i)
            end = _end_of_runtime_call(insns, i)
            if end is None:  # not a shape we know; better to leave it alone
                i += 1
                continue
            regions.append((start, end))
        i += 1
    return regions


#: What a runtime call's result gets consumed by, once it returns.
_CONSUMERS = (
    "POP_TOP",
    "STORE_FAST",
    "STORE_NAME",
    "STORE_GLOBAL",
    "STORE_DEREF",
)

#: A runtime call is a handful of instructions; refuse to swallow more than
#: that, so a misread never eats the script's own code.
_MAX_RUNTIME_CALL_LENGTH = 12


def _start_of_runtime_call(insns, index):
    """Where PyArmor's call really begins, padding included.

    It emits ``NOP``s around its own instructions -- with junk in the argument
    byte, so they stand out from anything the compiler produces -- and on some
    versions loads the callable after a ``PUSH_NULL`` rather than before it.
    Neither carries meaning, so both get swallowed.
    """
    while index and insns[index - 1].opname in ("NOP", "PUSH_NULL"):
        index -= 1
    return insns[index].offset


def _end_of_runtime_call(insns, start_index):
    stop = min(start_index + _MAX_RUNTIME_CALL_LENGTH, len(insns))
    for ins in insns[start_index + 1 : stop]:
        if ins.opname in _CONSUMERS:
            return ins.offset + 2
    return None


def _prologue_jump(insns, enter_end):
    """The ``JUMP_FORWARD`` 3.11 puts between the enter call and the real body.

    Returns the ``(start, end)`` range covering the jump plus the dead block it
    jumps over, or ``None`` when the version does not emit one.
    """
    for ins in insns:
        if ins.offset < enter_end:
            continue
        if ins.opname == "RESUME":
            continue
        if ins.opname == "JUMP_FORWARD" and ins.argval > ins.offset:
            return ins.offset, ins.argval
        return None
    return None


def _handler_extent(insns, target):
    """Byte range of the exception handler block starting at *target*.

    A handler runs until it either re-raises or returns, so stopping at the
    first ``RERAISE``/``RETURN_*`` after *target* covers exactly one block.
    """
    end = target
    for ins in insns:
        if ins.offset < target:
            continue
        end = ins.offset + 2
        if ins.opname == "RERAISE" or ins.opname.startswith("RETURN_"):
            break
    return target, end


def _drop_armor_handlers(insns, entries, regions):
    """Split *entries* into the script's own handlers and PyArmor's.

    PyArmor wraps every protected body in a ``try``/``finally`` whose only job is
    to call the leave helper.  Now that the leave calls are gone those handlers
    are dead weight, so they are removed from the table and blanked out too.
    Removing one can expose the cleanup handler behind it, hence the fixed point.
    """
    kept = list(entries)
    regions = list(regions)
    while True:
        for entry in kept:
            protected = (entry[0], entry[1])
            handler = _handler_extent(insns, entry[2])
            # The handler calls the leave helper, so the whole ``finally`` is
            # PyArmor's; or what it protects is a block we already blanked out,
            # which happens once the handler above it has been removed.
            dead = _is_dead_block(insns, protected, regions)
            if not (dead or _overlaps(handler, regions)):
                continue
            kept.remove(entry)
            regions.append(handler)
            if dead:
                regions.append(protected)
            break
        else:
            return kept, regions


def _overlaps(span, regions):
    return any(span[0] <= start < span[1] for start, _ in regions)


def _is_dead_block(insns, span, regions):
    """Whether *span* holds nothing but PyArmor's own exception plumbing.

    Anything that is not already blanked out has to be the ``PUSH_EXC_INFO`` and
    ``RERAISE`` that bracket a stripped leave call; a single real instruction is
    enough to disqualify the block, which keeps the script's own ``try``
    statements out of this.
    """
    saw_stripped = False
    for ins in insns:
        if not span[0] <= ins.offset < span[1]:
            continue
        if any(start <= ins.offset < end for start, end in regions):
            saw_stripped = True
        elif ins.opname not in ("PUSH_EXC_INFO", "RERAISE", "NOP", "CACHE"):
            return False
    return saw_stripped


def strip_armor(co, code=None):
    """Rebuild *co* with PyArmor's prologue and epilogue removed.

    *code* is the decrypted ``co_code`` snapshot taken while the code object was
    running; it defaults to ``co.co_code``, which is only correct if the object
    was already captured.  Instruction offsets are preserved -- PyArmor's
    instructions are overwritten with ``NOP`` rather than cut out -- so jump
    targets, the line table and the script's own exception handlers all stay
    valid.
    """
    if code is None:
        code = co.co_code
    runtime_indices = runtime_const_indices(co)
    if not runtime_indices:
        raise NotArmored(co.co_name)

    insns = _instructions(co, code)
    regions = _runtime_call_regions(insns, runtime_indices)
    if not regions:
        raise NotArmored(co.co_name)

    jump = _prologue_jump(insns, regions[0][1])
    if jump is not None:
        regions.append(jump)

    replacements = {}
    if HAS_EXCEPTION_TABLE:
        kept, regions = _drop_armor_handlers(
            insns, parse_exception_table(co.co_exceptiontable), regions
        )
        replacements["co_exceptiontable"] = assemble_exception_table(kept)

    buf = bytearray(code)
    for start, end in regions:
        _nop_out(buf, start, end)

    replacements["co_code"] = bytes(buf)
    replacements["co_consts"] = tuple(
        None if i in runtime_indices else c for i, c in enumerate(co.co_consts)
    )
    replacements.update(_drop_assert_local(co))
    return co.replace(**replacements)


def _drop_assert_local(co):
    """Remove the unused ``__assert_armored__`` local, when that is safe.

    PyArmor appends it to ``co_varnames``, so dropping it never renumbers a real
    local.  From 3.11 on, though, cells and free variables are indexed after the
    plain locals in one shared table, and shortening that table would renumber
    them -- so in that case the (now unassigned) local is left alone rather than
    risk rewriting every ``LOAD_DEREF``.
    """
    if not co.co_varnames or co.co_varnames[-1] != ASSERT_LOCAL:
        return {}
    if HAS_EXCEPTION_TABLE and (co.co_cellvars or co.co_freevars):
        return {}
    return {"co_varnames": co.co_varnames[:-1], "co_nlocals": co.co_nlocals - 1}


# --------------------------------------------------------------------------- #
# capturing decrypted code objects
# --------------------------------------------------------------------------- #


def _snapshot(code):
    """Copy the bytecode *out* of a live code object.

    Up to 3.10 ``co_code`` hands back the very buffer PyArmor decrypts into and
    wipes again on the way out, and ``bytes(b)`` on a ``bytes`` object returns
    that same object rather than a copy -- so the detour through ``bytearray``
    is what makes this a snapshot instead of a view.
    """
    return bytes(bytearray(code.co_code))


class _Abort(BaseException):
    """Unwinds a frame once we have its decrypted body.

    It derives from :class:`BaseException` so that ``except Exception`` inside
    the obfuscated script cannot swallow it.
    """


class Collector:
    """Snapshots armored code objects while they are decrypted.

    Install it with :meth:`install`, run the obfuscated script, and read the
    recovered code objects off :attr:`captured`.
    """

    def __init__(self):
        self.captured = {}  # id(code) -> (code object, decrypted co_code)
        self._body_offsets = {}  # id(code) -> offset just past the enter call
        self._abort_after_capture = False
        self._previous = None

    # -- installation ------------------------------------------------------ #

    def install(self):
        self._previous = sys.gettrace()
        sys.settrace(self.trace)

    def uninstall(self):
        sys.settrace(self._previous)
        self._previous = None

    def __enter__(self):
        self.install()
        return self

    def __exit__(self, *exc_info):
        self.uninstall()
        return False

    # -- the trace function ------------------------------------------------ #

    def trace(self, frame, event, arg):
        code = frame.f_code
        if event == "call":
            if not is_armored(code):
                return None  # nothing here or below is worth tracing
            if CALL_EVENT_IS_POST_ENTER:
                self._capture(code, frame)
            else:
                frame.f_trace_opcodes = True
                self._body_offsets.setdefault(id(code), self._body_offset(code))
            return self.trace
        if event == "opcode" and frame.f_lasti >= self._body_offsets.get(id(code), -1):
            self._capture(code, frame)
        return self.trace

    def _capture(self, code, frame):
        if id(code) not in self.captured:
            self.captured[id(code)] = (code, _snapshot(code))
        if self._abort_after_capture:
            raise _Abort(code.co_name)

    @staticmethod
    def _body_offset(code):
        """Offset of the first instruction after PyArmor's enter call.

        Only needed on Python versions where the ``call`` trace event fires
        before the enter call has run.  Those versions have a fixed two byte
        instruction format, which is just as well: the bytecode is still
        encrypted at this point, so :mod:`dis` would choke on the garbage and
        Python would silently drop our trace function.
        """
        runtime_indices = runtime_const_indices(code)
        raw = _snapshot(code)
        seen_enter = False
        arg = 0
        for offset in range(0, len(raw), 2):
            op, arg = raw[offset], (arg << 8) | raw[offset + 1]
            if op == EXTENDED_ARG:
                continue
            if op == LOAD_CONST and arg in runtime_indices:
                seen_enter = True
            elif seen_enter and op == POP_TOP:
                return offset + 2
            arg = 0
        return 0

    # -- forcing functions that the script never calls ---------------------- #

    def force(self, code, glob=None):
        """Run *code* just far enough for PyArmor to decrypt it.

        The trace function aborts the frame as soon as the body is readable, so
        none of the obfuscated code's own statements are executed.
        """
        if id(code) in self.captured:
            return True
        self._abort_after_capture = True
        previous = sys.gettrace()
        sys.settrace(self.trace)
        try:
            _call_blindly(code, glob if glob is not None else {})
        except _Abort:
            pass
        except BaseException:
            pass  # our made up arguments were wrong; we may still have the body
        finally:
            sys.settrace(previous)
            self._abort_after_capture = False
        return id(code) in self.captured

    def force_all(self, glob=None):
        """Force every armored code object reachable from what we captured."""
        pending = [code for code, _ in list(self.captured.values())]
        seen = set()
        while pending:
            code = pending.pop()
            if id(code) in seen:
                continue
            seen.add(id(code))
            snapshot = self.captured.get(id(code))
            source = code.replace(co_code=snapshot[1]) if snapshot else code
            for nested in iter_code_consts(source):
                if is_armored(nested):
                    self.force(nested, glob)
                pending.append(nested)


def _dummy_arguments(code):
    """Positional and keyword arguments that satisfy *code*'s signature."""
    posonly = getattr(code, "co_posonlyargcount", 0)
    kwonly = code.co_kwonlyargcount
    positional = [None] * code.co_argcount
    keywords = {name: None for name in code.co_varnames[code.co_argcount :][:kwonly]}
    del posonly
    return positional, keywords


def _call_blindly(code, glob):
    closure = tuple(_new_cell() for _ in code.co_freevars) or None
    func = types.FunctionType(code, glob, code.co_name, None, closure)
    args, kwargs = _dummy_arguments(code)
    result = func(*args, **kwargs)
    # Generators and coroutines do not run any of their body until stepped.
    if hasattr(result, "__next__"):
        next(result)
    elif hasattr(result, "send"):
        result.send(None)


def _new_cell():
    if hasattr(types, "CellType"):
        return types.CellType()
    return (lambda value: (lambda: value).__closure__[0])(None)


# --------------------------------------------------------------------------- #
# putting it back together
# --------------------------------------------------------------------------- #


def rebuild(code, captured):
    """Return *code* with PyArmor stripped from it and from every nested code.

    A code object we never managed to decrypt is kept as it is, minus the
    runtime helpers in its constants -- those are C functions, and leaving even
    one of them in place makes the whole module unmarshallable.
    """
    snapshot = captured.get(id(code))
    if is_armored(code):
        if snapshot is not None:
            code = strip_armor(code, snapshot[1])
        else:
            runtime_indices = runtime_const_indices(code)
            code = code.replace(
                co_consts=tuple(
                    None if i in runtime_indices else c
                    for i, c in enumerate(code.co_consts)
                )
            )
    consts = tuple(
        rebuild(c, captured) if isinstance(c, types.CodeType) else c
        for c in code.co_consts
    )
    return code.replace(co_consts=consts)


def recovered_modules(collector):
    """Map module name -> deobfuscated module code object."""
    modules = {}
    for code, _ in collector.captured.values():
        if code.co_name != "<module>":
            continue
        name = module_name_of(code)
        if name is None:
            continue
        modules[name] = rebuild(code, collector.captured)
    return modules
