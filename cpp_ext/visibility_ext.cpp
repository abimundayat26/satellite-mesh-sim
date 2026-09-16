// Phase 3: C++ port of the link/visibility hot path. See SPEC.md §5.2, §5.3.
//
// Mirrors the exact floating-point operation order of link.visibility.link_graph()
// (the numpy-vectorized reference) so that parity holds at rtol=1e-12
// (tests/test_cpp_parity.py).

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <cmath>
#include <limits>

namespace py = pybind11;

namespace {
constexpr double PI = 3.14159265358979323846;
}

py::array_t<double> link_distances(
    py::array_t<double, py::array::c_style | py::array::forcecast> positions,
    int num_sats,
    double max_isl_range_km,
    double min_elevation_deg,
    double earth_radius_km)
{
    py::buffer_info buf = positions.request();
    if (buf.ndim != 2 || buf.shape[1] != 3) {
        throw py::value_error("positions must have shape (V, 3)");
    }
    const py::ssize_t v = buf.shape[0];
    if (num_sats < 0 || num_sats > v) {
        throw py::value_error("num_sats must satisfy 0 <= num_sats <= V");
    }

    const double* pos = static_cast<const double*>(buf.ptr);
    const double inf = std::numeric_limits<double>::infinity();

    py::array_t<double> result({v, v});
    double* out = static_cast<double*>(result.request().ptr);

    for (py::ssize_t i = 0; i < v; ++i) {
        out[i * v + i] = inf;
    }

    for (py::ssize_t i = 0; i < v; ++i) {
        const double ix = pos[i * 3 + 0];
        const double iy = pos[i * 3 + 1];
        const double iz = pos[i * 3 + 2];
        const bool i_is_sat = i < num_sats;

        for (py::ssize_t j = i + 1; j < v; ++j) {
            const bool j_is_sat = j < num_sats;
            double link_dist = inf;

            if (i_is_sat || j_is_sat) {
                const double jx = pos[j * 3 + 0];
                const double jy = pos[j * 3 + 1];
                const double jz = pos[j * 3 + 2];

                // diff = pos[j] - pos[i]
                const double dx = jx - ix;
                const double dy = jy - iy;
                const double dz = jz - iz;
                const double dist = std::sqrt(dx * dx + dy * dy + dz * dz);

                if (i_is_sat && j_is_sat) {
                    const double a_dot_d = ix * dx + iy * dy + iz * dz;
                    const double d_sq = dx * dx + dy * dy + dz * dz;
                    double s = 0.0;
                    if (d_sq > 0.0) {
                        s = -a_dot_d / d_sq;
                        if (s < 0.0) s = 0.0;
                        if (s > 1.0) s = 1.0;
                    }
                    const double cx = ix + s * dx;
                    const double cy = iy + s * dy;
                    const double cz = iz + s * dz;
                    const double closest_norm = std::sqrt(cx * cx + cy * cy + cz * cz);
                    const bool los_ok = closest_norm >= earth_radius_km;

                    if (dist <= max_isl_range_km && los_ok) {
                        link_dist = dist;
                    }
                } else {
                    // sat-ground: elevation is always computed from the ground station's view.
                    const bool i_is_ground = !i_is_sat;
                    const double gx = i_is_ground ? ix : jx;
                    const double gy = i_is_ground ? iy : jy;
                    const double gz = i_is_ground ? iz : jz;
                    // v = sat - ground = diff[ground][sat]
                    const double vx = i_is_ground ? dx : -dx;
                    const double vy = i_is_ground ? dy : -dy;
                    const double vz = i_is_ground ? dz : -dz;

                    const double g_norm = std::sqrt(gx * gx + gy * gy + gz * gz);
                    const double ghx = gx / g_norm;
                    const double ghy = gy / g_norm;
                    const double ghz = gz / g_norm;

                    const double denom = dist > 0.0 ? dist : 1.0;
                    double sin_el = (ghx * vx + ghy * vy + ghz * vz) / denom;
                    if (sin_el < -1.0) sin_el = -1.0;
                    if (sin_el > 1.0) sin_el = 1.0;
                    const double elevation_deg = std::asin(sin_el) * (180.0 / PI);

                    if (elevation_deg >= min_elevation_deg) {
                        link_dist = dist;
                    }
                }
            }
            // ground-ground pairs stay inf.

            out[i * v + j] = link_dist;
            out[j * v + i] = link_dist;
        }
    }

    return result;
}

PYBIND11_MODULE(visibility_ext, m) {
    m.doc() = "C++ hot-path implementation of the link-graph distance computation";
    m.def("link_distances", &link_distances,
          py::arg("positions"), py::arg("num_sats"),
          py::arg("max_isl_range_km"), py::arg("min_elevation_deg"),
          py::arg("earth_radius_km"),
          "Compute the (V,V) symmetric link-distance matrix (inf = no link).");
}
