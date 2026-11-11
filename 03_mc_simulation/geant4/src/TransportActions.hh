#pragma once
// Included after the serial actions: both paths use the same scoring code.
RootTable& BookScores(RootOutput& output, Scores& scores) {
  auto& vertices = output.Book("vertices", {{"run",0},{"event",0},{"x_mm",0.},
    {"y_mm",0.},{"z_mm",0.},{"xy_attempts",ULong64_t{0}}});
  scores.ledger = &output.Book("events", {{"run",0},{"event",0},{"total_edep_MeV",0.},
    {"bgo_edep_MeV",0.},{"steps",ULong64_t{0}},{"aborted",0},{"hit_steps",ULong64_t{0}}});
  scores.hits = &output.Book("bgo_hits", {{"run",0},{"event",0},{"crystal",0},
    {"edep_MeV",0.},{"first_time_ns",0.}});
  return vertices;
}

struct WorkerState {
  RootOutput output{RootOutput::Buffered{}};
  Scores scores;
  PeriodConditions conditions;
  std::unique_ptr<DetectorHits> hits;
  OrderedTransport& writer;
  WorkerState(const Detector& detector, const PeriodConditions& period,
              OrderedTransport& writer, bool compact) : conditions(period), writer(writer) {
    conditions.SetVertices(BookScores(output, scores));
    hits = detector.WorkerHits(output, compact);
    output.Clear(); // Static inventory is emitted only by the master.
  }
  void Fail() {
    writer.Fail(std::current_exception());
    G4RunManager::GetRunManager()->AbortRun(true);
  }
};

class WorkerPrimary final : public G4VUserPrimaryGeneratorAction {
  std::shared_ptr<WorkerState> state;
  Primary action;
public:
  WorkerPrimary(std::shared_ptr<WorkerState> state, const rootreplay::Input& truth)
      : state(state), action({}, &state->conditions, &truth) {}
  void GeneratePrimaries(G4Event* event) override {
    try { state->writer.Check(); action.GeneratePrimaries(event); }
    catch (...) { state->Fail(); }
  }
};

class WorkerEvent final : public G4UserEventAction {
  std::shared_ptr<WorkerState> state;
  EventAction action;
public:
  WorkerEvent(std::shared_ptr<WorkerState> state, const Detector& detector)
      : state(state), action(state->scores, detector, state->hits.get()) {}
  void BeginOfEventAction(const G4Event* event) override {
    try {
      state->writer.Check();
      state->hits->ResetStreamCounters();
      // Vertices have already been buffered by GeneratePrimaries.
      action.BeginOfEventAction(event);
    } catch (...) { state->Fail(); }
  }
  void EndOfEventAction(const G4Event* event) override {
    try {
      state->writer.Check();
      action.EndOfEventAction(event);
      const auto& hits = *state->hits;
      state->writer.Submit(event->GetEventID(), state->output,
        {state->scores.hit_steps, hits.CallbackCount(), hits.PassiveCount(),
         hits.StoredCount(), hits.CylinderContextCount()}, event->IsAborted());
    } catch (...) { state->Fail(); }
  }
};

class WorkerStep final : public G4UserSteppingAction {
  std::shared_ptr<WorkerState> state;
  StepAction action;
public:
  WorkerStep(std::shared_ptr<WorkerState> state, const Detector& detector)
      : state(state), action(state->scores, detector, state->hits.get()) {}
  void UserSteppingAction(const G4Step* step) override {
    try { action.UserSteppingAction(step); }
    catch (...) { state->Fail(); G4RunManager::GetRunManager()->AbortEvent(); }
  }
};

class ParallelActions final : public G4VUserActionInitialization {
  const Detector& detector;
  const PeriodConditions& conditions;
  const rootreplay::Input& truth;
  OrderedTransport& writer;
  bool compact;
public:
  class FailedPrimary final : public G4VUserPrimaryGeneratorAction {
    void GeneratePrimaries(G4Event* event) override {
      event->SetEventAborted();
      G4RunManager::GetRunManager()->AbortRun(true);
    }
  };
  ParallelActions(const Detector& detector, const PeriodConditions& conditions,
                  const rootreplay::Input& truth, OrderedTransport& writer, bool compact)
      : detector(detector), conditions(conditions), truth(truth), writer(writer), compact(compact) {}
  void Build() const override {
    try {
      auto state = std::make_shared<WorkerState>(detector, conditions, writer, compact);
      auto primary = std::make_unique<WorkerPrimary>(state, truth);
      auto event = std::make_unique<WorkerEvent>(state, detector);
      auto step = std::make_unique<WorkerStep>(state, detector);
      SetUserAction(primary.release());
      SetUserAction(event.release());
      SetUserAction(step.release());
      // G4MTRunManager owns per-event seeds; never reseed at run start.
    } catch (...) {
      writer.Fail(std::current_exception());
      // Keep Geant4's mandatory primary-action contract even on failed setup.
      SetUserAction(new FailedPrimary);
    }
  }
};
