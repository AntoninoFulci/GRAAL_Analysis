#include "BgoCellular.hh"
#include <cassert>
#include <cstdlib>
#include <iostream>
using namespace bgo26;
int main(int argc,char**){
 static_assert(RAND_MAX==2147483647,"oracle integer stream profile");
 int cases;CellularConfig config;std::cin>>cases>>config.rcnt>>config.tde;
 for(auto& x:config.theta_deg)std::cin>>x;for(auto& x:config.phi_deg)std::cin>>x;for(auto& x:config.volume)std::cin>>x;
 if(argc>1){
  std::array<float,480> empty{};std::size_t calls=0;auto uniform=[&](){++calls;return .5f;};
  auto r=ClusterCellular(empty,config,uniform);assert(r.status==CellularStatus::Valid && r.source_nero==3 && r.clusters.empty() && r.draws==0 && calls==0);
  auto bad=empty;bad[0]=-1;r=ClusterCellular(bad,config,uniform);assert(r.status==CellularStatus::Valid && r.source_nero==3 && r.clusters.empty() && calls==0);
  bad[0]=std::numeric_limits<float>::quiet_NaN();r=ClusterCellular(bad,config,uniform);assert(r.status==CellularStatus::InvalidInput && calls==0);
  auto missing=config;missing.rcnt=CellularConfig{}.rcnt;r=ClusterCellular(empty,missing,uniform);assert(r.status==CellularStatus::InvalidInput && calls==0);
  auto badcfg=config;badcfg.volume[0]=0;r=ClusterCellular(empty,badcfg,uniform);assert(r.status==CellularStatus::InvalidInput && calls==0);
  bad={};bad[0]=1;auto invalid=[](){return 1.0001;};r=ClusterCellular(bad,config,invalid);assert(r.status==CellularStatus::InvalidInput && r.draws==1);
  auto valid0=[](){return 0.f;};auto first=ClusterCellular(bad,config,valid0);auto second=ClusterCellular(bad,config,valid0);assert(first.clusters==second.clusters && first.clusters==std::vector<std::vector<int>>{{101}});
  bad[0]=std::numeric_limits<float>::max();auto one=[](){return 1.f;};r=ClusterCellular(bad,config,one);assert(r.status==CellularStatus::UndefinedSource && r.clusters.empty());
  bad={};bad[0]=1;bad[1]=1;badcfg=config;badcfg.rcnt=std::numeric_limits<float>::max();auto zero=[](){return 0.f;};
  // Each seed has finite energy; overflowing contact ratio is unsupported.
  bad[0]=2;bad[1]=2;r=ClusterCellular(bad,badcfg,zero);assert(r.status==CellularStatus::UndefinedSource);
  std::cout<<"CA public domain and repeat fixtures passed\n";return 0;
 }
 for(int event=0;event<cases;++event){
  std::array<float,480> grid{};for(auto& x:grid)std::cin>>x;
  int n;std::cin>>n;std::vector<int> draws(n);for(auto& x:draws)std::cin>>x;std::size_t pos=0;
  auto uniform=[&](){if(pos==draws.size())throw std::invalid_argument("draw stream exhausted");return static_cast<float>(draws[pos++])/static_cast<float>(RAND_MAX);};
  auto r=ClusterCellular(grid,config,uniform);
  if(r.status!=CellularStatus::Valid){std::cout<<"UNSUPPORTED "<<static_cast<int>(r.status)<<' '<<r.reason<<'\n';continue;}
  std::cout<<"O "<<event<<' '<<r.source_nero<<' '<<r.draws<<' '<<r.clusters.size()<<'\n';
  for(const auto& c:r.clusters){std::cout<<"C "<<c.size();for(int id:c)std::cout<<' '<<id;std::cout<<'\n';}
 }
}
