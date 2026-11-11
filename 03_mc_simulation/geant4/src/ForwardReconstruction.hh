#ifndef GRAAL_FORWARD_RECONSTRUCTION_HH
#define GRAAL_FORWARD_RECONSTRUCTION_HH
#include "ForwardDigitization.hh"
#include "ForwardSourceKernels.hh"
#include <string>

namespace forward26 {
// Measured-only boundary. All source object indices below remain ONE-based;
// digit/planar_input indices are ZERO-based C++ input vector indices.
struct RWCalibration { std::array<float,16> rt{},rb{},by{},bt{},ae{}; float ay{}; };
struct ReconstructionConfig {
  Config response;
  RWCalibration rw;
  std::array<float,6> attn{},atts{};
  std::array<float,18> atth{};
  float zp1_cm{},zp2_cm{},zp3_cm{};
  int source_run{},rf_bunch{};
  bool simulation=true;
};
struct PlanarEndpoint { float u_cm{},v_cm{},x_cm{},y_cm{}; int confidence{}; };
struct WallCluster {
  std::array<float,8> par{}; // x,y cm; TOF1 ns,DE1 MeV,TOF2 ns,DE2 MeV,TOF ns,DE MeV
  std::array<int,4> source_indices{}; // IND_PAR: multiplicities, corrected H/V indices
  float theta_deg{},phi_deg{};
  int association{}; // source IASS_TRACK, not ANA_WAL mask
};
struct WallHit {
  int channel{},association{},digit_index{};
  float x_cm{},y_cm{},tof_ns{},de_MeV{},energy1{},energy2{},time1{},time2{};
};
struct ShowerCluster {
  float x_cm{},y_cm{},time_s{},energy_GeV{},theta_deg{},phi_deg{},pc_theta_deg{},pc_phi_deg{};
  int type{};
  std::vector<int> digit_indices;
};
struct UnrecognizedShower {
  int channel{},digit_index{};
  float energy{},time_s{}; // source ESH_UR: GeV except zero-product fallback
  bool energy_fallback_MeV=false; // source omits 1e-3 in this fallback
};
enum class ReconstructionStatus { Valid, UnavailableInput, InvalidDigit, UndefinedSource };
struct WallReconstruction {
  ReconstructionStatus status=ReconstructionStatus::Valid;
  std::string reason;
  std::vector<WallCluster> clusters;
  std::vector<WallHit> horizontal,vertical;
  std::array<int,5> source_summary{};
  bool multiplicity_rejected=false; // source >3 accepted hits/plane -> no WALL objects
};
struct ShowerReconstruction {
  ReconstructionStatus status=ReconstructionStatus::Valid;
  std::string reason;
  std::vector<ShowerCluster> clusters;
  std::vector<UnrecognizedShower> unrecognized;
};
struct ForwardMatch { int mask{},planar{},wall{},shower{}; };
struct ForwardParticle {
  std::array<float,3> direction{};
  float theta_deg{},phi_deg{},tof_ns{},de_MeV{};
  int match_index{},wall_info{}; // source INDEX_TRF / INFO_WAL
};
struct ForwardAssociations {
  ReconstructionStatus status=ReconstructionStatus::Valid;
  std::string reason;
  std::vector<ForwardMatch> matches;
  std::vector<ForwardParticle> particles;
  std::vector<int> planar_input_indices; // compact accepted PC index -> original endpoint
  int charged{},neutral{},strange{},source_iforw_c{},source_iforw_n{};
  std::array<int,7> mask_counts{};
};
struct ForwardReconstruction {
  WallReconstruction wall;
  ShowerReconstruction shower;
  ForwardAssociations associations;
};
namespace reconstruction_detail {
inline void Finite(float x) { if(!std::isfinite(x)) throw std::invalid_argument("nonfinite forward reconstruction input"); }
inline source::Kernels State(const ReconstructionConfig& c) {
  ValidateConfig(c.response);
  if(!(c.zp1_cm>0 && c.zp2_cm>c.zp1_cm && c.zp3_cm>c.zp2_cm) || c.source_run<0 || c.source_run>65535)
    throw std::invalid_argument("explicit unsigned16 source run and ordered forward geometry required");
  Finite(c.zp1_cm);Finite(c.zp2_cm);Finite(c.zp3_cm);
  if(c.rf_bunch < -1000 || c.rf_bunch > 1000) throw std::invalid_argument("RF bunch outside supported integer domain");
  source::Kernels s;
  auto copy=[](const auto& from,auto& to){std::copy(from.begin(),from.end(),to);};
  copy(c.response.pedestals,s.corr_.pedestals);copy(c.response.tdccal,s.corr_.tdccal);
  copy(c.response.gaincards,s.corr_.gaincards);copy(c.response.timewalk,s.corr_.timewalk);
  copy(c.response.tdcoffset,s.corr_.tdcoffset);copy(c.response.gainpms,s.corr_.gainpms);
  for(float x:c.attn)Finite(x);for(float x:c.atts)Finite(x);for(float x:c.atth)Finite(x);
  copy(c.attn,s.att_wall__.attn);copy(c.atts,s.att_wall__.atts);copy(c.atth,s.att_wall__.atth);
  for(int i=0;i<16;++i) {
    detail::Positive(c.rw.rt[i]);detail::Positive(c.rw.rb[i]);detail::Positive(c.rw.ae[i]);
    Finite(c.rw.by[i]);Finite(c.rw.bt[i]);
  }
  detail::Positive(c.rw.ay);
  copy(c.rw.rt,s.russ_wall_calibr__.rt);copy(c.rw.rb,s.russ_wall_calibr__.rb);
  copy(c.rw.by,s.russ_wall_calibr__.by);copy(c.rw.bt,s.russ_wall_calibr__.bt);copy(c.rw.ae,s.russ_wall_calibr__.ae);
  s.russ_wall_calibr__.ay=c.rw.ay;
  s.dime_.zp1=c.zp1_cm;s.dime_.zp2=c.zp2_cm;s.dime_.zp3=c.zp3_cm;
  s.lflag_.lsimul=c.simulation;s.lflag_.ldata=!c.simulation;
  s.event_.idrun=c.source_run;s.pm_tag_prean__.ind_bunch_rf__=c.rf_bunch;
  return s;
}
inline bool Digits(const std::vector<Digit>& v,int maximum) {
  if(v.size()>static_cast<std::size_t>(maximum)) return false;
  std::array<bool,27> seen{};
  for(const auto& d:v) {
    if(d.status || d.channel<1 || d.channel>maximum || seen[d.channel]) return false;
    seen[d.channel]=true;
    for(int x:d.adc) if(x<0 || x>100000) return false;
    for(int x:d.tdc) if(x<0 || x>100000) return false;
    if(maximum==16 && static_cast<long long>(d.adc[0])*d.adc[1]>std::numeric_limits<int>::max()) return false;
  }
  return true;
}
inline void LoadWall(source::Kernels& s,const WallResult& w) {
  s.tofwall_.lm1=static_cast<int>(w.horizontal.size());s.tofwall_.lm2=static_cast<int>(w.vertical.size());
  for(int p=0;p<2;++p) {
    const auto& digits=p?w.vertical:w.horizontal;
    int* channels=p?s.tofwall_.ip2:s.tofwall_.ip1;
    int* adc=p?s.tofwall_.ep2:s.tofwall_.ep1;int* tdc=p?s.tofwall_.tp2:s.tofwall_.tp1;
    for(std::size_t i=0;i<digits.size();++i) {
      channels[i]=digits[i].channel;
      for(int e=0;e<2;++e){adc[i+26*e]=digits[i].adc[e];tdc[i+26*e]=digits[i].tdc[e];}
    }
  }
}
inline int DigitIndex(const std::vector<Digit>& digits,int channel) {
  for(std::size_t i=0;i<digits.size();++i)if(digits[i].channel==channel)return static_cast<int>(i);
  throw source::Undefined("source channel has no measured digit");
}
inline void CheckOutput(float x) { if(!std::isfinite(x))throw source::Undefined("nonfinite source result"); }
inline void Planar(const std::vector<PlanarEndpoint>& pc) {
  if(pc.size()>20)throw std::invalid_argument("planar source capacity20 exceeded");
  for(const auto& p:pc){Finite(p.u_cm);Finite(p.v_cm);Finite(p.x_cm);Finite(p.y_cm);}
}
inline void WallObjects(source::Kernels& s,const std::vector<WallCluster>& wall) {
  if(wall.size()>3)throw std::invalid_argument("WALL source capacity3 exceeded");
  s.muroass_.m_wal__=static_cast<int>(wall.size());
  for(std::size_t i=0;i<wall.size();++i) {
    for(int k=0;k<8;++k){Finite(wall[i].par[k]);s.muroass_.wal_par__[8*i+k]=wall[i].par[k];}
    s.muroass_.iass_track__[i]=wall[i].association;
  }
}
} // reconstruction_detail

// WALL_CLUS and its three active ALESSIA dependencies. Coordinate clamp is the
// separate analysis.F boundary, included here AFTER the source wall angles.
inline WallReconstruction ReconstructWall(const WallResult& digits,const ReconstructionConfig& config) {
  using namespace reconstruction_detail;
  WallReconstruction out;
  if(digits.status || !Digits(digits.horizontal,26) || !Digits(digits.vertical,26)) {
    out.status=ReconstructionStatus::InvalidDigit;out.reason="unsupported WALL response or malformed/duplicate digit";return out;
  }
  auto s=State(config);LoadWall(s,digits);
  try {
    s.wall_clus__();
    out.multiplicity_rejected=s.wall_multiplicity_rejected;
    for(int i=0;i<s.muroass_.m_wal__;++i) {
      WallCluster w;
      for(int k=0;k<8;++k){w.par[k]=s.muroass_.wal_par__[8*i+k];CheckOutput(w.par[k]);}
      w.par[0]=std::clamp(w.par[0],-200.f,200.f);w.par[1]=std::clamp(w.par[1],-200.f,200.f);
      for(int k=0;k<4;++k)w.source_indices[k]=s.muroass_.ind_par__[4*i+k];
      w.theta_deg=s.muroass_.theta_w__[i];w.phi_deg=s.muroass_.phi_w__[i];w.association=s.muroass_.iass_track__[i];
      CheckOutput(w.theta_deg);CheckOutput(w.phi_deg);out.clusters.push_back(w);
    }
    for(int i=0;i<s.tofmuro1_.lm_1__;++i){auto& h=s.tofmuro1_;out.horizontal.push_back({h.ip1_cor__[i],h.iass_w1__[i],DigitIndex(digits.horizontal,h.ip1_cor__[i]),h.x_w1__[i],h.y_w1__[i],h.a_tof1__[i],h.a_de1__[i],h.ene_l__[i],h.ene_r__[i],h.tof_l__[i],h.tof_r__[i]});}
    for(int i=0;i<s.tofmuro2_.lm_2__;++i){auto& h=s.tofmuro2_;out.vertical.push_back({h.ip2_cor__[i],h.iass_w2__[i],DigitIndex(digits.vertical,h.ip2_cor__[i]),h.x_w2__[i],h.y_w2__[i],h.a_tof2__[i],h.a_de2__[i],h.ene_u__[i],h.ene_d__[i],h.tof_u__[i],h.tof_d__[i]});}
    for(const auto* hits:{&out.horizontal,&out.vertical})for(const auto& h:*hits)
      for(float x:{h.x_cm,h.y_cm,h.tof_ns,h.de_MeV,h.energy1,h.energy2,h.time1,h.time2})CheckOutput(x);
    std::copy_n(s.muroass_.ind_wal__,5,out.source_summary.begin());
  } catch(const source::Undefined& e){out={};out.status=ReconstructionStatus::UndefinedSource;out.reason=e.what();}
  return out;
}

inline ShowerReconstruction ReconstructShower(const ShowerResult& digits,const WallResult& raw_wall,
    const std::vector<PlanarEndpoint>& planar,const ReconstructionConfig& config) {
  using namespace reconstruction_detail;
  ShowerReconstruction out;Planar(planar);
  if(digits.status || raw_wall.status || !Digits(digits.digits,16) || !Digits(raw_wall.horizontal,26) || !Digits(raw_wall.vertical,26)) {
    out.status=ReconstructionStatus::InvalidDigit;out.reason="unsupported response or malformed/duplicate digit";return out;
  }
  auto s=State(config);LoadWall(s,raw_wall);
  s.russian_wall__.msho=static_cast<int>(digits.digits.size());
  for(std::size_t i=0;i<digits.digits.size();++i){const auto& d=digits.digits[i];auto& r=s.russian_wall__;r.ip3[i]=d.channel;r.ep3u[i]=d.adc[0];r.ep3d[i]=d.adc[1];r.tp3u[i]=d.tdc[0];r.tp3d[i]=d.tdc[1];}
  // FIND_TRACK source endpoints: NCL=NPCYL=0 before publication; all planar
  // endpoints copied, independent of its unused ANATOF TF/DE/ICOL metadata.
  s.track_.ntra=static_cast<int>(planar.size());
  for(std::size_t i=0;i<planar.size();++i){auto& t=s.track_;const auto& p=planar[i];t.a1[i]=p.u_cm;t.a2[i]=p.v_cm;t.a3[i]=config.zp1_cm;t.b1[i]=p.x_cm;t.b2[i]=p.y_cm;t.b3[i]=config.zp2_cm;}
  try {
    s.russwall_();
    for(int i=0;i<s.russ_wall__.nshow;++i){auto& r=s.russ_wall__;ShowerCluster h;
      h.x_cm=r.xshow[i];h.y_cm=r.yshow[i];h.time_s=r.tshow[i];h.energy_GeV=r.eshow[i];h.theta_deg=r.tetshow[i];h.phi_deg=r.phishow[i];h.pc_theta_deg=r.tshpc[i];h.pc_phi_deg=r.pshpc[i];h.type=r.typeshow[i];
      if(config.simulation){h.phi_deg=180.f-h.phi_deg;if(h.phi_deg<0)h.phi_deg+=360;if(h.phi_deg>360)h.phi_deg-=360;}
      for(float x:{h.x_cm,h.y_cm,h.time_s,h.energy_GeV,h.theta_deg,h.phi_deg,h.pc_theta_deg,h.pc_phi_deg})CheckOutput(x);
      for(int ch=s.shower_ranges.at(i).first;ch<=s.shower_ranges.at(i).second;++ch)h.digit_indices.push_back(DigitIndex(digits.digits,ch));
      out.clusters.push_back(h);
    }
    for(int i=0;i<s.rwur_.n_ur__;++i){
      int digit=DigitIndex(digits.digits,s.rwur_.nsh_ur__[i]);
      bool fallback=digits.digits[digit].adc[0]==0 || digits.digits[digit].adc[1]==0;
      CheckOutput(s.rwur_.esh_ur__[i]);CheckOutput(s.rwur_.tsh_ur__[i]);
      out.unrecognized.push_back({s.rwur_.nsh_ur__[i],digit,s.rwur_.esh_ur__[i],s.rwur_.tsh_ur__[i],fallback});
    }
  } catch(const source::Undefined& e){out={};out.status=ReconstructionStatus::UndefinedSource;out.reason=e.what();}
  return out;
}

inline ForwardAssociations AssociateForward(const std::vector<PlanarEndpoint>& planar,
    const std::vector<WallCluster>& wall,const std::vector<ShowerCluster>& shower,const ReconstructionConfig& config) {
  using namespace reconstruction_detail;
  Planar(planar);auto s=State(config);WallObjects(s,wall);
  if(shower.size()>16)throw std::invalid_argument("RW source capacity16 exceeded");
  s.russ_wall__.nshow=static_cast<int>(shower.size());
  for(std::size_t i=0;i<shower.size();++i){auto& r=s.russ_wall__;const auto& h=shower[i];for(float x:{h.x_cm,h.y_cm,h.time_s,h.energy_GeV,h.phi_deg})Finite(x);r.xshow[i]=h.x_cm;r.yshow[i]=h.y_cm;r.tshow[i]=h.time_s;r.eshow[i]=h.energy_GeV;r.phishow[i]=h.phi_deg;}
  // Pad element zero so f2c's one-based pointer adjustment stays in allocation.
  std::array<float,21> u{},v{},x{},y{};std::array<int,21> cl{};
  for(std::size_t i=0;i<planar.size();++i){u[i+1]=planar[i].u_cm;v[i+1]=planar[i].v_cm;x[i+1]=planar[i].x_cm;y[i+1]=planar[i].y_cm;cl[i+1]=planar[i].confidence;}
  int n=static_cast<int>(planar.size()),cltot=0; // CL/CLTOT are unused by ANA_WAL
  ForwardAssociations out;
  try {
    s.ana_wal__(u.data()+1,v.data()+1,x.data()+1,y.data()+1,cl.data()+1,&n,&cltot);
    for(std::size_t i=0;i<planar.size();++i){const auto& p=planar[i];float dx=std::abs(p.u_cm*config.zp2_cm/config.zp1_cm-p.x_cm),dy=std::abs(p.v_cm*config.zp2_cm/config.zp1_cm-p.y_cm);if(std::sqrt(dx*dx+dy*dy)<5.f)out.planar_input_indices.push_back(static_cast<int>(i));}
    for(int i=0;i<s.trackf_.n_traf__;++i){auto& t=s.trackf_;ForwardMatch m{t.iass_trf__[i],t.ind_traf__[3*i],t.ind_traf__[3*i+1],t.ind_traf__[3*i+2]};if(m.mask<1 || m.mask>7)throw source::Undefined("invalid source association mask");out.matches.push_back(m);++out.mask_counts[m.mask-1];}
    auto& b=s.best_trf__;
    for(int i=0;i<b.nparf;++i){ForwardParticle p{{b.cos_trf__[3*i],b.cos_trf__[3*i+1],b.cos_trf__[3*i+2]},b.theta_trf__[i],b.phi_trf__[i],b.tof_trf__[i],b.de_trf__[i],b.index_trf__[i],b.info_wal__[i]};for(float v:p.direction)CheckOutput(v);for(float v:{p.theta_deg,p.phi_deg,p.tof_ns,p.de_MeV})CheckOutput(v);out.particles.push_back(p);}
    out.charged=b.nparf_c__;out.neutral=b.nparf_n__;out.strange=b.nparf_strange__;out.source_iforw_c=s.trackf_.iforw_c__;out.source_iforw_n=s.trackf_.iforw_n__;
  }catch(const source::Undefined& e){out={};out.status=ReconstructionStatus::UndefinedSource;out.reason=e.what();}
  return out;
}
inline ForwardReconstruction ReconstructForward(const WallResult& wall,const ShowerResult& shower,
    const std::vector<PlanarEndpoint>& planar,const ReconstructionConfig& config,bool wall_available=true,bool shower_available=true,bool planar_available=true) {
  ForwardReconstruction out;
  if(wall_available)out.wall=ReconstructWall(wall,config);else{out.wall.status=ReconstructionStatus::UnavailableInput;out.wall.reason="WALL unavailable";}
  if(wall_available && shower_available && planar_available)out.shower=ReconstructShower(shower,wall,planar,config);
  else{out.shower.status=ReconstructionStatus::UnavailableInput;out.shower.reason="RUSSWALL dependency unavailable";}
  if(planar_available && out.wall.status==ReconstructionStatus::Valid && out.shower.status==ReconstructionStatus::Valid)
    out.associations=AssociateForward(planar,out.wall.clusters,out.shower.clusters,config);
  else{out.associations.status=ReconstructionStatus::UnavailableInput;out.associations.reason="measured forward reconstruction dependency unavailable";}
  return out;
}
} // forward26
#endif
