#pragma once
#include <Windows.h>
#include <iostream>
#include <fstream>

/*
 * Minimal CPython "SDK" for the injected DLL.
 *
 * The DLL is loaded into a process that already embeds (or links against) a
 * CPython interpreter, so it must not link against python3x.lib itself: the
 * exact version is only known at runtime. Instead the handful of CPython
 * functions we need are declared here as function pointer types and resolved
 * from the already loaded interpreter DLL with GetProcAddress, see
 * PythonRuntime::Load in sdk.cpp.
 */

/* Resolves the CPython entry points used by the payload runner. */
class PythonRuntime
{
public:
	/* Locate the loaded interpreter DLL and bind every function pointer below.
	 * Must be called before any of them is used. */
	void Load();
};

/* Mirrors of the CPython declarations we rely on. They are reproduced here
 * rather than included from Python.h so that the DLL builds without matching
 * the target's interpreter version. */

typedef
enum { PyGILState_LOCKED, PyGILState_UNLOCKED }
PyGILState_STATE;

typedef struct {
	int cf_flags;  /* bitmask of CO_xxx flags relevant to future */
	int cf_feature_version;  /* minor Python version (PyCF_ONLY_AST) */
} PyCompilerFlags;

/* CPython exports the ...Flags variant only; this is the convenience macro
 * from Python.h, repeated for the same reason as the types above. */
#define PyRun_SimpleString(s) PyRun_SimpleStringFlags(s, NULL)

typedef void(__stdcall* Py_SetProgramName_t)(const wchar_t*);
typedef void(__stdcall* PyEval_InitThreads_t)();
typedef PyGILState_STATE(__stdcall* PyGILState_Ensure_t)();
typedef void(__stdcall* PyGILState_Release_t)(PyGILState_STATE);
typedef int(__stdcall* PyRun_SimpleStringFlags_t)(const char*, PyCompilerFlags*);

/* Bound by PythonRuntime::Load, null until then. */
extern Py_SetProgramName_t Py_SetProgramName;
extern PyEval_InitThreads_t PyEval_InitThreads;
extern PyGILState_Ensure_t PyGILState_Ensure;
extern PyGILState_Release_t PyGILState_Release;
extern PyRun_SimpleStringFlags_t PyRun_SimpleStringFlags;
