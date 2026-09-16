cmake_minimum_required(VERSION 3.15)
project(visibility_ext)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 REQUIRED)

# Land the built module at the repo root, which is already on pytest's
# pythonpath, so `import visibility_ext` works with no sys.path changes.
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/..)

pybind11_add_module(visibility_ext visibility_ext.cpp)
