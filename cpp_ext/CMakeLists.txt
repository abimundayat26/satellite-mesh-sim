cmake_minimum_required(VERSION 3.15)
project(visibility_ext)

# TODO: point this at your pybind11 install, e.g.
#   pip install pybind11
#   find_package(pybind11 REQUIRED)
# or add pybind11 as a submodule/subdirectory instead.
find_package(pybind11 REQUIRED)

pybind11_add_module(visibility_ext visibility_ext.cpp)
