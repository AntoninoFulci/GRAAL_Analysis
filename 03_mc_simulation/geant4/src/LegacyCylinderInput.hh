#ifndef GRAAL_LEGACY_CYLINDER_INPUT_HH
#define GRAAL_LEGACY_CYLINDER_INPUT_HH
// Offline source-state replay. Only central rows are observed; passive epochs
// come from ALL transport callbacks. Neither tracks nor event starts reset SAVE.
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace legacy_cylinder {
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559 &&
              std::numeric_limits<float>::digits==24, "requires IEEE binary32");
enum InputStatus : std::uint32_t {
  InputOk=0, InputStateUnknown=1u<<0, InputOverflow=1u<<1,
  InputInvalidIndex=1u<<2, InputInvalidStep=1u<<3,
  InputArithmetic=1u<<4, InputUnresolvedPending=1u<<5
};
enum class GasState : int {
  Pending=0, Assigned=1, DiscardedPassive=2, Unsupported=3, Zero=4,
  UnresolvedEnd=5
};
struct Step {
  int role=0;
  bool charged=false, entrance=false;
  std::array<float,3> xyz_cm{};
  float edep_GeV=0;
  std::uint64_t source_row=0, callback_index=0, passive_epoch=0;
};
struct InputEvent {
  int run=0,event=0;
  std::array<std::size_t,2> raw_counts{},retained_counts{};
  bool source_state_known=false;
  std::uint32_t status=InputOk;
  // Accounting is double sums of source binary32 deposits; raw_gas is the
  // source's rounded binary32 accumulator. They need not be bitwise equal.
  double gas_input_GeV=0, discarded_pending_GeV=0, unsupported_gas_GeV=0;
  double cross_event_assigned_GeV=0, imported_pending_GeV=0;
  std::size_t crossing_begin=0,crossing_end=0, gas_begin=0,gas_end=0;
  bool legacy_eligible() const { return status==InputOk; }
};
struct InputCrossing {
  std::size_t event_index=0;
  int chamber=0; // 0 inner, 1 outer
  std::size_t crossing_index=0; // zero-based within chamber/event
  std::uint64_t source_row=0,callback_index=0,passive_epoch=0;
  std::array<float,3> xyz_cm{};
  float raw_gas_GeV=0,digitizer_GeV=0;
  bool floor_applied=false,source_retained=true;
  std::size_t contribution_count=0;
};
struct GasLink {
  std::size_t event_index=0;
  int chamber=0;
  std::uint64_t source_row=0,callback_index=0,passive_epoch=0;
  float energy_GeV=0;
  GasState state=GasState::Pending;
  std::int64_t crossing=-1,target_event_index=-1;
};
class Accumulator {
 public:
  void begin_event(int run,int event) {
    if(active_ || finished_) throw std::logic_error("invalid cylinder event lifecycle");
    for(const auto& e:events_) if(e.run==run && e.event==event)
      throw std::invalid_argument("duplicate cylinder event key");
    InputEvent e; e.run=run;e.event=event;e.source_state_known=known_;
    e.crossing_begin=crossings_.size();e.gas_begin=links_.size();
    events_.push_back(e); current_=events_.size()-1;
    last_crossing_={{-1,-1}}; active_=true;
  }
  void observe(const Step& s) {
    if(!active_ || finished_) throw std::logic_error("cylinder observation outside event");
    if(s.role!=6 && s.role!=7 && s.role!=10 && s.role!=11)
      throw std::invalid_argument("context must reference a central sensitive step");
    if(s.callback_index<s.source_row || s.passive_epoch>s.callback_index ||
       (have_context_ && (s.source_row<=last_row_ || s.callback_index<=last_callback_ ||
        s.passive_epoch<last_epoch_ || s.passive_epoch-last_epoch_>s.callback_index-last_callback_)))
      throw std::invalid_argument("invalid cylinder source/callback/epoch ordering");
    if(s.passive_epoch>last_epoch_) {
      dispose_pending(GasState::DiscardedPassive);
      touched_=false; degas_=0; known_=true;
    }
    have_context_=true;last_row_=s.source_row;last_callback_=s.callback_index;last_epoch_=s.passive_epoch;
    auto& e=events_[current_];e.source_state_known=known_;
    const int chamber=(s.role==6 || s.role==10)?0:1;
    if(s.role==6 || s.role==7) {
      if(!s.charged || !s.entrance) return;
      const std::size_t index=e.raw_counts[chamber]++;
      InputCrossing c;c.event_index=current_;c.chamber=chamber;c.crossing_index=index;
      c.source_row=s.source_row;c.callback_index=s.callback_index;c.passive_epoch=s.passive_epoch;c.xyz_cm=s.xyz_cm;
      c.source_retained=index<20;
      if(!c.source_retained) e.status|=InputOverflow;
      else {++e.retained_counts[chamber];touched_=true;}
      for(float v:s.xyz_cm) if(!std::isfinite(v)) e.status|=InputInvalidStep;
      crossings_.push_back(c);last_crossing_[chamber]=static_cast<std::int64_t>(crossings_.size()-1);
      return;
    }
    GasLink link;link.event_index=current_;link.chamber=chamber;link.source_row=s.source_row;
    link.callback_index=s.callback_index;link.passive_epoch=s.passive_epoch;link.energy_GeV=s.edep_GeV;
    links_.push_back(link); const std::size_t li=links_.size()-1;
    if(!std::isfinite(s.edep_GeV) || s.edep_GeV<0) {
      e.status|=InputInvalidStep;links_[li].state=GasState::Unsupported;return;
    }
    e.gas_input_GeV+=s.edep_GeV;
    if(s.edep_GeV==0) {links_[li].state=GasState::Zero;return;}
    if(!known_) e.status|=InputStateUnknown;
    if(!touched_) {
      degas_=degas_+s.edep_GeV;pending_.push_back(li);
      if(!std::isfinite(degas_)) e.status|=InputArithmetic;
      return;
    }
    const auto ci=last_crossing_[chamber];
    if(ci<0 || !crossings_[static_cast<std::size_t>(ci)].source_retained) {
      e.status|=InputInvalidIndex;
      pending_.push_back(li);dispose_pending(GasState::Unsupported);degas_=0;return;
    }
    auto& c=crossings_[static_cast<std::size_t>(ci)];
    // Keep source evaluation order: DECI = (DECI + DEGAS) + DESTEP.
    c.raw_gas_GeV=(c.raw_gas_GeV+degas_)+s.edep_GeV;
    if(!std::isfinite(c.raw_gas_GeV)) e.status|=InputArithmetic;
    pending_.push_back(li);
    for(std::size_t index:pending_) {
      auto& l=links_[index];l.state=GasState::Assigned;l.crossing=ci;l.target_event_index=static_cast<std::int64_t>(current_);
      ++c.contribution_count;
      if(l.event_index!=current_) {
        events_[l.event_index].cross_event_assigned_GeV+=l.energy_GeV;
        e.imported_pending_GeV+=l.energy_GeV;
      }
    }
    pending_.clear();degas_=0;
  }
  void end_event() {
    if(!active_) throw std::logic_error("no active cylinder event");
    auto& e=events_[current_];e.crossing_end=crossings_.size();e.gas_end=links_.size();
    for(std::size_t i=e.crossing_begin;i<e.crossing_end;++i) {
      auto& c=crossings_[i];c.floor_applied=c.source_retained && c.raw_gas_GeV==0;
      c.digitizer_GeV=c.floor_applied?1.e-7f:c.raw_gas_GeV;
    }
    active_=false;
  }
  // Supply the validated final transport passive_callbacks epoch. A larger
  // epoch proves a passive reset after the last central row, including in a
  // passive-only tail/event. Equality supplies no such disposal evidence.
  // The caller validates this summary against the complete transport stream.
  void finish(std::uint64_t final_passive_epoch) {
    if(active_) throw std::logic_error("finish with active cylinder event");
    if(final_passive_epoch<last_epoch_)
      throw std::invalid_argument("final cylinder passive epoch decreases");
    if(finished_) {
      if(final_passive_epoch!=last_epoch_)
        throw std::logic_error("cylinder stream already finalized with different epoch");
      return;
    }
    if(final_passive_epoch>last_epoch_) {
      dispose_pending(GasState::DiscardedPassive);
      touched_=false;degas_=0;known_=true;last_epoch_=final_passive_epoch;
    } else dispose_pending(GasState::UnresolvedEnd);
    finished_=true;
  }
  // Compatibility for callers without final transport evidence: conservatively
  // mark pending links unresolved, never invent a stream-tail passive reset.
  void finish() {finish(last_epoch_);}
  const std::vector<InputEvent>& events() const {return events_;}
  const std::vector<InputCrossing>& crossings() const {return crossings_;}
  const std::vector<GasLink>& gas_links() const {return links_;}
 private:
  void dispose_pending(GasState state) {
    for(std::size_t i:pending_) {
      auto& l=links_[i];l.state=state;auto& e=events_[l.event_index];
      if(state==GasState::DiscardedPassive) e.discarded_pending_GeV+=l.energy_GeV;
      else if(state==GasState::Unsupported) {e.unsupported_gas_GeV+=l.energy_GeV;e.status|=InputInvalidIndex;}
      else if(state==GasState::UnresolvedEnd) e.status|=InputUnresolvedPending;
    }
    pending_.clear();
  }
  bool active_=false,finished_=false,known_=false,touched_=false,have_context_=false;
  float degas_=0; // Declared safe initialization extension; epoch0 is unknown.
  std::size_t current_=0;
  std::uint64_t last_row_=0,last_callback_=0,last_epoch_=0;
  std::array<std::int64_t,2> last_crossing_{{-1,-1}};
  std::vector<InputEvent> events_;
  std::vector<InputCrossing> crossings_;
  std::vector<GasLink> links_;
  std::vector<std::size_t> pending_;
};
} // namespace legacy_cylinder
#endif
