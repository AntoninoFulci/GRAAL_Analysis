#ifndef GRAAL_CENTRAL_ASSOCIATION_HH
#define GRAAL_CENTRAL_ASSOCIATION_HH
// Measured-object port of PREAN ASSOCIA_2_NEW, ASSOCIA_3_NEW and
// FIND_TRACK_CBB (GRAAL_ASSOCIA_CYLBGO_BAR). This is not BGO clustering.
// Original REAL arithmetic requires binary32 and no fast-math/FP contraction.
#if defined(__FAST_MATH__)
#error "Central association requires strict floating-point arithmetic"
#endif
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>
namespace centralassociation {
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559 &&
              std::numeric_limits<float>::digits==24,"PREAN requires binary32");
inline constexpr const char* classification_source=
  "docs/reference/fortran/prog/prean/src/read_option.F:164-181";
inline constexpr float degrad=.0174532925199432958f,raddeg=57.2957795130823209f;
// Good: corrected matching angles are emitted and energy is ECLUSC.
// SP: corrected matching angles are distinct from raw emitted angles and
// energy is ECLUS_SP. All angles are degrees. Units pass through unchanged.
struct BgoCluster {
  float matching_theta_deg=0,matching_phi_deg=0;
  float emitted_theta_deg=0,emitted_phi_deg=0,energy=0;
};
struct Barrel { int channel=0,problem_index=0; float energy=0,time=0; };
struct CylinderTrack { float theta_deg=0,phi_deg=0; };
struct Input {
  std::vector<BgoCluster> good_bgo,sp_bgo;
  std::vector<Barrel> barrel;
  std::vector<CylinderTrack> cylinder;
};
struct Config {
  bool enable_bgo_sp=false;
  std::array<float,32> phi_deg{},xba1{};
  // Source IND_BAR -6..0 maps to index+6. -4,-3,-2 are undefined.
  std::array<int,7> bar_prob{};
  // TYPE_ARRAY(0:1,0:5,0:2), Fortran linear order. LBAR=5 is
  // uninitialized in read_option.F and is never an accepted config value.
  std::array<int,36> type_array{};
  Config() {
    // Undefined geometry is never silently interpreted as zero calibration.
    phi_deg.fill(std::numeric_limits<float>::quiet_NaN());
    xba1.fill(std::numeric_limits<float>::quiet_NaN());
    bar_prob={{4,3,-10,-10,-10,2,1}};
    int code=0;
    for(int bgo=0;bgo<3;++bgo) for(int bar=0;bar<5;++bar)
      for(int cyl=0;cyl<2;++cyl) type_array[cyl+2*bar+12*bgo]=++code;
  }
};
// Only source-defined classifications are supplied. Detector angles and XBA1
// must be explicit caller inputs, independently selected from their source.
inline Config source_config(const std::array<float,32>& phi,
                            const std::array<float,32>& xba,bool enable_sp) {
  Config c; c.enable_bgo_sp=enable_sp; c.phi_deg=phi; c.xba1=xba;
  return c;
}
enum Status : std::uint32_t {
  Supported=0,CapacityExceeded=1u,InvalidInput=2u,InvalidConfig=4u,
  UndefinedNoCylinder=8u,DisabledSpInput=16u,NonFiniteArithmetic=32u
};
enum class ObjectKind { GoodBgo,SpBgo,Barrel,Cylinder };
// Every input is linked, including unsupported inputs. Indices are one-based
// within their original input collection; no truth identifiers are accepted.
struct DiagnosticLink { ObjectKind kind; std::size_t index; };
struct Pair { int bgo=0,cylinder=0; };
struct Association {
  // One-based source indices; bgo is good followed by SP, zero means missing.
  int bgo=0,barrel=0,cylinder=0,type=0,barrel_channel=0,barrel_problem_index=-1;
  float dedx=-1,barrel_time=-1,barrel_phi_deg=-1;
  float bgo_energy=-1,bgo_theta_deg=-1,bgo_phi_deg=-1;
  float cylinder_theta_deg=-1,cylinder_phi_deg=-1,theta_deg=-1,phi_deg=-1;
};
struct Result {
  std::uint32_t status=Supported;
  std::vector<Pair> stage2;
  std::vector<Association> associations;
  std::vector<DiagnosticLink> diagnostic_links;
};
inline float delta_phi(float first,float second) {
  const float dp=(second-first)*degrad;
  const float cosine=std::cos(dp);
  return std::acos(cosine)*raddeg;
}
namespace detail {
inline bool finite(float x) { return std::isfinite(x); }
inline bool angle(float theta,float phi) {
  return finite(theta)&&finite(phi)&&theta>=0&&theta<=180;
}
// Original scan uses <=, so the last equal pair wins. Rows and columns
// are retired even when the selected minimum exceeds the angular cut.
inline std::vector<std::array<int,2>> greedy(std::vector<std::vector<float>> d) {
  std::vector<std::array<int,2>> out;
  if(d.empty()||d[0].empty()) return out;
  const int nr=static_cast<int>(d.size()),nc=static_cast<int>(d[0].size());
  for(int k=0;k<nr+nc;++k) {
    int imin=0,jmin=0;
    for(int i=0;i<nr;++i) for(int j=0;j<nc;++j)
      if(d[i][j]<=d[imin][jmin]) { imin=i; jmin=j; }
    const float minimum=d[imin][jmin];
    if(minimum==1.e6f) break;
    if(minimum<=11.5f) out.push_back({imin+1,jmin+1});
    for(int j=0;j<nc;++j) d[imin][j]=1.e6f;
    for(int i=0;i<nr;++i) d[i][jmin]=1.e6f;
  }
  return out;
}
} // namespace detail
inline Result find_track_cbb(const Input& in,const Config& c) {
  Result r;
  auto links=[&](ObjectKind k,std::size_t n) {
    for(std::size_t i=0;i<n;++i) r.diagnostic_links.push_back({k,i+1});
  };
  links(ObjectKind::GoodBgo,in.good_bgo.size()); links(ObjectKind::SpBgo,in.sp_bgo.size());
  links(ObjectKind::Barrel,in.barrel.size()); links(ObjectKind::Cylinder,in.cylinder.size());
  if(in.good_bgo.size()>30||in.sp_bgo.size()>30||in.barrel.size()>32||in.cylinder.size()>5)
    r.status|=CapacityExceeded;
  if(!c.enable_bgo_sp&&!in.sp_bgo.empty()) r.status|=DisabledSpInput;
  if(r.status) return r;
  std::vector<BgoCluster> bgo=in.good_bgo;
  bgo.insert(bgo.end(),in.sp_bgo.begin(),in.sp_bgo.end());
  for(const auto& b:bgo) if(!detail::angle(b.matching_theta_deg,b.matching_phi_deg)||
     !detail::angle(b.emitted_theta_deg,b.emitted_phi_deg)||!detail::finite(b.energy)) r.status|=InvalidInput;
  for(const auto& t:in.cylinder) if(!detail::angle(t.theta_deg,t.phi_deg)) r.status|=InvalidInput;
  for(const auto& b:in.barrel) {
    if(b.channel<1||b.channel>32||b.problem_index< -6||b.problem_index>0||
       !detail::finite(b.energy)||!detail::finite(b.time)) { r.status|=InvalidInput; continue; }
    const int bar=c.bar_prob[b.problem_index+6];
    if(bar<1||bar>4) r.status|=InvalidInput;
    if(!detail::finite(c.phi_deg[b.channel-1])||!detail::finite(c.xba1[b.channel-1])) r.status|=InvalidConfig;
  }
  if(r.status) return r;
  const int n1=static_cast<int>(bgo.size()),n2=static_cast<int>(in.barrel.size()),n3=static_cast<int>(in.cylinder.size());
  // ASSOCIA_3_NEW reads uninitialized IOUT_TET only when both its dimensions
  // are nonzero. Pure BGO is defined; pure barrel uses FIND_TRACK_CBB bypass.
  if(n3==0&&n1!=0&&n2!=0) { r.status=UndefinedNoCylinder; return r; }
  std::vector<std::vector<float>> d(n1,std::vector<float>(n3));
  for(int i=0;i<n1;++i) for(int j=0;j<n3;++j) {
    float dp=delta_phi(bgo[i].matching_phi_deg,in.cylinder[j].phi_deg);
    if(in.cylinder[j].theta_deg<=24||in.cylinder[j].theta_deg>=156) dp=1.e6f;
    const float dt=bgo[i].matching_theta_deg-in.cylinder[j].theta_deg;
    const float aa=dp*dp,bb=dt*dt;
    d[i][j]=std::sqrt(aa+bb);
    if(!detail::finite(d[i][j])) r.status|=NonFiniteArithmetic;
  }
  if(r.status) return r;
  for(const auto& p:detail::greedy(d)) r.stage2.push_back({p[0],p[1]});
  for(int i=1;i<=n1;++i) {
    bool found=false; for(const auto& p:r.stage2) if(p.bgo==i) found=true;
    if(!found) r.stage2.push_back({i,0});
  }
  for(int j=1;j<=n3;++j) {
    bool found=false; for(const auto& p:r.stage2) if(p.cylinder==j) found=true;
    if(!found) r.stage2.push_back({0,j});
  }
  const int np=static_cast<int>(r.stage2.size());
  std::vector<std::array<int,3>> triples;
  if(n1+n3==0) { // Source bypass also avoids stale IASS_2 for pure barrel.
    for(int i=1;i<=n2;++i) triples.push_back({0,i,0});
  } else {
    d.assign(n2,std::vector<float>(np));
    for(int i=0;i<n2;++i) for(int j=0;j<np;++j) {
      const auto p=r.stage2[j];
      const float phi=p.cylinder?in.cylinder[p.cylinder-1].phi_deg:bgo[p.bgo-1].matching_phi_deg;
      d[i][j]=delta_phi(c.phi_deg[in.barrel[i].channel-1],phi);
      if(!p.bgo&&p.cylinder&&(in.cylinder[p.cylinder-1].theta_deg<=24||in.cylinder[p.cylinder-1].theta_deg>=156)) d[i][j]=1.e6f;
      if(!detail::finite(d[i][j])) r.status|=NonFiniteArithmetic;
    }
    if(r.status) return r;
    for(const auto& p:detail::greedy(d)) {
      const auto pair=r.stage2[p[1]-1]; triples.push_back({pair.bgo,p[0],pair.cylinder});
    }
    if(n2&&np) {
      for(int i=1;i<=n2;++i) {
        bool found=false; for(const auto& t:triples) if(t[1]==i) found=true;
        if(!found) triples.push_back({0,i,0});
      }
      // Preserve original zero-comparison semantics in unmatched append.
      for(const auto& p:r.stage2) {
        bool fb=false,fc=false;
        for(const auto& t:triples) { if(t[0]==p.bgo) fb=true; if(t[2]==p.cylinder) fc=true; }
        if(!fb||!fc) triples.push_back({p.bgo,0,p.cylinder});
      }
    } else for(const auto& p:r.stage2) triples.push_back({p.bgo,0,p.cylinder});
  }
  for(const auto& t:triples) {
    Association a; a.bgo=t[0]; a.barrel=t[1]; a.cylinder=t[2];
    const int lbgo=a.bgo?(a.bgo<=static_cast<int>(in.good_bgo.size())?1:2):0;
    const int lbar=a.barrel?c.bar_prob[in.barrel[a.barrel-1].problem_index+6]:0;
    a.type=c.type_array[(a.cylinder?1:0)+2*lbar+12*lbgo];
    if(lbar) {
      const auto b=in.barrel[a.barrel-1]; a.barrel_channel=b.channel;
      a.barrel_problem_index=b.problem_index; a.dedx=b.energy; a.barrel_time=b.time;
      a.barrel_phi_deg=c.phi_deg[b.channel-1];
    }
    if(lbgo) {
      const auto b=bgo[a.bgo-1]; a.bgo_energy=b.energy;
      a.bgo_theta_deg=lbgo==1?b.matching_theta_deg:b.emitted_theta_deg;
      a.bgo_phi_deg=lbgo==1?b.matching_phi_deg:b.emitted_phi_deg;
    }
    if(a.cylinder) {
      const auto t=in.cylinder[a.cylinder-1]; a.cylinder_theta_deg=t.theta_deg; a.cylinder_phi_deg=t.phi_deg;
      a.theta_deg=t.theta_deg; a.phi_deg=t.phi_deg;
    } else if(lbgo) { a.theta_deg=a.bgo_theta_deg; a.phi_deg=a.bgo_phi_deg; }
    else if(lbar) a.phi_deg=a.barrel_phi_deg;
    if(lbar&&a.theta_deg!=-1) {
      const float yy=a.theta_deg;
      const float xol=std::abs(yy-90.f)<.1f?.5f:4.7f/(21.7f*std::tan(yy*degrad))+.5f;
      if(!detail::finite(xol)) {
        r.status=NonFiniteArithmetic; r.associations.clear(); return r;
      }
      const float exponent=-c.xba1[a.barrel_channel-1]*xol;
      if(!detail::finite(exponent)) {
        r.status=NonFiniteArithmetic; r.associations.clear(); return r;
      }
      const float fexp=std::exp(exponent);
      // Infinite attenuation can hide as finite zero after division, while
      // exponential underflow gives a zero divisor. Neither is valid data.
      if(!detail::finite(fexp)||fexp<=0) {
        r.status=NonFiniteArithmetic; r.associations.clear(); return r;
      }
      const float fnorm=(2.f*std::sin(yy*degrad))/fexp;
      a.dedx=a.dedx*fnorm;
      if(!detail::finite(a.dedx)||!detail::finite(fnorm)) { r.status=NonFiniteArithmetic; r.associations.clear(); return r; }
    }
    r.associations.push_back(a);
  }
  return r;
}
} // namespace centralassociation
#endif
