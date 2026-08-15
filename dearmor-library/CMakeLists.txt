cmake_minimum_required(VERSION 3.23)
project(dearmor)

# sdk.h declares the CPython types it needs and sdk.cpp resolves every symbol
# with GetProcAddress at runtime, so this library needs neither the python
# headers nor an import library. Not linking against a pythonXY.lib is what
# allows a single build to be injected into any of the supported interpreters.

add_compile_definitions("DEARMOR_CODE=\"dearmor.txt\"")

if (UNIX)
    set (CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../dearmor)
endif()
if(WIN32)
    set (CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}\\..\\dearmor)
endif()

add_library(dearmor
    SHARED
    sdk.h
    sdk.cpp
    main.cpp
)
