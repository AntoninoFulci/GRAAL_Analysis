// Offline selected26 NEW_PLAN: transport entrances -> wires -> chamber tracks.
#include "NewPlan.hh"
#include "TransportStorage.hh"
#include "nlohmann/json.hpp"
#include <map>
#include <set>

using namespace rootinput;
using Json=nlohmann::json;
using Key=std::pair<int,int>;
struct Channel { int sensitive,copy,channel; };
struct Event { int run,event,aborted; double total,bgo; ULong64_t steps,hits; };
static const std::array<std::string,4> plane_paths={
  "/LAGR:1/PLG1:1/PLN1:1","/LAGR:1/PLG1:1/PLN1:2",
  "/LAGR:1/PLG2:1/PLN2:1","/LAGR:1/PLG2:1/PLN2:2"};

int main(int argc,char** argv) {
 try {
  Require(argc==4,"Usage: graal_newplan INPUT.root CONFIG.root NEW_OUTPUT_DIR");
  const fs::path input=fs::absolute(argv[1]), config_path=fs::absolute(argv[2]), output=fs::absolute(argv[3]);
  Require(input.filename().string().find(".partial") == std::string::npos,"Partial transport input rejected");
  const auto input_md5=Digest(input),config_md5=Digest(config_path);
  auto in=Open(input),cf=Open(config_path); TransportSchema(*in);TransportStorage storage(*in);
  const auto input_summary=Json::parse(Text(*in,"summary"));
  Require(input_summary.at("status")=="diagnostic_transport_only"
    && input_summary.at("aborted")==0 && input_summary.at("events")==input_summary.at("attempted_events"),"Incomplete/schema-incompatible transport summary");
  const auto cm=Json::parse(Text(*cf,"metadata"));
  Require(cm.at("schema")==1 && cm.at("mode")=="selected26_newplan_diagnostic"
    && cm.at("physical_validation")==false && cm.at("physics_validation")==false
    && cm.at("baseline")==Json({"GRAAL_26","GRAAL_NEW_PLAN","GRAAL_OLD_CYL"}),"Wrong selected26 config schema/mode/baseline");
  Require(cm.at("units").at("length")=="cm" && cm.at("units").at("angle")=="degree","Wrong selected26 units");
  Require(cm.at("sources").size()==1 && cm.at("sources").at(0).at("path")=="base/data26.base","Wrong selected26 source identity");
  const auto source_hash=cm.at("sources").at(0).at("sha256").get<std::string>();
  Require(source_hash.size()==64 && source_hash.find_first_not_of("0123456789abcdef")==std::string::npos,"Invalid selected26 source hash");
  TTreeReader cr(&Tree(*cf,"scalars")); Require(cr.GetTree()->GetEntries()==1,"Config scalars must have one row");
#define REAL_FIELD(name) Number<double> c_##name(cr,#name,"Double_t")
  REAL_FIELD(xp1_cm); REAL_FIELD(xp2_cm); REAL_FIELD(zp1_cm); REAL_FIELD(zp2_cm); REAL_FIELD(angle_deg);
  REAL_FIELD(efficiency_0); REAL_FIELD(efficiency_1); REAL_FIELD(efficiency_2); REAL_FIELD(efficiency_3);
#undef REAL_FIELD
  Number<int> c_nf1(cr,"nf1","Int_t"),c_nf2(cr,"nf2","Int_t");
  Require(Next(cr),"Missing config row"); newplan::Geometry geometry{};
#define ASSIGN(name) Require(cm.at(#name).get<double>()==c_##name.get(),"Config metadata/scalar mismatch: " #name); geometry.name=Real(c_##name.get())
  ASSIGN(xp1_cm); ASSIGN(xp2_cm); ASSIGN(zp1_cm); ASSIGN(zp2_cm); ASSIGN(angle_deg);
#undef ASSIGN
  geometry.nf1=c_nf1.get(); geometry.nf2=c_nf2.get();
  Require(cm.at("nf1")==geometry.nf1 && cm.at("nf2")==geometry.nf2 && geometry.nf1==320 && geometry.nf2==384 && geometry.angle_deg==-45.f,"Requires selected26 NEW_PLAN counts/angle");
#define EFF(i) Require(c_efficiency_##i.get()==1. && cm.at("efficiency_" #i)==1.,"Only unit efficiency supported")
  EFF(0); EFF(1); EFF(2); EFF(3);
#undef EFF
  Require(newplan::supported(newplan::digitize({},geometry).status),"Invalid NEW_PLAN geometry"); Require(!Next(cr),"Extra config row");
  // Double source geometry is used only for an observed slab compatibility check.
  const std::array<double,4> plane_z={cm.at("zp1_cm").get<double>()-.5,cm.at("zp1_cm").get<double>()+.5,
    cm.at("zp2_cm").get<double>()-.5,cm.at("zp2_cm").get<double>()+.5};
  std::map<std::string,Channel> inventory; std::set<std::string> planes;
  TTreeReader ir(&Tree(*in,"channels")); String ip(ir,"path"),id(ir,"detector"),iv(ir,"volume"),ik(ir,"channel_kind");
  Number<int> is(ir,"sensitive","Int_t"),ic(ir,"copy","Int_t"),il(ir,"legacy_channel","Int_t");
  static const std::array<const char*,15> roles={"","bgo","barrel","tof_h","tof_v","shower","cyl_surface_1","cyl_surface_2","plane_1","plane_2","cyl_gas_1","cyl_gas_2","disk_1","disk_2","bc448"};
  while(Next(ir)) {
    const Channel c{is.get(),ic.get(),il.get()}; const auto p=ip.get();
    Require(!p.empty() && c.sensitive>=1 && c.sensitive<=14 && id.get()==roles[c.sensitive],"Invalid channel role/path");
    const auto suffix="/"+iv.get()+":"+std::to_string(c.copy);
    Require(p.size()>=suffix.size() && p.compare(p.size()-suffix.size(),suffix.size(),suffix)==0,"Path/copy inventory mismatch");
    Require(inventory.emplace(p,c).second,"Duplicate channel path");
    if(c.sensitive==8 || c.sensitive==9) {
      Require(c.copy>=1 && c.copy<=2 && c.channel==c.copy && ik.get()=="chamber_plane","Invalid plane copy/channel/kind");
      const auto plane=2*(c.sensitive-8)+c.copy-1;
      Require(p==plane_paths[plane],"Unexpected selected26 plane path"); planes.insert(p);
    }
  }
  Require(planes.size()==4,"Incomplete four-plane inventory");
  std::vector<Event> events; std::map<Key,std::size_t> event_index;
  TTreeReader er(&Tree(*in,"events")); Number<int> eu(er,"run","Int_t"),ev(er,"event","Int_t"),ea(er,"aborted","Int_t");
  Number<double> et(er,"total_edep_MeV","Double_t"),eb(er,"bgo_edep_MeV","Double_t");
  Number<ULong64_t> es(er,"steps","ULong64_t"),eh(er,"hit_steps","ULong64_t");
  while(Next(er)) {
    Event e{eu.get(),ev.get(),ea.get(),et.get(),eb.get(),es.get(),eh.get()};
    Require(e.run>=0 && e.event>=0 && e.aborted==0,"Aborted/invalid event"); Nonnegative(e.total,"event total"); Nonnegative(e.bgo,"event BGO");
    Require(e.hits<=e.steps && e.bgo<=e.total+1e-9,"Inconsistent event ledger");
    Require(event_index.emplace(Key{e.run,e.event},events.size()).second,"Duplicate event key"); events.push_back(e);
  }
  Require(input_summary.at("events").get<ULong64_t>()==events.size(),"Input summary event count mismatch");
  TTreeReader sr(&Tree(*in,"detector_steps")); SourceEntry source_entry(sr,storage); Number<int> su(sr,"run","Int_t"),sv(sr,"event","Int_t"); String sp(sr,"path");
  Number<int> pre_boundary(sr,"pre_boundary","Int_t"),post_boundary(sr,"post_boundary","Int_t"),track(sr,"track","Int_t"),parent(sr,"parent","Int_t"),track_step(sr,"track_step","Int_t");
  Number<int> pre_status(sr,"pre_status","Int_t"),post_status(sr,"post_status","Int_t"),track_status(sr,"track_status","Int_t");
  Number<double> charge(sr,"charge_e","Double_t"),x(sr,"pre_x_mm","Double_t"),y(sr,"pre_y_mm","Double_t"),z(sr,"pre_z_mm","Double_t"),energy(sr,"edep_MeV","Double_t");
  std::vector<std::unique_ptr<Number<double>>> positive_fields,finite_fields;
  for(const char* key:{"track_weight","nonionizing_edep_MeV","step_length_mm","pre_time_ns","post_time_ns","pre_kinetic_MeV","post_kinetic_MeV"})
    if(!storage.compact() || sr.GetTree()->GetBranch(key)) positive_fields.push_back(std::make_unique<Number<double>>(sr,key,"Double_t"));
  for(const char* key:{"post_x_mm","post_y_mm","post_z_mm","pre_local_x_mm","pre_local_y_mm","pre_local_z_mm","post_local_x_mm","post_local_y_mm","post_local_z_mm",
    "pre_dir_x","pre_dir_y","pre_dir_z","post_dir_x","post_dir_y","post_dir_z"}) if(!storage.compact() || sr.GetTree()->GetBranch(key)) finite_fields.push_back(std::make_unique<Number<double>>(sr,key,"Double_t"));
  Require(fs::create_directory(output),"Output exists; refusing overwrite"); RootOutput out(output,"tracking");
  auto& ledger=out.Book("tracking_events",{{"run",0},{"event",0},{"status",std::string{}},{"kernel_status",0},{"digit_status",0},{"reconstruction_status",0},
    {"total_edep_MeV",0.},{"bgo_edep_MeV",0.},{"steps",ULong64_t{0}},{"hit_steps",ULong64_t{0}},{"aborted",0},
    {"crossings_u",ULong64_t{0}},{"crossings_v",ULong64_t{0}},{"crossings_x",ULong64_t{0}},{"crossings_y",ULong64_t{0}},
    {"digits_u",0},{"digits_v",0},{"digits_x",0},{"digits_y",0},{"clusters_u",0},{"clusters_v",0},{"clusters_x",0},{"clusters_y",0},
    {"candidate_count",0},{"cltot",0},{"ntracks",0},{"full_trigger_available",0}});
  auto& crossings=out.Book("plane_crossings",{{"run",0},{"event",0},{"plane",0},{"crossing_index",ULong64_t{0}},{"source_step_entry",ULong64_t{0}},
    {"pre_x_mm",0.},{"pre_y_mm",0.},{"pre_z_mm",0.},{"charge_e",0.}});
  auto& digits=out.Book("plane_digits",{{"run",0},{"event",0},{"plane",0},{"ordered_digit_index",0},{"wire",0}});
  auto& links=out.Book("crossing_digit_links",{{"run",0},{"event",0},{"crossing_index",ULong64_t{0}},{"plane",0},{"wire",0},{"ordered_digit_index",0},{"state",0}});
  auto& tracks=out.Book("planar_tracks",{{"run",0},{"event",0},{"track_index",0},{"first_x_cm",0.},{"first_y_cm",0.},{"first_z_cm",0.},{"second_x_cm",0.},{"second_y_cm",0.},{"second_z_cm",0.},{"cl",0}});
  auto& track_links=out.Book("track_wire_links",{{"run",0},{"event",0},{"track_index",0},{"plane",0},{"cluster_index",0},{"ordered_digit_index",0}});
  out.Metadata("input_summary",input_summary.dump()); out.Metadata("config_metadata",cm.dump());
  if(cf->Get("launcher_provenance")) out.Metadata("launcher_provenance",Text(*cf,"launcher_provenance"));
  bool step=Next(sr); ULong64_t total_steps=0,total_crossings=0,total_digits=0,total_tracks=0,unsupported=0;
  std::array<ULong64_t,4> coverage{}; std::map<std::string,ULong64_t> statuses;
  for(std::size_t index=0;index<events.size();++index) {
    const auto& e=events[index]; std::vector<newplan::Crossing> measured; ULong64_t hit_count=0; double bgo_sum=storage.omitted_bgo(e.run,e.event),sensitive_sum=bgo_sum;
    while(step) {
      const Key key{su.get(),sv.get()}; auto found=event_index.find(key); Require(found!=event_index.end(),"Orphan detector step");
      Require(found->second>=index,"Out-of-order detector event steps"); if(found->second!=index) break;
      const auto channel=inventory.find(sp.get()); Require(channel!=inventory.end(),"Unknown referenced detector path");
      const double edep=energy.get(),xx=x.get(),yy=y.get(),zz=z.get(),q=charge.get(); Nonnegative(edep,"step deposit");
      Require(std::isfinite(xx)&&std::isfinite(yy)&&std::isfinite(zz)&&std::isfinite(q),"Nonfinite crossing observable");
      for(auto& field:positive_fields) Nonnegative(field->get(),"step magnitude");
      for(auto& field:finite_fields) Require(std::isfinite(field->get()),"Nonfinite step observable");
      Require((pre_boundary.get()==0 || pre_boundary.get()==1) && (post_boundary.get()==0 || post_boundary.get()==1),"Invalid step boundary flag");
      Require(track.get()>0 && parent.get()>=0 && track_step.get()>0,"Invalid track/step identity");
      Require(pre_status.get()>=0 && pre_status.get()<=7 && post_status.get()>=0 && post_status.get()<=7 && track_status.get()>=0 && track_status.get()<=5,"Invalid step status flag");
      sensitive_sum+=edep; Nonnegative(sensitive_sum,"sensitive energy sum"); if(channel->second.sensitive==1) bgo_sum+=edep;
      const auto& c=channel->second;
      if((c.sensitive==8 || c.sensitive==9) && q!=0. && pre_boundary.get()==1) {
        const int plane=2*(c.sensitive-8)+c.copy-1;
        const double tolerance=1e-7+1e-7*std::max(std::abs(zz/10.),std::abs(plane_z[plane]));
        Require(std::abs(zz/10.-plane_z[plane])<=.01+tolerance,"Plane entrance z conflicts with selected26 thin slab");
        crossings.Fill({e.run,e.event,plane,ULong64_t(measured.size()),source_entry.get(),xx,yy,zz,q});
        measured.push_back({plane,Real(xx/10.),Real(yy/10.)}); ++coverage[plane];
      }
      ++hit_count; ++total_steps; step=Next(sr);
    }
    Require(hit_count==storage.stored(e.run,e.event,e.hits),"Per-event hit step count mismatch");
    const auto tolerance=[](double a,double b){return 1e-9+1e-10*std::max(std::abs(a),std::abs(b));};
    Require(std::abs(bgo_sum-e.bgo)<=tolerance(bgo_sum,e.bgo),"BGO step/ledger energy mismatch");
    Require(sensitive_sum<=e.total+tolerance(sensitive_sum,e.total),"Sensitive step energy exceeds event ledger");
    const auto d=newplan::digitize(measured,geometry);
    newplan::Reconstruction r;
    if(newplan::supported(d.status)) r=newplan::reconstruct(d.wires,geometry);
    const auto status=d.status|r.status;
    const std::string event_status=newplan::supported(status)?(r.tracks.empty()?"diagnostic_no_track":"diagnostic_tracks"):"unsupported_kernel_domain";
    if(!newplan::supported(status)) {++unsupported; Require(r.tracks.empty(),"Unsupported event returned tracks");}
    ++statuses[event_status]; total_crossings+=measured.size(); total_tracks+=r.tracks.size();
    for(int p=0;p<4;++p) for(std::size_t j=0;j<d.wires[p].size();++j) {digits.Fill({e.run,e.event,p,int(j),d.wires[p][j]});++total_digits;}
    for(const auto& a:d.associations) links.Fill({e.run,e.event,ULong64_t(a.crossing_index),a.plane,a.wire,a.digit_index,int(a.state)});
    for(std::size_t j=0;j<r.tracks.size();++j) {
      const auto& t=r.tracks[j]; tracks.Fill({e.run,e.event,int(j),double(t.first_cm[0]),double(t.first_cm[1]),double(t.first_cm[2]),double(t.second_cm[0]),double(t.second_cm[1]),double(t.second_cm[2]),t.cl});
      for(int p=0;p<4;++p) for(auto k:t.wire_indices[p]) track_links.Fill({e.run,e.event,int(j),p,t.cluster_indices[p],int(k)});
    }
    ledger.Fill({e.run,e.event,event_status,int(status),int(d.status),int(r.status),e.total,e.bgo,e.steps,e.hits,e.aborted,
      ULong64_t(d.raw_counts[0]),ULong64_t(d.raw_counts[1]),ULong64_t(d.raw_counts[2]),ULong64_t(d.raw_counts[3]),
      int(d.wires[0].size()),int(d.wires[1].size()),int(d.wires[2].size()),int(d.wires[3].size()),
      r.reduced_multiplicity[0],r.reduced_multiplicity[1],r.reduced_multiplicity[2],r.reduced_multiplicity[3],r.candidate_count,r.cltot,int(r.tracks.size()),0});
  }
  Require(!step,"Orphan/out-of-order trailing detector steps");
  Require(storage.rows()==total_steps,"Input summary step count mismatch");
  Require(Digest(input)==input_md5 && Digest(config_path)==config_md5,"Input/config changed during NEW_PLAN reconstruction");
  Json metadata={{"schema_version",1},{"mode","selected26_newplan_diagnostic"},{"physical_validation",false},{"physics_validation",false},
    {"response_calibrated",false},{"full_trigger_available",false},{"input_path",input.string()},{"input_md5",input_md5},{"config_path",config_path.string()},{"config_md5",config_md5},
    {"provenance_policy","native_MD5_stability_only; SHA256_authoritative_only_when_launcher_provenance_present"},
    {"source_access",storage.compact()?"immutable input retains original primaries/truth/weights and compact response inputs; source links use original sensitive indices":"original primaries, truth, weights, metadata and raw steps remain in immutable referenced input"},
    {"measurement","charged pre_boundary entrances; global pre x/y mm -> cm -> REAL; source entry order; all charged secondaries"},
    {"response","source PLCH wire quantization, fixed unit efficiency; no random stream or spatial smearing"},
    {"tracking_inputs","ordered digital wires and selected26 geometry only; no truth grouping or endpoint copying"},
    {"geometry_certification","selected_configuration_only; observed entrance z compatibility does not independently certify full input geometry"},
    {"observed_view_crossings",coverage},{"plane_centers_cm",plane_z},{"plane_half_thickness_cm",.01},
    {"slab_tolerance_cm","1e-7 + 1e-7*max(abs(observed_z_cm),abs(center_cm)); no crossing means no geometric evidence"},
    {"indexing","planes U,V,X,Y = 0,1,2,3; crossing/digit/track/source-entry indices zero-based; wires one-based"},
    {"crossing_states",{{"accepted",0},{"duplicate",1},{"efficiency_rejected",2},{"invalid",3},{"unsupported_overflow",4}}},
    {"kernel_status_bits",{{"invalid_geometry",1},{"invalid_crossing",2},{"invalid_efficiency",4},{"raw_overflow",8},{"invalid_wire",16},{"undefined_xy_upper",32},{"combination_overflow",64},{"coordinate_collision",128},{"nonfinite_arithmetic",256},{"uv_upper_clamped",512}}},
    {"limitations","chamber-only; no wall matching, PID, full trigger, fitted momentum/charge/covariance or detector-efficiency claim"}};
  out.Metadata("metadata",metadata.dump());
  Json summary={{"status","selected26_newplan_diagnostic_complete"},{"mode","selected26_newplan_diagnostic"},{"schema_version",1},{"events",events.size()},
    {"detector_steps",input_summary.at("detector_steps")},{"crossings",total_crossings},{"digits",total_digits},{"tracks",total_tracks},{"unsupported_events",unsupported},{"event_status_counts",statuses},
    {"physical_validation",false},{"physics_validation",false},{"full_trigger_available",false},{"output_format","ROOT_TTree"},{"compression","ZSTD_5"}};
  out.Finish(summary.dump()); std::cout<<"NEW_PLAN_DIAGNOSTIC_COMPLETE events="<<events.size()<<" crossings="<<total_crossings<<" tracks="<<total_tracks<<'\n'; return 0;
 }catch(const std::exception& error) {std::cerr<<"ERROR: "<<error.what()<<'\n';return 1;}
}
