#include "sdk.h"

SDK sdk;

void ExecutePython(){
    sdk.InitCPython();
    PyEval_InitThreads();
    PyGILState_STATE s = PyGILState_Ensure();
    PyRun_SimpleString("with open('"DEARMOR_CODE"', 'r') as file: data=file.read() ; exec(data)");
    PyGILState_Release(s);
    
}

DWORD WINAPI MainThread(HMODULE hModule)
{
    ExecutePython();
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