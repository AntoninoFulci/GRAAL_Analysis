#pragma once
#include "G4Event.hh"
#include "G4PrimaryVertex.hh"
#include "G4SystemOfUnits.hh"
#include "Randomize.hh"
#include "RootOutput.hh"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

// Flat, self-contained export of the verified period NPZ. Coordinates in mm.
// XY is an observed-interaction proxy conditioned on the nominal cell radius.
// z is independent and uniform within the fitted active cell, not the observed
// acceptance-shaped longitudinal histogram.
class PeriodConditions {
public:
  explicit PeriodConditions(const std::filesystem::path& path) {
    std::ifstream input(path);
    std::string line, magic, extra;
    if (!std::getline(input, line)) throw std::runtime_error("Cannot read period conditions");
    std::istringstream header(line);
    if (!(header >> magic >> period >> material >> length >> center >> diameter >> seed)
        || (header >> extra) || magic != "GRAAL_PERIOD_V1" || period.empty()
        || period.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_") != std::string::npos
        || (material != "P" && material != "D") || !std::isfinite(length) || length <= 0
        || !std::isfinite(center) || diameter != 50 || seed <= 0 || seed > 2147483647)
      throw std::runtime_error("Invalid period conditions header");
    double total = 0;
    bool intersects = false;
    while (std::getline(input, line)) {
      Bin bin;
      double weight;
      std::istringstream row(line);
      if (!(row >> bin.x0 >> bin.x1 >> bin.y0 >> bin.y1 >> weight) || (row >> extra)
          || !std::isfinite(bin.x0) || !std::isfinite(bin.x1)
          || !std::isfinite(bin.y0) || !std::isfinite(bin.y1)
          || bin.x0 >= bin.x1 || bin.y0 >= bin.y1 || !std::isfinite(weight) || weight <= 0)
        throw std::runtime_error("Invalid period XY histogram bin");
      total += weight;
      bin.cumulative = total;
      bins.push_back(bin);
      const double x = std::max({bin.x0, -bin.x1, 0.});
      const double y = std::max({bin.y0, -bin.y1, 0.});
      intersects = intersects || x*x+y*y < diameter*diameter/4;
    }
    if (bins.empty() || !std::isfinite(total) || std::abs(total-1.) > 1.e-10 || !intersects)
      throw std::runtime_error("Period XY histogram must be normalized and intersect the target");
    for (auto& bin : bins) bin.cumulative /= total;
    bins.back().cumulative = 1.;
  }

  void SetVertices(RootTable& output) { vertices = &output; }

  void Apply(G4Event* event, int run) {
    double x = 0, y = 0;
    unsigned attempts = 0;
    do {
      if (++attempts > 100000) throw std::runtime_error("Period XY rejection limit exceeded");
      const double u = G4UniformRand();
      const auto it = std::upper_bound(bins.begin(), bins.end(), u,
          [](double value, const Bin& bin) { return value < bin.cumulative; });
      if (it == bins.end()) throw std::runtime_error("Period XY sampling failed");
      x = it->x0 + (it->x1-it->x0)*G4UniformRand();
      y = it->y0 + (it->y1-it->y0)*G4UniformRand();
    } while (x*x+y*y >= diameter*diameter/4);
    const double z = center+(G4UniformRand()-.5)*length;
    if (!event->GetPrimaryVertex()) throw std::runtime_error("No primary vertex to position");
    for (auto* vertex = event->GetPrimaryVertex(); vertex; vertex = vertex->GetNext())
      vertex->SetPosition(x*mm, y*mm, z*mm);
    if (!vertices) throw std::runtime_error("Period vertex output not initialized");
    vertices->Fill({run, event->GetEventID(), x, y, z, ULong64_t{attempts}});
  }

  std::string period, material;
  double length = 0, center = 0, diameter = 0;
  long seed = 0;
private:
  struct Bin { double x0, x1, y0, y1, cumulative; };
  std::vector<Bin> bins;
  RootTable* vertices = nullptr;
};
