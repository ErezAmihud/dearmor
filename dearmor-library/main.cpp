/*
 * Entry point of dearmor.dll, the library injected into the obfuscated process.
 *
 * Its only job is to run the dearmor payload inside the interpreter that is
 * already running in the target: it resolves the CPython API from the loaded
 * interpreter DLL, takes the GIL and executes the payload file (dearmor.txt,
 * a copy of dearmor/code.py, see DEARMOR_CODE in CMakeLists.txt) in the target's
 * __main__ namespace. Everything else happens in Python from there on.
 */

#include "sdk.h"

PythonRuntime pythonRuntime;

/* Read the payload file and execute it in the target interpreter. */
void RunDearmorPayload(){
    pythonRuntime.Load();
    PyEval_InitThreads();

    /* The target's threads are running, so the GIL has to be acquired before
     * touching the interpreter. */
    PyGILState_STATE gilState = PyGILState_Ensure();
    PyRun_SimpleString("with open('"DEARMOR_CODE"', 'r') as file: data=file.read() ; exec(data)");
    PyGILState_Release(gilState);

}

/* Runs on a dedicated thread so DllMain returns immediately and the loader lock
 * is not held while Python code executes. */
DWORD WINAPI MainThread(HMODULE hModule)
{
    RunDearmorPayload();
    /* The payload has already dumped everything; unload ourselves so the target
     * can carry on (and exit) as usual. */
    FreeLibraryAndExitThread(hModule, 0);
    CloseHandle(hModule);
}


BOOL APIENTRY DllMain( HMODULE hModule,
                       DWORD  ul_reason_for_call,
                       LPVOID lpReserved
                     )
{
    switch (ul_reason_for_call)
    {
    case DLL_PROCESS_ATTACH:
                CloseHandle(CreateThread(0, 0, (LPTHREAD_START_ROUTINE)MainThread, hModule, 0, 0));
    case DLL_THREAD_ATTACH:
    case DLL_THREAD_DETACH:
    case DLL_PROCESS_DETACH:
        break;
    }
    return TRUE;
}
