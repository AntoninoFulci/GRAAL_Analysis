#include "ForwardDigitization.hh"
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
using namespace forward26;
static void selftest() {
  auto w=GroupWallSteps({{1,.001f,0,2e-9f},{1,.002f,4,1e-9f},{1,.003f,5,0},{2,.001f,0,0},{1,.001f,0,0}});
  assert(w.records.size()==4 && w.records[0].position_cm==2 && w.records[0].time_s==2e-9f);
  assert(w.source_indices[0]==std::vector<std::size_t>({0,1}));
  auto s=GroupShowerSteps({{1,.001f,0,1e-9f},{2,.001f,0,0},{1,.001f,9,2e-9f},{1,.001f,18,2e-9f}});
  assert(s.records.size()==3 && s.records[0].position_cm==4.5f && s.records[0].time_s==1e-9f);
  auto consecutive=GroupShowerSteps({{1,.001f,0,1e-9f},{1,.001f,9,100e-9f}});
  assert(consecutive.records.size()==1); // consecutive SHOW has no time condition
  auto ten=GroupShowerSteps({{1,.001f,0,0},{2,.001f,0,0},{1,.001f,0,10e-9f}});
  assert(ten.records.size()==3);
  std::vector<CompactHit> many;
  for(int i=0;i<101;++i) many.push_back({1,.001f,float(i*10),0});
  auto overflow=GroupWallSteps(many);assert(overflow.overflow && overflow.records.size()==101 && overflow.source_indices.back()[0]==100);
  Config c;c.shower=Run340ShowConfig();c.tdccal.fill(1);c.gaincards.fill(1);c.gainpms.fill(1);
  int n=0;auto rng=[&](){++n;return 0.f;};
  auto bad=DigitizeWall({},{{14,.1f,0,0}},c,rng);assert(bad.status==UndefinedHorizontalCounterpart && n==0);
  auto over=DigitizeWall(many,{},c,rng);assert(over.status==CompactOverflow && n==0);
  auto sh=DigitizeShower(many,c,rng);assert(sh.status==CompactOverflow && n==0);
  c.tdcoffset.fill(-1000);
  auto neg=DigitizeWall({{5,.1f,0,0}},{},c,rng);
  assert(neg.status==NegativeTimePartialWrite && neg.horizontal.size()==1 && neg.time_draws==1 && neg.horizontal[0].tdc[0]==0);
  bool threw=false;try { GroupWallSteps({{27,.1f,0,0}}); } catch(const std::invalid_argument&) { threw=true; } assert(threw);
  std::cout<<"forward response fixtures passed\n";
}
static void print(const std::vector<Digit>& d) {
  std::cout<<d.size()<<'\n';
  for(const auto& x:d) std::cout<<x.channel<<' '<<x.adc[0]<<' '<<x.adc[1]<<' '<<x.tdc[0]<<' '<<x.tdc[1]<<' '<<x.status<<'\n';
}
static int compact() {
  int cases;std::cin>>cases;
  while(cases--) {
    int role,n;std::cin>>role>>n;std::vector<CompactHit> steps(n);
    for(auto& h:steps) std::cin>>h.channel>>h.energy_GeV>>h.position_cm>>h.time_s;
    auto result=role==5?GroupShowerSteps(steps):GroupWallSteps(steps);
    std::cout<<result.records.size()<<'\n';
    for(const auto& h:result.records) {
      auto bits=[](float x){std::int32_t b;std::memcpy(&b,&x,4);return b;};
      std::cout<<h.channel<<' '<<bits(h.energy_GeV)<<' '<<bits(h.position_cm)<<' '<<bits(h.time_s)<<'\n';
    }
  }
  return 0;
}
int main(int argc,char**argv) {
  if(argc>1 && std::string(argv[1])=="--compact") return compact();
  if(argc>1 && std::string(argv[1])=="--selftest") { selftest();return 0; }
  Config c;c.shower=Run340ShowConfig();
  for(auto* a:{&c.pedestals,&c.tdccal,&c.gaincards,&c.timewalk,&c.tdcoffset,&c.gainpms}) for(float& x:*a) std::cin>>x;
  int count;std::cin>>count;
  while(count--) {
    int nh,nv,ns;std::cin>>nh>>nv>>ns;
    std::vector<CompactHit> h(nh),v(nv),s(ns);
    for(auto* a:{&h,&v,&s}) for(auto& x:*a) std::cin>>x.channel>>x.energy_GeV>>x.position_cm>>x.time_s;
    int nd;std::cin>>nd;std::vector<float> draws(nd);for(auto& x:draws) std::cin>>x;
    std::size_t cursor=0;auto rng=[&](){return draws.at(cursor++);};
    auto w=DigitizeWall(h,v,c,rng);auto sh=DigitizeShower(s,c,rng);
    std::cout<<w.energy_draws+w.time_draws<<' '<<sh.energy_draws+sh.time_draws<<'\n';
    print(w.horizontal);print(w.vertical);print(sh.digits);
  }
}
