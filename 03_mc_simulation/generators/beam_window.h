#ifndef GRAAL_BEAM_WINDOW_H
#define GRAAL_BEAM_WINDOW_H

#include <algorithm>
#include <cmath>
#include <stdexcept>

struct BeamWindow {
    double low;
    double high;
};

inline BeamWindow ResolveBeamWindow(
    double threshold,
    double requested_min_gev,
    double requested_max_gev
) {
    const double low = std::max(
        threshold,
        requested_min_gev < 0.0 ? threshold : requested_min_gev
    );
    if (!std::isfinite(low) || !std::isfinite(requested_max_gev)
        || requested_max_gev <= low) {
        throw std::invalid_argument("beam energy window is empty or invalid");
    }
    return {low, requested_max_gev};
}

#endif
