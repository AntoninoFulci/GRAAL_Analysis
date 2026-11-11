#pragma once

// Raw transport inputs for later digitization. No thresholds, quenching or PID.
#include "G4Event.hh"
#include "G4GDMLParser.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"
#include "G4Step.hh"
#include "G4SystemOfUnits.hh"
#include "G4TouchableHistory.hh"
#include "G4Track.hh"
#include "G4VProcess.hh"
#include "RootOutput.hh"
#include <map>
#include <set>
#include <stdexcept>
#include <string>

class DetectorHits {
  struct Volume { std::string name; int medium, material, sensitive; };
  std::map<const G4LogicalVolume*, Volume> volumes;
  std::set<std::string> paths;
  std::map<int, std::set<int>> scintillator_channels;
  RootTable *steps = nullptr, *primaries = nullptr, *cylinder_context = nullptr, *storage_events = nullptr;
  bool compact = false;
  ULong64_t stored_entries = 0, event_stored = 0, event_bgo = 0;
  // These are stream counters, never reset at track/event/run boundaries.
  ULong64_t callbacks = 0, passive_callbacks = 0, sensitive_entries = 0, cylinder_rows = 0;

  static int Integer(const std::map<std::string, std::string>& values, const std::string& key) {
    const auto found = values.find(key);
    if (found == values.end())
      throw std::runtime_error("Missing " + key + "; regenerate GDML with graal_geometry");
    std::size_t used = 0;
    const int result = std::stoi(found->second, &used);
    if (used != found->second.size() || result < 0)
      throw std::runtime_error("Invalid " + key);
    return result;
  }
  static const char* Role(int sensitive) {
    // ISVOL dispatch in preserved laggen/src/gustep.F, cases 1..14.
    static const char* roles[] = {"", "bgo", "barrel", "tof_h", "tof_v", "shower",
      "cyl_surface_1", "cyl_surface_2", "plane_1", "plane_2", "cyl_gas_1",
      "cyl_gas_2", "disk_1", "disk_2", "bc448"};
    return sensitive >= 1 && sensitive <= 14 ? roles[sensitive] : "";
  }
  static const char* ChannelKind(int sensitive) {
    if (sensitive <= 5 || sensitive == 14) return "legacy_scintillator";
    if (sensitive <= 7) return "chamber_surface";
    if (sensitive <= 9) return "chamber_plane";
    if (sensitive <= 11) return "gas_volume";
    return "unsegmented_disk";
  }
  std::string Component(const G4VPhysicalVolume* pv, int copy) const {
    return '/' + volumes.at(pv->GetLogicalVolume()).name + ':' + std::to_string(copy);
  }
  void Channels(G4VPhysicalVolume* pv, std::string path, RootTable& out) {
    if (pv->IsReplicated() || pv->IsParameterised())
      throw std::runtime_error("Hit channel inventory requires explicit placements");
    const auto* lv = pv->GetLogicalVolume();
    path += Component(pv, pv->GetCopyNo());
    const auto& v = volumes.at(lv);
    if (*Role(v.sensitive)) {
      if (!paths.insert(path).second) throw std::runtime_error("Duplicate detector path " + path);
      const int channel = pv->GetCopyNo() - (v.sensitive == 2 ? 100 : 0);
      if (v.sensitive <= 5 || v.sensitive == 14) {
        const int maximum = v.sensitive == 1 ? 480 : v.sensitive == 2 ? 32 :
                            v.sensitive <= 4 ? 26 : v.sensitive == 5 ? 16 : 8;
        if (channel < 1 || channel > maximum)
          throw std::runtime_error("Invalid scintillator channel " + path);
        if (!scintillator_channels[v.sensitive].insert(channel).second)
          throw std::runtime_error("Duplicate legacy scintillator channel " + path);
      }
      out.Fill({path, std::string(Role(v.sensitive)), v.sensitive, v.name,
                pv->GetCopyNo(), channel, std::string(ChannelKind(v.sensitive)),
                v.medium, v.material, std::string(lv->GetMaterial()->GetName())});
    }
    for (std::size_t i = 0; i < lv->GetNoDaughters(); ++i) Channels(lv->GetDaughter(i), path, out);
  }
  static void Vector(std::vector<RootTable::Value>& row, const G4ThreeVector& v, double unit) {
    row.insert(row.end(), {v.x()/unit, v.y()/unit, v.z()/unit});
  }
public:
  DetectorHits(const G4GDMLParser& parser, RootOutput& output, bool compact_storage = false) : compact(compact_storage) {
    for (const auto& [lv, auxiliary] : *parser.GetAuxMap()) {
      std::map<std::string, std::string> values;
      for (const auto& item : auxiliary)
        if (!values.emplace(item.type, item.value).second)
          throw std::runtime_error("Duplicate GDML auxiliary " + item.type);
      const auto name = values.find("geant3_volume");
      if (name == values.end() || name->second.empty() ||
          name->second.find_first_of("/:,\"\r\n") != std::string::npos)
        throw std::runtime_error("Missing or invalid geant3_volume");
      Volume v{name->second, Integer(values, "geant3_medium"),
               Integer(values, "geant3_material"), Integer(values, "geant3_sensitive")};
      // Passive codes are explicit legacy material markers, not an open range.
      const bool passive = v.sensitive >= 200 && v.sensitive <= 340 && v.sensitive % 10 == 0;
      if (v.sensitive > 14 && !passive)
        throw std::runtime_error("Unknown GEANT3 sensitivity code");
      volumes.emplace(lv, v);
    }
    auto& channels = output.Book("channels", {
      {"path", std::string{}}, {"detector", std::string{}}, {"sensitive", 0},
      {"volume", std::string{}}, {"copy", 0}, {"legacy_channel", 0},
      {"channel_kind", std::string{}}, {"medium", 0}, {"material_id", 0}, {"material", std::string{}}});
    Channels(parser.GetWorldVolume(), "", channels);
    const std::map<int, std::size_t> expected{{1,480}, {2,32}, {3,26}, {4,26}, {5,16}};
    for (const auto& [role, count] : expected)
      if (scintillator_channels[role].size() != count)
        throw std::runtime_error("Incomplete legacy scintillator inventory: " + std::string(Role(role)));
    if (paths.empty()) throw std::runtime_error("Empty detector channel inventory");
    if (compact) {
      steps = &output.Book("detector_steps", {
        {"run",0},{"event",0},{"track",0},{"parent",0},{"track_step",0},
        {"pre_boundary",0},{"post_boundary",0},{"pre_status",0},{"post_status",0},{"track_status",0},
        {"path",std::string{}},{"charge_e",0.},{"edep_MeV",0.},{"pre_time_ns",0.},{"post_time_ns",0.},
        {"pre_x_mm",0.},{"pre_y_mm",0.},{"pre_z_mm",0.},
        {"post_x_mm",0.},{"post_y_mm",0.},{"post_z_mm",0.},{"source_step_entry",ULong64_t{0}}});
      storage_events = &output.Book("storage_events", {
        {"run",0},{"event",0},{"stored_steps",ULong64_t{0}},{"bgo_steps",ULong64_t{0}}});
      output.Metadata("storage_metadata",
        R"({"schema_version":1,"mode":"compact","bgo":"sum_per_crystal_float64","source_index":"original_sensitive_step","response_scope":"current_response_no_step_quenching"})");
    } else steps = &output.Book("detector_steps", {
      {"run", 0}, {"event", 0}, {"track", 0},
      {"parent", 0}, {"pdg", 0}, {"charge_e", 0.},
      {"track_step", 0}, {"track_weight", 0.}, {"path", std::string{}},
      {"material", std::string{}}, {"edep_MeV", 0.}, {"nonionizing_edep_MeV", 0.},
      {"step_length_mm", 0.}, {"pre_time_ns", 0.}, {"post_time_ns", 0.},
      {"pre_kinetic_MeV", 0.}, {"post_kinetic_MeV", 0.}, {"pre_x_mm", 0.},
      {"pre_y_mm", 0.}, {"pre_z_mm", 0.}, {"post_x_mm", 0.},
      {"post_y_mm", 0.}, {"post_z_mm", 0.}, {"pre_local_x_mm", 0.},
      {"pre_local_y_mm", 0.}, {"pre_local_z_mm", 0.}, {"post_local_x_mm", 0.},
      {"post_local_y_mm", 0.}, {"post_local_z_mm", 0.}, {"pre_dir_x", 0.},
      {"pre_dir_y", 0.}, {"pre_dir_z", 0.}, {"post_dir_x", 0.},
      {"post_dir_y", 0.}, {"post_dir_z", 0.}, {"pre_status", 0},
      {"post_status", 0}, {"pre_boundary", 0}, {"post_boundary", 0},
      {"track_status", 0}, {"process", std::string{}}, {"creator_process", std::string{}}});
    primaries = &output.Book("primaries", {
      {"run", 0}, {"event", 0}, {"vertex", 0},
      {"particle", 0}, {"pdg", 0}, {"vertex_weight", 0.},
      {"particle_weight", 0.}, {"x_mm", 0.}, {"y_mm", 0.},
      {"z_mm", 0.}, {"time_ns", 0.}, {"px_MeV", 0.},
      {"py_MeV", 0.}, {"pz_MeV", 0.}, {"kinetic_MeV", 0.}});
    cylinder_context = &output.Book("cylinder_step_context", {
      {"run", 0}, {"event", 0}, {"source_step_entry", ULong64_t{0}},
      {"callback_index", ULong64_t{0}}, {"passive_epoch", ULong64_t{0}}});
    output.Metadata("cylinder_context_metadata",
      std::string(compact ? "{\"source_index\":\"original_sensitive_step\"," : "{") +
      "\"schema_version\":1,\"scope\":\"all_central_sensitive_steps\","
      "\"source_tree\":\"detector_steps\",\"source_entry_origin\":0,"
      "\"callback_origin\":0,\"passive_epoch_origin\":\"0_unknown\","
      "\"counter_scope\":\"output_stream_across_tracks_events_runs\","
      "\"reset_rule\":\"every_callback_with_sensitivity_outside_1_to_14\","
      "\"legacy_source\":\"laggen/src/gustep.F\","
      // Pinned source revision defining this implementation's reset semantics.
      "\"legacy_source_sha256\":\"e5fb4bb8474ec8f657241b678f1c0661a0a30a7617a8a31136ed64f9141ec660\","
      "\"physical_validation\":false}");
  }

  // MT workers use event-local counters; the ordered writer restores stream offsets.
  void ResetStreamCounters() {
    stored_entries = callbacks = passive_callbacks = sensitive_entries = cylinder_rows = 0;
  }
  void BeginEvent() { event_stored = event_bgo = 0; }
  void EndEvent(int run, int event) {
    if (storage_events) storage_events->Fill({run, event, event_stored, event_bgo});
  }
  ULong64_t StoredCount() const { return stored_entries; }
  ULong64_t CallbackCount() const { return callbacks; }
  ULong64_t PassiveCount() const { return passive_callbacks; }
  ULong64_t CylinderContextCount() const { return cylinder_rows; }

  void Primaries(const G4Event* event, int run) {
    for (int i = 0; i < event->GetNumberOfPrimaryVertex(); ++i) {
      const auto* vertex = event->GetPrimaryVertex(i);
      for (int j = 0; j < vertex->GetNumberOfParticle(); ++j) {
        const auto* particle = vertex->GetPrimary(j);
        std::vector<RootTable::Value> row{run, event->GetEventID(), i, j,
          particle->GetPDGcode(), vertex->GetWeight(), particle->GetWeight()};
        Vector(row, vertex->GetPosition(), mm);
        row.push_back(vertex->GetT0()/ns);
        Vector(row, particle->GetMomentum(), MeV);
        row.push_back(particle->GetKineticEnergy()/MeV);
        primaries->Fill(row);
      }
    }
  }
  bool Record(const G4Step* step, int run, int event) {
    const auto* pre = step->GetPreStepPoint();
    const auto* post = step->GetPostStepPoint();
    const auto* pv = pre->GetPhysicalVolume();
    if (callbacks == std::numeric_limits<ULong64_t>::max())
      throw std::runtime_error("Transport callback counter overflow");
    const auto callback_index = callbacks++;
    const int sensitivity = pv ? volumes.at(pv->GetLogicalVolume()).sensitive : 0;
    if (!*Role(sensitivity)) {
      // A passive zero-deposit step also resets saved ITOUCH/DEGAS in GUSTEP.
      // Counting resets rather than storing passive rows preserves that state.
      ++passive_callbacks; // Bounded by callbacks, already checked above.
      return false;
    }
    if (compact && sensitivity == 1) {
      // BGO sums and first positive-deposit times are accumulated by StepAction.
      // Preserve original sensitive indices even though these rows are not stored.
      ++event_bgo;
      ++sensitive_entries;
      return true;
    }
    const auto& touch = pre->GetTouchableHandle();
    std::string path;
    for (int depth = touch->GetHistoryDepth(); depth >= 0; --depth)
      path += Component(touch->GetVolume(depth), touch->GetCopyNumber(depth));
    if (!paths.count(path)) throw std::runtime_error("Unmapped detector path " + path);
    const auto* track = step->GetTrack();
    if (compact) {
      std::vector<RootTable::Value> row{run,event,track->GetTrackID(),track->GetParentID(),
        track->GetCurrentStepNumber(),int(pre->GetStepStatus()==fGeomBoundary),
        int(post->GetStepStatus()==fGeomBoundary || post->GetStepStatus()==fWorldBoundary),
        int(pre->GetStepStatus()),int(post->GetStepStatus()),int(track->GetTrackStatus()),path,
        pre->GetCharge()/eplus,step->GetTotalEnergyDeposit()/MeV,pre->GetGlobalTime()/ns,post->GetGlobalTime()/ns};
      Vector(row,pre->GetPosition(),mm);
      Vector(row,post->GetPosition(),mm);
      row.push_back(sensitive_entries);
      steps->Fill(row);
    } else {
    const auto* process = post->GetProcessDefinedStep();
    const auto* creator = track->GetCreatorProcess();
    std::vector<RootTable::Value> row{run, event, track->GetTrackID(), track->GetParentID(),
      track->GetDefinition()->GetPDGEncoding(), pre->GetCharge()/eplus,
      track->GetCurrentStepNumber(), pre->GetWeight(), path, std::string(pre->GetMaterial()->GetName()),
      step->GetTotalEnergyDeposit()/MeV, step->GetNonIonizingEnergyDeposit()/MeV,
      step->GetStepLength()/mm, pre->GetGlobalTime()/ns, post->GetGlobalTime()/ns,
      pre->GetKineticEnergy()/MeV, post->GetKineticEnergy()/MeV};
    Vector(row, pre->GetPosition(), mm);
    Vector(row, post->GetPosition(), mm);
    // Both endpoints use the PRE volume frame, including a step leaving that volume.
    const auto& transform = touch->GetHistory()->GetTopTransform();
    Vector(row, transform.TransformPoint(pre->GetPosition()), mm);
    Vector(row, transform.TransformPoint(post->GetPosition()), mm);
    Vector(row, pre->GetMomentumDirection(), 1.);
    Vector(row, post->GetMomentumDirection(), 1.);
    row.insert(row.end(), {static_cast<int>(pre->GetStepStatus()), static_cast<int>(post->GetStepStatus()),
      int(pre->GetStepStatus() == fGeomBoundary),
      int(post->GetStepStatus() == fGeomBoundary || post->GetStepStatus() == fWorldBoundary),
      static_cast<int>(track->GetTrackStatus()), std::string(process ? process->GetProcessName() : ""),
      std::string(creator ? creator->GetProcessName() : "")});
    steps->Fill(row);
    }
    ++stored_entries;
    ++event_stored;
    if (sensitivity == 6 || sensitivity == 7 || sensitivity == 10 || sensitivity == 11) {
      cylinder_context->Fill({run, event, sensitive_entries, callback_index, passive_callbacks});
      ++cylinder_rows;
    }
    ++sensitive_entries;
    return true;
  }
};
