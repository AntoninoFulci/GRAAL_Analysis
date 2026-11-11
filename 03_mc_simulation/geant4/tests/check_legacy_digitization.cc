#include "LegacyDigitization.hh"
#include <cstring>
#include <iostream>
#include <limits>
#include <string>

namespace {
using namespace legacy09;
void Check(bool value, const char* message) {
  if (!value) throw std::runtime_error(message);
}
template<class F> void Reject(F operation) {
  bool rejected = false;
  try { operation(); } catch (const std::invalid_argument&) { rejected = true; }
  Check(rejected, "invalid input was accepted");
}
Config Standard() {
  Config c;
  c.scbgo=2048; c.vscbgo_GeV=1.2901f; c.thres_GeV=.0022f;
  c.scdeb=2048; c.vscdeb_GeV=.02294f; c.debdis=.1458f; c.dthres_GeV=.0000392f;
  c.zc3_cm=21.7f; c.sdetof=2048; c.vdetof_s=116.3e-9f;
  c.ddetof_s=.47e-9f; c.dlight_cm_s=detail::Div(3.e10f,1.58f); c.dedxat=true;
  for (auto& a:c.attenuation) a={.1f,0,0,0};
  return c;
}
int Bits(float x) { int result; static_assert(sizeof(result)==sizeof(x)); std::memcpy(&result,&x,sizeof(x)); return result; }

void Independent() {
  const auto c=Standard();
  const auto zero=[](){return 0.0f;};
  Check(DigitizeBgo({},c).digits.empty(),"empty BGO");
  auto b=DigitizeBgo({{1,.01f}},c);
  Check(b.digits.size()==1 && b.digits[0].adc==16 && b.total_adc==16,"BGO 10MeV fixture");
  b=DigitizeBgo({{1,1},{480,1}},c);
  Check(b.digits.size()==2 && b.digits[0].adc==1587 && b.total_adc==2048 && b.soft_total_adc==2048,"BGO saturation fixture");
  std::vector<BgoDeposit> sub;
  for(int i=1;i<=50;++i) sub.push_back({i,.0019f});
  b=DigitizeBgo(sub,c);
  Check(b.digits.empty() && b.total_adc>0 && b.soft_total_adc==0 && b.raw_total_GeV>=.09f,"subthreshold analog total");
  auto d=DigitizeBarrel({{1,.001f,-c.zc3_cm,10.e-9f}},c,zero);
  Check(d.digits.size()==1 && d.digits[0].adc==89 && d.digits[0].tdc==176,"barrel independent fixture");
  d=DigitizeBarrel({{1,.001f,c.zc3_cm,0}},c,zero);
  Check(d.digits[0].tdc==40,"propagation fixture");
  d=DigitizeBarrel({{1,c.dthres_GeV,-c.zc3_cm,0}},c,zero);
  Check(d.digits.size()==1 && d.digits[0].adc==3,"inclusive energy threshold");
  d=DigitizeBarrel({{1,std::nextafter(c.dthres_GeV,0.f),0,0}},c,zero);
  Check(d.digits.empty() && d.energy_draws==1 && d.time_draws==0,"subthreshold draw count");
  d=DigitizeBarrel({{1,.001f,0,std::nextafter(100.e-9f,1.f)}},c,zero);
  Check(d.digits.empty() && d.energy_draws==0 && d.time_draws==0,"strict TOF cutoff");
  d=DigitizeBarrel({{1,.001f,0,100.e-9f}},c,zero);
  Check(d.digits.size()==1 && d.energy_draws==1,"inclusive TOF cutoff");
  int draw=0;
  const std::array<float,5> gs={-10.f,0.f,0.f,0.f,1000.f};
  d=DigitizeBarrel({{3,.001f,-c.zc3_cm,0},{1,.001f,0,0},{3,.002f,-c.zc3_cm,20.e-9f}},c,[&](){return gs.at(draw++);});
  Check(d.digits.size()==2 && d.digits[0].channel==3 && d.digits[1].channel==1,"first-seen output order");
  Check(d.digits[0].adc==138 && d.digits[0].tdc==0 && d.digits[1].tdc==2048,"negative contribution/time saturation");
  Check(d.energy_draws==3 && d.time_draws==2 && draw==5,"energy then surviving time draws");
  Check(d.digits[0].energy_GeV<.002f,"negative Gaussian contribution was clipped");
  draw=0;
  d=DigitizeBarrel({{1,.001f,-c.zc3_cm,0}},c,[&](){return draw++==0 ? 0.f:-100.f;});
  Check(d.digits[0].time_s<0 && d.digits[0].tdc==0,"negative final time");
  // Huge finite REAL counts safely saturate even outside Fortran INT's domain.
  Check(DigitizeBgo({{1,1.e20f}},c).digits[0].adc==2048,"safe BGO int overflow");
  d=DigitizeBarrel({{1,1.e20f,0,0}},c,zero);
  Check(d.digits[0].adc==2048,"safe barrel int overflow");
  Reject([&](){DigitizeBgo({{1,std::numeric_limits<float>::max()}},c);});
  Reject([&](){DigitizeBarrel({{1,std::numeric_limits<float>::max(),0,0}},c,zero);});
  Reject([&](){DigitizeBgo({{2,1},{1,1}},c);});
  Reject([&](){DigitizeBgo({{1,1},{1,1}},c);});
  Reject([&](){DigitizeBgo({{481,1}},c);});
  Reject([&](){DigitizeBgo({{0,1}},c);});
  Reject([&](){DigitizeBgo({{1,-1}},c);});
  draw=0;
  Reject([&](){DigitizeBarrel({{1,1,0,0},{33,1,0,0}},c,[&](){++draw; return 0.f;});});
  Check(draw==0,"invalid event consumed RNG state");
  Reject([&](){DigitizeBarrel({{33,1,0,0}},c,zero);});
  Reject([&](){DigitizeBarrel({{0,1,0,0}},c,zero);});
  Reject([&](){DigitizeBarrel(std::vector<BarrelHit>(101,{1,1,0,0}),c,zero);});
  Reject([&](){DigitizeBarrel({{1,1,0,std::numeric_limits<float>::quiet_NaN()}},c,zero);});
  Reject([&](){DigitizeBarrel({{1,1,0,0}},c,[](){return std::numeric_limits<float>::infinity();});});
  Reject([&](){auto bad=c; bad.scbgo=2048.5f; ValidateConfig(bad);});
  Reject([&](){auto bad=c; bad.dlight_cm_s=0; ValidateConfig(bad);});
  Reject([&](){auto bad=c; bad.debdis=-1; ValidateConfig(bad);});
  Reject([&](){auto bad=c; bad.attenuation[0]={0,0,0,0}; ValidateConfig(bad);});
  for(int ch=1;ch<=32;++ch) for(float z:{-c.zc3_cm,0.f,c.zc3_cm})
    Check(Attenuation(ch,z,c)==1,"period09 attenuation must equal one");
  auto grouped=GroupBarrelSteps({{1,.001f,0,2.e-6f},{1,.1f,.9f,0},{1,.001f,1.1f,0},{2,.1f,0,0},{1,.1f,1.1f,0}});
  Check(grouped.records.size()==4 && grouped.source_indices[0]==std::vector<std::size_t>({0,1}),"anchor and ordering grouping");
  Check(grouped.records[0].z_cm==.45f && grouped.records[0].time_s==1.e-6f,"unweighted mean/first capped time");
  grouped=GroupBarrelSteps({{1,1,0,0},{1,1,1,0}});
  Check(grouped.records.size()==2,"strict 1cm merge boundary");
  grouped=GroupBarrelSteps({{1,1,0,10.e-9f},{1,1,.5f,0}});
  Check(grouped.records[0].time_s==10.e-9f,"grouping must retain first time");
  Check(GroupBarrelSteps({}).records.empty(),"empty grouping");
  Reject([&](){GroupBarrelSteps({{1,0,0,0}});});
  std::cout<<"independent kernel fixtures passed\n";
}

void Protocol() {
  int cases; std::cin>>cases;
  for(int n=0;n<cases;++n) {
    Config c; int enabled,mode,count;
    std::cin>>c.scbgo>>c.vscbgo_GeV>>c.thres_GeV>>c.scdeb>>c.vscdeb_GeV>>c.debdis>>c.dthres_GeV
      >>c.zc3_cm>>c.sdetof>>c.vdetof_s>>c.ddetof_s>>c.dlight_cm_s>>enabled;
    c.dedxat=enabled!=0;
    for(auto& row:c.attenuation) for(float& x:row) std::cin>>x;
    std::cin>>mode;
    if(mode==1) {
      std::cin>>count; std::vector<BgoDeposit> deposits;
      for(int i=0;i<count;++i) { BgoDeposit h; std::cin>>h.channel>>h.energy_GeV; deposits.push_back(h); }
      auto result=DigitizeBgo(deposits,c);
      std::cout<<"B "<<result.digits.size()<<' '<<Bits(result.raw_total_GeV)<<' '<<result.total_adc<<' '<<result.soft_total_adc<<'\n';
      for(const auto& h:result.digits) std::cout<<h.channel<<' '<<h.adc<<'\n';
    } else if(mode==2) {
      std::cin>>count; std::vector<BarrelHit> hits;
      for(int i=0;i<count;++i) { BarrelHit h; std::cin>>h.channel>>h.energy_GeV>>h.z_cm>>h.time_s; hits.push_back(h); }
      int size; std::cin>>size; std::vector<float> draws(static_cast<std::size_t>(size));
      for(auto& g:draws) std::cin>>g;
      std::size_t used=0;
      const auto result=DigitizeBarrel(hits,c,[&](){return draws.at(used++);});
      std::cout<<"D "<<result.digits.size()<<' '<<used<<'\n';
      for(const auto& h:result.digits) std::cout<<h.channel<<' '<<h.adc<<' '<<h.tdc<<'\n';
    } else if(mode==3) {
      int channel; float z; std::cin>>channel>>z;
      ValidateConfig(c);
      std::cout<<"A "<<Bits(Attenuation(channel,z,c))<<'\n';
    } else throw std::runtime_error("unknown oracle mode");
    Check(static_cast<bool>(std::cin),"truncated oracle test protocol");
  }
}
}  // namespace
int main(int argc,char** argv) {
  try {
    if(argc==2 && std::string(argv[1])=="--selftest") Independent();
    else Protocol();
  } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 1; }
}
