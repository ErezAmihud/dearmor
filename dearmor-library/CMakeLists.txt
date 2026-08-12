# Builds dearmor.dll, the library that gets injected into the obfuscated
# process. Use ../build_binary.bat, which configures and builds in Release.
#
# The output goes straight into the python package directory so that the wheel
# picks it up (see package_data in ../setup.py).

cmake_minimum_required(VERSION 3.23)
project(dearmor)

find_package(PythonLibs REQUIRED)

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

# Name of the payload file the DLL reads from the working directory of the
# target process. Must match PAYLOAD_FILE_NAME in ../dearmor/__main__.py.
add_compile_definitions("DEARMOR_CODE=\"dearmor.txt\"")

include_directories(${PYTHON_INCLUDE_DIRS})
target_link_libraries(dearmor ${PYTHON_LIBRARIES})
