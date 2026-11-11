#include "ForwardReconstruction.hh"
#include <iostream>
#include <iomanip>
#include <cassert>
using namespace forward26;
template<class T>void read(T& c){for(auto& x:c)std::cin>>x;}
template<class T>void emit(const T& c){for(auto x:c)std::cout<<' '<<x;}
void wall_output(const WallReconstruction& w){
 if(w.status!=ReconstructionStatus::Valid){std::cout<<"UNSUPPORTED "<<w.reason<<'\n';return;}
 std::cout<<"W "<<w.clusters.size()<<' '<<w.horizontal.size()<<' '<<w.vertical.size();emit(w.source_summary);std::cout<<'\n';
 for(const auto& x:w.clusters){std::cout<<"WC";emit(x.par);emit(x.source_indices);std::cout<<' '<<x.theta_deg<<' '<<x.phi_deg<<' '<<x.association<<'\n';}
 for(int p=0;p<2;++p)for(const auto& h:p?w.vertical:w.horizontal)std::cout<<(p?"WV":"WH")<<' '<<h.channel<<' '<<h.association<<' '<<h.x_cm<<' '<<h.y_cm<<' '<<h.tof_ns<<' '<<h.de_MeV<<' '<<h.energy1<<' '<<h.energy2<<' '<<h.time1<<' '<<h.time2<<'\n';
}
void shower_output(const ShowerReconstruction& s){
 if(s.status!=ReconstructionStatus::Valid){std::cout<<"UNSUPPORTED "<<s.reason<<'\n';return;}
 std::cout<<"S "<<s.clusters.size()<<' '<<s.unrecognized.size()<<'\n';
 for(const auto& h:s.clusters)std::cout<<"SC "<<h.x_cm<<' '<<h.y_cm<<' '<<h.time_s<<' '<<h.energy_GeV<<' '<<h.theta_deg<<' '<<h.phi_deg<<' '<<h.pc_theta_deg<<' '<<h.pc_phi_deg<<' '<<h.type<<'\n';
 for(const auto& h:s.unrecognized)std::cout<<"SU "<<h.channel<<' '<<h.energy<<' '<<h.time_s<<'\n';
}
void assoc_output(const ForwardAssociations& a){
 if(a.status!=ReconstructionStatus::Valid){std::cout<<"UNSUPPORTED "<<a.reason<<'\n';return;}
 std::cout<<"A "<<a.matches.size()<<' '<<a.particles.size()<<' '<<a.charged<<' '<<a.neutral<<' '<<a.strange<<' '<<a.source_iforw_c<<' '<<a.source_iforw_n<<' '<<a.planar_input_indices.size()<<'\n';
 for(const auto& m:a.matches)std::cout<<"AM "<<m.mask<<' '<<m.planar<<' '<<m.wall<<' '<<m.shower<<'\n';
 for(const auto& p:a.particles){std::cout<<"AP";emit(p.direction);std::cout<<' '<<p.theta_deg<<' '<<p.phi_deg<<' '<<p.tof_ns<<' '<<p.de_MeV<<' '<<p.match_index<<' '<<p.wall_info<<'\n';}
}
int main(){
 std::cout<<std::scientific<<std::setprecision(9);
 ReconstructionConfig c;read(c.response.pedestals);read(c.response.tdccal);read(c.response.gaincards);read(c.response.timewalk);read(c.response.tdcoffset);read(c.response.gainpms);c.response.shower=Run340ShowConfig();
 read(c.rw.rt);read(c.rw.rb);std::cin>>c.rw.ay;read(c.rw.by);read(c.rw.bt);read(c.rw.ae);read(c.attn);read(c.atts);read(c.atth);
 std::cin>>c.zp1_cm>>c.zp2_cm>>c.zp3_cm>>c.source_run>>c.rf_bunch>>c.simulation;
 int mode,nh,nv,ns,np;std::cin>>mode>>nh>>nv>>ns>>np;
 WallResult w;ShowerResult sh;std::vector<PlanarEndpoint> pc(np);
 w.horizontal.resize(nh);w.vertical.resize(nv);sh.digits.resize(ns);
 for(auto* a:{&w.horizontal,&w.vertical,&sh.digits})for(auto& d:*a){std::cin>>d.channel;read(d.adc);read(d.tdc);}
 for(auto& p:pc)std::cin>>p.u_cm>>p.v_cm>>p.x_cm>>p.y_cm>>p.confidence;
 if(mode==6){
 auto empty=ReconstructForward(w,sh,pc,c);assert(empty.wall.status==ReconstructionStatus::Valid && empty.shower.status==ReconstructionStatus::Valid && empty.associations.status==ReconstructionStatus::Valid);
 auto absent=ReconstructForward(w,sh,pc,c,false);assert(absent.wall.status==ReconstructionStatus::UnavailableInput && absent.associations.status==ReconstructionStatus::UnavailableInput);
 auto bad=w;bad.status=NegativeTimePartialWrite;assert(ReconstructWall(bad,c).status==ReconstructionStatus::InvalidDigit);
 bad={};bad.horizontal={{1,{100,100},{100,100},0},{1,{100,100},{100,100},0}};assert(ReconstructWall(bad,c).status==ReconstructionStatus::InvalidDigit);
 std::vector<PlanarEndpoint> p(20);for(auto& a:p){a.u_cm=100;a.v_cm=100;a.x_cm=100*c.zp2_cm/c.zp1_cm;a.y_cm=a.x_cm;}
 std::vector<WallCluster> ow(3);for(auto& a:ow){a.par[0]=-100;a.par[1]=-100;}
 std::vector<ShowerCluster> rw(16);for(auto& a:rw){a.x_cm=0;a.y_cm=-140;}
 auto overflow=AssociateForward(p,ow,rw,c);assert(overflow.status==ReconstructionStatus::UndefinedSource);
 bool rejected=false;try{AssociateForward(std::vector<PlanarEndpoint>(21),{}, {},c);}catch(const std::invalid_argument&){rejected=true;}assert(rejected);
 auto selected=AssociateForward({{0,0,6,0,0},{0,0,0,0,1}}, {},{},c);assert(selected.planar_input_indices==std::vector<int>{1});
 auto shbad=sh;shbad.digits={{1,{0,20},{0,0},0}};auto unrec=ReconstructShower(shbad,w,pc,c);assert(unrec.unrecognized.size()==1 && unrec.unrecognized[0].energy_fallback_MeV);
 std::cout<<"public boundary fixtures passed\n";
 }
 if(mode==5){int opt,opt1;std::cin>>opt>>opt1;auto k=reconstruction_detail::State(c);
 k.tofmuro1_.lm_1__=2;k.tofmuro2_.lm_2__=2;
 for(int i=0;i<3;++i){auto& h=k.tofmuro1_;auto& v=k.tofmuro2_;h.ip1_cor__[i]=8;v.ip2_cor__[i]=8;h.a_tof1__[i]=20;v.a_tof2__[i]=20;h.a_de1__[i]=10;v.a_de2__[i]=10;h.ene_l__[i]=h.ene_r__[i]=20;v.ene_u__[i]=v.ene_d__[i]=20;}
 k.muroass_.m_wal__=opt1;int i=1,j=2,bar=1,check=0,l1=2,l2=2;
 k.double_bar__(&opt,&i,&j,&bar,&opt1,&check,&l1,&l2);
 std::cout<<"D "<<check<<' '<<k.muroass_.m_wal__<<'\n';
 for(int n=opt1;n<k.muroass_.m_wal__;++n){std::cout<<"DC";for(int j=0;j<8;++j)std::cout<<' '<<k.muroass_.wal_par__[8*n+j];for(int j=0;j<4;++j)std::cout<<' '<<k.muroass_.ind_par__[4*n+j];std::cout<<' '<<k.muroass_.theta_w__[n]<<' '<<k.muroass_.phi_w__[n]<<' '<<k.muroass_.iass_track__[n]<<'\n';}
 }
 if(mode==1)wall_output(ReconstructWall(w,c));
 if(mode==2)shower_output(ReconstructShower(sh,w,pc,c));
 if(mode==3){int nw,nr;std::cin>>nw>>nr;std::vector<WallCluster> wall(nw);std::vector<ShowerCluster> rw(nr);for(auto& h:wall){read(h.par);std::cin>>h.association;}for(auto& h:rw)std::cin>>h.x_cm>>h.y_cm>>h.time_s>>h.energy_GeV>>h.phi_deg;assoc_output(AssociateForward(pc,wall,rw,c));}
 if(mode==4){auto out=ReconstructForward(w,sh,pc,c);wall_output(out.wall);shower_output(out.shower);assoc_output(out.associations);}
}
