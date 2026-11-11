#include "CylinderTracking.hh"
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
using namespace cylindertracking;
static int bits(float value) { std::int32_t result; std::memcpy(&result,&value,4); return result; }
static void selftest() {
  auto c=old_cyl_simulation_config(); Digits d;
  auto r=reconstruct(d,c); assert(r.unsupported==0 && r.tracks.empty() && r.legacy_status==0);
  d.wires[0].assign(21,1); r=reconstruct(d,c); assert(r.wire_status[0]==1 && r.legacy_status==10);
  d={}; d.cathodes[0]={{61,1}}; assert(reconstruct(d,c).unsupported==InvalidDigit);
  d={}; d.cathodes[0].assign(65,{1,1}); assert(reconstruct(d,c).unsupported==RawCapacityExceeded);
  // Original local lists are initialized only through active NB1=60, even
  // though the physical COMMON array capacity is64. Repeated valid strip IDs
  // do not make source input slots61..64 defined.
  for(int length:{61,62,63,64}) {
    d={};d.cathodes[0].assign(length,{1,10});
    assert(reconstruct(d,c).unsupported==RawCapacityExceeded);
  }
  d={}; c.cathodes[0].gain[0]=std::numeric_limits<float>::quiet_NaN(); assert(reconstruct(d,c).unsupported==InvalidConfig);
  c=old_cyl_simulation_config();
  // The original length5 IND_BAND*_TEMP scratch arrays cannot accept6 candidates.
  for(auto& cc:c.cathodes) { cc.a=0; cc.b=-1; cc.c=0; cc.min_multiplicity=1; }
  d={}; d.wires[0]={1}; d.cathodes[1]={{1,10}};
  for(int k=1;k<=16;k+=3) d.cathodes[0].push_back({k,10});
  assert(reconstruct(d,c).unsupported==CathodeCandidateScratchOverflow);
  c=old_cyl_simulation_config();
  for(auto& cc:c.cathodes) { cc.a=0; cc.b=-1; cc.c=0; cc.width_cm=40; }
  d={}; d.wires[0]={1}; d.wires[1]={1};
  for(auto& cathode:d.cathodes) cathode={{10,10},{11,10}};
  c.dphi_cut_deg=.46875f;
  assert(reconstruct(d,c).tracks.size()==1); // DPHI equality is inclusive.
  c.dphi_cut_deg=std::nextafter(.46875f,0.f);
  assert(reconstruct(d,c).tracks.empty());
  c.dphi_cut_deg=8;
  c.z_max_cm[0]=4.f;
  assert(reconstruct(d,c).associations[0].size()==1); // ZMAX inclusive.
  c.z_max_cm[0]=std::nextafter(4.f,0.f);
  assert(reconstruct(d,c).associations[0].empty());
  c.z_max_cm[0]=39.f; c.cathodes[1].offset_cm=.45f; c.dz_cut_cm[0]=.25f;
  assert(reconstruct(d,c).associations[0].empty()); // DZ equality is strict.
  c.dz_cut_cm[0]=std::nextafter(.25f,1.f);
  assert(reconstruct(d,c).associations[0].size()==1);
  float theta=0,phi=0;
  assert(calculate_angles({0,0,0},{0,1,0},theta,phi) && theta==90.f && phi==0.f);
  assert(!calculate_angles({0,0,0},{0,0,0},theta,phi) && theta==0.f && phi==0.f);
  std::cout << "cylinder tracking fixtures passed\n";
}
int main(int argc,char** argv) {
  if(argc>1 && std::string(argv[1])=="--selftest") { selftest(); return 0; }
  int count; std::cin>>count;
  while(count--) {
    int mode; std::cin>>mode;
    if(mode==2) {
      std::array<float,3> a,b; for(auto& x:a) std::cin>>x; for(auto& x:b) std::cin>>x;
      float theta,phi; const bool ok=calculate_angles(a,b,theta,phi);
      std::cout<<ok<<' '<<bits(theta)<<' '<<bits(phi)<<'\n'; continue;
    }
    Config c=old_cyl_simulation_config();
    if(mode==1) {
      for(auto& cc:c.cathodes) std::cin>>cc.a>>cc.b>>cc.c>>cc.width_cm>>cc.offset_cm>>cc.strip_threshold>>cc.overlap>>cc.min_multiplicity>>cc.min_charge;
      for(int ch=0;ch<2;++ch) std::cin>>c.phi_offset_deg[ch]>>c.z_min_cm[ch]>>c.z_max_cm[ch]>>c.dz_cut_cm[ch];
      std::cin>>c.dphi_cut_deg;
    }
    Digits d;
    for(auto& wires:d.wires) { int n; std::cin>>n; for(int i=0;i<n;++i) { int w; std::cin>>w; wires.push_back(w); } }
    for(auto& strips:d.cathodes) { int n; std::cin>>n; for(int i=0;i<n;++i) { StripDigit s; std::cin>>s.strip>>s.adc; strips.push_back(s); } }
    const auto r=reconstruct(d,c);
    std::cout<<r.unsupported<<' '<<r.legacy_status<<'\n';
    for(const auto& cc:c.cathodes) std::cout<<bits(cc.a)<<' '<<bits(cc.b)<<' '<<bits(cc.c)<<' '<<bits(cc.width_cm)<<'\n';
    for(int p=0;p<4;++p) {
      std::cout<<r.clusters[p].size()<<' '<<r.cathode_status[p]<<'\n';
      for(const auto& x:r.clusters[p]) std::cout<<x.multiplicity<<' '<<bits(x.center_cm)<<' '<<bits(x.charge)<<'\n';
    }
    for(int p=0;p<2;++p) {
      std::cout<<r.groups[p].size()<<' '<<r.wire_status[p]<<'\n';
      for(const auto& x:r.groups[p]) std::cout<<x.multiplicity<<' '<<bits(x.phi_deg)<<'\n';
    }
    for(int p=0;p<2;++p) {
      std::cout<<r.associations[p].size()<<' '<<r.association_status[p]<<'\n';
      for(const auto& x:r.associations[p]) std::cout<<x.multiplicity1<<' '<<x.multiplicity2<<' '<<bits(x.charge1)<<' '<<bits(x.charge2)<<' '<<bits(x.dz_cm)<<' '<<bits(x.z_cm)<<' '<<bits(x.phi_deg)<<' '<<x.cathode1<<' '<<x.cathode2<<' '<<x.wire_group<<'\n';
    }
    std::cout<<r.tracks.size()<<'\n';
    for(const auto& t:r.tracks) {
      std::cout<<t.inner_association<<' '<<t.outer_association<<' '<<bits(t.dz_inner_cm)<<' '<<bits(t.dz_outer_cm)<<' ';
      for(float x:t.inner_cm) std::cout<<bits(x)<<' ';
      for(float x:t.outer_cm) std::cout<<bits(x)<<' ';
      std::cout<<bits(t.dphi_deg)<<' '<<bits(t.theta_deg)<<' '<<bits(t.phi_deg)<<' '<<bits(t.z_vertex_cm)<<'\n';
    }
  }
}
