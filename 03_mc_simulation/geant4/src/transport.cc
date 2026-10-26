// Diagnostic transport through the preserved geometry, not a GRAAL event producer.
#include "FTFP_BERT_HP.hh"
#include "G4EmStandardPhysics_option4.hh"
#include "G4Event.hh"
#include "G4GDMLParser.hh"
#include "G4GeneralParticleSource.hh"
#include "G4HEPEvtInterface.hh"
#include "G4LogicalVolume.hh"
#include "G4Run.hh"
#include "G4RunManager.hh"
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

namespace fs = std::filesystem;

class Detector final : public G4VUserDetectorConstruction {
public:
  Detector(const std::string& input, const std::string& report) {
    parser.SetOverlapCheck(false); // The converter performs the sampled audit.
    parser.Read(input, false);     // Local GDML: no network schema lookup.
    ApplyTransportMaterials(parser, report);
    for (const auto& [volume, auxiliary] : *parser.GetAuxMap()) {
      for (const auto& item : auxiliary) {
        if (item.type == "geant3_volume" && item.value == "BGO") bgo.insert(volume);
        if (item.type == "geant3_world_copy")
          parser.GetWorldVolume()->SetCopyNo(std::stoi(item.value));
      }
    }
    if (bgo.empty()) throw std::runtime_error("GDML has no GRAAL BGO metadata");
  }
  G4VPhysicalVolume* Construct() override { return parser.GetWorldVolume(); }
  bool IsBgo(const G4LogicalVolume* volume) const { return bgo.count(volume) != 0; }
private:
  G4GDMLParser parser;
  std::set<const G4LogicalVolume*> bgo;
};

class Primary final : public G4VUserPrimaryGeneratorAction {
public:
  explicit Primary(const fs::path& input) {
    if (input.empty()) source = std::make_unique<G4GeneralParticleSource>();
    else replay = std::make_unique<G4HEPEvtInterface>(input.string().c_str(), 0);
  }
  void GeneratePrimaries(G4Event* event) override {
    if (replay) replay->GeneratePrimaryVertex(event);
    else source->GeneratePrimaryVertex(event);
  }
private:
  std::unique_ptr<G4GeneralParticleSource> source;
  std::unique_ptr<G4HEPEvtInterface> replay;
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
  std::ofstream csv, hits;
  std::map<int, CrystalScore> crystals;
};

class EventAction final : public G4UserEventAction {
public:
  explicit EventAction(Scores& value) : scores(value) {}
  void BeginOfEventAction(const G4Event*) override {
    scores.total = scores.bgo = 0;
    scores.steps = 0;
    scores.crystals.clear();
  }
  void EndOfEventAction(const G4Event* event) override {
    if (event->IsAborted()) { ++scores.aborted; return; }
    ++scores.events;
    if (scores.csv.is_open()) {
      const auto* run = G4RunManager::GetRunManager()->GetCurrentRun();
      scores.csv << run->GetRunID() << ',' << event->GetEventID() << ','
                 << scores.total / MeV << ',' << scores.bgo / MeV << ',' << scores.steps << '\n';
      for (const auto& [crystal, hit] : scores.crystals)
        scores.hits << run->GetRunID() << ',' << event->GetEventID() << ',' << crystal << ','
                    << hit.energy / MeV << ',' << hit.first_time / ns << '\n';
    }
  }
private:
  Scores& scores;
};

class StepAction final : public G4UserSteppingAction {
public:
  StepAction(Scores& value, const Detector& geometry) : scores(value), detector(geometry) {}
  void UserSteppingAction(const G4Step* step) override {
    ++scores.steps;
    const auto deposit = step->GetTotalEnergyDeposit();
    scores.total += deposit;
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
};

class RunAction final : public G4UserRunAction {
public:
  explicit RunAction(fs::path directory) : output(std::move(directory)) {}
  void BeginOfRunAction(const G4Run* run) override {
    if (!output.empty()) {
      const auto path = output / ("run-" + std::to_string(run->GetRunID()) + ".rndm");
      G4Random::saveEngineStatus(path.string().c_str());
    }
  }
private:
  fs::path output;
};

int main(int argc, char** argv) {
  try {
    const bool replay = argc == 5 && std::string(argv[2]) == "--hepevt";
    if (argc != 4 && !replay)
      throw std::runtime_error("Usage: graal_g4 geometry.gdml macro.mac NEW_OUTPUT_DIR\n"
                               "   or: graal_g4 geometry.gdml --vis vis.mac\n"
                               "   or: graal_g4 geometry.gdml --hepevt primaries.dat NEW_OUTPUT_DIR");
    const bool visual = !replay && std::string(argv[2]) == "--vis";
    const fs::path macro = fs::absolute(argv[visual || replay ? 3 : 2]);
    if (!fs::is_regular_file(argv[1])) throw std::runtime_error("GDML file not found");
    if (!fs::is_regular_file(macro)) throw std::runtime_error("Primary input or macro file not found");
#ifndef GRAAL_WITH_QT
    if (visual) throw std::runtime_error("Rebuild with -DGRAAL_WITH_QT=ON for --vis");
#endif
    Scores scores;
    fs::path output;
    int expected_events = 0;
    if (!visual) {
      output = fs::absolute(argv[replay ? 4 : 3]);
      if (!fs::create_directory(output)) throw std::runtime_error("Output exists; refusing overwrite");
      fs::copy_file(macro, output / (replay ? "primaries.dat" : "input.mac"));
      if (replay) expected_events = CountPrimaries(output / "primaries.dat");
      scores.csv.open(output / "events.csv");
      scores.hits.open(output / "bgo_hits.csv");
      if (!scores.csv || !scores.hits) throw std::runtime_error("Cannot write score files");
      scores.csv << "run,event,total_edep_MeV,bgo_edep_MeV,steps\n" << std::setprecision(17);
      scores.hits << "run,event,crystal,edep_MeV,first_time_ns\n" << std::setprecision(17);
    }
    std::cerr << "DIAGNOSTIC ONLY: frozen GRAAL_26 deuterium geometry; runtime material "
                 "policy diagnostic_materials_v1; response and acceptance are not validated.\n";
    // Serial execution gives reproducible diagnostics and avoids hidden worker state.
    auto manager = std::make_unique<G4RunManager>();
    auto* detector = new Detector(argv[1], visual ? "" : (output / "materials.json").string());
    manager->SetUserInitialization(detector);
    auto* physics = new FTFP_BERT_HP;
    physics->ReplacePhysics(new G4EmStandardPhysics_option4);
    physics->SetDefaultCutValue(0.1 * mm);
    physics->SetCutValue(0., "proton");
    manager->SetUserInitialization(physics);
    manager->SetUserAction(new Primary(replay ? output / "primaries.dat" : fs::path{}));
    manager->SetUserAction(new RunAction(output));
    manager->SetUserAction(new EventAction(scores));
    manager->SetUserAction(new StepAction(scores, *detector));
    G4Random::setTheSeed(20261026);
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
      if (scores.events != static_cast<unsigned long>(expected_events))
        throw std::runtime_error("HEPEvt event count mismatch");
    } else {
      ui->ExecuteMacroFile((output / "input.mac").string().c_str());
      if (ui->GetLastReturnCode() != 0) throw std::runtime_error("Transport macro failed");
    }
    if (scores.events == 0 || scores.aborted != 0)
      throw std::runtime_error("No completed events or aborted events; diagnostic run failed");
    scores.csv.flush();
    scores.hits.flush();
    if (!scores.csv || !scores.hits) throw std::runtime_error("Failed writing event scores");
    std::ofstream summary(output / "summary.json");
    summary << std::setprecision(17)
            << "{\"status\":\"diagnostic_transport_only\",\"physics_list\":\"FTFP_BERT_HP_EMZ\","
            << "\"geant4_version\":" << std::quoted(std::string(G4Version))
            << ",\"events\":" << scores.events << ",\"aborted\":" << scores.aborted
            << ",\"source_mode\":\"" << (replay ? "hepevt" : "gps") << '"'
            << ",\"em_range_cut_mm\":" << physics->GetCutValue("gamma") / mm
            << ",\"electron_range_cut_mm\":" << physics->GetCutValue("e-") / mm
            << ",\"positron_range_cut_mm\":" << physics->GetCutValue("e+") / mm
            << ",\"proton_range_cut_mm\":" << physics->GetCutValue("proton") / mm
            << ",\"materials\":\"diagnostic_materials_v1\",\"target\":\"deuterium\"}\n";
    summary.close();
    if (!summary) throw std::runtime_error("Failed writing summary");
    std::cout << "DIAGNOSTIC_TRANSPORT_COMPLETE events=" << scores.events << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
