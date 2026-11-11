#ifndef GRAAL_NEW_PLAN_HH
#define GRAAL_NEW_PLAN_HH

// Port of preserved lagdig PLCH/LAGROTA/LAGLWH and prean
// ANAPLN4/ANAPLN_CLUSTERS/TRANSFO. Compile without fast-math or FP contraction.
// Inputs/outputs are cm, binary32, ordered channels; no truth enters tracking.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <numeric>
#include <vector>

namespace newplan {
static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559 &&
              std::numeric_limits<float>::digits==24, "NEW_PLAN requires IEEE binary32");
struct Geometry {
  float xp1_cm, xp2_cm, zp1_cm, zp2_cm;
  int nf1, nf2;
  float angle_deg;
};
inline Geometry geometry26() { return {48.f,57.6f,94.4f,134.4f,320,384,-45.f}; }
enum Status : std::uint32_t {
  Ok=0, InvalidGeometry=1u<<0, InvalidCrossing=1u<<1,
  InvalidEfficiency=1u<<2, RawOverflow=1u<<3, InvalidWire=1u<<4,
  UndefinedXYUpper=1u<<5, CombinationOverflow=1u<<6,
  CoordinateCollision=1u<<7, NonFiniteArithmetic=1u<<8,
  // U/V clamp is defined, but deduplication occurs BEFORE this clamp.
  UVUpperClamped=1u<<9
};
inline bool supported(std::uint32_t status) {
  return status == Ok;
}
using WireLists = std::array<std::vector<int>,4>;
struct Crossing { int plane; float x_cm,y_cm; };
enum class CrossingState : int { Accepted=0, Duplicate=1, EfficiencyRejected=2,
                                Invalid=3, UnsupportedOverflow=4 };
struct CrossingAssociation {
  std::size_t crossing_index;
  int plane, wire, digit_index; // index within plane; -1 if no digit
  CrossingState state;
};
struct DigitResult {
  WireLists wires;
  std::array<std::size_t,4> raw_counts{};
  std::vector<CrossingAssociation> associations;
  std::uint32_t status=Ok;
};
struct Track {
  std::array<float,3> first_cm{},second_cm{};
  int cl=0;
  std::array<int,4> cluster_indices{{-1,-1,-1,-1}};
  std::array<std::vector<std::size_t>,4> wire_indices;
};
struct Reconstruction {
  std::vector<Track> tracks;
  std::array<int,4> raw_multiplicity{},reduced_multiplicity{};
  int candidate_count=0, cltot=0;
  std::uint32_t status=Ok;
};
namespace detail {
inline bool valid(const Geometry& g) {
  // The selected26 kernel deliberately exposes only the recovered NEW_PLAN
  // channel layout. Bounds also prevent arithmetic overflow on user config.
  return g.nf1==320 && g.nf2==384 && std::isfinite(g.angle_deg) &&
    std::abs(g.angle_deg)<=360.f && std::isfinite(g.xp1_cm) &&
    std::isfinite(g.xp2_cm) && std::isfinite(g.zp1_cm) &&
    std::isfinite(g.zp2_cm) && g.xp1_cm>0.f && g.xp2_cm>0.f &&
    g.zp1_cm>0.f && g.zp2_cm>g.zp1_cm &&
    g.xp1_cm<=1.e6f && g.xp2_cm<=1.e6f && g.zp2_cm<=1.e6f &&
    g.xp1_cm>=1.e-6f && g.xp2_cm>=1.e-6f && g.zp1_cm>=1.e-6f;
}
struct Rotation {
  float s,c;
  explicit Rotation(float degrees, bool digitization=false) {
    // LAGFILL uses gconsp DEGRAD (DOUBLE without CERNLIB_SINGLE);
    // PREAN CONSTAN uses its own implicit-REAL prean_const.inc DEGRAD.
    const float radians=digitization
      ? static_cast<float>(static_cast<double>(degrees)*0.0174532925199432958)
      : degrees*0.0174532925199432958f;
    s=std::sin(radians); c=std::cos(radians);
  }
  std::array<float,2> operator()(float x,float y,bool inverse) const {
    if(inverse) return {x*c-y*s,y*c+x*s};
    return {x*c+y*s,y*c-x*s};
  }
};
struct Cluster { float center; std::vector<std::size_t> indices; };
inline std::vector<Cluster> clusters(const std::vector<int>& wires) {
  std::vector<Cluster> out;
  for(std::size_t i=0;i<wires.size();++i) {
    bool found=false;
    for(auto& c:out) {
      const float distance=static_cast<float>(wires[i])-c.center;
      if(std::abs(distance)==1.f || std::abs(distance)==1.5f) {
        c.center += distance>=0.f ? .5f : -.5f;
        c.indices.push_back(i); found=true; break;
      }
    }
    // Original duplicate / half-distance warnings still create a cluster.
    if(!found) out.push_back({static_cast<float>(wires[i]),{i}});
  }
  return out;
}
// CERNLIB SORTZV MODE=1, NWAY=0, NSORT=0: SORTTF max heap; exact
// nonstable tie ordering. Source provenance is recorded in kernels report.
inline std::vector<int> sort_indices(const std::vector<float>& values) {
  std::vector<int> heap(values.size());
  std::iota(heap.begin(),heap.end(),0);
  for(std::size_t i=1;i<heap.size();++i) {
    const int index=heap[i]; std::size_t child=i;
    while(child>0) {
      const std::size_t parent=(child-1)/2;
      if(values[index]<=values[heap[parent]]) break;
      heap[child]=heap[parent]; child=parent;
    }
    heap[child]=index;
  }
  for(std::size_t end=heap.size();end>1;--end) {
    const int index=heap[end-1]; heap[end-1]=heap[0];
    std::size_t parent=0;
    while(2*parent+1<end-1) {
      std::size_t child=2*parent+1;
      if(child+1<end-1 && values[heap[child]]<values[heap[child+1]]) ++child;
      if(values[index]>=values[heap[child]]) break;
      heap[parent]=heap[child]; parent=child;
    }
    heap[parent]=index;
  }
  return heap;
}
} // namespace detail

// Draws follow U,V,X,Y and original within-plane order, including duplicates.
// Default selected26 response is exact efficiency 1, with no random smearing.
inline DigitResult digitize(const std::vector<Crossing>& crossings,
                            const Geometry& g,
                            const std::function<float(int)>& draw={}) {
  DigitResult out;
  for(const auto& c:crossings) {
    if(c.plane<0 || c.plane>3) out.status|=InvalidCrossing;
    else ++out.raw_counts[c.plane];
  }
  if(!detail::valid(g)) out.status|=InvalidGeometry;
  for(auto n:out.raw_counts) if(n>20) out.status|=RawOverflow;
  if(out.status!=Ok) {
    for(std::size_t i=0;i<crossings.size();++i)
      out.associations.push_back({i,crossings[i].plane,0,-1,
        out.status&RawOverflow ? CrossingState::UnsupportedOverflow : CrossingState::Invalid});
    return out;
  }
  const detail::Rotation rotate(g.angle_deg,true);
  for(int p=0;p<4;++p) {
    const int nf=p<2?g.nf1:g.nf2;
    const float pitch=2.f*(p<2?g.xp1_cm:g.xp2_cm)/static_cast<float>(nf);
    for(std::size_t i=0;i<crossings.size();++i) {
      const auto& c=crossings[i]; if(c.plane!=p) continue;
      CrossingAssociation a{i,p,0,-1,CrossingState::Invalid};
      const float efficiency=draw ? draw(p) : 1.f;
      if(!std::isfinite(efficiency) || efficiency<0.f || efficiency>1.f) {
        out.status|=InvalidEfficiency; out.associations.push_back(a); continue;
      }
      if(static_cast<int>(efficiency+.5f)==0) {
        a.state=CrossingState::EfficiencyRejected; out.associations.push_back(a); continue;
      }
      if(!std::isfinite(c.x_cm) || !std::isfinite(c.y_cm)) {
        out.status|=InvalidCrossing; out.associations.push_back(a); continue;
      }
      const auto xy=p<2?rotate(c.x_cm,c.y_cm,false):std::array<float,2>{c.x_cm,c.y_cm};
      const float address=xy[p%2]/pitch;
      // Use binary64 only for the conversion guard. All source arithmetic
      // remains binary32; avoid undefined float-to-int or signed overflow.
      if(!std::isfinite(address) || static_cast<double>(address)<-2147483000. ||
         static_cast<double>(address)>2147483000.) {
        out.status|=InvalidCrossing; out.associations.push_back(a); continue;
      }
      int wire=static_cast<int>(address)-(address<0.f?1:0)+1+nf/2;
      if(wire==0) wire=1;
      a.wire=wire;
      if(wire<1) { out.status|=InvalidWire; out.associations.push_back(a); continue; }
      auto& wires=out.wires[p];
      auto previous=std::find(wires.begin(),wires.end(),wire);
      if(previous!=wires.end()) {
        a.digit_index=static_cast<int>(previous-wires.begin());
        a.state=CrossingState::Duplicate; out.associations.push_back(a); continue;
      }
      if(wire>nf) {
        if(p>=2) { out.status|=UndefinedXYUpper; out.associations.push_back(a); continue; }
        wire=nf; a.wire=wire; out.status|=UVUpperClamped;
      }
      a.digit_index=static_cast<int>(wires.size()); a.state=CrossingState::Accepted;
      wires.push_back(wire); out.associations.push_back(a);
    }
  }
  return out;
}

inline Reconstruction reconstruct(const WireLists& wires,const Geometry& g) {
  Reconstruction out;
  for(int p=0;p<4;++p) {
    if(wires[p].size()>static_cast<std::size_t>(std::numeric_limits<int>::max())) {
      out.status|=RawOverflow; out.raw_multiplicity[p]=std::numeric_limits<int>::max();
    } else out.raw_multiplicity[p]=static_cast<int>(wires[p].size());
    if(wires[p].size()>20) out.status|=RawOverflow;
  }
  if(!detail::valid(g)) { out.status|=InvalidGeometry; out.cltot=-999; return out; }
  if(out.status&RawOverflow) {out.cltot=10; return out;}
  for(int p=0;p<4;++p) for(int w:wires[p])
    if(w<1 || w>(p<2?g.nf1:g.nf2)) out.status|=InvalidWire;
  if(out.status!=Ok) { out.cltot=-999; return out; }
  std::array<std::vector<detail::Cluster>,4> clustered;
  std::array<std::vector<float>,4> coordinates;
  int product=1, maximum=0,minimum=20,sum=0;
  for(int p=0;p<4;++p) {
    clustered[p]=detail::clusters(wires[p]);
    const int n=static_cast<int>(clustered[p].size());
    out.reduced_multiplicity[p]=n; product*=n; maximum=std::max(maximum,n);
    minimum=std::min(minimum,n); sum+=n;
    for(const auto& c:clustered[p]) {
      float v=((2.f*c.center-1.f)/static_cast<float>(p<2?g.nf1:g.nf2)-1.f)*(p<2?g.xp1_cm:g.xp2_cm);
      if(p<2) v=v*g.zp2_cm/g.zp1_cm;
      if(!std::isfinite(v)) out.status|=NonFiniteArithmetic;
      coordinates[p].push_back(v);
    }
  }
  out.candidate_count=product;
  if(product>256) {out.status|=CombinationOverflow; out.cltot=10; return out;}
  if(out.status!=Ok) {out.cltot=-999;return out;}
  if(maximum==0) return out;
  const detail::Rotation rotate(g.angle_deg);
  struct Candidate {float u,v,x,y; std::array<int,4> indices;};
  std::vector<Candidate> candidates,chosen;
  if(minimum>0) {
    std::vector<float> differences;
    for(int i=0;i<out.reduced_multiplicity[0];++i)
      for(int j=0;j<out.reduced_multiplicity[1];++j)
        for(int k=0;k<out.reduced_multiplicity[2];++k)
          for(int l=0;l<out.reduced_multiplicity[3];++l) {
            const auto uv=rotate(coordinates[0][i],coordinates[1][j],true);
            const float x=coordinates[2][k],y=coordinates[3][l];
            const float dx=uv[0]-x,dy=uv[1]-y;
            const float difference=dx*dx+dy*dy;
            if(!std::isfinite(difference)) out.status|=NonFiniteArithmetic;
            differences.push_back(difference);
            candidates.push_back({uv[0],uv[1],x,y,{i,j,k,l}});
          }
    if(out.status!=Ok) {out.cltot=-999;return out;}
    for(int index:detail::sort_indices(differences)) {
      const auto& c=candidates[index]; bool reused=false;
      for(const auto& old:chosen)
        if(c.u==old.u || c.v==old.v || c.x==old.x || c.y==old.y) {reused=true;break;}
      if(reused) continue;
      chosen.push_back(c);
      if(static_cast<int>(chosen.size())==minimum) break;
    }
    out.cltot=minimum==maximum?0:(maximum-minimum==1?sum-4*minimum:9);
    if(static_cast<int>(chosen.size())!=minimum) {
      out.status|=CoordinateCollision; return out; // Legacy reads unset U1 etc.
    }
  } else {
    if(maximum!=1) {out.cltot=9;return out;}
    if(sum!=3) {out.cltot=sum;return out;}
    Candidate c{}; c.indices={0,0,0,0};
    const int missing=static_cast<int>(std::find(out.reduced_multiplicity.begin(),out.reduced_multiplicity.end(),0)-out.reduced_multiplicity.begin());
    c.indices[missing]=-1;
    if(missing<2) {
      c.x=coordinates[2][0];c.y=coordinates[3][0];
      const auto inferred=rotate(c.x,c.y,false);
      const auto uv=rotate(missing==0?inferred[0]:coordinates[0][0],missing==1?inferred[1]:coordinates[1][0],true);
      c.u=uv[0];c.v=uv[1];
    } else {
      const auto uv=rotate(coordinates[0][0],coordinates[1][0],true);
      c.u=uv[0];c.v=uv[1];
      c.x=missing==2?c.u:coordinates[2][0];c.y=missing==3?c.v:coordinates[3][0];
    }
    chosen.push_back(c);out.cltot=-1;
  }
  for(auto c:chosen) {
    c.u=c.u*g.zp1_cm/g.zp2_cm; c.v=c.v*g.zp1_cm/g.zp2_cm;
    const float xw=c.x-c.u,yw=c.y-c.v,zw=g.zp2_cm-g.zp1_cm;
    const float vect=1.f/std::sqrt(xw*xw+yw*yw+zw*zw);
    const float cx=xw*vect,cy=yw*vect,cz=zw*vect;
    const auto first=rotate(c.u,c.v,false);
    const auto slope=rotate(cx*.5f/cz,cy*.5f/cz,false);
    const auto uv=rotate(first[0]+slope[0],first[1]-slope[1],true);
    Track t;
    t.first_cm={uv[0],uv[1],g.zp1_cm};
    t.second_cm={c.x+cx*.5f/cz,c.y-cy*.5f/cz,g.zp2_cm};
    t.cluster_indices=c.indices;
    for(int p=0;p<4;++p) {
      if(c.indices[p]<0) t.cl=p+1;
      else t.wire_indices[p]=clustered[p][c.indices[p]].indices;
    }
    for(float v:t.first_cm) if(!std::isfinite(v)) out.status|=NonFiniteArithmetic;
    for(float v:t.second_cm) if(!std::isfinite(v)) out.status|=NonFiniteArithmetic;
    out.tracks.push_back(t);
  }
  if(out.status!=Ok) out.tracks.clear();
  return out;
}
} // namespace newplan
#endif
