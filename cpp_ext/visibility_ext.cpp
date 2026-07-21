// Phase 3: C++ port of the link/visibility hot path.
//
// Goal: identical output to link.visibility.link_graph() given the same
// input positions array. Prove correctness with a parity test
// (tests/test_cpp_parity.py) before you touch the benchmark.
//
// TODO:
//   - accept a numpy array of positions (pybind11::array_t<double>)
//   - implement the same line-of-sight + range checks as visibility.py
//   - return an adjacency structure numpy can consume back in Python

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <stdexcept>

namespace py = pybind11;

// TODO: implement
py::array_t<bool> link_graph(py::array_t<double> positions,
                              double max_range_km,
                              double earth_radius_km) {
    throw std::runtime_error("not implemented yet");
}

PYBIND11_MODULE(visibility_ext, m) {
    m.doc() = "C++ hot-path port of the link/visibility computation";
    m.def("link_graph", &link_graph, "Compute link adjacency for one timestep");
}
