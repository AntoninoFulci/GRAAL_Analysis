#ifndef GRAAL_CYLINDER_TRACKING_HH
#define GRAAL_CYLINDER_TRACKING_HH

// Digit-only port of PREAN's active OLD_CYL + LSIMUL chain. All source REAL
// arithmetic is binary32; compile without fast-math and FP contraction.
#if defined(__FAST_MATH__)
#error "OLD_CYL tracking requires strict floating-point arithmetic"
#endif
#include "NewPlan.hh" // Reuse the recovered CERNLIB SORTZV MODE=1 heap order.
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace cylindertracking {
inline constexpr const char* configuration_source =
  "docs/reference/fortran/prog/prean/src/initialisation_cylindres.F";
inline constexpr const char* configuration_sha256 =
  "7e8d158f8da2f7e663363fcc29b8af20bbd9c31a8a60cd321b08f078905f6f21";
inline constexpr const char* pedestal_source =
  "docs/reference/fortran/prog/prean/src/mwpc_ped.F";
inline constexpr const char* pedestal_sha256 =
  "f5be63d3d3576338df395c1f65d1a38614ebafe146f0ff4e193584b20e6fd039";
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559 &&
              std::numeric_limits<float>::digits==24,"OLD_CYL requires binary32");
struct StripDigit { int strip,adc; };
struct Digits {
  std::array<std::vector<int>,2> wires;
  std::array<std::vector<StripDigit>,4> cathodes;
};
struct CathodeConfig {
  int strips=0, overlap=2, min_multiplicity=2;
  float a=0,b=0,c=0,width_cm=0,offset_cm=.2f,strip_threshold=0,min_charge=0;
  std::array<int,96> pedestal{};
  std::array<float,96> gain{};
};
struct Config {
  std::array<CathodeConfig,4> cathodes;
  std::array<int,2> wire_count{{128,192}};
  std::array<float,2> phi_offset_deg{{0,0}},z_min_cm{{0,0}},
    z_max_cm{{39.f,49.5f}},dz_cut_cm{{.35f,.30f}};
  float dphi_cut_deg=8.f;
};
// Sources: prean/src/initialisation_cylindres.F OLD_CYL+LSIMUL,
// prean/src/mwpc_ped.F LSIMUL (zero pedestals). No run alignment/calibration.
inline Config old_cyl_simulation_config() {
  Config out;
  constexpr float pi=3.14159265358979324f,degrad=.0174532925199432958f;
  const int counts[4]={60,64,96,96};
  const float radii[4]={5.f-.4f,5.f+.4f,8.5f-.4f,8.5f+.4f};
  const float angles[4]={33.86f,-41.01f,41.01f,-46.63f};
  for(int p=0;p<4;++p) {
    auto& c=out.cathodes[p]; c.strips=counts[p]; c.gain.fill(1.f);
    const float angle=angles[p]*degrad;
    c.a=-radii[p]/std::tan(angle); c.a=c.a*pi/180.f;
    c.b=-1.f/std::sin(angle); c.c=360.f*std::abs(c.a);
    c.width_cm=2.f*pi*radii[p]*std::cos(angle);
  }
  return out;
}
enum Unsupported : std::uint32_t {
  Supported=0, InvalidConfig=1u, InvalidDigit=2u, RawCapacityExceeded=4u,
  CathodeCandidateScratchOverflow=8u, NonFiniteArithmetic=16u
};
struct Cluster {
  int multiplicity=0;
  float center_cm=0,charge=0;
  // Original digit indices (zero based), in source cluster interval order.
  std::vector<std::size_t> digit_indices;
};
struct Group { int multiplicity=1; float phi_deg=0; std::size_t digit_index=0; };
struct Association {
  int multiplicity1=0,multiplicity2=0;
  float charge1=0,charge2=0,dz_cm=0,z_cm=0,phi_deg=0;
  int cathode1=0,cathode2=0,wire_group=0; // Original one-based indices.
};
struct Track {
  std::array<float,3> inner_cm{},outer_cm{};
  float dz_inner_cm=0,dz_outer_cm=0,dphi_deg=0,theta_deg=0,phi_deg=0,z_vertex_cm=0;
  int inner_association=0,outer_association=0; // Original one-based indices.
};
struct Reconstruction {
  std::array<std::vector<Cluster>,4> clusters;
  std::array<std::vector<Group>,2> groups;
  std::array<std::vector<Association>,2> associations;
  std::vector<Track> tracks;
  std::array<int,4> cathode_status{};
  std::array<int,2> wire_status{},association_status{};
  int track_status=0,legacy_status=0;
  std::uint32_t unsupported=Supported;
};
namespace detail {
inline bool bounded(float value,float bound=1.e4f) {
  return std::isfinite(value) && std::abs(value)<=bound;
}
inline bool valid(const Config& g) {
  if(g.wire_count!=std::array<int,2>{{128,192}} ||
     !bounded(g.dphi_cut_deg,360.f) || g.dphi_cut_deg<0) return false;
  for(int i=0;i<2;++i)
    if(!bounded(g.phi_offset_deg[i],360.f) || !bounded(g.z_min_cm[i]) ||
       !bounded(g.z_max_cm[i]) || g.z_min_cm[i]>g.z_max_cm[i] ||
       !bounded(g.dz_cut_cm[i],1000.f) || g.dz_cut_cm[i]<0) return false;
  const int counts[4]={60,64,96,96};
  for(int p=0;p<4;++p) {
    const auto& c=g.cathodes[p];
    if(c.strips!=counts[p] || c.overlap<0 || c.overlap>96 ||
       c.min_multiplicity<0 || c.min_multiplicity>50 ||
       !bounded(c.a) || !bounded(c.b) || !bounded(c.c) ||
       !bounded(c.width_cm) || c.width_cm<=0 || !bounded(c.offset_cm) ||
       !bounded(c.strip_threshold) || c.strip_threshold<0 ||
       !bounded(c.min_charge)) return false;
    for(int k=0;k<c.strips;++k)
      if(!bounded(c.gain[k]) || c.gain[k]<0) return false;
  }
  return true;
}
inline std::vector<Cluster> cathode(const std::vector<StripDigit>& input,
                                  const CathodeConfig& c,int& status,
                                  std::uint32_t& unsupported) {
  std::vector<Cluster> out;
  std::array<float,193> charge{};
  std::array<int,193> index{}; index.fill(-1);
  for(std::size_t i=0;i<input.size();++i) {
    const auto& d=input[i]; const int k=d.strip;
    // Original reads pedestal/gain BEFORE its K<=NB check: inactive IDs,
    // including61..64 in cathode1, are undefined and explicitly excluded.
    if(k<1 || k>c.strips) { unsupported|=InvalidDigit; return {}; }
    const std::int64_t delta=std::int64_t(d.adc)-c.pedestal[k-1];
    if(delta<std::numeric_limits<int>::min() || delta>std::numeric_limits<int>::max()) {
      unsupported|=InvalidDigit; return {};
    }
    const float q=static_cast<float>(delta)*c.gain[k-1];
    if(q>c.strip_threshold) { charge[k]=q; index[k]=static_cast<int>(i); }
  }
  struct Range { int lo=0,hi=0,peak=0; float maximum=0; };
  std::vector<Range> runs;
  for(int k=1;k<=c.strips;) {
    if(index[k]<0) { ++k; continue; }
    const int lo=k;
    while(k<=c.strips && index[k]>=0) ++k;
    runs.push_back({lo,k-1,0,0});
  }
  if(runs.empty()) return out;
  if(runs.front().lo==1 && runs.back().hi==c.strips) {
    runs.front().lo=runs.back().lo; runs.front().hi+=c.strips;
    for(int k=c.strips+1;k<=runs.front().hi;++k) {
      charge[k]=charge[k-c.strips]; index[k]=index[k-c.strips];
    }
    // This deliberately reproduces the all-strips-occupied source case: its
    // only run is joined to itself, NB_CLUSTERS_0 becomes zero.
    runs.pop_back();
  }
  std::vector<Range> split;
  for(const auto& run:runs) {
    std::vector<Range> maxima(1); maxima[0].lo=run.lo;
    for(int k=run.lo;k<run.hi;++k) {
      auto& m=maxima.back();
      if(charge[k]>=m.maximum) { m.peak=k; m.maximum=charge[k]; m.hi=k; }
      else if(charge[k]>=charge[k+1]) m.hi=k;
      else maxima.push_back({k,0,k,charge[k]});
    }
    auto& last=maxima.back();
    if(charge[run.hi]>=last.maximum) { last.peak=run.hi; last.maximum=charge[run.hi]; }
    last.hi=run.hi;
    split.push_back(maxima[0]);
    for(std::size_t j=1;j<maxima.size();++j) {
      if(maxima[j].peak-maxima[j-1].peak-1>=c.overlap) split.push_back(maxima[j]);
      else {
        auto& s=split.back();
        if(maxima[j].maximum>=s.maximum) { s.peak=maxima[j].peak; s.maximum=maxima[j].maximum; }
        s.hi=maxima[j].hi;
      }
    }
  }
  if(split.size()>20) { status=1; return {}; }
  for(const auto& s:split) {
    Cluster cluster; const int mult=s.hi-s.lo+1;
    float total=0,barycenter=0;
    for(int k=s.lo;k<=s.hi;++k) {
      total=total+charge[k]; cluster.digit_indices.push_back(static_cast<std::size_t>(index[k]));
    }
    if(mult==1) barycenter=static_cast<float>(s.lo);
    else if(mult==2)
      barycenter=(charge[s.lo]*static_cast<float>(s.lo)+charge[s.hi]*static_cast<float>(s.hi))/(charge[s.lo]+charge[s.hi]);
    else if(s.peak!=s.lo && s.peak!=s.hi)
      barycenter=static_cast<float>(s.peak)+1.45f*(-charge[s.peak-1]+charge[s.peak+1])/(charge[s.peak-1]+charge[s.peak]+charge[s.peak+1]);
    else barycenter=static_cast<float>(s.peak);
    cluster.center_cm=(barycenter-1.f)*.4f;
    cluster.center_cm=cluster.center_cm+c.offset_cm;
    if(cluster.center_cm<0.f) cluster.center_cm=cluster.center_cm+c.width_cm;
    if(cluster.center_cm>c.width_cm) cluster.center_cm=cluster.center_cm-c.width_cm;
    cluster.multiplicity=std::min(mult,50); cluster.charge=std::min(total,15.e3f);
    if(!std::isfinite(cluster.center_cm) || !std::isfinite(cluster.charge)) {
      unsupported|=NonFiniteArithmetic; return {};
    }
    out.push_back(cluster);
  }
  return out;
}
inline std::vector<Association> associate(const std::vector<Cluster>& first,
    const std::vector<Cluster>& second,const std::vector<Group>& groups,
    const Config& config,int chamber,int& status,std::uint32_t& unsupported) {
  std::vector<Association> out;
  if(first.empty() || second.empty() || groups.empty()) return out;
  struct Candidate { int index; float z; };
  for(std::size_t w=0;w<groups.size();++w) {
    std::array<std::vector<Candidate>,2> candidates;
    for(int p=0;p<2;++p) {
      const auto& clusters=p==0?first:second;
      const auto& c=config.cathodes[2*chamber+p];
      for(std::size_t k=0;k<clusters.size();++k) {
        const auto& cluster=clusters[k];
        if(cluster.multiplicity>=c.min_multiplicity && cluster.charge>c.min_charge) {
          float z=c.a*groups[w].phi_deg-c.b*cluster.center_cm;
          if(z<0.f) z=z+c.c;
          if(z>=config.z_min_cm[chamber] && z<=config.z_max_cm[chamber])
            candidates[p].push_back({static_cast<int>(k),z});
        }
      }
      // IND_BAND{1,2}_TEMP is declared length5 in the ORIGINAL routine,
      // even though its other scratch arrays are length20.
      if(candidates[p].size()>5) { unsupported|=CathodeCandidateScratchOverflow; return {}; }
    }
    float dz_min=1000000.f; int i1=-1,i2=-1;
    for(std::size_t i=0;i<candidates[0].size();++i)
      for(std::size_t j=0;j<candidates[1].size();++j) {
        const float dz=candidates[1][j].z-candidates[0][i].z;
        if(std::abs(dz)<std::abs(dz_min)) { dz_min=dz; i1=static_cast<int>(i); i2=static_cast<int>(j); }
      }
    if(std::abs(dz_min)<config.dz_cut_cm[chamber]) {
      if(out.size()==5) { status=1; return {}; }
      const auto& a=candidates[0][i1]; const auto& b=candidates[1][i2];
      const auto& c1=first[a.index]; const auto& c2=second[b.index];
      out.push_back({c1.multiplicity,c2.multiplicity,c1.charge,c2.charge,dz_min,
                     .5f*(a.z+b.z),groups[w].phi_deg,a.index+1,b.index+1,static_cast<int>(w)+1});
    }
  }
  return out;
}
} // namespace detail

inline bool calculate_angles(const std::array<float,3>& first,
                             const std::array<float,3>& second,
                             float& theta,float& phi) {
  const float dx=second[0]-first[0],dy=second[1]-first[1],dz=second[2]-first[2];
  const float dr=std::sqrt(dx*dx+dy*dy+dz*dz);
  if(!std::isfinite(dr) || dr==0.f) { theta=phi=0.f; return false; }
  theta=std::acos(dz/dr)*57.2957795130823209f;
  if(dx!=0.f) {
    phi=std::atan(dy/dx)*57.2957795130823209f;
    if(dx<0.f) phi=phi+180.f;
    else if(dy<0.f) phi=phi+360.f;
  } else phi=0.f; // Preserve the source's explicit degenerate-X convention.
  return std::isfinite(theta) && std::isfinite(phi);
}
inline Reconstruction reconstruct(const Digits& digits,const Config& config) {
  Reconstruction out;
  if(!detail::valid(config)) { out.unsupported=InvalidConfig; return out; }
  const int capacity[4]={64,64,96,96};
  for(int p=0;p<4;++p) {
    // Original cathode-method2 locals are initialized only through NB(p).
    // COMMON capacity64 does not define input slots61..64 for cathode1.
    if(digits.cathodes[p].size()>static_cast<std::size_t>(capacity[p]) ||
       digits.cathodes[p].size()>static_cast<std::size_t>(config.cathodes[p].strips))
      out.unsupported|=RawCapacityExceeded;
  }
  for(int ch=0;ch<2;++ch) {
    if(digits.wires[ch].size()>static_cast<std::size_t>(config.wire_count[ch])) out.unsupported|=RawCapacityExceeded;
    for(int w:digits.wires[ch]) if(w<1 || w>config.wire_count[ch]) out.unsupported|=InvalidDigit;
  }
  if(out.unsupported) return out;
  for(int p=0;p<4;++p)
    out.clusters[p]=detail::cathode(digits.cathodes[p],config.cathodes[p],out.cathode_status[p],out.unsupported);
  if(out.unsupported) return out;
  for(int ch=0;ch<2;++ch) {
    if(digits.wires[ch].size()>20) out.wire_status[ch]=1;
    else for(std::size_t i=0;i<digits.wires[ch].size();++i) {
      float phi=(static_cast<float>(digits.wires[ch][i])-.5f)*360.f/static_cast<float>(config.wire_count[ch]);
      phi=phi+config.phi_offset_deg[ch];
      if(phi<0.f) phi=phi+360.f;
      if(phi>=360.f) phi=phi-360.f;
      out.groups[ch].push_back({1,phi,i});
    }
    out.associations[ch]=detail::associate(out.clusters[2*ch],out.clusters[2*ch+1],out.groups[ch],config,ch,out.association_status[ch],out.unsupported);
  }
  if(!out.unsupported) {
    struct Pair { int first,second; float delta; };
    std::vector<Pair> pairs; std::vector<float> scores;
    for(std::size_t a=0;a<out.associations[0].size();++a)
      for(std::size_t b=0;b<out.associations[1].size();++b) {
        float delta=out.associations[0][a].phi_deg-out.associations[1][b].phi_deg;
        if(delta<-180.f) delta=delta+360.f;
        if(delta>180.f) delta=delta-360.f;
        pairs.push_back({static_cast<int>(a),static_cast<int>(b),delta}); scores.push_back(std::abs(delta));
      }
    for(int index:newplan::detail::sort_indices(scores)) {
      const auto& pair=pairs[index]; if(scores[index]>config.dphi_cut_deg) continue;
      bool used=false;
      for(const auto& t:out.tracks) if(t.inner_association==pair.first+1 || t.outer_association==pair.second+1) used=true;
      if(used) continue;
      if(out.tracks.size()==5) { out.track_status=1; out.tracks.clear(); break; }
      const auto& a=out.associations[0][pair.first]; const auto& b=out.associations[1][pair.second];
      constexpr float degrad=.0174532925199432958f;
      Track t; t.inner_association=pair.first+1; t.outer_association=pair.second+1;
      t.inner_cm={5.f*std::cos(a.phi_deg*degrad),5.f*std::sin(a.phi_deg*degrad),19.5f-a.z_cm+.9f};
      t.outer_cm={8.5f*std::cos(b.phi_deg*degrad),8.5f*std::sin(b.phi_deg*degrad),24.75f-b.z_cm+.9f};
      t.dz_inner_cm=a.dz_cm; t.dz_outer_cm=b.dz_cm; t.dphi_deg=pair.delta;
      if(!calculate_angles(t.inner_cm,t.outer_cm,t.theta_deg,t.phi_deg)) {
        out.unsupported|=NonFiniteArithmetic; out.tracks.clear(); break;
      }
      t.z_vertex_cm=(5.f*t.outer_cm[2]-8.5f*t.inner_cm[2])/(5.f-8.5f);
      out.tracks.push_back(t);
      if(out.tracks.size()==std::min(out.associations[0].size(),out.associations[1].size())) break;
    }
  }
  for(int status:out.cathode_status) out.legacy_status+=status;
  for(int status:out.wire_status) out.legacy_status+=10*status;
  for(int status:out.association_status) out.legacy_status+=100*status;
  out.legacy_status+=1000*out.track_status;
  return out;
}
} // namespace cylindertracking
#endif
