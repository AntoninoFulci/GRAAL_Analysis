// Diagnostic transport through the preserved geometry, not a GRAAL event producer.
#include "FTFP_BERT_HP.hh"
#include "G4EmStandardPhysics_option4.hh"
#include "G4Event.hh"
#include "G4GDMLParser.hh"
#include "G4GeneralParticleSource.hh"
#include "G4HEPEvtInterface.hh"
#include "G4PrimaryParticle.hh"
#include "G4PrimaryVertex.hh"
#include "G4LogicalVolume.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
#ifdef G4MULTITHREADED
#include "G4MTRunManager.hh"
#endif
#include "G4VUserActionInitialization.hh"
#include "G4Step.hh"
#include "G4SystemOfUnits.hh"
#include "G4UImanager.hh"
#include "G4UserEventAction.hh"
#include "G4UserRunAction.hh"
#include "G4UserSteppingAction.hh"
#include "G4VUserDetectorConstruction.hh"
#include "G4VUserPrimaryGeneratorAction.hh"
#include "G4Version.hh"
#include "Randomize.hh"
#include "TransportMaterials.hh"
#include "PeriodConditions.hh"
#include "DetectorHits.hh"
#include "RootReplay.hh"
#include "OrderedTransport.hh"
#include "TROOT.h"
#include "TMD5.h"
#include "G4PhysicalVolumeStore.hh"
#include "G4Tubs.hh"
#ifdef GRAAL_WITH_QT
#include "G4UIExecutive.hh"
#include "G4VisExecutive.hh"
#endif
#include <filesystem>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <map>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <cstdlib>

namespace fs = std::filesystem;

class Detector final : public G4VUserDetectorConstruction {
public:
  Detector(const std::string& input, RootOutput* output, const PeriodConditions* conditions, bool compact = false) {
    parser.SetOverlapCheck(false); // The converter performs the sampled audit.
    parser.Read(input, false);     // Local GDML: no network schema lookup.
    std::ostringstream materials;
    ApplyTransportMaterials(parser, output ? &materials : nullptr, conditions ? conditions->material : "D");
    if (output) output->Metadata("materials", materials.str());
    if (conditions) {
      unsigned found = 0;
      for (const auto& [volume, auxiliary] : *parser.GetAuxMap())
        for (const auto& item : auxiliary)
          if (item.type == "geant3_volume" && item.value == "CIBM") {
            auto* tube = dynamic_cast<G4Tubs*>(volume->GetSolid());
            if (!tube || std::abs(2*tube->GetZHalfLength()/mm-conditions->length) > 1.e-6
                || std::abs(2*tube->GetOuterRadius()/mm-conditions->diameter) > 1.e-6)
              throw std::runtime_error("Period conditions do not match target solid");
            for (auto* placement : *G4PhysicalVolumeStore::GetInstance())
              if (placement->GetLogicalVolume() == volume) {
                ++found;
                const auto position = placement->GetTranslation();
                if (placement->GetMotherLogical() != parser.GetWorldVolume()->GetLogicalVolume()
                    || placement->GetRotation() || std::abs(position.x()) > 1.e-6*mm
                    || std::abs(position.y()) > 1.e-6*mm
                    || std::abs(position.z()/mm-conditions->center) > 1.e-6)
                  throw std::runtime_error("Period conditions do not match target placement");
              }
          }
      if (found != 1) throw std::runtime_error("Period conditions require one target placement");
    }
    for (const auto& [volume, auxiliary] : *parser.GetAuxMap()) {
      for (const auto& item : auxiliary) {
        if (item.type == "geant3_volume" && item.value == "BGO") bgo.insert(volume);
        if (item.type == "geant3_world_copy")
          parser.GetWorldVolume()->SetCopyNo(std::stoi(item.value));
      }
    }
    if (bgo.empty()) throw std::runtime_error("GDML has no GRAAL BGO metadata");
    if (output) hits = std::make_unique<DetectorHits>(parser, *output, compact);
  }
  G4VPhysicalVolume* Construct() override { return parser.GetWorldVolume(); }
  bool IsBgo(const G4LogicalVolume* volume) const { return bgo.count(volume) != 0; }
  DetectorHits* Hits() const { return hits.get(); }
  std::unique_ptr<DetectorHits> WorkerHits(RootOutput& output, bool compact) const {
    return std::make_unique<DetectorHits>(parser, output, compact);
  }
private:
  G4GDMLParser parser;
  std::set<const G4LogicalVolume*> bgo;
  std::unique_ptr<DetectorHits> hits;
};

class Primary final : public G4VUserPrimaryGeneratorAction {
public:
  explicit Primary(const fs::path& input, PeriodConditions* period, const rootreplay::Input* root = nullptr)
      : conditions(period), root_replay(root) {
    if (root_replay) return;
    if (input.empty()) source = std::make_unique<G4GeneralParticleSource>();
    else replay = std::make_unique<G4HEPEvtInterface>(input.string().c_str(), 0);
  }
  void GeneratePrimaries(G4Event* event) override {
    if (root_replay) {
      if (G4RunManager::GetRunManager()->GetCurrentRun()->GetRunID() != 0
          || event->GetEventID() < 0 || std::size_t(event->GetEventID()) >= root_replay->events().size())
        throw std::runtime_error("ROOT replay event outside validated run zero");
      auto vertex = std::make_unique<G4PrimaryVertex>(G4ThreeVector(), 0.);
      for (const auto& p : root_replay->events().at(event->GetEventID()).primaries) {
        auto primary = std::make_unique<G4PrimaryParticle>(p.pdg);
        primary->SetMass(p.mass * GeV);
        primary->SetMomentum(p.px * GeV, p.py * GeV, p.pz * GeV);
        vertex->SetPrimary(primary.release());
      }
      event->AddPrimaryVertex(vertex.release());
    }
    else if (replay) replay->GeneratePrimaryVertex(event);
    else source->GeneratePrimaryVertex(event);
    if (conditions) conditions->Apply(event, G4RunManager::GetRunManager()->GetCurrentRun()->GetRunID());
  }
private:
  std::unique_ptr<G4GeneralParticleSource> source;
  std::unique_ptr<G4HEPEvtInterface> replay;
  PeriodConditions* conditions;
  const rootreplay::Input* root_replay;
};

// Validate our flat final-state subset before handing it to Geant4's reader.
int CountPrimaries(const fs::path& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("Cannot read HEPEvt input");
  std::string line, extra;
  int events = 0;
  while (std::getline(input, line)) {
    std::istringstream count(line);
    int particles;
    if (!(count >> particles) || (count >> extra) || particles < 2 || particles > 9)
      throw std::runtime_error("Invalid HEPEvt particle count (expected proton and 1..8 photons)");
    for (int i = 0; i < particles; ++i) {
      if (!std::getline(input, line)) throw std::runtime_error("Truncated HEPEvt event");
      std::istringstream record(line);
      int status, pdg, first, last;
      double px, py, pz, mass;
      if (!(record >> status >> pdg >> first >> last >> px >> py >> pz >> mass)
          || (record >> extra) || status != 1 || first != 0 || last != 0
          || pdg != (i == 0 ? 2212 : 22)
          || !std::isfinite(px) || !std::isfinite(py) || !std::isfinite(pz) || !std::isfinite(mass)
          || std::abs(mass - (i == 0 ? 0.938272 : 0.)) > 1.e-9
          || (i != 0 && px == 0 && py == 0 && pz == 0)
          || std::hypot(px, py, pz) > 10.)
        throw std::runtime_error("Invalid HEPEvt final-state particle (GeV, proton then photons required)");
    }
    if (events == std::numeric_limits<int>::max()) throw std::runtime_error("Too many HEPEvt events");
    ++events;
  }
  if (!input.eof() || events == 0) throw std::runtime_error("Empty or unreadable HEPEvt input");
  return events;
}

struct CrystalScore { double energy = 0, first_time = 0; };
struct Scores {
  double total = 0, bgo = 0;
  unsigned long steps = 0, events = 0, aborted = 0;
  unsigned long attempted = 0, hit_steps = 0, all_hit_steps = 0;
  int run = 0, event = 0;
  RootTable *ledger = nullptr, *hits = nullptr;
  std::map<int, CrystalScore> crystals;
};

class EventAction final : public G4UserEventAction {
public:
  EventAction(Scores& value, const Detector& geometry, DetectorHits* local = nullptr)
      : scores(value), hits(local ? local : geometry.Hits()) {}
  void BeginOfEventAction(const G4Event* event) override {
    scores.total = scores.bgo = 0;
    scores.steps = 0;
    scores.crystals.clear();
    scores.hit_steps = 0;
    scores.run = G4RunManager::GetRunManager()->GetCurrentRun()->GetRunID();
    scores.event = event->GetEventID();
    ++scores.attempted;
    if (hits) {
      hits->BeginEvent();
      hits->Primaries(event, scores.run);
    }
  }
  void EndOfEventAction(const G4Event* event) override {
    if (hits) hits->EndEvent(scores.run, event->GetEventID());
    if (event->IsAborted()) ++scores.aborted;
    else ++scores.events;
    if (scores.ledger) {
      scores.ledger->Fill({scores.run, event->GetEventID(), scores.total/MeV, scores.bgo/MeV,
                          ULong64_t{scores.steps}, int(event->IsAborted()), ULong64_t{scores.hit_steps}});
      for (const auto& [crystal, hit] : scores.crystals)
        scores.hits->Fill({scores.run, event->GetEventID(), crystal, hit.energy/MeV, hit.first_time/ns});
    }
  }
private:
  Scores& scores;
  DetectorHits* hits;
};

class StepAction final : public G4UserSteppingAction {
public:
  StepAction(Scores& value, const Detector& geometry, DetectorHits* local = nullptr)
      : scores(value), detector(geometry), hits(local ? local : geometry.Hits()) {}
  void UserSteppingAction(const G4Step* step) override {
    ++scores.steps;
    const auto deposit = step->GetTotalEnergyDeposit();
    scores.total += deposit;
    if (hits && hits->Record(step, scores.run, scores.event)) {
      ++scores.hit_steps;
      ++scores.all_hit_steps;
    }
    const auto* volume = step->GetPreStepPoint()->GetPhysicalVolume();
    if (volume && detector.IsBgo(volume->GetLogicalVolume()) && deposit > 0) {
      scores.bgo += deposit;
      const auto* point = step->GetPreStepPoint();
      const int crystal = point->GetTouchableHandle()->GetCopyNumber();
      if (crystal < 1 || crystal > 480) throw std::runtime_error("Invalid BGO crystal copy number");
      auto& hit = scores.crystals[crystal];
      const double time = point->GetGlobalTime();
      if (hit.energy == 0 || time < hit.first_time) hit.first_time = time;
      hit.energy += deposit;
    }
  }
private:
  Scores& scores;
  const Detector& detector;
  DetectorHits* hits;
};

#include "TransportActions.hh"

class RunAction final : public G4UserRunAction {
public:
  explicit RunAction(RootOutput* data, const PeriodConditions* period)
      : output(data), conditions(period) {}
  void BeginOfRunAction(const G4Run* run) override {
    if (conditions) {
      const long seed = conditions->seed + run->GetRunID();
      if (seed > 2147483647) throw std::runtime_error("Period run seed exceeds supported range");
      // A macro's /random/setSeeds must not silently override period provenance.
      G4Random::setTheSeed(seed);
    }
    if (output) {
      std::ostringstream state;
      G4Random::saveFullState(state);
      output->Metadata("random_state_run_" + std::to_string(run->GetRunID()), state.str());
    }
  }
private:
  RootOutput* output;

  const PeriodConditions* conditions;
};

std::string ReadText(const fs::path& path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("Cannot read input metadata");
  std::ostringstream text;
  text << input.rdbuf();
  if (input.bad()) throw std::runtime_error("Failed reading input metadata");
  return text.str();
}

std::string InputDigest(const fs::path& path) {
  std::unique_ptr<TMD5> digest(TMD5::FileChecksum(path.string().c_str()));
  if (!digest) throw std::runtime_error("Cannot hash transport input");
  return digest->AsString();
}

int main(int argc, char** argv) {
  try {
    std::unique_ptr<PeriodConditions> conditions;
    std::string conditions_path;
    bool compact = false, storage_seen = false;
    int threads = 0; // Absent option preserves the historical serial stream.
    bool threads_seen = false;
    // Trailing options may appear in either order; duplicate options fail closed.
    while (argc >= 3) {
      const std::string option = argv[argc-2];
      if (option == "--threads") {
        if (threads_seen) throw std::runtime_error("Duplicate --threads option");
        threads_seen = true;
        const std::string value = argv[argc-1];
        if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos
            || value.size() > 10 || std::stoll(value) < 1 || std::stoll(value) > 2147483647)
          throw std::runtime_error("--threads must be a positive integer <= 2147483647");
        threads = std::stoi(value);
      } else if (option == "--conditions") {
        if (conditions) throw std::runtime_error("Duplicate --conditions option");
        conditions_path = argv[argc-1];
        conditions = std::make_unique<PeriodConditions>(conditions_path);
      } else if (option == "--storage") {
        if (storage_seen) throw std::runtime_error("Duplicate --storage option");
        storage_seen = true;
        const std::string mode = argv[argc-1];
        if (mode != "full" && mode != "compact") throw std::runtime_error("Storage mode must be full or compact");
        compact = mode == "compact";
      } else break;
      argc -= 2;
    }
    const bool root_mode = argc == 5 && std::string(argv[2]) == "--root-events";
    const bool replay = root_mode || (argc == 5 && std::string(argv[2]) == "--hepevt");
    if (threads_seen && !root_mode) throw std::runtime_error("--threads requires ROOT replay");
    if (threads_seen && std::getenv("G4FORCENUMBEROFTHREADS"))
      throw std::runtime_error("Unset G4FORCENUMBEROFTHREADS; use explicit --threads");
#ifndef G4MULTITHREADED
    if (threads_seen) throw std::runtime_error("--threads requires a multithread-capable Geant4 build");
#endif
    if (argc != 4 && !replay)
      throw std::runtime_error("Usage: graal_g4 geometry.gdml macro.mac NEW_OUTPUT_DIR\n"
                               "   or: graal_g4 geometry.gdml --vis vis.mac\n"
                               "   or: graal_g4 geometry.gdml --hepevt primaries.dat NEW_OUTPUT_DIR\n"
                               "   or: graal_g4 geometry.gdml --root-events truth.root NEW_OUTPUT_DIR --conditions period.dat");
    const bool visual = !replay && std::string(argv[2]) == "--vis";
    if (storage_seen && visual) throw std::runtime_error("Storage option requires batch transport");
    if (conditions && visual) throw std::runtime_error("Period conditions require batch transport");
    if (conditions && replay && conditions->material != "P")
      throw std::runtime_error("Free-proton replay cannot represent a deuterium period");
    if (root_mode && !conditions)
      throw std::runtime_error("ROOT replay requires hydrogen period conditions");
    const fs::path macro = fs::absolute(argv[visual || replay ? 3 : 2]);
    if (!fs::is_regular_file(argv[1])) throw std::runtime_error("GDML file not found");
    if (!fs::is_regular_file(macro)) throw std::runtime_error("Primary input or macro file not found");
#ifndef GRAAL_WITH_QT
    if (visual) throw std::runtime_error("Rebuild with -DGRAAL_WITH_QT=ON for --vis");
#endif
    Scores scores;
    std::unique_ptr<RootOutput> data;
    fs::path output;
    const auto input_digest = InputDigest(macro);
    int expected_events = 0;
    std::unique_ptr<rootreplay::Input> root_events;
    if (root_mode) {
      root_events = std::make_unique<rootreplay::Input>(macro);
      expected_events = static_cast<int>(root_events->events().size());
      if (InputDigest(macro) != input_digest)
        throw std::runtime_error("ROOT truth input changed during preflight");
    }
    if (!visual) {
      output = fs::absolute(argv[replay ? 4 : 3]);
      if (!fs::create_directory(output)) throw std::runtime_error("Output exists; refusing overwrite");
      data = std::make_unique<RootOutput>(output);
      data->Metadata("input_source", macro.string());
      data->Metadata("input_md5", input_digest);
      // The launcher retains the authoritative SHA-256 truth provenance separately.
      if (replay && !root_mode) expected_events = CountPrimaries(macro);
      else if (!replay) data->Metadata("input_macro", ReadText(macro));
      auto& vertices = BookScores(*data, scores);
      if (conditions) {
        data->Metadata("conditions", ReadText(conditions_path));
        conditions->SetVertices(vertices);
      }
    }
    std::cerr << "DIAGNOSTIC ONLY: " << (conditions ? "period target geometry; " : "frozen GRAAL_26 deuterium geometry; ")
              << "runtime material "
                 "policy diagnostic_materials_v1; response and acceptance are not validated.\n";
    G4Random::setTheSeed(conditions ? conditions->seed : 20261026);
    std::unique_ptr<OrderedTransport> ordered;
    std::unique_ptr<G4RunManager> manager;
#ifdef G4MULTITHREADED
    if (threads_seen) {
      ROOT::EnableThreadSafety();
      auto mt = std::make_unique<G4MTRunManager>();
      mt->SetNumberOfThreads(threads);
      if (mt->GetNumberOfThreads() != threads) throw std::runtime_error("Effective MT thread count differs");
      mt->SetEventModulo(1);
      G4MTRunManager::SetSeedOncePerCommunication(0);
      ordered = std::make_unique<OrderedTransport>(*data, expected_events);
      ordered->compact = compact;
      manager = std::move(mt);
      std::ostringstream state;
      G4Random::saveFullState(state);
      data->Metadata("random_state_run_0", state.str());
    } else
#endif
      manager = std::make_unique<G4RunManager>();
    auto* detector = new Detector(argv[1], data.get(), conditions.get(), compact);
    manager->SetUserInitialization(detector);
    auto* physics = new FTFP_BERT_HP;
    physics->ReplacePhysics(new G4EmStandardPhysics_option4);
    physics->SetDefaultCutValue(0.1 * mm);
    physics->SetCutValue(0., "proton");
    manager->SetUserInitialization(physics);
    if (ordered) manager->SetUserInitialization(
        new ParallelActions(*detector, *conditions, *root_events, *ordered, compact));
    else {
      manager->SetUserAction(new Primary(replay ? macro : fs::path{}, conditions.get(), root_events.get()));
      manager->SetUserAction(new RunAction(data.get(), conditions.get()));
      manager->SetUserAction(new EventAction(scores, *detector));
      manager->SetUserAction(new StepAction(scores, *detector));
    }
    auto* ui = G4UImanager::GetUIpointer();
#ifdef GRAAL_WITH_QT
    if (visual) {
      // Only pass the application name to Qt, not our batch arguments.
      G4UIExecutive session(1, argv, "Qt");
      manager->Initialize();
      G4VisExecutive vis;
      vis.Initialize();
      ui->ExecuteMacroFile(macro.string().c_str());
      if (ui->GetLastReturnCode() != 0) throw std::runtime_error("Visualization macro failed");
      session.SessionStart();
      return 0;
    }
#endif
    if (replay) {
      manager->Initialize();
      manager->BeamOn(expected_events);
      if (ordered) {
        ordered->Finish();
        scores.events = ordered->next - ordered->aborts;
        scores.attempted = ordered->next;
        scores.aborted = ordered->aborts;
        scores.all_hit_steps = ordered->total.sensitive;
      }
      if (scores.events != static_cast<unsigned long>(expected_events))
        throw std::runtime_error("Replay event count mismatch");
    } else {
      ui->ExecuteMacroFile(macro.string().c_str());
      if (ui->GetLastReturnCode() != 0) throw std::runtime_error("Transport macro failed");
    }
    if (scores.events == 0 || scores.aborted != 0)
      throw std::runtime_error("No completed events or aborted events; diagnostic run failed");
    if (InputDigest(macro) != input_digest) throw std::runtime_error("Transport input changed during execution");
    std::ostringstream summary;
    summary << std::setprecision(17)
            << "{\"status\":\"diagnostic_transport_only\",\"physics_list\":\"FTFP_BERT_HP_EMZ\","
            << "\"geant4_version\":" << std::quoted(std::string(G4Version))
            << ",\"execution_mode\":\"" << (ordered ? "multithreaded" : "serial") << '\"'
            << ",\"threads\":" << (ordered ? threads : 1)
            << ",\"event_modulo\":" << (ordered ? 1 : 0)
            << ",\"random_engine\":" << std::quoted(G4Random::getTheEngine()->name())
            << ",\"events\":" << scores.events << ",\"aborted\":" << scores.aborted
            << ",\"attempted_events\":" << scores.attempted
            << ",\"hit_schema_version\":" << (compact ? 3 : 2)
            << ",\"storage_mode\":\"" << (compact ? "compact" : "full") << '\"'
            << ",\"stored_detector_steps\":" << (ordered ? ordered->total.stored : detector->Hits()->StoredCount())
            << ",\"output_format\":\"ROOT_TTree\",\"compression\":\"ZSTD_5\",\"detector_steps\":" << scores.all_hit_steps
            << ",\"cylinder_context_schema\":1,\"cylinder_context_rows\":" << (ordered ? ordered->total.cylinder : detector->Hits()->CylinderContextCount())
            << ",\"all_callbacks\":" << (ordered ? ordered->total.callbacks : detector->Hits()->CallbackCount())
            << ",\"passive_callbacks\":" << (ordered ? ordered->total.passive : detector->Hits()->PassiveCount())
            << ",\"hit_policy\":\"" << (compact ? "compact_response_inputs_v1" : "all_steps_in_sensitive_volumes_no_response_cuts") << '\"'
            << ",\"source_mode\":\"" << (root_mode ? "root_replay" : replay ? "hepevt" : "gps") << '"'
            << ",\"em_range_cut_mm\":" << physics->GetCutValue("gamma") / mm
            << ",\"electron_range_cut_mm\":" << physics->GetCutValue("e-") / mm
            << ",\"positron_range_cut_mm\":" << physics->GetCutValue("e+") / mm
            << ",\"proton_range_cut_mm\":" << physics->GetCutValue("proton") / mm
            << ",\"materials\":\"diagnostic_materials_v1\",\"target\":\""
            << (conditions && conditions->material == "P" ? "hydrogen" : "deuterium") << '"';
    if (root_mode) summary << ",\"input_source\":" << std::quoted(macro.string())
                           << ",\"input_md5\":" << std::quoted(input_digest)
                           << ",\"replay_input_path\":" << std::quoted(macro.string())
                           << ",\"replay_input_md5\":" << std::quoted(input_digest);
    if (conditions) summary << ",\"period\":" << std::quoted(conditions->period)
                            << ",\"seed\":" << conditions->seed
                            << ",\"run_seed_policy\":\"" << (ordered ? "geant4_mt_per_event" : "base_seed_plus_run_id") << '\"'
                            << ",\"vertex_policy\":\"observed_xy_conditioned_on_nominal_cell_radius; independent_uniform_z\"";
    summary << "}\n";
    data->Finish(summary.str());
    std::cout << "DIAGNOSTIC_TRANSPORT_COMPLETE events=" << scores.events << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
