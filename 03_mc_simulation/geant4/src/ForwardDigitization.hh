#ifndef GRAAL_FORWARD_DIGITIZATION_HH
#define GRAAL_FORWARD_DIGITIZATION_HH
// Active GRAAL_WALL_DEV / GRAAL_SHOW_DEV, selected26. Compile without fast-math
// or FP contraction. This is a diagnostic response, not calibrated efficiency.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <vector>

namespace forward26 {
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559, "requires source REAL binary32");
enum Status : unsigned { Ok=0, CompactOverflow=1, UndefinedHorizontalCounterpart=2, NegativeTimePartialWrite=4 };
struct ShowConfig {
  std::array<float,16> rt{},rb{},ae{},bu{},bd{};
  float ay=8.015f;
};
struct Config {
  std::array<float,110> pedestals{},tdccal{},gaincards{},timewalk{},tdcoffset{},gainpms{};
  ShowConfig shower;
};
struct CompactHit { int channel; float energy_GeV,position_cm,time_s; };
struct CompactResult {
  std::vector<CompactHit> records;
  std::vector<std::vector<std::size_t>> source_indices;
  bool overflow=false;
};
struct Digit {
  int channel{};
  std::array<int,2> adc{},tdc{}; // WALL H:left/right, V:up/down; SHOW:up/down
  unsigned status=Ok; // nonzero means unsupported; TDC zeros are not valid data
};
struct WallResult {
  std::vector<Digit> horizontal,vertical;
  std::size_t energy_draws{},time_draws{};
  unsigned status=Ok;
};
struct ShowerResult {
  std::vector<Digit> digits;
  std::size_t energy_draws{},time_draws{};
  unsigned status=Ok;
};
namespace detail {
inline float F(float x) { if(!std::isfinite(x)) throw std::invalid_argument("nonfinite forward REAL"); return x; }
inline float A(float a,float b) { volatile float r=a+b; return F(r); }
inline float M(float a,float b) { volatile float r=a*b; return F(r); }
inline float D(float a,float b) { volatile float r=a/b; return F(r); }
inline float S(float x) { volatile float r=std::sqrt(x); return F(r); }
inline float E(float x) { volatile float r=std::exp(x); return F(r); }
inline int I(float x) { F(x); if(double(x)>std::numeric_limits<int>::max() || double(x)<std::numeric_limits<int>::min()) throw std::invalid_argument("outside source INTEGER domain"); return static_cast<int>(x); }
inline void Hit(const CompactHit& h,int maximum) {
  if(h.channel<1 || h.channel>maximum) throw std::invalid_argument("invalid forward channel");
  if(F(h.energy_GeV)<0) throw std::invalid_argument("negative forward deposit");
  F(h.position_cm); F(h.time_s);
}
inline void Positive(float x) { if(!(F(x)>0)) throw std::invalid_argument("nonpositive forward divisor"); }
inline float Polynomial(const float* c,float x) {
  // Preserve WALL_ATT's explicit powers and left-to-right additions.
  const float x2=M(x,x),x3=M(x2,x),x4=M(x2,x2),x5=M(x4,x);
  return A(A(A(A(A(c[0],M(c[1],x)),M(c[2],x2)),M(c[3],x3)),M(c[4],x4)),M(c[5],x5));
}
}
inline ShowConfig Run340ShowConfig() {
  return {{.05604f,.05709f,.05526f,.05575f,.05580f,.05644f,.05644f,.05626f,.05658f,.05604f,.05614f,.05664f,.05594f,.05575f,.05626f,.05704f},
          {.05580f,.05502f,.05541f,.05546f,.05580f,.05536f,.05551f,.05536f,.05536f,.05503f,.05536f,.05498f,.05565f,.05594f,.05555f,.05508f},
          {.375f,.328f,.295f,.283f,.291f,.293f,.302f,.312f,.328f,.263f,.320f,.323f,.314f,.292f,.310f,.332f},
          {68.54f,68.37f,68.79f,63.52f,66.91f,67.03f,67.65f,67.62f,68.13f,68.40f,66.34f,64.64f,68.98f,71.43f,69.12f,68.52f},
          {69.60f,69.57f,68.49f,69.52f,68.76f,71.07f,66.04f,67.41f,69.92f,68.44f,69.38f,69.78f,70.05f,69.70f,70.67f,71.27f},8.015f};
}
inline void ValidateConfig(const Config& c) {
  for(std::size_t i=0;i<110;++i) {
    detail::F(c.pedestals[i]);detail::F(c.timewalk[i]);detail::F(c.tdcoffset[i]);
    detail::F(c.tdccal[i]);detail::F(c.gaincards[i]);detail::F(c.gainpms[i]);
    if(i<104) { detail::Positive(c.tdccal[i]);detail::Positive(c.gaincards[i]);detail::Positive(c.gainpms[i]); }
  }
  detail::Positive(c.shower.ay);
  for(std::size_t i=0;i<16;++i) {
    detail::Positive(c.shower.rt[i]);detail::Positive(c.shower.rb[i]);detail::Positive(c.shower.ae[i]);
    detail::F(c.shower.bu[i]);detail::F(c.shower.bd[i]);
  }
}
inline float WallAttenuation(float x,int bar,bool horizontal) {
  detail::F(x);
  if(bar<1 || bar>26) throw std::invalid_argument("invalid wall bar");
  if(x<0 || x>300) return 1;
  static constexpr float n[]={1,-.0090441f,8.86025e-5f,-5.23746e-7f,1.55206e-9f,-1.75968e-12f};
  static constexpr float s[]={1,-.00908852f,8.81039e-5f,-5.22587e-7f,1.54894e-9f,-1.74078e-12f};
  static constexpr float h[]={1,-.00844889f,8.99927e-5f,-5.07708e-7f,1.53732e-9f,-2.00825e-12f,
    1.20693f,-.00801887f,8.96254e-5f,-5.2653e-7f,1.31254e-9f,-4.12714e-12f,
    1.00797f,-.00907159f,8.65683e-5f,-5.18868e-7f,1.53184e-9f,-1.69594e-12f};
  if(horizontal && bar<=4) return detail::Polynomial(s,x);
  if(bar==13 || bar==14) return detail::D(detail::Polynomial(h+(x<=140?0:x<=160?6:12),x),1.2f);
  return detail::Polynomial(n,x);
}
// Ordered post-step GLOBAL x(H)/y(V,SHOW), cm; deposit GeV, time seconds.
// G3 mechanism22 has no established G4 mapping. Caller declares all-process
// diagnostic policy; these pure routines neither accept truth nor infer it.
inline CompactResult GroupSteps(const std::vector<CompactHit>& steps,bool shower) {
  CompactResult out;
  std::vector<float> anchor,sum;
  for(std::size_t row=0;row<steps.size();++row) {
    const auto& h=steps[row];detail::Hit(h,shower?16:26);
    if(shower ? h.energy_GeV<=1.e-9f : h.energy_GeV==0) continue;
    std::size_t selected=out.records.size();
    if(!out.records.empty()) {
      auto last=out.records.size()-1;
      if(out.records[last].channel==h.channel && std::abs(detail::A(anchor[last],-h.position_cm))<(shower?10.f:5.f)) selected=last;
      else if(shower) {
        for(std::size_t j=0;j<out.records.size();++j)
          if(out.records[j].channel==h.channel && std::abs(detail::A(anchor[j],-h.position_cm))<10.f && std::abs(detail::A(out.records[j].time_s,-h.time_s))<10.e-9f) { selected=j;break; }
      }
    }
    if(selected==out.records.size()) {
      out.records.push_back(h);out.source_indices.push_back({row});anchor.push_back(h.position_cm);sum.push_back(h.position_cm);
    } else {
      auto& r=out.records[selected];r.energy_GeV=detail::A(r.energy_GeV,h.energy_GeV);
      sum[selected]=detail::A(sum[selected],h.position_cm);out.source_indices[selected].push_back(row);
      if(shower) r.time_s=std::min(r.time_s,h.time_s);
    }
  }
  for(std::size_t j=0;j<out.records.size();++j) {
    out.records[j].position_cm=detail::D(sum[j],static_cast<float>(out.source_indices[j].size()));
    out.records[j].time_s=std::min(out.records[j].time_s,1.e-6f); // LAGWREV
  }
  out.overflow=out.records.size()>100; // retain every source link, never truncate
  return out;
}
inline CompactResult GroupWallSteps(const std::vector<CompactHit>& s) { return GroupSteps(s,false); }
inline CompactResult GroupShowerSteps(const std::vector<CompactHit>& s) { return GroupSteps(s,true); }

template<class Gaussian>
WallResult DigitizeWall(const std::vector<CompactHit>& horizontal,const std::vector<CompactHit>& vertical,const Config& c,Gaussian&& gaussian) {
  ValidateConfig(c);WallResult out;
  for(const auto& h:horizontal) detail::Hit(h,26);
  for(const auto& h:vertical) detail::Hit(h,26);
  if(horizontal.size()>100 || vertical.size()>100) { out.status=CompactOverflow;return out; }
  // Fortran OR need not short-circuit, so demand an initialized horizontal
  // counterpart for EVERY vertical record, including channel13. Never infer 14.
  if(vertical.size()>horizontal.size()) { out.status=UndefinedHorizontalCounterpart;return out; }
  for(int orientation=0;orientation<2;++orientation) {
    bool hor=orientation==0; const auto& hits=hor?horizontal:vertical;
    std::array<std::array<float,2>,26> energy{},time{};std::array<bool,26> seen{};std::vector<int> order;
    for(std::size_t row=0;row<hits.size();++row) {
      const auto& h=hits[row];float en=detail::M(h.energy_GeV,1.e3f),t=detail::M(h.time_s,1.e9f);
      if(hor ? h.channel==13 || h.channel==14 : h.channel==13 || horizontal[row].channel==14) en=detail::D(en,1.3f);
      else if(hor && h.channel<=4) en=detail::D(en,.9f);
      if(en<1 || t>95 || (hor && h.channel<=4 && h.position_cm<=-110)) continue;
      auto i=static_cast<std::size_t>(h.channel-1);
      std::array<float,2> distance={detail::A(150,-h.position_cm),detail::A(150,h.position_cm)};
      for(int e=0;e<2;++e) {
        energy[i][e]=detail::A(energy[i][e],detail::M(en,WallAttenuation(distance[e],h.channel,hor)));
        float arrival=detail::A(t,detail::D(distance[e],16));
        if(hor && h.channel<=4 && e==1) arrival=detail::A(arrival,-detail::D(40,16));
        time[i][e]=seen[i]?std::min(time[i][e],arrival):arrival;
      }
      if(!seen[i]) { seen[i]=true;order.push_back(h.channel); }
    }
    for(int channel:order) {
      auto i=static_cast<std::size_t>(channel-1);std::array<std::size_t,2> k={i+(hor?52:0),i+(hor?78:26)};
      bool rejected=false;
      for(int e=0;e<2;++e) {
        float g=detail::F(static_cast<float>(gaussian()));++out.energy_draws;
        energy[i][e]=detail::D(detail::M(energy[i][e],detail::A(1,detail::M(.086f,g))),c.gainpms[k[e]]);
        if(energy[i][e]<10) { rejected=true;break; }
      }
      if(rejected) continue;
      Digit d;d.channel=channel;
      for(int e=0;e<2;++e) {
        int raw=detail::I(detail::D(energy[i][e],c.gaincards[k[e]]));
        d.adc[e]=std::min(1024,detail::I(detail::A(static_cast<float>(raw),c.pedestals[k[e]])));
      }
      std::array<float,2> final{};
      for(int e=0;e<2;++e) {
        float g=detail::F(static_cast<float>(gaussian()));++out.time_draws;
        float t=detail::A(time[i][e],detail::M(.3f,g));
        final[e]=detail::D(detail::A(detail::A(t,c.tdcoffset[k[e]]),detail::D(c.timewalk[k[e]],detail::S(energy[i][e]))),c.tdccal[k[e]]);
        if(final[e]<0) { d.status=NegativeTimePartialWrite;out.status|=d.status;break; }
      }
      if(d.status==Ok) for(int e=0;e<2;++e) d.tdc[e]=std::min(2048,detail::I(final[e]));
      (hor?out.horizontal:out.vertical).push_back(d);
    }
  }
  return out;
}

template<class Gaussian>
ShowerResult DigitizeShower(const std::vector<CompactHit>& hits,const Config& c,Gaussian&& gaussian) {
  ValidateConfig(c);ShowerResult out;
  for(const auto& h:hits) detail::Hit(h,16);
  if(hits.size()>100) { out.status=CompactOverflow;return out; }
  std::array<std::array<float,2>,16> energy{},time{};std::array<int,16> count{};
  const auto& s=c.shower;
  for(const auto& h:hits) {
    float ns=detail::M(h.time_s,1.e9f);if(ns>75) continue;
    auto i=static_cast<std::size_t>(h.channel-1);++count[i];
    for(int e=0;e<2;++e) {
      float distance=std::abs(detail::A(e==0?150.f:-150.f,-h.position_cm));
      float attenuation=detail::D(detail::A(detail::M(.36f,detail::E(detail::D(-distance,35))),detail::E(detail::D(-distance,200))),.4773215f);
      float de=detail::M(detail::M(h.energy_GeV,1.e3f),attenuation);
      energy[i][e]=detail::A(energy[i][e],de);
      if(de<detail::M(4,s.ae[i])) continue;
      float arrival=detail::A(ns,detail::D(distance,detail::M(2,s.ay)));
      float g=detail::F(static_cast<float>(gaussian()));++out.time_draws;
      float resolution=detail::M(1.41f,detail::S(detail::A(.05f,detail::D(.5f,detail::A(de,1)))));
      arrival=detail::A(arrival,detail::M(resolution,g));
      if(time[i][e]==0 || time[i][e]>arrival) time[i][e]=arrival;
    }
  }
  for(std::size_t i=0;i<16;++i) {
    if(count[i]==0) continue;
    for(int e=0;e<2;++e) {
      float g=detail::F(static_cast<float>(gaussian()));++out.energy_draws;
      energy[i][e]=detail::A(energy[i][e],detail::M(detail::M(1.4f,g),detail::A(2,detail::M(.4f,detail::S(energy[i][e])))));
      energy[i][e]=std::max(0.f,std::min(2000.f,energy[i][e]));
    }
  }
  for(std::size_t i=0;i<16;++i) {
    if(count[i]==0) continue;
    Digit d;d.channel=static_cast<int>(i+1);
    for(int e=0;e<2;++e) {
      d.adc[e]=detail::I(detail::D(energy[i][e],s.ae[i]));
      float t=0;
      if(time[i][e]!=0) t=detail::D(-detail::A(detail::A(time[i][e],-(e==0?s.bu[i]:s.bd[i])),-detail::D(75,s.ay)),e==0?s.rt[i]:s.rb[i]);
      d.tdc[e]=detail::I(std::max(0.f,t));
    }
    out.digits.push_back(d);
  }
  return out;
}
} // namespace forward26
#endif
