#include "sdk.h"

Py_SetProgramName_t Py_SetProgramName;
PyEval_InitThreads_t PyEval_InitThreads;
PyGILState_Ensure_t PyGILState_Ensure;
PyGILState_Release_t PyGILState_Release;
PyRun_SimpleStringFlags_t PyRun_SimpleStringFlags;

/* Interpreter DLLs we know how to talk to, newest first. The list matches the
 * Python versions dearmor is tested against.
 * TODO add more types of python */
static const char* const PYTHON_MODULE_NAMES[] = {
    "Python39.dll",
    "Python38.dll",
    "Python37.dll",
    "Python36.dll",
};

/* Return the handle of whichever supported interpreter is already loaded into
 * this process, or NULL when none of them is. */
static HMODULE FindLoadedPythonModule()
{
    for (const char* moduleName : PYTHON_MODULE_NAMES)
    {
        HMODULE pythonModule = GetModuleHandleA(moduleName);
        if (pythonModule)
            return pythonModule;
    }
    return NULL;
}

void PythonRuntime::Load()
{
    HMODULE pythonModule = FindLoadedPythonModule();

    Py_SetProgramName = (Py_SetProgramName_t)(GetProcAddress(pythonModule, "Py_SetProgramName"));
    PyEval_InitThreads = (PyEval_InitThreads_t)(GetProcAddress(pythonModule, "PyEval_InitThreads"));
    PyGILState_Ensure = (PyGILState_Ensure_t)(GetProcAddress(pythonModule, "PyGILState_Ensure"));
    PyGILState_Release = (PyGILState_Release_t)(GetProcAddress(pythonModule, "PyGILState_Release"));
    PyRun_SimpleStringFlags = (PyRun_SimpleStringFlags_t)(GetProcAddress(pythonModule, "PyRun_SimpleStringFlags"));
}
