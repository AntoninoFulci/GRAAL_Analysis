// Exercise the real diagnostic driver with a test-only Geant4 abort command.
// No test hooks, abort switches or alternate physics enter the production binary.
#define main graal_transport_main
#include "../src/transport.cc"
#undef main
#include "G4UIcmdWithoutParameter.hh"
#include "G4UImessenger.hh"

class AbortInBarrel final : public G4UserSteppingAction {
  std::unique_ptr<G4UserSteppingAction> original;
public:
  explicit AbortInBarrel(G4UserSteppingAction* action) : original(action) {}
  void UserSteppingAction(const G4Step* step) override {
    original->UserSteppingAction(step);
    if (step->GetPreStepPoint()->GetPhysicalVolume()->GetName() == "DEDX")
      G4RunManager::GetRunManager()->AbortEvent();
  }
};

class AbortCommand final : public G4UImessenger {
  G4UIcmdWithoutParameter command{"/test/abortInBarrel", this};
public:
  AbortCommand() { command.AvailableForStates(G4State_Idle); }
  void SetNewValue(G4UIcommand*, G4String) override {
    auto* manager = G4RunManager::GetRunManager();
    auto* action = const_cast<G4UserSteppingAction*>(manager->GetUserSteppingAction());
    manager->SetUserAction(new AbortInBarrel(action));
  }
};

int main(int argc, char** argv) {
  AbortCommand command;
  return graal_transport_main(argc, argv);
}
