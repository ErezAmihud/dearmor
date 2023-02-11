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

add_compile_definitions("DEARMOR_CODE=\"dearmor.txt\"")

include_directories(${PYTHON_INCLUDE_DIRS})
target_link_libraries(dearmor ${PYTHON_LIBRARIES})
