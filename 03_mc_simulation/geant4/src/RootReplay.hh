#pragma once
#include "RootInput.hh"
#include "nlohmann/json.hpp"
#include <set>

// Preflight the complete unsmeared truth product before Geant4 or output creation.
// This in-memory snapshot also prevents a later file mutation changing primaries.
namespace rootreplay {
using namespace rootinput;
using Json = nlohmann::json;
struct Particle { int pdg; double px, py, pz, energy, mass; };
struct Event { double energy; std::vector<Particle> primaries; };

inline ULong64_t Integer(const Json& object, const char* key) {
  const auto& value = object.at(key);
  Require(value.is_number_integer(), std::string("Expected JSON integer: ") + key);
  Require(value.is_number_unsigned() || value.get<Json::number_integer_t>() >= 0,
          std::string("Negative JSON integer: ") + key);
  return value.get<ULong64_t>();
}

class Input {
public:
  explicit Input(const fs::path& path) {
    auto file = Open(path);
    std::set<std::string> names;
    TIter next(file->GetListOfKeys());
    while (auto* key = next())
      Require(names.insert(key->GetName()).second, "Duplicate ROOT key/cycle in truth input");
    const auto text = Text(*file, "metadata");
    Require(text.size() == std::size_t(dynamic_cast<TObjString*>(file->Get("metadata"))->GetString().Length()),
            "Embedded NUL in truth metadata");
    std::vector<std::set<std::string>> keys;
    const auto metadata = Json::parse(text, [&](int, Json::parse_event_t kind, Json& value) {
      if (kind == Json::parse_event_t::object_start) keys.emplace_back();
      if (kind == Json::parse_event_t::key)
        Require(keys.back().insert(value.get<std::string>()).second, "Duplicate truth JSON key");
      if (kind == Json::parse_event_t::object_end) keys.pop_back();
      return true;
    });
    Require(metadata.is_object() && Integer(metadata, "schema_version") == 2
            && metadata.at("status") == "diagnostic_truth_export", "Unsupported truth metadata schema/status");
    Require(metadata.at("units") == "GeV" && metadata.at("generation_target") == "free_proton"
            && metadata.at("geometry_target") == "period_conditions_required"
            && metadata.at("weight_policy") == "unit_unweighted_no_flux_or_cross_section_normalization",
            "Unsupported truth units/target/weight policy");
    Require(Integer(metadata, "generator_schema_version") == 1
            && metadata.at("sampling") == "accept-reject-unweighted; TRandom3 shared with TGenPhaseSpace",
            "Unsupported truth generator schema/sampling");
    for (const auto* name : {"source", "generator"})
      Require(metadata.at(name).is_string() && !metadata.at(name).get<std::string>().empty(),
              std::string("Missing truth provenance: ") + name);
    const auto& hash = metadata.at("source_sha256");
    Require(hash.is_string(), "Missing source SHA256");
    const auto source_hash = hash.get<std::string>();
    Require(source_hash.size() == 64 && source_hash.find_first_not_of("0123456789abcdef") == std::string::npos,
            "Invalid source SHA256");
    auto& ledger = Tree(*file, "events");
    auto& particles = Tree(*file, "primaries");
    const auto count = Integer(metadata, "events");
    Require(count > 0 && count <= ULong64_t(std::numeric_limits<int>::max())
            && ledger.GetEntries() == Long64_t(count) && Integer(metadata, "source_events") >= count,
            "Truth event count mismatch");
    // Validate all branches, including empty trees, before iterating.
    TTreeReader er(&ledger), pr(&particles);
    Number<Int_t> event(er, "event", "Int_t"), n(er, "nprimaries", "Int_t");
    Number<ULong64_t> entry(er, "source_entry", "ULong64_t");
    Number<Double_t> beam(er, "energy_GeV", "Double_t"), weight(er, "generation_weight", "Double_t");
    Number<Int_t> pe(pr, "event", "Int_t"), index(pr, "primary_index", "Int_t"), pdg(pr, "pdg", "Int_t");
    Number<Double_t> px(pr, "px_GeV", "Double_t"), py(pr, "py_GeV", "Double_t"),
      pz(pr, "pz_GeV", "Double_t"), energy(pr, "energy_GeV", "Double_t"), mass(pr, "mass_GeV", "Double_t");
    for (auto* tree : {&ledger, &particles}) {
      TIter branches(tree->GetListOfBranches());
      while (auto* object = branches()) {
        auto* branch = dynamic_cast<TBranch*>(object);
        Require(branch && branch->GetEntries() == tree->GetEntries(), "Truth branch cardinality mismatch");
      }
    }
    Long64_t total = 0;
    while (Next(er)) {
      Require(event.get() == int(rows.size()) && entry.get() == rows.size(), "Truth event/source ordering mismatch");
      Require(n.get() >= 2 && n.get() <= 9, "Expected proton and 1..8 photons");
      Require(weight.get() == 1., "Truth generation weight must be finite and unit");
      Event row{beam.get(), {}};
      Require(std::isfinite(row.energy) && row.energy > 0, "Invalid truth beam energy");
      long double sx = 0, sy = 0, sz = 0, se = 0;
      for (int i = 0; i < n.get(); ++i) {
        Require(Next(pr), "Missing truth primary row");
        Require(pe.get() == event.get() && index.get() == i, "Truth primary ordering mismatch");
        Particle p{pdg.get(), px.get(), py.get(), pz.get(), energy.get(), mass.get()};
        Require(p.pdg == (i == 0 ? 2212 : 22), "Truth requires proton then photons");
        for (double value : {p.px, p.py, p.pz, p.energy, p.mass})
          Require(std::isfinite(value), "Nonfinite truth primary");
        Require(p.energy > 0 && p.mass >= 0 && std::abs(p.mass - (i == 0 ? 0.938272 : 0.)) <= 1.e-9,
                "Invalid truth primary energy/mass");
        const long double shell = static_cast<long double>(p.energy)*p.energy
          - static_cast<long double>(p.px)*p.px - static_cast<long double>(p.py)*p.py
          - static_cast<long double>(p.pz)*p.pz - static_cast<long double>(p.mass)*p.mass;
        Require(std::abs(shell) <= 1.e-8L, "Truth primary is off shell");
        Require(i == 0 || std::hypot(p.px, p.py, p.pz) > 0, "Zero truth photon momentum");
        sx += p.px; sy += p.py; sz += p.pz; se += p.energy;
        row.primaries.push_back(p);
        ++total;
      }
      Require(std::abs(sx) <= 1.e-8L && std::abs(sy) <= 1.e-8L
              && std::abs(sz - row.energy) <= 1.e-8L
              && std::abs(se - (row.energy + 0.938272)) <= 1.e-8L,
              "Truth four-momentum conservation failed");
      rows.push_back(std::move(row));
    }
    Require(!Next(pr) && total == particles.GetEntries() && rows.size() == count,
            "Orphan truth primaries or count mismatch");
  }
  const std::vector<Event>& events() const { return rows; }
private:
  std::vector<Event> rows;
};
} // namespace rootreplay
