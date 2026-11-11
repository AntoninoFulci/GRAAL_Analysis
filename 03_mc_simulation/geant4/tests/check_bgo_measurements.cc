#include "BgoMeasurements.hh"
#include <cassert>
#include <iomanip>
#include <iostream>
#include <string>
using namespace bgomeasurements;
int main(int argc,char** argv) {
  if(argc>1&&std::string(argv[1])=="--selftest") {
    Config c=source_tables();
    assert(decode_bgo_digits({},c).status==InvalidConfig);
    c.crystal_threshold=.002f; c.cluster_threshold=.015f;
    c.bgo_adc_channels=2048; c.bgo_adc_fullscale_gev=1;
    auto g=decode_bgo_digits({{8,1,4},{8,2,5},{8,3,601}},c);
    assert(g.accepted_digits==2&&g.energy[index(8,1)]==0&&g.problem[index(8,3)]==0);
    assert(decode_bgo_digits({{0,1,10}},c).status==InvalidInput);
    assert(decode_bgo_digits(std::vector<BgoDigit>(481),c).status==CapacityExceeded);
    assert(decode_barrel({},{}).status==InvalidConfig);
    BarrelConfig bc; bc.adc_channels=1000; bc.adc_fullscale_gev=.01f;
    bc.tdc_channels=1000; bc.tdc_fullscale_seconds=1.e-7f; bc.energy_threshold_mev=1;
    auto bars=decode_barrel({{1,100,0},{2,99,12}},bc);
    assert(bars.status==0&&bars.records[0].problem_index==0&&bars.records[1].problem_index==-5);
    Grid h; h.energy[index(8,1)]=.1f; h.energy[index(8,2)]=.02f;
    auto r=measure(h,{{801,802}},{},c);
    assert(r.status==UndefinedOldShape&&r.good.size()==1&&std::isnan(r.good[0].sx1)&&std::isfinite(r.good[0].sx2));
    assert(measure(h,{{801,801}},{},c).status==InvalidInput);
    assert(measure(h,{{0}},{},c).status==InvalidInput);
    c.theta[7]=20; assert(measure(h,{{801}},{},c).status==CorrectionOutsideDomain);
    c=source_tables(); c.crystal_threshold=.002f; c.cluster_threshold=0;
    h={}; h.energy[index(2,1)]=3; r=measure(h,{{201}},{},c);
    assert(r.good[0].raw_energy==2&&r.good[0].problem_index==-3&&r.good[0].corrected_energy>3);
    std::cout<<"BGO measurement fixtures passed\n"; return 0;
  }
  int cases; std::cin>>cases; std::cout<<std::setprecision(9);
  while(cases--) {
    int nd,nc,nb,err; Config c=source_tables(); BarrelConfig bc;
    std::cin>>nd>>nc>>nb>>err>>c.crystal_threshold>>c.cluster_threshold>>c.bgo_adc_channels>>c.bgo_adc_fullscale_gev
      >>bc.adc_channels>>bc.adc_fullscale_gev>>bc.tdc_channels>>bc.tdc_fullscale_seconds>>bc.energy_threshold_mev;
    std::vector<BgoDigit> digits(nd); for(auto& d:digits) std::cin>>d.theta>>d.phi>>d.adc;
    std::vector<std::vector<int>> clusters(nc); for(auto& m:clusters) { int n; std::cin>>n; m.resize(n); for(int& x:m) std::cin>>x; }
    std::vector<BarrelDigit> bd(nb); std::vector<int> channels;
    for(auto& d:bd) {std::cin>>d.channel>>d.adc>>d.tdc;channels.push_back(d.channel);}
    auto g=decode_bgo_digits(digits,c); auto r=measure(g,clusters,channels,c,err); auto b=decode_barrel(bd,bc);
    std::cout<<(r.status|b.status)<<' '<<r.good.size()<<' '<<r.sp.size()<<' '<<b.records.size()<<'\n';
    for(int x:r.problem_slots) std::cout<<x<<' '; std::cout<<'\n';
    for(const auto& list:{r.good,r.sp}) for(const auto& x:list)
      std::cout<<x.multiplicity<<' '<<x.raw_energy<<' '<<x.theta<<' '<<x.phi<<' '<<x.corrected_energy<<' '
       <<x.corrected_theta<<' '<<x.corrected_phi<<' '<<x.sx1<<' '<<x.sy1<<' '<<x.sx2<<' '<<x.sy2<<' '<<x.flag<<'\n';
    for(const auto& x:b.records) std::cout<<x.channel<<' '<<x.problem_index<<' '<<x.energy<<' '<<x.time<<'\n';
  }
}
