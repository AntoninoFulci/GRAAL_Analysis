#ifndef GRAAL_LEGACY_DIGITIZATION_HH
#define GRAAL_LEGACY_DIGITIZATION_HH

// Isolated GRAAL_09 BGOD/DEDX/ATDEDX arithmetic. All REAL operations are
// deliberately rounded to binary32. Transport input and output storage may be
// double precision; the caller owns unit conversion and diagnostic provenance.
// Compile without fast-math. This models neither the trigger nor electronics.
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace legacy09 {
static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559 &&
              std::numeric_limits<float>::digits == 24, "legacy09 requires IEEE binary32 REAL");
static_assert(sizeof(int) == 4, "legacy09 requires 32-bit INTEGER");
struct Config {
  float scbgo{}, vscbgo_GeV{}, thres_GeV{};
  float scdeb{}, vscdeb_GeV{}, debdis{}, dthres_GeV{};
  float zc3_cm{}, sdetof{}, vdetof_s{}, ddetof_s{}, dlight_cm_s{};
  bool dedxat{};
  std::array<std::array<float, 4>, 32> attenuation{};
};
struct BgoDeposit { int channel; float energy_GeV; };
struct BgoDigit { int channel; int adc; };
struct BgoResult {
  std::vector<BgoDigit> digits;
  float raw_total_GeV{};
  int total_adc{}, soft_total_adc{};
};
struct BarrelHit { int channel; float energy_GeV, z_cm, time_s; };
struct BarrelDigit { int channel, adc, tdc; float energy_GeV, time_s; };
struct BarrelResult {
  std::vector<BarrelDigit> digits;
  std::size_t energy_draws{}, time_draws{};
};
struct BarrelGrouping {
  std::vector<BarrelHit> records;
  // Indices refer to the caller's ordered barrel-step vector. Anchors do not
  // move; means are unweighted; each record retains its first step's time.
  std::vector<std::vector<std::size_t>> source_indices;
};

namespace detail {
inline float Finite(float x) {
  if (!std::isfinite(x)) throw std::invalid_argument("nonfinite legacy09 value/intermediate");
  return x;
}
// Separate volatile stores also prevent contraction/reassociation at ordinary
// optimization levels and excess intermediate precision on older targets.
inline float Add(float a, float b) { volatile float r = a + b; return Finite(r); }
inline float Mul(float a, float b) { volatile float r = a * b; return Finite(r); }
inline float Div(float a, float b) { volatile float r = a / b; return Finite(r); }
inline float Exp(float x) { volatile float r = std::exp(x); return Finite(r); }
inline void Nonnegative(float x) {
  if (Finite(x) < 0) throw std::invalid_argument("negative legacy09 magnitude");
}
inline void Positive(float x) {
  if (!(Finite(x) > 0)) throw std::invalid_argument("nonpositive legacy09 divisor/scale");
}
inline int Scale(float x) {
  Positive(x);
  if (static_cast<double>(x) > std::numeric_limits<int>::max() || std::trunc(x) != x)
    throw std::invalid_argument("legacy09 full scale must be an integral int");
  return static_cast<int>(x);
}
// Fortran INT truncates, rather than floors. Values outside the defined
// Fortran INTEGER domain use a documented safe saturation boundary.
inline int Truncate(float x) {
  Finite(x);
  if (static_cast<double>(x) >= std::numeric_limits<int>::max()) return std::numeric_limits<int>::max();
  if (static_cast<double>(x) <= std::numeric_limits<int>::min()) return std::numeric_limits<int>::min();
  return static_cast<int>(x);
}
inline int Adc(float energy, float scale, float range) {
  return Truncate(Add(Div(Mul(energy, scale), range), 0.5f));
}
inline float AttenuationReference(const std::array<float, 4>& a, float zc3) {
  return Add(Mul(a[0], Exp(Mul(a[1], zc3))), Mul(a[2], Exp(Mul(a[3], zc3))));
}
inline void BarrelInput(const BarrelHit& h) {
  if (h.channel < 1 || h.channel > 32) throw std::invalid_argument("barrel channel outside 1..32");
  Nonnegative(h.energy_GeV); Finite(h.z_cm); Finite(h.time_s);
}
}  // namespace detail

inline void ValidateConfig(const Config& c) {
  detail::Scale(c.scbgo); detail::Scale(c.scdeb); detail::Scale(c.sdetof);
  detail::Positive(c.vscbgo_GeV); detail::Positive(c.vscdeb_GeV);
  detail::Positive(c.zc3_cm); detail::Positive(c.vdetof_s); detail::Positive(c.dlight_cm_s);
  detail::Nonnegative(c.thres_GeV); detail::Nonnegative(c.debdis);
  detail::Nonnegative(c.dthres_GeV); detail::Nonnegative(c.ddetof_s);
  for (const auto& a : c.attenuation) {
    for (float x : a) detail::Finite(x);
    if (c.dedxat) detail::Positive(detail::AttenuationReference(a, c.zc3_cm));
  }
}

inline float Attenuation(int channel, float z_cm, const Config& c) {
  if (channel < 1 || channel > 32) throw std::invalid_argument("barrel channel outside 1..32");
  detail::Finite(z_cm);
  if (!c.dedxat) return 1.0f;
  const auto& a = c.attenuation[static_cast<std::size_t>(channel - 1)];
  const float x = detail::Mul(-1.0f, z_cm);
  const float numerator = detail::Add(detail::Mul(a[0], detail::Exp(detail::Mul(a[1], x))),
                                       detail::Mul(a[2], detail::Exp(detail::Mul(a[3], x))));
  return detail::Div(numerator, detail::AttenuationReference(a, c.zc3_cm));
}

inline BgoResult DigitizeBgo(const std::vector<BgoDeposit>& deposits, const Config& c) {
  ValidateConfig(c);
  BgoResult result;
  const int scale = detail::Scale(c.scbgo);
  const int threshold = detail::Truncate(detail::Mul(detail::Div(c.scbgo, c.vscbgo_GeV), c.thres_GeV));
  std::int64_t soft = 0;
  int previous = 0;
  for (const auto& h : deposits) {
    if (h.channel <= previous || h.channel > 480) throw std::invalid_argument("BGO requires unique ascending channels 1..480");
    previous = h.channel;
    detail::Nonnegative(h.energy_GeV);
    result.raw_total_GeV = detail::Add(result.raw_total_GeV, h.energy_GeV);
    const int adc = detail::Adc(h.energy_GeV, c.scbgo, c.vscbgo_GeV);
    if (adc <= threshold) continue;
    const int saturated = adc > scale ? scale : adc;
    result.digits.push_back({h.channel, saturated});
    soft += saturated;
  }
  const int total = detail::Adc(result.raw_total_GeV, c.scbgo, c.vscbgo_GeV);
  result.total_adc = total > scale ? scale : total;
  result.soft_total_adc = soft > scale ? scale : static_cast<int>(soft);
  return result;
}

// The caller injects standard normal float draws. Energy draws precede all
// time draws. Rejected late records draw nothing; surviving bars draw once.
template <class Gaussian>
BarrelResult DigitizeBarrel(const std::vector<BarrelHit>& records, const Config& c, Gaussian&& gaussian) {
  ValidateConfig(c);
  if (records.size() > 100) throw std::invalid_argument("legacy barrel compact-record overflow (>100)");
  // Validate the whole event before consuming any caller RNG state.
  for (const auto& h : records) detail::BarrelInput(h);
  BarrelResult result;
  std::array<float, 32> energy{}, time{};
  std::array<bool, 32> seen{};
  std::vector<int> order;
  for (const auto& h : records) {
    if (h.time_s > 100.0e-9f) continue;
    const auto i = static_cast<std::size_t>(h.channel - 1);
    const float attenuated = detail::Mul(h.energy_GeV, Attenuation(h.channel, h.z_cm, c));
    const float g = detail::Finite(static_cast<float>(gaussian()));
    ++result.energy_draws;
    const float contribution = detail::Mul(attenuated, detail::Add(1.0f, detail::Mul(g, c.debdis)));
    energy[i] = detail::Add(energy[i], contribution);
    const float arrival = detail::Add(h.time_s, detail::Div(detail::Add(c.zc3_cm, h.z_cm), c.dlight_cm_s));
    if (seen[i]) { if (arrival < time[i]) time[i] = arrival; }
    else { seen[i] = true; order.push_back(h.channel); time[i] = arrival; }
  }
  const int adc_scale = detail::Scale(c.scdeb), tdc_scale = detail::Scale(c.sdetof);
  for (int channel : order) {
    const auto i = static_cast<std::size_t>(channel - 1);
    if (energy[i] < c.dthres_GeV) continue;
    int adc = detail::Adc(energy[i], c.scdeb, c.vscdeb_GeV);
    if (adc > adc_scale) adc = adc_scale;
    const float g = detail::Finite(static_cast<float>(gaussian()));
    ++result.time_draws;
    const float final_time = detail::Add(time[i], detail::Mul(c.ddetof_s, g));
    int tdc = final_time < 0 ? 0 : detail::Adc(final_time, c.sdetof, c.vdetof_s);
    if (tdc > tdc_scale) tdc = tdc_scale;
    result.digits.push_back({channel, adc, tdc, energy[i], final_time});
  }
  return result;
}

inline BarrelGrouping GroupBarrelSteps(const std::vector<BarrelHit>& steps) {
  BarrelGrouping result;
  std::vector<float> anchors, z_sums;
  for (std::size_t i = 0; i < steps.size(); ++i) {
    const auto& h = steps[i];
    detail::BarrelInput(h);
    if (!(h.energy_GeV > 0)) throw std::invalid_argument("grouping requires strictly positive barrel steps");
    if (!result.records.empty() && result.records.back().channel == h.channel &&
        std::abs(detail::Add(anchors.back(), -h.z_cm)) < 1.0f) {
      result.records.back().energy_GeV = detail::Add(result.records.back().energy_GeV, h.energy_GeV);
      z_sums.back() = detail::Add(z_sums.back(), h.z_cm);
      result.source_indices.back().push_back(i);
    } else {
      result.records.push_back(h);
      anchors.push_back(h.z_cm); z_sums.push_back(h.z_cm);
      result.source_indices.push_back({i});
    }
  }
  for (std::size_t i = 0; i < result.records.size(); ++i) {
    result.records[i].z_cm = detail::Div(z_sums[i], static_cast<float>(result.source_indices[i].size()));
    if (result.records[i].time_s > 1.0e-6f) result.records[i].time_s = 1.0e-6f;
  }
  return result;
}
}  // namespace legacy09
#endif
