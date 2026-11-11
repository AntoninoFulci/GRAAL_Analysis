#include "CentralAssociation.hh"
#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>
#include <string>
using namespace centralassociation;
Config fixture_config(bool sp=true) {
  std::array<float,32> phi{},xba{};
  for(int i=0;i<32;++i) { phi[i]=i*11.25f; xba[i]=.07f; }
  return source_config(phi,xba,sp);
}
void selftest() {
  auto c=fixture_config(); Input in;
  auto r=find_track_cbb(in,c); assert(r.status==Supported && r.associations.empty());
  in.good_bgo={{90,0,90,0,123}}; in.barrel={{1,0,2,3}};
  r=find_track_cbb(in,c);
  assert(r.status==UndefinedNoCylinder && r.associations.empty() && r.diagnostic_links.size()==2);
  in.cylinder={{90,0}}; r=find_track_cbb(in,c);
  assert(r.status==Supported && r.associations.size()==1);
  const auto a=r.associations[0];
  assert(a.bgo==1 && a.barrel==1 && a.cylinder==1 && a.type==14);
  assert(a.theta_deg==90 && a.phi_deg==0 && a.barrel_time==3 && a.barrel_channel==1);
  assert(std::abs(a.dedx-4*std::exp(.035f))<.00001f);
  in.good_bgo={{90,0,90,0,1},{90,0,90,0,2}};
  in.cylinder={{90,0},{90,0}}; in.barrel.clear();
  r=find_track_cbb(in,c); assert(r.stage2[0].bgo==2 && r.stage2[0].cylinder==2);
  in={}; in.sp_bgo={{60,45,70,47,10}};
  r=find_track_cbb(in,c); assert(r.status==Supported && r.associations[0].theta_deg==70);
  in.barrel={{1,0,1,1}}; in.cylinder={{60,45}};
  r=find_track_cbb(in,c); assert(r.status==Supported && r.stage2[0].cylinder==1);
  c.enable_bgo_sp=false; r=find_track_cbb(in,c); assert(r.status==DisabledSpInput);
  c=fixture_config(); in={}; in.barrel={{1,-4,1,1}};
  assert(find_track_cbb(in,c).status==InvalidInput);
  in={}; in.good_bgo.resize(31); assert(find_track_cbb(in,c).status==CapacityExceeded);
  in={}; in.cylinder.resize(6); assert(find_track_cbb(in,c).status==CapacityExceeded);
  in={}; in.barrel.resize(33); assert(find_track_cbb(in,c).status==CapacityExceeded);
  in={}; in.cylinder={{90,std::numeric_limits<float>::quiet_NaN()}};
  assert(find_track_cbb(in,c).status==InvalidInput);
  in={}; in.barrel={{33,0,1,1}}; assert(find_track_cbb(in,c).status==InvalidInput);
  in={}; in.cylinder={{181,0}}; assert(find_track_cbb(in,c).status==InvalidInput);
  in={}; in.barrel={{1,0,1,1}}; c.xba1[0]=std::numeric_limits<float>::quiet_NaN();
  assert(find_track_cbb(in,c).status==InvalidConfig);
  c=Config{}; in={}; in.barrel={{1,0,1,1}};
  assert(find_track_cbb(in,c).status==InvalidConfig);
  c=fixture_config(); in={}; in.good_bgo={{0,0,0,0,1}}; in.barrel={{1,0,2,3}}; in.cylinder={{0,0}};
  r=find_track_cbb(in,c); assert(r.status==NonFiniteArithmetic && r.associations.empty());
  in={}; in.sp_bgo.resize(31); assert(find_track_cbb(in,c).status==CapacityExceeded);
  in={}; in.barrel={{1,-7,1,1}}; assert(find_track_cbb(in,c).status==InvalidInput);
  in={}; in.barrel={{1,0,1,1}}; c.phi_deg[0]=std::numeric_limits<float>::infinity();
  assert(find_track_cbb(in,c).status==InvalidConfig);
  c=fixture_config(); in={}; in.good_bgo={{90,0,90,0,1}}; in.cylinder={{101.5f,0}};
  r=find_track_cbb(in,c); assert(r.status==Supported && r.stage2.size()==1 && r.stage2[0].cylinder==1);
  in.cylinder={{101.501f,0}}; r=find_track_cbb(in,c); assert(r.stage2.size()==2);
  // 10 degrees in each coordinate: Euclidean source metric rejects it.
  in.cylinder={{100,10}}; r=find_track_cbb(in,c); assert(r.stage2.size()==2);
  in.good_bgo[0].matching_phi_deg=std::numeric_limits<float>::max();
  in.cylinder={{90,-std::numeric_limits<float>::max()}};
  r=find_track_cbb(in,c); assert(r.status==NonFiniteArithmetic && r.associations.empty());
  // Finite measured inputs can overflow attenuation while division by +inf
  // yields a misleading finite zero. Reject every correction intermediate.
  for(float xba:{.07f,-.07f,std::numeric_limits<float>::max()}) {
    c=fixture_config(); c.xba1[0]=xba;
    in={}; in.good_bgo={{179.999f,0,179.999f,0,1}};
    in.barrel={{1,0,2,3}}; in.cylinder={{0,0}};
    r=find_track_cbb(in,c);
    assert(r.status==NonFiniteArithmetic && r.associations.empty());
    assert(r.diagnostic_links.size()==3);
  }
  // A rejected later correction must also discard earlier final associations.
  c=fixture_config(); in={};
  in.good_bgo={{90,90,90,90,1},{179.999f,1,179.999f,1,1}};
  in.barrel={{9,0,2,3},{1,0,2,3}}; in.cylinder={{0,180}};
  r=find_track_cbb(in,c);
  assert(r.status==NonFiniteArithmetic && r.associations.empty());
  assert(r.diagnostic_links.size()==5);
  std::cout << "central association fixtures passed\n";
}
int main(int argc,char**argv) {
  if(argc>1 && std::string(argv[1])=="--selftest") { selftest(); return 0; }
  int cases; std::cin>>cases;
  while(cases--) {
    int ng,ns,nb,nc,sp; std::cin>>ng>>ns>>nb>>nc>>sp;
    std::array<float,32> phi{},xba{};
    for(int i=0;i<32;++i) std::cin>>phi[i]>>xba[i];
    auto c=source_config(phi,xba,sp!=0); Input in;
    for(int i=0;i<ng+ns;++i) {
      BgoCluster b; std::cin>>b.matching_theta_deg>>b.matching_phi_deg>>b.emitted_theta_deg>>b.emitted_phi_deg>>b.energy;
      (i<ng?in.good_bgo:in.sp_bgo).push_back(b);
    }
    for(int i=0;i<nb;++i) { Barrel b; std::cin>>b.channel>>b.problem_index>>b.energy>>b.time; in.barrel.push_back(b); }
    for(int i=0;i<nc;++i) { CylinderTrack t; std::cin>>t.theta_deg>>t.phi_deg; in.cylinder.push_back(t); }
    const auto r=find_track_cbb(in,c);
    std::cout<<r.status<<' '<<r.stage2.size()<<' '<<r.associations.size()<<' '<<r.diagnostic_links.size()<<'\n';
    for(const auto& a:r.stage2) std::cout<<a.bgo<<' '<<a.cylinder<<'\n';
    for(const auto& a:r.associations) {
      std::cout<<a.bgo<<' '<<a.barrel<<' '<<a.cylinder<<' '<<a.type<<' '<<a.barrel_channel<<' '<<a.barrel_problem_index;
      for(float f:{a.dedx,a.barrel_time,a.barrel_phi_deg,a.bgo_energy,a.bgo_theta_deg,a.bgo_phi_deg,a.cylinder_theta_deg,a.cylinder_phi_deg,a.theta_deg,a.phi_deg}) {
        int bits=0; std::memcpy(&bits,&f,sizeof(bits)); std::cout<<' '<<bits;
      }
      std::cout<<'\n';
    }
  }
}
