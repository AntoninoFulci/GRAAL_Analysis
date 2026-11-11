#ifndef GRAAL_BGO_MEASUREMENTS_HH
#define GRAAL_BGO_MEASUREMENTS_HH
// LSIMUL PREAN ANABGO/CALC_CLUST/SIGMA_XY_*/CLUS_FLAG/ANABAR.
// All arithmetic is REAL binary32; build with -ffp-contract=off, no fast-math.
#if defined(__FAST_MATH__)
#error "BGO measurements require strict floating-point arithmetic"
#endif
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
namespace bgomeasurements {
static_assert(sizeof(float)==4 && std::numeric_limits<float>::digits==24 &&
              std::numeric_limits<float>::is_iec559,"PREAN requires binary32");
inline constexpr float missing=std::numeric_limits<float>::quiet_NaN();
inline constexpr float pi=3.14159265358979324f,twopi=6.28318530717958648f;
inline constexpr float degrad=.0174532925199432958f,raddeg=57.2957795130823209f;
enum Status : std::uint32_t { Supported=0,InvalidInput=1,InvalidConfig=2,
  CapacityExceeded=4,CorrectionOutsideDomain=8,UndefinedOldShape=16,
  NonFiniteArithmetic=32 };
// Crystal arrays use theta-1 + 15*(phi-1), matching Fortran EDEPTH(15,32).
inline int index(int theta,int phi) { return theta-1+15*(phi-1); }
struct Config {
  std::array<float,15> theta{},volume{};
  std::array<float,32> phi{};
  // Fortran PARAM_CORR_[AB](12,8): threshold index varies fastest.
  std::array<float,96> correction_a{},correction_b{};
  float crystal_threshold=missing,cluster_threshold=missing;
  float bgo_adc_channels=missing,bgo_adc_fullscale_gev=missing;
  bool enable_sp=true;
  Config() { theta.fill(missing); volume.fill(missing); phi.fill(missing);
    correction_a.fill(missing); correction_b.fill(missing); }
};
// Literal PREAN BLOCKDATA tables; callers must still supply runtime thresholds
// and separately selected digitizer ADC scales. There are no threshold defaults.
inline Config source_tables();
struct BgoDigit { int theta=0,phi=0,adc=0; };
struct Grid {
  std::uint32_t status=Supported;
  std::array<float,480> energy{};
  std::array<int,480> problem{};
  int accepted_digits=0;
};
struct BarrelDigit { int channel=0,adc=0,tdc=0; };
struct BarrelConfig {
  float adc_channels=missing,adc_fullscale_gev=missing;
  float tdc_channels=missing,tdc_fullscale_seconds=missing;
  float energy_threshold_mev=missing;
};
struct Barrel { int channel=0,problem_index=0; float energy=0,time=0; };
struct BarrelResult { std::uint32_t status=Supported; std::vector<Barrel> records; };
struct Cluster {
  int source_cluster=0,multiplicity=0,problem_index=0,flag=0;
  float raw_energy=0,theta=0,phi=0,corrected_energy=0,corrected_theta=0,corrected_phi=0;
  float maximum_energy=0,sx1=0,sy1=0,sx2=0,sy2=0;
  std::uint32_t status=Supported;
};
struct Result {
  std::uint32_t status=Supported;
  std::vector<Cluster> good,sp;
  // ANABGO indexes IND_BGO by input ICL during CALC_CLUST but by output
  // NBCLUS during clipping. Preserve the actual slot array, even with SP gaps.
  std::array<int,30> problem_slots{};
};
inline bool positive(float x) { return std::isfinite(x)&&x>0; }
inline bool nonnegative(float x) { return std::isfinite(x)&&x>=0; }
inline Grid decode_bgo_digits(const std::vector<BgoDigit>& digits,const Config& c) {
  Grid r;
  if(!positive(c.bgo_adc_channels)||!positive(c.bgo_adc_fullscale_gev)||
     !nonnegative(c.crystal_threshold)) { r.status=InvalidConfig; return r; }
  if(digits.size()>480) { r.status=CapacityExceeded; return r; }
  const float cut=(c.bgo_adc_channels/c.bgo_adc_fullscale_gev)*c.crystal_threshold;
  if(!std::isfinite(cut)||cut>=2147483648.f) { r.status=InvalidConfig; return r; }
  const int threshold=static_cast<int>(cut);
  for(const auto& d:digits) {
    if(d.theta<1||d.theta>15||d.phi<1||d.phi>32||d.adc<0) { r.status=InvalidInput; return r; }
    const int k=index(d.theta,d.phi);
    if(d.adc>threshold) {
      ++r.accepted_digits;
      r.energy[k]=(static_cast<float>(d.adc)*c.bgo_adc_fullscale_gev)/c.bgo_adc_channels;
      if(!std::isfinite(r.energy[k])) { r.status=NonFiniteArithmetic; return r; }
    }
    if(d.adc>(d.theta<=5?1100:d.theta<=10?800:600)) r.problem[k]=-1;
  }
  return r;
}
inline BarrelResult decode_barrel(const std::vector<BarrelDigit>& digits,const BarrelConfig& c) {
  BarrelResult r;
  if(!positive(c.adc_channels)||!positive(c.adc_fullscale_gev)||!positive(c.tdc_channels)||
     !positive(c.tdc_fullscale_seconds)||!nonnegative(c.energy_threshold_mev)) {
    r.status=InvalidConfig; return r;
  }
  if(digits.size()>32) { r.status=CapacityExceeded; return r; }
  for(const auto& d:digits) {
    if(d.channel<1||d.channel>32||d.adc<0||d.tdc<0) { r.status=InvalidInput; r.records.clear(); return r; }
    Barrel b; b.channel=d.channel;
    b.energy=((static_cast<float>(d.adc)*c.adc_fullscale_gev)/c.adc_channels)*1000.f;
    b.time=((static_cast<float>(d.tdc)*c.tdc_fullscale_seconds)/c.tdc_channels)*1.e9f;
    if(!std::isfinite(b.energy)||!std::isfinite(b.time)) { r.status=NonFiniteArithmetic; r.records.clear(); return r; }
    if(b.energy<c.energy_threshold_mev) b.problem_index=-5;
    r.records.push_back(b);
  }
  return r;
}
namespace detail {
inline int shifted(int phi,int shift) { int j=phi+shift; if(j<=0) j+=32; if(j>32) j-=32; return j; }
inline int theta_bin(float t) {
  constexpr float low[]={25,31,38,45.5f,55.5f,65.5f,75.5f};
  constexpr float high[]={31,38,45.5f,55.5f,65.5f,75.5f,85.17f};
  constexpr float reverse_low[]={149,142,134.5f,124.5f,114.5f,104.5f,94.84f};
  constexpr float reverse_high[]={155,149,142,134.5f,124.5f,114.5f,104.5f};
  for(int i=0;i<7;++i) if((t>=low[i]&&t<=high[i])||(t>=reverse_low[i]&&t<=reverse_high[i])) return i;
  return t>=85.17f&&t<=94.84f?7:-1;
}
inline void shapes(const Grid& grid,const std::vector<int>& members,const Config& c,Cluster& out) {
  const int n=static_cast<int>(members.size());
  if(n==1) return;
  auto ti=[](int m){return m/100;}; auto pj=[](int m){return m%100;};
  auto energy=[&](int m){return grid.energy[index(ti(m),pj(m))];};
  auto density=[&](int m){return energy(m)/c.volume[ti(m)-1];};
  int im=0;
  for(int k=1;k<n;++k) if(density(members[k])>density(members[im])) im=k;
  const int it=ti(members[im]),shift=16-pj(members[im]);
  std::array<float,480> mapped{};
  std::vector<float> xx(n),yy(n),zz(n);
  for(int k=0;k<n;++k) {
    const int i=ti(members[k]),j=shifted(pj(members[k]),shift);
    mapped[index(i,j)]=density(members[k]);
    xx[k]=c.theta[i-1]; yy[k]=c.phi[j-1]; zz[k]=density(members[k]);
  }
  float xm=0,ym=0,zs=0;
  for(int k=0;k<n;++k) { xm=xm+xx[k]*zz[k]; ym=ym+yy[k]*zz[k]; zs=zs+zz[k]; }
  xm=xm/zs; ym=ym/zs;
  float sxy=0;
  for(int k=0;k<n;++k) {
    const float dx=xx[k]-xm,dy=yy[k]-ym;
    out.sx2=out.sx2+zz[k]*(dx*dx); out.sy2=out.sy2+zz[k]*(dy*dy);
    sxy=sxy+(zz[k]*dx)*dy;
  }
  out.sx2=out.sx2/zs; out.sy2=out.sy2/zs; sxy=sxy/zs;
  const float bb=-(out.sx2+out.sy2),cc=out.sx2*out.sy2-sxy*sxy;
  const float disc=bb*bb-4.f*cc;
  float x1=0,x2=0;
  if(disc>=0) { const float dd=std::sqrt(disc); x1=(-bb-dd)/2.f; x2=(-bb+dd)/2.f; }
  if(x1>0) out.sx2=std::sqrt(x1);
  if(x2>0) out.sy2=std::sqrt(x2);
  constexpr int near[8][2]={{-1,-1},{0,-1},{1,-1},{-1,0},{1,0},{-1,1},{0,1},{1,1}};
  constexpr int far[16][2]={{-2,-2},{-1,-2},{0,-2},{1,-2},{2,-2},{-2,-1},{2,-1},{-2,0},{2,0},{-2,1},{2,1},{-2,2},{-1,2},{0,2},{1,2},{2,2}};
  auto neighbor=[&](const auto& offsets,int count) {
    int best=0; float maximum=0;
    for(int k=0;k<count;++k) {
      const int i=it+offsets[k][0],j=16+offsets[k][1];
      const float e=i>=1&&i<=15?mapped[index(i,j)]/c.volume[i-1]:0;
      if(k==0||e>maximum) { maximum=e; best=k; }
    }
    return std::array<int,2>{{it+offsets[best][0],16+offsets[best][1]}};
  };
  const auto a=neighbor(near,8);
  if(a[0]<1||a[0]>15||mapped[index(a[0],a[1])]==0) return;
  int bt=0,bp=0; float xl11=2;
  if(n!=2) {
    const auto b=neighbor(far,16); bt=b[0]; bp=b[1];
    if(bt<1||bt>15) { bt=bp=0; }
    else {
      if(mapped[index(bt,bp)]==0) bt=bp=0;
      // Preserve source's unconditional XL11=3 after a zero-energy neighbor.
      xl11=3;
    }
  }
  const float xl12=static_cast<float>(it+a[0]+bt);
  const float xl22=static_cast<float>(it*it+a[0]*a[0]+bt*bt);
  const float g1=static_cast<float>(16+a[1]+bp),g2=static_cast<float>(it*16+a[0]*a[1]+bt*bp);
  const float xnn=g2*xl11-g1*xl12,dd=xl11*xl22-xl12*xl12;
  float angle=0;
  if(std::abs(dd)<1.e-10f) {
    if(xnn==0) { out.status|=UndefinedOldShape; out.sx1=out.sy1=missing; return; }
    angle=xnn>0?pi/2.f:-pi/2.f;
  } else angle=std::atan(xnn/dd);
  float sx=0,sy=0,st=0;
  for(int k=0;k<n;++k) {
    const float dx=static_cast<float>(ti(members[k])-it),dy=static_cast<float>(shifted(pj(members[k]),shift)-16);
    xx[k]=dx*std::cos(angle)+dy*std::sin(angle);
    yy[k]=-dx*std::sin(angle)+dy*std::cos(angle);
    sx=sx+xx[k]*zz[k]; sy=sy+yy[k]*zz[k]; st=st+zz[k];
  }
  sx=sx/st; sy=sy/st; float sxx=0,syy=0;
  for(int k=0;k<n;++k) { const float dx=xx[k]-sx,dy=yy[k]-sy;
    sxx=sxx+zz[k]*(dx*dx); syy=syy+zz[k]*(dy*dy); }
  out.sx1=std::sqrt(sxx/st); out.sy1=std::sqrt(syy/st);
}
inline int cluster_flag(const Grid& g,const std::vector<int>& m) {
  if(m.size()==1) return 0;
  auto e=[&](int v){return g.energy[index(v/100,v%100)];};
  int a=0,b=-1;
  for(std::size_t k=1;k<m.size();++k) if(e(m[k])>e(m[a])) a=static_cast<int>(k);
  for(std::size_t k=0;k<m.size();++k) if(static_cast<int>(k)!=a&&(b<0||e(m[k])>e(m[b]))) b=static_cast<int>(k);
  const int shift=16-m[a]%100;
  auto distance=[&](int v) { const float x=static_cast<float>(m[a]/100-v/100),y=static_cast<float>(16-shifted(v%100,shift)); return std::sqrt(x*x+y*y); };
  if(e(m[b])>=.2f*e(m[a])&&distance(m[b])>1.5f) return 1;
  float outside=0; int flag=0;
  for(std::size_t k=0;k<m.size();++k) if(static_cast<int>(k)!=a) {
    if(distance(m[k])>1.5f) outside=outside+e(m[k]);
    if(outside>.2f*e(m[a])) flag=2;
  }
  return flag;
}
} // detail
inline Result measure(const Grid& grid,const std::vector<std::vector<int>>& clusters,
                      const std::vector<int>& barrel_channels,const Config& c,int membership_error=0) {
  Result r;
  if(grid.status) { r.status=grid.status; return r; }
  if(!nonnegative(c.crystal_threshold)||!nonnegative(c.cluster_threshold)) r.status|=InvalidConfig;
  for(float v:c.theta) if(!std::isfinite(v)) r.status|=InvalidConfig;
  for(float v:c.phi) if(!std::isfinite(v)) r.status|=InvalidConfig;
  for(float v:c.volume) if(!positive(v)) r.status|=InvalidConfig;
  for(float v:c.correction_a) if(!std::isfinite(v)) r.status|=InvalidConfig;
  for(float v:c.correction_b) if(!std::isfinite(v)) r.status|=InvalidConfig;
  for(int b:barrel_channels) if(b<1||b>32) r.status|=InvalidInput;
  if(clusters.size()>480||barrel_channels.size()>32) r.status|=CapacityExceeded;
  std::array<bool,480> seen{};
  for(const auto& m:clusters) {
    if(m.empty()||m.size()>480) { r.status|=InvalidInput; continue; }
    for(int v:m) {
      const int i=v/100,j=v%100;
      if(i<1||i>15||j<1||j>32) { r.status|=InvalidInput; continue; }
      const int k=index(i,j);
      if(seen[k]||!positive(grid.energy[k])||(grid.problem[k]!=0&&grid.problem[k]!=-1)) r.status|=InvalidInput;
      seen[k]=true;
    }
  }
  if(r.status) return r;
  // Source caps cluster list at 30 and flags every retained slot on NERR.
  const std::size_t count=std::min<std::size_t>(30,clusters.size());
  if(membership_error||clusters.size()>30) for(std::size_t k=0;k<count;++k) r.problem_slots[k]=-3;
  const float scaled=(c.crystal_threshold+.0005f)/.001f;
  if(!std::isfinite(scaled)||scaled>=2147483648.f) { r.status=InvalidConfig; return r; }
  const int threshold_bin=std::min(11,static_cast<int>(scaled));
  for(std::size_t k=0;k<count;++k) {
    const auto& m=clusters[k]; Cluster out; out.source_cluster=static_cast<int>(k+1); out.multiplicity=static_cast<int>(m.size());
    int maximum=0; float total=0,th=0,ss=0,cs=0;
    std::vector<float> density,phi;
    for(std::size_t l=0;l<m.size();++l) {
      const int i=m[l]/100,j=m[l]%100,p=index(i,j); const float e=grid.energy[p];
      out.raw_energy=out.raw_energy+e; density.push_back(e/c.volume[i-1]); phi.push_back(c.phi[j-1]*degrad);
      if(e>grid.energy[index(m[maximum]/100,m[maximum]%100)]) maximum=static_cast<int>(l);
      if(grid.problem[p]==-1) r.problem_slots[k]=-4;
    }
    const int im=m[maximum]/100,jm=m[maximum]%100;
    out.maximum_energy=grid.energy[index(im,jm)];
    if(im==15) r.problem_slots[k]=-15;
    if(im==1) {
      bool adjacent=false; for(int b:barrel_channels) if(std::abs(b-jm)<=1||std::abs(b-jm)==31) adjacent=true;
      if(!adjacent) r.problem_slots[k]=-1;
    }
    for(std::size_t l=0;l<m.size();++l) {
      th=th+c.theta[m[l]/100-1]*density[l]; ss=ss+std::sin(phi[l])*density[l];
      cs=cs+std::cos(phi[l])*density[l]; total=total+density[l];
    }
    out.theta=th/total; out.phi=std::atan2(ss/total,cs/total);
    if(out.phi<0) out.phi=out.phi+twopi;
    out.phi=out.phi*raddeg;
    th=ss=cs=0; float total2=0;
    for(std::size_t l=0;l<m.size();++l) {
      const float w=std::max(0.f,4.f+std::log(density[l]/total));
      th=th+c.theta[m[l]/100-1]*w; ss=ss+std::sin(phi[l])*w; cs=cs+std::cos(phi[l])*w; total2=total2+w;
    }
    out.corrected_theta=out.corrected_phi=-1;
    if(total2>0) {
      out.corrected_theta=th/total2; out.corrected_phi=std::atan2(ss/total2,cs/total2);
      if(out.corrected_phi<0) out.corrected_phi=out.corrected_phi+twopi;
      out.corrected_phi=out.corrected_phi*raddeg;
    }
    if(!std::isfinite(out.theta)||!std::isfinite(out.phi)||!std::isfinite(out.corrected_theta)||
       !std::isfinite(out.corrected_phi)||!std::isfinite(out.raw_energy)) {
      r.status|=NonFiniteArithmetic; r.good.clear(); r.sp.clear(); return r;
    }
    const int tb=detail::theta_bin(out.theta);
    if(tb<0) { r.status|=CorrectionOutsideDomain; r.good.clear(); r.sp.clear(); return r; }
    const int p=threshold_bin+12*tb;
    out.corrected_energy=(c.correction_a[p]+(c.correction_b[p]*out.raw_energy)*1000.f)/1000.f;
    if(!std::isfinite(out.raw_energy)||!std::isfinite(out.corrected_energy)||!std::isfinite(out.theta)||
       !std::isfinite(out.phi)||!std::isfinite(out.corrected_theta)||!std::isfinite(out.corrected_phi)) {
      r.status|=NonFiniteArithmetic; r.good.clear(); r.sp.clear(); return r;
    }
    if(out.corrected_energy>=c.cluster_threshold) {
      detail::shapes(grid,m,c,out); out.flag=detail::cluster_flag(grid,m);
      if(!std::isfinite(out.sx2)||!std::isfinite(out.sy2)||
         (!(out.status&UndefinedOldShape)&&(!std::isfinite(out.sx1)||!std::isfinite(out.sy1))))
        out.status|=NonFiniteArithmetic;
      const std::size_t slot=r.good.size();
      if(out.multiplicity>50) { r.problem_slots[slot]=-3; out.multiplicity=50; }
      if(out.raw_energy>2) { r.problem_slots[slot]=-3; out.raw_energy=2; }
      r.good.push_back(out);
    } else if(c.enable_sp) r.sp.push_back(out);
    r.status|=out.status;
  }
  // Read final slot values after all input clusters have updated IND_BGO.
  for(std::size_t k=0;k<r.good.size();++k) r.good[k].problem_index=r.problem_slots[k];
  return r;
}
inline Config source_tables() {
  Config c;
  c.theta={{28.0f,34.5f,41.75f,50.5f,60.5f,70.5f,80.33333f,90.0f,99.66667f,109.5f,119.5f,129.5f,138.25f,145.5f,152.0f}};
  c.phi={{0.f,11.25f,22.5f,33.75f,45.f,56.25f,67.5f,78.75f,90.f,101.25f,112.5f,123.75f,135.f,146.25f,157.5f,168.75f,180.f,191.25f,202.5f,213.75f,225.f,236.25f,247.5f,258.75f,270.f,281.25f,292.5f,303.75f,315.f,326.25f,337.5f,348.75f}};
  c.volume={{324.49679f,369.02685f,386.76088f,511.83943f,516.59423f,517.52124f,503.60275f,500.49170f,503.60275f,517.52124f,516.59423f,511.83943f,386.76088f,369.02685f,324.49679f}};
  c.correction_a={{0.1865306f,0.5437917f,2.028834f,2.339624f,3.805543f,4.354187f,4.861798f,5.147007f,5.683217f,7.258035f,6.988981f,9.066722f,0.6674137f,1.824387f,3.042997f,4.052002f,5.253223f,5.729486f,6.699599f,7.260611f,8.236045f,8.812378f,8.771852f,8.963801f,1.070377f,1.921186f,3.742139f,4.129861f,5.392849f,5.909466f,6.847512f,7.836720f,8.298282f,8.862308f,9.059187f,9.801394f,1.217824f,1.961640f,3.240293f,4.179872f,5.195312f,5.460753f,6.248158f,7.106476f,7.489673f,7.944979f,8.312744f,8.626810f,1.120871f,2.041034f,3.665500f,4.118726f,5.434139f,5.768640f,6.445040f,7.123962f,7.735042f,8.336172f,8.488257f,9.268137f,1.216194f,2.238097f,3.701854f,4.259646f,5.364082f,5.749393f,6.491737f,7.409210f,7.733249f,8.736183f,8.842468f,9.308415f,1.189939f,2.365473f,3.866582f,4.615329f,5.464015f,5.986786f,6.717750f,7.352932f,7.817393f,8.983421f,9.217216f,9.730333f,1.423137f,2.297350f,3.776061f,4.460130f,5.567859f,6.051650f,6.977559f,7.505108f,7.989120f,8.590480f,8.996863f,9.719628f}};
  c.correction_b={{1.054509f,1.061659f,1.070633f,1.075681f,1.079998f,1.082659f,1.089075f,1.093419f,1.096505f,1.096893f,1.103051f,1.102207f,1.032050f,1.033505f,1.040527f,1.043176f,1.050406f,1.052922f,1.058572f,1.064995f,1.066195f,1.071533f,1.074240f,1.080174f,1.025608f,1.028552f,1.033907f,1.037837f,1.044148f,1.047203f,1.052838f,1.058506f,1.061248f,1.066475f,1.069705f,1.072424f,1.020877f,1.023174f,1.031802f,1.033372f,1.040152f,1.043577f,1.048956f,1.053156f,1.055320f,1.060787f,1.063096f,1.068246f,1.023258f,1.025136f,1.030574f,1.035125f,1.039112f,1.043049f,1.048569f,1.053385f,1.055832f,1.060256f,1.062785f,1.066378f,1.022311f,1.022960f,1.029897f,1.033390f,1.039965f,1.043056f,1.049147f,1.053710f,1.056006f,1.060022f,1.062628f,1.067520f,1.022290f,1.022139f,1.029173f,1.031647f,1.038495f,1.041309f,1.048049f,1.052985f,1.055044f,1.058582f,1.061517f,1.065511f,1.018984f,1.021844f,1.028258f,1.031511f,1.037132f,1.040243f,1.045521f,1.051521f,1.053910f,1.058276f,1.061309f,1.064629f}};
  return c;
}
} // namespace bgomeasurements
#endif
