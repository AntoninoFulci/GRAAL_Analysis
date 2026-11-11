#ifndef GRAAL_LEGACY_CYLINDER_RESPONSE_HH
#define GRAAL_LEGACY_CYLINDER_RESPONSE_HH
// CYCH_OLD + LAGSTRIP_OLD + LAGFILL + LAGANGLE + LAGROTA +
// LAGLWH + LAGMOD, selected26. Compile -fno-fast-math -ffp-contract=off.
// Injected draws are a diagnostic stream, not historical whole-event RNG parity.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <vector>
namespace legacy_cylinder {
struct Config {
  std::array<float,2> rc,zc,pc;
  std::array<int,2> nfc;
  std::array<int,4> nb;
  float bl,dfca,sccat,vsccat,conv,cythre;
  std::array<float,4> sigce;
  float sigct;
  std::array<float,4> angle_deg;
  std::array<float,2> effcyc;
  int nbord;
};
enum ResponseStatus : std::uint32_t {
  ResponseOk=0,ResponseInvalidConfig=1u<<0,ResponseInvalidCrossing=1u<<1,
  ResponseOverflow=1u<<2,ResponseInvalidDraw=1u<<3,
  ResponseArithmetic=1u<<4,ResponseInvalidAddress=1u<<5
};
struct CrossingInput {
  int chamber=0;
  std::array<float,3> xyz_cm{};
  float energy_GeV=0;
  std::size_t source_crossing=0;
};
struct StripDigit {int strip=0,adc=0;};
enum class WireState : int {Accepted=0,Duplicate=1,EfficiencyRejected=2,Invalid=3};
struct WireAssociation {
  std::size_t source_crossing=0;
  int chamber=0,wire=0,digit_index=-1;
  WireState state=WireState::Invalid;
};
struct ChargeLink {
  std::size_t source_crossing=0;
  int cathode=0,strip=0;
  float charge=0;
};
struct DigitResult {
  std::array<std::vector<int>,2> wires;
  std::array<std::vector<StripDigit>,4> cathodes;
  std::array<std::vector<float>,4> charges; // after electronics noise
  std::array<std::vector<bool>,4> read_flags;
  std::vector<WireAssociation> associations;
  std::vector<ChargeLink> charge_links;
  std::size_t normal_draws=0;
  std::vector<int> efficiency_histograms;
  std::uint32_t status=ResponseOk;
};
namespace response_detail {
constexpr double pi=3.14159265358979324,twopi=6.28318530717958648;
inline bool valid(const Config& c) {
  if(c.nfc!=std::array<int,2>{{128,192}} || c.nb!=std::array<int,4>{{60,64,96,96}} ||
     c.nbord<0 || c.nbord>60) return false;
  auto positive=[](float v){return std::isfinite(v)&&v>0 && v<=1.e20f;};
  for(int i=0;i<2;++i)
    if(!positive(c.rc[i]) || !positive(c.zc[i]) || !std::isfinite(c.pc[i]) ||
       std::abs(c.pc[i])>1.e6f || !std::isfinite(c.effcyc[i]) || c.effcyc[i]<0 || c.effcyc[i]>1) return false;
  if(!positive(c.bl) || !positive(c.dfca) || c.dfca>=std::min(c.rc[0],c.rc[1]) ||
     !positive(c.sccat) || c.sccat!=std::trunc(c.sccat) || c.sccat>1.e6f ||
     !positive(c.vsccat) || !positive(c.conv) || !std::isfinite(c.cythre) || c.cythre<0 ||
     !std::isfinite(c.sigct) || c.sigct<0) return false;
  for(int i=0;i<4;++i)
    if(!std::isfinite(c.sigce[i]) || c.sigce[i]<0 || !std::isfinite(c.angle_deg[i]) ||
       std::abs(c.angle_deg[i])>=90.f) return false;
  return true;
}
inline bool laglwh(float x,int& result) {
  if(!std::isfinite(x) || std::abs(static_cast<double>(x))>1.e8) return false;
  result=static_cast<int>(x);if(x<0) --result;return true;
}
inline int lagmod(int i,int n) {int r=i%n;return r<=0?r+n:r;}
struct Derived {
  std::array<float,4> radius{},sang{},cang{},xbl{},be{};
  std::array<float,2> ucf{};
  explicit Derived(const Config& c) {
    for(int ch=0;ch<2;++ch) {
      radius[2*ch]=c.rc[ch]-c.dfca;radius[2*ch+1]=c.rc[ch]+c.dfca;
      ucf[ch]=static_cast<float>(twopi*c.rc[ch]);
    }
    for(int i=0;i<4;++i) {
      const float angle=static_cast<float>(c.angle_deg[i]*0.0174532925199432958);
      sang[i]=std::sin(angle);cang[i]=std::cos(angle);
      const float uc=static_cast<float>(twopi*radius[i]);
      xbl[i]=uc*cang[i];be[i]=xbl[i]/static_cast<float>(c.nb[i])-c.bl;
    }
  }
};
} // namespace response_detail

inline DigitResult digitize(const std::vector<CrossingInput>& crossings,const Config& c,
                           const std::function<float()>& normal,
                           const std::function<float(int)>& efficiency) {
  using namespace response_detail;
  DigitResult out;
  if(!valid(c)) {out.status|=ResponseInvalidConfig;return out;}
  const Derived d(c);
  for(int i=0;i<4;++i) {
    if(!std::isfinite(d.xbl[i]) || d.xbl[i]<=0 || !std::isfinite(d.be[i]) || d.be[i]<0) {
      out.status|=ResponseInvalidConfig;return out;
    }
    out.charges[i].assign(c.nb[i],0.f);out.read_flags[i].assign(c.nb[i],false);
  }
  std::array<int,2> counts{};
  for(const auto& h:crossings) {
    if(h.chamber<0 || h.chamber>1 || !std::isfinite(h.energy_GeV) || h.energy_GeV<0) {
      out.status|=ResponseInvalidCrossing;continue;
    }
    ++counts[h.chamber];
    for(float v:h.xyz_cm) if(!std::isfinite(v) || std::abs(v)>1.e6f) out.status|=ResponseInvalidCrossing;
  }
  if(counts[0]>20 || counts[1]>20) out.status|=ResponseOverflow;
  if(out.status) return out;
  auto draw_normal=[&](float& value) {
    value=normal();++out.normal_draws;
    if(!std::isfinite(value)) {out.status|=ResponseInvalidDraw;return false;}return true;
  };
  auto draw_efficiency=[&](int chamber,bool& accepted) {
    const int hist=1001+chamber;const float value=efficiency(hist);out.efficiency_histograms.push_back(hist);
    // HISTO books two unit bins over [-.5,1.5]; HRNDM samples within bins.
    // The caller may equivalently supply exact masks0/1 for this decision.
    if(!std::isfinite(value) || value<-.5f || value>1.5f) {out.status|=ResponseInvalidDraw;return false;}
    accepted=static_cast<int>(value+.5f)!=0;return true;
  };
  for(int ch=0;ch<2;++ch) {
    const float fac=static_cast<float>(c.nfc[ch])/d.ucf[ch];
    for(const auto& h:crossings) {
      if(h.chamber!=ch) continue;
      float g;if(!draw_normal(g)) return out;
      float total=h.energy_GeV*c.conv;total=total*(1.f+c.sigct*g);
      if(!std::isfinite(total)) {out.status|=ResponseArithmetic;return out;}
      float angle=0;
      // Original LAGANGLE treats either exactly-zero coordinate as angle zero.
      if(h.xyz_cm[0]!=0 && h.xyz_cm[1]!=0) {
        angle=std::atan2(h.xyz_cm[1],h.xyz_cm[0]);
        if(angle<0) angle=static_cast<float>(twopi+angle);
      }
      const float bow=angle*c.rc[ch];int wire;
      if(!laglwh(bow*fac,wire)) {out.status|=ResponseInvalidAddress;return out;}++wire;
      if(wire<1 || wire>c.nfc[ch]) {out.status|=ResponseInvalidAddress;return out;}
      const float phi=(static_cast<float>(wire)-.5f)/(fac*c.rc[ch]);
      for(int plane=0;plane<2;++plane) {
        const int k=2*ch+plane;
        const float bol=phi*d.radius[k];
        // PC1 in BOTH chambers is intentional source behavior.
        float x=bol*d.cang[k]-(h.xyz_cm[2]-c.pc[0])*d.sang[k];
        x=x+c.zc[ch]*d.sang[k];
        int index;
        if(!laglwh(x*static_cast<float>(c.nb[k])/d.xbl[k],index)) {
          out.status|=ResponseInvalidAddress;return out;
        }
        ++index;
        for(int j=-4;j<=4;++j) {
          const float a=static_cast<float>(index-1+j)*(c.bl+d.be[k])+d.be[k]/2.f;
          const float b=a+c.bl;
          // gconsp PI is DOUBLE in the preserved non-CERNLIB_SINGLE build;
          // differences B-X and A-X evaluate in REAL before promotion.
          const float charge=static_cast<float>(static_cast<double>(total)/pi/2.*
            (std::atan(std::sinh(pi*static_cast<double>(b-x)/2./c.dfca))-
             std::atan(std::sinh(pi*static_cast<double>(a-x)/2./c.dfca))));
          const int strip=lagmod(index+j,c.nb[k]);
          out.charges[k][strip-1]=out.charges[k][strip-1]+charge;
          out.charge_links.push_back({h.source_crossing,k,strip,charge});
          if(!std::isfinite(charge) || !std::isfinite(out.charges[k][strip-1])) {
            out.status|=ResponseArithmetic;return out;
          }
        }
      }
      WireAssociation link;link.source_crossing=h.source_crossing;link.chamber=ch;link.wire=wire;
      auto found=std::find(out.wires[ch].begin(),out.wires[ch].end(),wire);
      bool accepted=true;
      if(ch==0 && !draw_efficiency(ch,accepted)) return out;
      if(ch==0 && !accepted) link.state=WireState::EfficiencyRejected;
      else if(found!=out.wires[ch].end()) {
        link.state=WireState::Duplicate;link.digit_index=static_cast<int>(found-out.wires[ch].begin());
      } else {
        if(ch==1 && !draw_efficiency(ch,accepted)) return out;
        if(!accepted) link.state=WireState::EfficiencyRejected;
        else {link.state=WireState::Accepted;link.digit_index=static_cast<int>(out.wires[ch].size());out.wires[ch].push_back(wire);}
      }
      out.associations.push_back(link);
    }
  }
  // Every active strip is drawn, even for empty events; order is cathodes1..4.
  for(int k=0;k<4;++k) {
    for(int i=0;i<c.nb[k];++i) {
      float g;if(!draw_normal(g)) return out;
      float& charge=out.charges[k][i];charge=charge+c.sigce[k]*g;
      if(!std::isfinite(charge)) {out.status|=ResponseArithmetic;return out;}
      if(charge>=c.cythre) {
        out.read_flags[k][i]=true;
        for(int j=1;j<=c.nbord;++j) {
          out.read_flags[k][lagmod(i+1+j,c.nb[k])-1]=true;
          out.read_flags[k][lagmod(i+1-j,c.nb[k])-1]=true;
        }
      }
    }
    for(int i=0;i<c.nb[k];++i) {
      const float value=out.charges[k][i]*c.sccat/c.vsccat+.5f;
      // Source INT is signed32; never execute undefined nonfinite/overflow.
      if(!std::isfinite(value) || static_cast<double>(value)>=2147483648. || value<-2147483648.f) {
        out.status|=ResponseArithmetic;return out;
      }
      const int adc=static_cast<int>(value);
      if(out.read_flags[k][i] && adc>=1) out.cathodes[k].push_back({i+1,std::min(adc,static_cast<int>(c.sccat))});
    }
  }
  return out;
}
} // namespace legacy_cylinder
#endif
