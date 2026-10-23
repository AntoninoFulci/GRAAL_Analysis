
#include <ROOT/RDataFrame.hxx>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace GraalStripEnergyRDF {

std::string IsoTimestamp()
{
    const auto now = std::chrono::system_clock::now();
    const std::time_t raw_time = std::chrono::system_clock::to_time_t(now);
    std::tm local_time{};
#if defined(_WIN32)
    localtime_s(&local_time, &raw_time);
#else
    localtime_r(&raw_time, &local_time);
#endif
    char date_buffer[32]{};
    char zone_buffer[8]{};
    std::strftime(
        date_buffer, sizeof(date_buffer), "%Y-%m-%dT%H:%M:%S", &local_time
    );
    std::strftime(zone_buffer, sizeof(zone_buffer), "%z", &local_time);
    std::string zone(zone_buffer);
    if (zone.size() == 5)
        zone.insert(3, ":");
    return std::string(date_buffer) + zone;
}

struct StripSummary {
    int run_number = 0;
    int xstrip = 0;
    std::uint64_t event_count = 0;
    double energy_median_gev = 0.0;
    double energy_mad_gev = 0.0;
    double energy_min_gev = 0.0;
    double energy_max_gev = 0.0;
};

struct BuildResult {
    std::vector<StripSummary> summaries;
    std::vector<int> extra_runs;
    std::uint64_t entries = 0;
    std::uint64_t sampled_entries = 0;
    std::uint64_t fractional_xstrip_entries = 0;
    std::uint64_t invalid_xstrip_entries = 0;
};

struct CalibrationCell {
    int run_number = 0;
    int polarization = 0;
    int xstrip = 0;
    std::uint64_t event_count = 0;
    double xstrip_mean = 0.0;
    double energy_mean_gev = 0.0;
};

struct CalibrationResult {
    std::vector<CalibrationCell> cells;
    struct EnergyBin {
        int run_number = 0;
        int polarization = 0;
        int xstrip = 0;
        int energy_bin = 0;
        std::uint64_t event_count = 0;
    };
    std::vector<EnergyBin> energy_bins;
    std::uint64_t entries = 0;
};

struct CalibrationAccumulator {
    std::uint64_t count = 0;
    double xstrip_sum = 0.0;
    double energy_sum = 0.0;
};

double ExactMedian(std::vector<double> &values)
{
    const auto size = values.size();
    if (size == 0)
        throw std::runtime_error("cannot compute median of empty values");
    const auto middle = size / 2;
    std::nth_element(values.begin(), values.begin() + middle, values.end());
    const double upper = values[middle];
    if (size % 2 != 0)
        return upper;
    const double lower = *std::max_element(values.begin(), values.begin() + middle);
    return (lower + upper) / 2.0;
}

BuildResult BuildSampledLookup(
    const std::vector<std::string> &paths,
    const std::vector<int> &requested_runs,
    std::uint64_t sample_capacity,
    std::uint64_t progress_every,
    double elapsed_before_scan
)
{
    if (requested_runs.empty())
        throw std::runtime_error("requested run list is empty");
    if (sample_capacity == 0)
        throw std::runtime_error("sample capacity must be positive");

    const auto run_indices = [&requested_runs]() {
        std::unordered_map<int, std::size_t> indices;
        indices.reserve(requested_runs.size());
        for (std::size_t index = 0; index < requested_runs.size(); ++index) {
            if (requested_runs[index] <= 0)
                throw std::runtime_error("run_number must be positive");
            if (!indices.emplace(requested_runs[index], index).second)
                throw std::runtime_error("requested run list contains duplicates");
        }
        return indices;
    }();
    const std::size_t key_count = requested_runs.size() * 128;
    if (key_count > std::numeric_limits<std::size_t>::max() / sample_capacity)
        throw std::runtime_error("sample buffer size overflow");

    ROOT::RDataFrame frame("h80", paths);
    const auto slots = frame.GetNSlots();
    std::vector<std::unordered_set<int>> extra_run_sets(slots);
    std::vector<std::uint64_t> slot_event_counts(slots * key_count, 0);
    std::vector<std::atomic<std::uint64_t>> sample_claims(key_count);
    for (auto &count : sample_claims)
        count.store(0, std::memory_order_relaxed);
    std::vector<double> sampled_energies(key_count * sample_capacity);
    std::vector<std::uint64_t> slot_processed(slots, 0);
    std::vector<std::uint64_t> slot_fractional_xstrip_entries(slots, 0);
    std::vector<std::uint64_t> slot_invalid_xstrip_entries(slots, 0);
    const std::uint64_t progress_chunk = progress_every == 0
        ? 4096
        : std::max<std::uint64_t>(
            1, std::min<std::uint64_t>(4096, progress_every / (slots * 2))
        );
    std::atomic<std::uint64_t> aggregated_progress{0};
    std::atomic<std::uint64_t> next_progress{progress_every};
    std::mutex progress_mutex;
    const auto scan_started = std::chrono::steady_clock::now();
    const auto report_progress = [&](std::uint64_t current) {
        if (progress_every == 0)
            return;
        auto next = next_progress.load(std::memory_order_relaxed);
        while (current >= next) {
            if (next_progress.compare_exchange_weak(
                    next, next + progress_every, std::memory_order_relaxed
                )) {
                const double elapsed = elapsed_before_scan +
                    std::chrono::duration<double>(
                        std::chrono::steady_clock::now() - scan_started
                    ).count();
                std::ostringstream line;
                line << "[" << IsoTimestamp() << "] [+"
                     << std::fixed << std::setprecision(1) << elapsed
                     << "s] h80 events processed: " << next;
                {
                    std::lock_guard<std::mutex> lock(progress_mutex);
                    std::cerr << line.str() << std::endl;
                }
                next += progress_every;
            }
        }
    };

    auto sampled = frame
        .Define("graal_run_number", "static_cast<int>(RunNumber)")
        .Define("graal_raw_xstrip", "static_cast<double>(Xstrip)")
        .DefineSlot(
            "graal_sample_offset",
            [&](unsigned int slot, int run_number, double xstrip) -> long long {
                const auto local_processed = ++slot_processed.at(slot);
                if (local_processed % progress_chunk == 0) {
                    const auto current = aggregated_progress.fetch_add(
                        progress_chunk, std::memory_order_relaxed
                    ) + progress_chunk;
                    report_progress(current);
                }
                if (std::isfinite(xstrip) && xstrip != std::trunc(xstrip))
                    ++slot_fractional_xstrip_entries.at(slot);

                const auto run = run_indices.find(run_number);
                if (run == run_indices.end()) {
                    extra_run_sets.at(slot).insert(run_number);
                    return -1;
                }
                if (!std::isfinite(xstrip) || xstrip < 1.0 || xstrip >= 129.0) {
                    ++slot_invalid_xstrip_entries.at(slot);
                    return -1;
                }
                const int strip = static_cast<int>(xstrip);
                const std::size_t key = run->second * 128 +
                    static_cast<std::size_t>(strip - 1);
                ++slot_event_counts[slot * key_count + key];
                if (sample_claims[key].load(std::memory_order_relaxed) >=
                    sample_capacity)
                    return -1;
                const auto ordinal = sample_claims[key].fetch_add(
                    1, std::memory_order_relaxed
                );
                if (ordinal >= sample_capacity)
                    return -1;
                return static_cast<long long>(key * sample_capacity + ordinal);
            },
            {"graal_run_number", "graal_raw_xstrip"}
        )
        .Filter("graal_sample_offset >= 0")
        .Define("graal_beam_energy", "static_cast<double>(beam.E())");

    sampled.Foreach(
        [&](long long sample_offset, double energy) {
            if (!std::isfinite(energy) || energy <= 0.0)
                throw std::runtime_error("beam energy must be finite and positive");
            sampled_energies.at(static_cast<std::size_t>(sample_offset)) = energy;
        },
        {"graal_sample_offset", "graal_beam_energy"}
    );

    BuildResult result;
    for (std::size_t slot = 0; slot < slots; ++slot) {
        result.entries += slot_processed[slot];
        result.fractional_xstrip_entries +=
            slot_fractional_xstrip_entries[slot];
        result.invalid_xstrip_entries += slot_invalid_xstrip_entries[slot];
    }
    report_progress(result.entries);
    std::unordered_set<int> unique_extra_runs;
    for (const auto &slot_runs : extra_run_sets)
        unique_extra_runs.insert(slot_runs.begin(), slot_runs.end());
    result.extra_runs.assign(unique_extra_runs.begin(), unique_extra_runs.end());
    std::sort(result.extra_runs.begin(), result.extra_runs.end());

    result.summaries.reserve(key_count);
    for (std::size_t run_index = 0; run_index < requested_runs.size(); ++run_index) {
        for (std::size_t strip_index = 0; strip_index < 128; ++strip_index) {
            const std::size_t key = run_index * 128 + strip_index;
            std::uint64_t event_count = 0;
            for (std::size_t slot = 0; slot < slots; ++slot)
                event_count += slot_event_counts[slot * key_count + key];
            if (event_count == 0)
                continue;
            const std::size_t sample_count = static_cast<std::size_t>(
                std::min<std::uint64_t>(event_count, sample_capacity)
            );
            const auto begin = sampled_energies.begin() + key * sample_capacity;
            std::vector<double> energies(begin, begin + sample_count);
            const auto limits = std::minmax_element(
                energies.begin(), energies.end()
            );
            const double minimum = *limits.first;
            const double maximum = *limits.second;
            const double center = ExactMedian(energies);
            std::vector<double> deviations;
            deviations.reserve(sample_count);
            for (const double energy : energies)
                deviations.push_back(std::abs(energy - center));

            result.sampled_entries += sample_count;
            result.summaries.push_back(StripSummary{
                requested_runs[run_index],
                static_cast<int>(strip_index + 1),
                event_count,
                center,
                ExactMedian(deviations),
                minimum,
                maximum,
            });
        }
    }
    return result;
}

CalibrationResult BuildCalibrationCells(
    const std::vector<std::string> &paths,
    const std::vector<int> &requested_runs
)
{
    if (requested_runs.empty())
        throw std::runtime_error("requested run list is empty");

    std::unordered_map<int, std::size_t> run_indices;
    run_indices.reserve(requested_runs.size());
    for (std::size_t index = 0; index < requested_runs.size(); ++index) {
        if (!run_indices.emplace(requested_runs[index], index).second)
            throw std::runtime_error("requested run list contains duplicates");
    }

    ROOT::RDataFrame frame("h80", paths);
    const auto slots = frame.GetNSlots();
    std::vector<std::unordered_map<std::size_t, CalibrationAccumulator>>
        slot_cells(slots);
    std::vector<std::unordered_map<std::size_t, std::uint64_t>>
        slot_energy_bins(slots);
    std::vector<std::uint64_t> slot_entries(slots, 0);

    auto values = frame
        .Define("graal_cal_run", "static_cast<int>(RunNumber)")
        .Define("graal_cal_pol", "static_cast<int>(Polarization)")
        .Define("graal_cal_x", "static_cast<double>(Xstrip)")
        .Define("graal_cal_e", "static_cast<double>(beam.E())");
    values.ForeachSlot(
        [&](unsigned int slot, int run_number, int polarization,
            double xstrip, double energy) {
            ++slot_entries.at(slot);
            const auto run = run_indices.find(run_number);
            if (run == run_indices.end())
                return;
            if (polarization < 0 || polarization > 2)
                throw std::runtime_error("Polarization must be 0, 1, or 2");
            if (!std::isfinite(xstrip) || xstrip < 1.0 || xstrip >= 129.0)
                return;
            if (!std::isfinite(energy) || energy <= 0.0)
                throw std::runtime_error("beam energy must be finite and positive");
            const int strip = static_cast<int>(xstrip);
            const std::size_t key =
                (run->second * 3 + static_cast<std::size_t>(polarization)) * 128
                + static_cast<std::size_t>(strip - 1);
            auto &cell = slot_cells.at(slot)[key];
            ++cell.count;
            cell.xstrip_sum += xstrip;
            cell.energy_sum += energy;

            constexpr int energy_bins = 2048;
            constexpr double energy_low = 0.5;
            constexpr double energy_high = 2.0;
            int energy_bin = 0;
            if (energy >= energy_high) {
                energy_bin = energy_bins + 1;
            } else if (energy >= energy_low) {
                energy_bin = 1 + static_cast<int>(
                    (energy - energy_low) / (energy_high - energy_low)
                    * energy_bins
                );
                energy_bin = std::min(energy_bins, energy_bin);
            }
            const std::size_t distribution_key =
                key * static_cast<std::size_t>(energy_bins + 2)
                + static_cast<std::size_t>(energy_bin);
            ++slot_energy_bins.at(slot)[distribution_key];
        },
        {"graal_cal_run", "graal_cal_pol", "graal_cal_x", "graal_cal_e"}
    );

    std::unordered_map<std::size_t, CalibrationAccumulator> merged;
    std::unordered_map<std::size_t, std::uint64_t> merged_energy_bins;
    CalibrationResult result;
    for (std::size_t slot = 0; slot < slots; ++slot) {
        result.entries += slot_entries[slot];
        for (const auto &[key, source] : slot_cells[slot]) {
            auto &target = merged[key];
            target.count += source.count;
            target.xstrip_sum += source.xstrip_sum;
            target.energy_sum += source.energy_sum;
        }
        for (const auto &[key, count] : slot_energy_bins[slot])
            merged_energy_bins[key] += count;
    }

    std::vector<std::size_t> keys;
    keys.reserve(merged.size());
    for (const auto &[key, unused] : merged)
        keys.push_back(key);
    std::sort(keys.begin(), keys.end());
    result.cells.reserve(keys.size());
    for (const auto key : keys) {
        const auto &cell = merged.at(key);
        const std::size_t strip_index = key % 128;
        const std::size_t group = key / 128;
        const int polarization = static_cast<int>(group % 3);
        const std::size_t run_index = group / 3;
        result.cells.push_back(CalibrationCell{
            requested_runs.at(run_index),
            polarization,
            static_cast<int>(strip_index + 1),
            cell.count,
            cell.xstrip_sum / static_cast<double>(cell.count),
            cell.energy_sum / static_cast<double>(cell.count),
        });
    }

    constexpr std::size_t energy_bin_count = 2050;
    keys.clear();
    keys.reserve(merged_energy_bins.size());
    for (const auto &[key, unused] : merged_energy_bins)
        keys.push_back(key);
    std::sort(keys.begin(), keys.end());
    result.energy_bins.reserve(keys.size());
    for (const auto distribution_key : keys) {
        const int energy_bin = static_cast<int>(
            distribution_key % energy_bin_count
        );
        const std::size_t key = distribution_key / energy_bin_count;
        const std::size_t strip_index = key % 128;
        const std::size_t group = key / 128;
        const int polarization = static_cast<int>(group % 3);
        const std::size_t run_index = group / 3;
        result.energy_bins.push_back(CalibrationResult::EnergyBin{
            requested_runs.at(run_index),
            polarization,
            static_cast<int>(strip_index + 1),
            energy_bin,
            merged_energy_bins.at(distribution_key),
        });
    }
    return result;
}

} // namespace GraalStripEnergyRDF
