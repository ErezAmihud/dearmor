cmake_minimum_required(VERSION 3.23)
project(dearmor)

find_package(PythonLibs REQUIRED)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_BINARY_DIR}/lib)

add_library(dearmor
    SHARED
    sdk.h
    sdk.cpp
    main.cpp
)

add_compile_definitions("DEARMOR_CODE=\"dearmor.txt\"")

include_directories(${PYTHON_INCLUDE_DIRS})
target_link_libraries(dearmor ${PYTHON_LIBRARIES})
