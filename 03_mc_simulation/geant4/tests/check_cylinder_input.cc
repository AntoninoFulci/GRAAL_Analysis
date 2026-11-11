#include "LegacyCylinderInput.hh"
#include <cassert>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
using namespace legacy_cylinder;
static Step step(int role, float energy=0, std::uint64_t epoch=1) {
  static std::uint64_t row=0;
  Step s; s.role=role; s.edep_GeV=energy; s.passive_epoch=epoch;
  s.source_row=row; s.callback_index=2*row+2; ++row;
  s.charged=true; s.entrance=true; s.xyz_cm={{1,2,3}}; return s;
}
static int source_replay() {
  int events;std::cin>>events;Accumulator a;
  std::uint64_t source=0,callback=0,epoch=0;
  for(int event=0;event<events;++event) {
    a.begin_event(1,event);int steps;std::cin>>steps;
    for(int i=0;i<steps;++i) {
      Step s;int charged,entrance;
      std::cin>>s.role>>charged>>entrance>>s.xyz_cm[0]>>s.xyz_cm[1]>>s.xyz_cm[2]>>s.edep_GeV;
      s.charged=charged!=0;s.entrance=entrance!=0;
      if(s.role<1 || s.role>14)++epoch;
      else {
        s.source_row=source++;s.callback_index=callback;s.passive_epoch=epoch;
        if(s.role==6 || s.role==7 || s.role==10 || s.role==11)a.observe(s);
      }
      ++callback;
    }
    a.end_event();
    const auto& e=a.events().back();std::cout<<e.raw_counts[0]<<' '<<e.raw_counts[1]<<'\n';
    auto bits=[](float v){std::int32_t b;std::memcpy(&b,&v,4);return b;};
    for(int ch=0;ch<2;++ch)for(std::size_t i=e.crossing_begin;i<e.crossing_end;++i) {
      const auto& c=a.crossings()[i];if(c.chamber!=ch)continue;
      for(float v:c.xyz_cm)std::cout<<bits(v)<<' ';
      std::cout<<bits(c.raw_gas_GeV)<<' '<<bits(c.digitizer_GeV)<<'\n';
    }
  }
  a.finish();return 0;
}
int main(int argc,char**) {
  if(argc>1)return source_replay();
  {
    Accumulator a; a.begin_event(1,0);
    a.observe(step(10,1)); a.observe(step(6)); a.observe(step(10,2));
    a.observe(step(10)); a.observe(step(11,3)); a.end_event(); a.finish();
    assert(a.crossings().size()==1 && a.crossings()[0].raw_gas_GeV==3);
    assert(a.crossings()[0].contribution_count==2);
    assert(a.gas_links().size()==4 && a.gas_links()[0].state==GasState::Assigned);
    assert(a.gas_links()[2].state==GasState::Zero);
    assert(a.gas_links()[3].state==GasState::Unsupported);
    assert(a.events()[0].status&InputInvalidIndex);
  }
  {
    Accumulator a; a.begin_event(1,0); a.observe(step(10,.25f)); a.end_event();
    a.begin_event(1,1); a.observe(step(7)); a.observe(step(11,.5f)); a.end_event(); a.finish();
    assert(a.crossings()[0].raw_gas_GeV==.75f);
    assert(a.gas_links()[0].state==GasState::Assigned && a.gas_links()[0].target_event_index==1);
    assert(a.events()[0].cross_event_assigned_GeV==.25);
    assert(a.events()[1].imported_pending_GeV==.25);
  }
  {
    Accumulator a; a.begin_event(1,0); a.observe(step(10,.25f)); a.end_event();
    a.begin_event(1,1); a.observe(step(6,0,2)); a.end_event(); a.finish();
    assert(a.gas_links()[0].state==GasState::DiscardedPassive);
    assert(a.events()[0].discarded_pending_GeV==.25);
    assert(a.crossings()[0].raw_gas_GeV==0 && a.crossings()[0].floor_applied);
    assert(a.crossings()[0].digitizer_GeV==1.e-7f);
  }
  {
    Accumulator a; a.begin_event(1,0); a.observe(step(6,0,0)); a.observe(step(10,.1f,0));
    a.end_event(); a.begin_event(1,1); a.observe(step(10,.2f,0)); a.end_event(); a.finish();
    assert(a.events()[0].status&InputStateUnknown);
    assert(a.events()[1].status&InputInvalidIndex);
    assert(!a.events()[1].source_state_known);
  }
  {
    Accumulator a; a.begin_event(1,0);
    for(int i=0;i<21;++i) a.observe(step(6));
    a.observe(step(10,1)); a.end_event(); a.finish();
    assert(a.crossings().size()==21 && a.events()[0].raw_counts[0]==21);
    assert(a.events()[0].retained_counts[0]==20 && (a.events()[0].status&InputOverflow));
    assert(!a.crossings().back().source_retained);
    assert(a.gas_links()[0].state==GasState::Unsupported);
  }
  {
    Accumulator a; a.begin_event(1,0); a.observe(step(10,.25f)); a.end_event(); a.finish();
    assert(a.gas_links()[0].state==GasState::UnresolvedEnd);
    assert(a.events()[0].status&InputUnresolvedPending);
  }
  {
    // A validated final transport epoch proves the reset after the last
    // central row, even when the rest of this event is entirely passive.
    Accumulator a;a.begin_event(1,0);a.observe(step(10,.25f));a.end_event();a.finish(2);
    assert(a.gas_links()[0].state==GasState::DiscardedPassive);
    assert(a.events()[0].discarded_pending_GeV==.25);
    assert(!(a.events()[0].status&InputUnresolvedPending));
    assert(a.events()[0].legacy_eligible());
    a.finish(2); // Same final evidence is idempotent.
  }
  {
    // Equality supplies no reset evidence: preserve genuine stream-tail gas.
    Accumulator a;a.begin_event(1,0);a.observe(step(10,.25f));a.end_event();a.finish(1);
    assert(a.gas_links()[0].state==GasState::UnresolvedEnd);
    assert(a.events()[0].status&InputUnresolvedPending);
    assert(a.events()[0].discarded_pending_GeV==0);
  }
  {
    Accumulator a;a.begin_event(1,0);a.observe(step(10,.25f,3));a.end_event();
    bool caught=false;try{a.finish(2);}catch(const std::invalid_argument&){caught=true;}
    assert(caught && a.gas_links()[0].state==GasState::Pending);
    a.finish(3);assert(a.gas_links()[0].state==GasState::UnresolvedEnd);
  }
  {
    // A passive-only last event need not have any central context rows.
    Accumulator a;a.begin_event(1,0);a.observe(step(10,.25f));a.end_event();
    a.begin_event(1,1);a.end_event();a.finish(2);
    assert(a.events().size()==2 && a.events()[1].raw_counts[0]==0);
    assert(a.events()[0].discarded_pending_GeV==.25 && a.events()[1].status==InputOk);
    Accumulator none;none.begin_event(1,0);none.end_event();none.finish(10);
    assert(none.events().size()==1 && none.gas_links().empty() && none.crossings().empty());
    Accumulator empty;empty.finish(0);assert(empty.events().empty());
  }
  {
    Accumulator a; a.begin_event(1,0); auto s=step(10,1);
    a.observe(s); bool caught=false; try{a.observe(s);}catch(const std::invalid_argument&){caught=true;}
    assert(caught); a.end_event(); a.finish();
  }
  {
    Accumulator a; a.begin_event(1,0); auto s=step(10); s.edep_GeV=std::nanf("");
    a.observe(s); a.end_event(); a.finish();
    assert(a.events()[0].status&InputInvalidStep);
  }
  {
    // Independent source-deposit accounting, including resolution across the
    // event boundary and discard at a passive zero-deposit callback.
    Accumulator a;a.begin_event(1,0);a.observe(step(10,.125f));a.end_event();
    a.begin_event(1,1);a.observe(step(7));a.observe(step(11,.25f));
    a.observe(step(10,.5f,2));a.end_event();
    a.begin_event(1,2);a.observe(step(6,0,3));a.observe(step(10,.0625f,3));a.end_event();a.finish();
    double input=0,assigned=0,discarded=0,unsupported=0,tail=0;
    for(const auto& e:a.events())input+=e.gas_input_GeV;
    for(const auto& l:a.gas_links()) {
      assert(l.state!=GasState::Pending);
      if(l.state==GasState::Assigned) {
        assigned+=l.energy_GeV;assert(l.crossing>=0 && l.target_event_index>=0);
      }
      else if(l.state==GasState::DiscardedPassive)discarded+=l.energy_GeV;
      else if(l.state==GasState::Unsupported)unsupported+=l.energy_GeV;
      else if(l.state==GasState::UnresolvedEnd)tail+=l.energy_GeV;
    }
    assert(input==assigned+discarded+unsupported+tail);
    assert(assigned==.4375 && discarded==.5 && unsupported==0 && tail==0);
  }
  std::cout << "cylinder input fixtures passed\n";
}
