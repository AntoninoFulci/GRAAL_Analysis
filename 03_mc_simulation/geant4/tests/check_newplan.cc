#include "NewPlan.hh"
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>

static int bits(float value) {int result; std::memcpy(&result,&value,4);return result;}
static void selftest() {
  using namespace newplan;
  const auto g=geometry26();
  auto zero=g;zero.angle_deg=0.f;
  assert(reconstruct({},g).tracks.empty());
  assert(reconstruct({},g).cltot==0);
  const auto d=digitize({{2,0.f,0.f},{2,-.3f,0.f},{2,-.3f,0.f},{3,0.f,0.f}},zero);
  assert(d.status==Ok && d.wires[2]==std::vector<int>({193,191}));
  assert(d.associations[2].state==CrossingState::Duplicate);
  assert(d.associations[2].digit_index==1);
  const auto turn=digitize({{0,3.f,0.f},{1,3.f,0.f}},g);
  assert(turn.wires[0][0]==168 && turn.wires[1][0]==168);
  auto plus=g;plus.angle_deg=45;
  assert(digitize({{1,3.f,0.f}},plus).wires[1][0]==153);
  auto boundary=digitize({{2,-57.6f,0.f},{2,57.6f,0.f}},g);
  assert(boundary.wires[2]==std::vector<int>({1}));
  assert(boundary.status&UndefinedXYUpper);
  auto clamp=digitize({{0,49.f,0.f},{0,50.f,0.f}},zero);
  assert(clamp.status==UVUpperClamped && clamp.wires[0]==std::vector<int>({320,320}));
  assert(!supported(clamp.status));
  std::vector<int> order;
  auto ineff=digitize({{3,0,0},{0,0,0},{2,0,0},{0,0,0}},g,[&](int p){order.push_back(p);return p==0?0.f:1.f;});
  assert((order==std::vector<int>{0,0,2,3}) && ineff.wires[0].empty());
  assert(digitize({{2,0,0}},g,[](int){return 2.f;}).status==InvalidEfficiency);
  assert(digitize({{4,0,0}},g).status==InvalidCrossing);
  assert(digitize({{2,std::numeric_limits<float>::max(),0}},g).status==InvalidCrossing);
  assert(digitize({{2,-100,0}},g).status==InvalidWire);
  assert(digitize({{0,std::numeric_limits<float>::infinity(),0}},g).status==InvalidCrossing);
  std::vector<Crossing> many(21,{0,0,0});
  const auto overflow=digitize(many,g);
  assert(overflow.status==RawOverflow && overflow.associations.size()==21 && overflow.wires[0].empty());
  WireLists w{{{160},{161},{192},{193}}};
  auto one=reconstruct(w,g);
  assert(one.status==Ok && one.tracks.size()==1 && one.cltot==0);
  assert(one.tracks[0].first_cm[2]==94.4f && one.tracks[0].second_cm[2]==134.4f);
  for(int p=0;p<4;++p) {
    auto missing=w;missing[p].clear();auto r=reconstruct(missing,g);
    assert(r.status==Ok && r.cltot==-1 && r.tracks.size()==1 && r.tracks[0].cl==p+1);
    assert(r.tracks[0].cluster_indices[p]==-1 && r.tracks[0].wire_indices[p].empty());
  }
  auto slope=reconstruct({{{161},{161},{194},{194}}},zero);
  assert(slope.tracks.size()==1);
  assert(std::abs(slope.tracks[0].first_cm[0]-.15375f)<1.e-5f);
  assert(std::abs(slope.tracks[0].first_cm[1]-.14625f)<1.e-5f);
  assert(std::abs(slope.tracks[0].second_cm[0]-.45375f)<1.e-5f);
  assert(std::abs(slope.tracks[0].second_cm[1]-.44625f)<1.e-5f);
  auto raw=w;raw[0].resize(21,1);
  assert(reconstruct(raw,g).status==RawOverflow && reconstruct(raw,g).cltot==10);
  WireLists excessive;for(auto& v:excessive) v={10,20,30,40,50};
  assert(reconstruct(excessive,g).status==CombinationOverflow);
  auto invalid=w;invalid[0]={0};assert(reconstruct(invalid,g).status==InvalidWire);
  invalid=w;invalid[2]={385};assert(reconstruct(invalid,g).status==InvalidWire);
  auto bad=g;bad.zp2_cm=bad.zp1_cm;assert(reconstruct(w,bad).status==InvalidGeometry);
  // Source equality reuse: duplicated wire centers leave fewer initialized
  // candidates than requested NTRA, so no plausible track is published.
  WireLists duplicate{{{10,10},{20,20},{30,30},{40,40}}};
  auto collision=reconstruct(duplicate,g);
  assert(collision.status==CoordinateCollision && collision.tracks.empty());
  auto clustered=detail::clusters({1,2,3});
  assert(clustered.size()==1 && clustered[0].center==2.f && clustered[0].indices.size()==3);
  assert((detail::sort_indices({1,1,1,1})==std::vector<int>{1,2,3,0}));
  std::cout<<"fixtures passed\n";
}
int main(int argc,char** argv) {
  if(argc>1 && std::string(argv[1])=="--selftest") {selftest();return 0;}
  int cases;std::cin>>cases;
  while(cases--) {
    int mode;std::cin>>mode;
    if(mode==3) {
      int n;std::cin>>n;std::vector<float> values(n);for(auto& v:values) std::cin>>v;
      for(int i:newplan::detail::sort_indices(values)) std::cout<<i<<' ';
      std::cout<<'\n';continue;
    }
    newplan::Geometry g{};
    std::cin>>g.xp1_cm>>g.xp2_cm>>g.zp1_cm>>g.zp2_cm>>g.nf1>>g.nf2>>g.angle_deg;
    if(mode==1) {
      int n;std::cin>>n;std::vector<newplan::Crossing> crossings(n);
      for(auto& c:crossings) std::cin>>c.plane>>c.x_cm>>c.y_cm;
      std::cin>>n;std::vector<float> draws(n);for(float& d:draws) std::cin>>d;
      std::vector<int> order;std::size_t used=0;
      auto d=newplan::digitize(crossings,g,[&](int p){order.push_back(p);return draws.at(used++);});
      for(auto& w:d.wires) std::cout<<w.size()<<' ';std::cout<<used<<'\n';
      for(int p:order) std::cout<<p<<' ';std::cout<<'\n';
      for(const auto& w:d.wires) {for(int wire:w) std::cout<<wire<<' ';std::cout<<'\n';}
    } else {
      newplan::WireLists wires;std::array<int,4> counts{};
      for(int& n:counts) std::cin>>n;
      for(int p=0;p<4;++p) {wires[p].resize(counts[p]);for(int& w:wires[p]) std::cin>>w;}
      auto r=newplan::reconstruct(wires,g);
      if(mode==4) std::cout<<r.status<<' '<<r.candidate_count<<' ' ;
      std::cout<<r.tracks.size()<<' '<<r.cltot<<' ';
      for(int n:r.reduced_multiplicity) std::cout<<n<<' ';std::cout<<'\n';
      for(const auto& t:r.tracks)
        std::cout<<t.cl<<' '<<bits(t.first_cm[0])<<' '<<bits(t.first_cm[1])<<' '
          <<bits(t.second_cm[0])<<' '<<bits(t.second_cm[1])<<'\n';
    }
  }
}
