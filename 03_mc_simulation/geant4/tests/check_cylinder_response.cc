#include "LegacyCylinderResponse.hh"
#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>
#include <string>
using namespace legacy_cylinder;
static Config fixture() {
  return {{{5,8.5}},{{20,25.25}},{{.9f,.9f}},{{128,192}},{{60,64,96,96}},
          .35f,.4f,1024,400000,16.e10f,6000,{{2300,2300,2300,2300}},.13f,
          {{33.86f,-41.01f,41.01f,-46.63f}},{{1,1}},2};
}
static std::int32_t bits(float value) {std::int32_t b;std::memcpy(&b,&value,4);return b;}
int main(int argc,char**) {
  if(argc>1) {
    auto c=fixture(); auto zero=[](){return 0.f;};auto yes=[](int){return 1.f;};
    auto empty=digitize({},c,zero,yes);
    assert(empty.status==ResponseOk && empty.normal_draws==316 && empty.efficiency_histograms.empty());
    for(const auto& d:empty.cathodes) assert(d.empty());
    auto noisy=digitize({},c,[](){return 4.f;},yes);
    for(int k=0;k<4;++k) assert(noisy.cathodes[k].size()==static_cast<std::size_t>(c.nb[k]));
    auto saturated=digitize({},c,[](){return 1000.f;},yes);
    for(auto& v:saturated.cathodes) for(auto d:v) assert(d.adc==1024);
    std::vector<CrossingInput> hits{{0,{{3,4,0}},1.e-6f,0},{0,{{3,4,0}},1.e-6f,1},
                                    {1,{{3,4,0}},1.e-6f,2},{1,{{3,4,0}},1.e-6f,3}};
    auto d=digitize(hits,c,zero,yes);
    assert(d.status==ResponseOk && d.normal_draws==320 && d.efficiency_histograms==std::vector<int>({1001,1001,1002}));
    assert(d.wires[0].size()==1 && d.wires[1].size()==1 && d.charge_links.size()==72);
    assert(d.associations[1].state==WireState::Duplicate && d.associations[3].state==WireState::Duplicate);
    auto lost=digitize(hits,c,zero,[](int){return 0.f;});
    assert(lost.wires[0].empty() && lost.wires[1].empty() && lost.efficiency_histograms.size()==4);
    assert(lost.charges==d.charges); // cathode charge precedes efficiency
    auto invalid=hits;invalid[0].energy_GeV=std::numeric_limits<float>::infinity();
    assert(digitize(invalid,c,zero,yes).status&ResponseInvalidCrossing);
    assert(digitize(hits,c,[](){return std::numeric_limits<float>::infinity();},yes).status&ResponseInvalidDraw);
    assert(digitize(hits,c,zero,[](int){return -1.f;}).status&ResponseInvalidDraw);
    c.dfca=0;assert(digitize({},c,zero,yes).status&ResponseInvalidConfig);
    c=fixture();std::vector<CrossingInput> overflow(21,hits[0]);
    auto over=digitize(overflow,c,zero,yes);
    assert((over.status&ResponseOverflow) && over.normal_draws==0);
    assert(digitize({},c,[](){return 1.e30f;},yes).status&ResponseArithmetic);
    c.angle_deg[0]=90;assert(digitize({},c,zero,yes).status&ResponseInvalidConfig);
    std::cout << "cylinder response fixtures passed\n";return 0;
  }
  int cases;std::cin>>cases;
  while(cases--) {
    Config c;
    for(auto&v:c.rc) std::cin>>v;for(auto&v:c.zc) std::cin>>v;for(auto&v:c.pc) std::cin>>v;
    for(auto&v:c.nfc) std::cin>>v;for(auto&v:c.nb) std::cin>>v;
    std::cin>>c.bl>>c.dfca>>c.sccat>>c.vsccat>>c.conv>>c.cythre;
    for(auto&v:c.sigce) std::cin>>v;std::cin>>c.sigct;
    for(auto&v:c.angle_deg) std::cin>>v;for(auto&v:c.effcyc) std::cin>>v;std::cin>>c.nbord;
    int n;std::cin>>n;std::vector<CrossingInput> hits;
    for(int i=0;i<n;++i) {CrossingInput h;std::cin>>h.chamber>>h.xyz_cm[0]>>h.xyz_cm[1]>>h.xyz_cm[2]>>h.energy_GeV;h.source_crossing=i;hits.push_back(h);}
    std::size_t ng,ne;std::cin>>ng;std::vector<float> normal(ng);for(auto&v:normal) std::cin>>v;
    std::cin>>ne;std::vector<float> efficiency(ne);for(auto&v:efficiency) std::cin>>v;
    std::size_t gi=0,ei=0;auto d=digitize(hits,c,[&](){return normal.at(gi++);},[&](int){return efficiency.at(ei++);});
    assert(d.status==ResponseOk);
    std::cout<<d.wires[0].size()<<' '<<d.wires[1].size()<<' '<<gi<<' '<<ei<<'\n';
    for(int h:d.efficiency_histograms) std::cout<<h<<' ';std::cout<<'\n';
    for(auto&v:d.wires) {for(int w:v)std::cout<<w<<' ';std::cout<<'\n';}
    for(int k=0;k<4;++k) {
      std::cout<<d.cathodes[k].size()<<'\n';
      for(auto s:d.cathodes[k])std::cout<<s.strip<<' '<<s.adc<<' ';std::cout<<'\n';
      for(float v:d.charges[k])std::cout<<bits(v)<<' ';std::cout<<'\n';
      for(bool v:d.read_flags[k])std::cout<<static_cast<int>(v)<<' ';std::cout<<'\n';
    }
  }
}
