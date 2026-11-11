// Offline diagnostic only: schema-2/3 transport -> legacy period09 BGO/barrel.
#include "LegacyDigitization.hh"
#include "TransportStorage.hh"
#include "TBranch.h"
#include "TLeaf.h"
#include "TMD5.h"
#include "TTreeReader.h"
#include "TTreeReaderValue.h"
#include "nlohmann/json.hpp" // Distributed in ROOT's public include directory.
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <map>
#include <random>
#include <set>
#include <sstream>

namespace fs = std::filesystem;
using Json = nlohmann::json;
using Key = std::pair<int,int>;
using namespace rootinput;
struct Channel { int sensitive,copy,channel; std::string detector; };
struct Event { int run,event; double total,bgo; ULong64_t steps,hits; };

// Exactly specified independent uniform conversion and uncached Box-Muller.
// libm remains platform dependent; this is not historical RAND/Gaussian replay.
class Gaussian {
  std::mt19937_64 engine;
public:
  ULong64_t draws=0;
  explicit Gaussian(std::uint64_t seed):engine(seed){}
  float operator()() {
    const double u1=(double(engine()>>12)+0.5)*0x1.0p-52;
    const double u2=(double(engine()>>12)+0.5)*0x1.0p-52;
    ++draws; return Real(std::sqrt(-2.*std::log(u1))*std::cos(6.283185307179586476925286766559*u2));
  }
};

int main(int argc,char** argv) {
 try {
  Require(argc==5,"Usage: graal_digitize INPUT.root CONFIG.root NEW_OUTPUT_DIR SEED");
  const fs::path input=fs::absolute(argv[1]), config_path=fs::absolute(argv[2]), output=fs::absolute(argv[3]);
  const std::string seed_text=argv[4]; std::size_t used=0;
  Require(!seed_text.empty() && seed_text.find_first_not_of("0123456789")==std::string::npos,"Invalid seed");
  const auto seed=std::stoull(seed_text,&used); Require(used==seed_text.size(),"Invalid seed");
  Require(input.filename().string().find(".partial.")==std::string::npos,"Partial transport input rejected");
  const auto input_md5=Digest(input), config_md5=Digest(config_path);
  auto in=Open(input), cf=Open(config_path);
  TransportSchema(*in);TransportStorage storage(*in);
  const auto input_summary=Json::parse(Text(*in,"summary"));
  Require(input_summary.at("status")=="diagnostic_transport_only"
    && input_summary.at("aborted")==0 && input_summary.at("events")==input_summary.at("attempted_events"),"Incomplete/schema-incompatible transport summary");
  const auto transport_period=input_summary.value("period",std::string("unspecified"));
  Require(transport_period=="1998_uv" || transport_period=="unspecified","Transport period conflicts with legacy09 response");
  const auto cm=Json::parse(Text(*cf,"metadata"));
  Require(cm.at("schema")==1 && cm.at("mode")=="legacy09_diagnostic" && cm.at("physics_validation")==false
    && cm.at("detector_geometry_status")=="unqualified_for_1998", "Wrong response config schema/mode");
  legacy09::Config config;
  TTreeReader cr(&Tree(*cf,"scalars"));
  Require(cr.GetTree()->GetEntries()==1,"Config scalars must have one row");
#define REAL_FIELD(name) Number<double> c_##name(cr,#name,"Double_t")
  REAL_FIELD(scbgo); REAL_FIELD(vscbgo_GeV); REAL_FIELD(thres_GeV); REAL_FIELD(scdeb); REAL_FIELD(vscdeb_GeV);
  REAL_FIELD(debdis); REAL_FIELD(dthres_GeV); REAL_FIELD(zc3_cm); REAL_FIELD(sdetof); REAL_FIELD(vdetof_s); REAL_FIELD(ddetof_s); REAL_FIELD(dlight_cm_s);
#undef REAL_FIELD
  Number<int> c_dedxat(cr,"dedxat","Int_t"), c_run(cr,"historical_run","Int_t");
  Require(Next(cr),"Missing config row");
#define ASSIGN(name) Require(cm.at(#name).get<double>()==c_##name.get(), "Config metadata/scalar mismatch: " #name); config.name=Real(c_##name.get())
  ASSIGN(scbgo); ASSIGN(vscbgo_GeV); ASSIGN(thres_GeV); ASSIGN(scdeb); ASSIGN(vscdeb_GeV);
  ASSIGN(debdis); ASSIGN(dthres_GeV); ASSIGN(zc3_cm); ASSIGN(sdetof); ASSIGN(vdetof_s); ASSIGN(ddetof_s); ASSIGN(dlight_cm_s);
#undef ASSIGN
  Require(c_dedxat.get()==1 && cm.at("dedxat")==1,"Diagnostic requires DEDXAT=1"); config.dedxat=true;
  const int historical_run=c_run.get(); Require((historical_run==1321 || historical_run==1324) && cm.at("historical_run")==historical_run,"Historical run mismatch"); Require(!Next(cr),"Extra config row");
  TTreeReader ar(&Tree(*cf,"attenuation")); Number<int> ac(ar,"channel","Int_t");
  Number<double> x1(ar,"x1","Double_t"),x2(ar,"x2","Double_t"),x3(ar,"x3","Double_t"),x4(ar,"x4","Double_t");
  int count=0; while(Next(ar)) {Require(ac.get()==++count && count<=32,"Invalid attenuation channel order"); const std::array<double,4> row={x1.get(),x2.get(),x3.get(),x4.get()};
    Require(row[0]>0 && row[0]<=1 && row[2]>=0,"Unsupported attenuation coefficient domain");
    for(int j=0;j<4;++j) {Require(cm.at("attenuation").at(count-1).at(j).get<double>()==row[j],"Config metadata/attenuation mismatch"); config.attenuation[count-1][j]=Real(row[j]);}}
  Require(count==32 && cm.at("attenuation").size()==32,"Incomplete attenuation"); legacy09::ValidateConfig(config);

  std::map<std::string,Channel> inventory; std::set<int> bgo_channels,barrel_channels;
  TTreeReader ir(&Tree(*in,"channels")); String ip(ir,"path"),id(ir,"detector"),iv(ir,"volume"),ik(ir,"channel_kind");
  Number<int> is(ir,"sensitive","Int_t"),ic(ir,"copy","Int_t"),il(ir,"legacy_channel","Int_t");
  static const std::array<const char*,15> roles={"","bgo","barrel","tof_h","tof_v","shower","cyl_surface_1","cyl_surface_2","plane_1","plane_2","cyl_gas_1","cyl_gas_2","disk_1","disk_2","bc448"};
  while(Next(ir)) {
    Channel c{is.get(),ic.get(),il.get(),id.get()}; const auto p=ip.get();
    Require(!p.empty() && c.sensitive>=1 && c.sensitive<=14 && c.detector==roles[c.sensitive],"Invalid channel role/path");
    const auto suffix="/"+iv.get()+":"+std::to_string(c.copy);
    Require(p.size()>=suffix.size() && p.compare(p.size()-suffix.size(),suffix.size(),suffix)==0,"Path/copy inventory identity mismatch: "+p+" expected suffix "+suffix);
    Require(inventory.emplace(p,c).second,"Duplicate channel path");
    if(c.sensitive==1 || c.sensitive==2) {
      Require(ik.get()=="legacy_scintillator","Wrong scintillator channel kind");
      const int max=c.sensitive==1?480:32;
      Require(c.channel>=1 && c.channel<=max && c.copy==c.channel+(c.sensitive==2?100:0),"Invalid BGO/barrel copy identity");
      Require((c.sensitive==1?bgo_channels:barrel_channels).insert(c.channel).second,"Duplicate scintillator identity");
    }
  }
  Require(bgo_channels.size()==480 && barrel_channels.size()==32,"Incomplete BGO/barrel inventory");
  std::vector<Event> events; std::map<Key,std::size_t> event_index;
  TTreeReader er(&Tree(*in,"events")); Number<int> eu(er,"run","Int_t"),ev(er,"event","Int_t"),ea(er,"aborted","Int_t");
  Number<double> et(er,"total_edep_MeV","Double_t"),eb(er,"bgo_edep_MeV","Double_t");
  Number<ULong64_t> es(er,"steps","ULong64_t"),eh(er,"hit_steps","ULong64_t");
  while(Next(er)) {
    Event e{eu.get(),ev.get(),et.get(),eb.get(),es.get(),eh.get()};
    Require(e.run>=0 && e.event>=0 && ea.get()==0,"Aborted/invalid event"); Nonnegative(e.total,"event total"); Nonnegative(e.bgo,"event BGO");
    Require(e.hits<=e.steps && e.bgo<=e.total+1e-9,"Inconsistent event ledger");
    Require(event_index.emplace(Key{e.run,e.event},events.size()).second,"Duplicate event key"); events.push_back(e);
  }
  Require(input_summary.at("events").get<ULong64_t>()==events.size(),"Input summary event count mismatch");
  // Immutable whole-input digest and path retain all original primaries, weights,
  // source metadata and float64 raw steps without duplicating the huge step tree.
  Require(in->Get("primaries") && dynamic_cast<TTree*>(in->Get("primaries")),"Missing primaries reference");
  TTreeReader sr(&Tree(*in,"detector_steps")); SourceEntry source_entry(sr,storage); Number<int> su(sr,"run","Int_t"),sv(sr,"event","Int_t"); String sp(sr,"path");
  Number<double> se(sr,"edep_MeV","Double_t"),sz(sr,"post_z_mm","Double_t"),st(sr,"post_time_ns","Double_t");
  std::vector<std::unique_ptr<Number<double>>> positive_fields,finite_fields;
  for(const char* key:{"track_weight","nonionizing_edep_MeV","step_length_mm","pre_time_ns","pre_kinetic_MeV","post_kinetic_MeV"})
    if(!storage.compact() || sr.GetTree()->GetBranch(key)) positive_fields.push_back(std::make_unique<Number<double>>(sr,key,"Double_t"));
  for(const char* key:{"charge_e","pre_x_mm","pre_y_mm","pre_z_mm","post_x_mm","post_y_mm","pre_local_x_mm","pre_local_y_mm","pre_local_z_mm","post_local_x_mm","post_local_y_mm","post_local_z_mm",
    "pre_dir_x","pre_dir_y","pre_dir_z","post_dir_x","post_dir_y","post_dir_z"}) if(!storage.compact() || sr.GetTree()->GetBranch(key)) finite_fields.push_back(std::make_unique<Number<double>>(sr,key,"Double_t"));
  Require(fs::create_directory(output),"Output exists; refusing overwrite"); RootOutput out(output,"response");
  auto& ledger=out.Book("response_events",{{"run",0},{"event",0},{"historical_run",0},{"status",std::string{}},
    {"total_edep_MeV",0.},{"bgo_edep_MeV",0.},{"steps",ULong64_t{0}},{"hit_steps",ULong64_t{0}},{"aborted",0},
    {"bgo_raw_total_GeV",0.},{"bgo_total_adc",0},{"bgo_soft_total_adc",0},{"bgo_digits",0},
    {"barrel_records",ULong64_t{0}},{"barrel_digits",0},{"energy_draws",ULong64_t{0}},{"time_draws",ULong64_t{0}},{"full_trigger_available",0}});
  auto& bd=out.Book("bgo_digits",{{"run",0},{"event",0},{"channel",0},{"adc",0}});
  auto& dd=out.Book("barrel_digits",{{"run",0},{"event",0},{"channel",0},{"adc",0},{"tdc",0},{"energy_GeV",0.},{"time_s",0.}});
  auto& records=out.Book("barrel_records",{{"run",0},{"event",0},{"record_index",ULong64_t{0}},{"channel",0},{"energy_GeV",0.},{"z_cm",0.},{"time_s",0.},{"source_steps",ULong64_t{0}}});
  auto& links=out.Book("barrel_step_links",{{"run",0},{"event",0},{"record_index",ULong64_t{0}},{"input_step_entry",ULong64_t{0}}});
  auto& trace=out.Book("gaussian_draws",{{"run",0},{"event",0},{"draw_index",ULong64_t{0}},{"value",0.}});
  Json metadata={{"schema_version",1},{"mode","legacy09_diagnostic"},{"period","1998_uv"},{"historical_run",historical_run},
    {"transport_period",transport_period},{"response_period","1998_uv"},
    {"physics_validation",false},{"detector_geometry_status","unqualified_for_1998"},{"response_calibrated",false},
    {"trigger","not_implemented"},{"masks","unknown"},{"quenching","not_implemented"},
    {"bgo_adaptation","float64_MeV_sum_per_channel_then_GeV_binary32_once; not_GUSTEP_per_step_REAL_accumulation"},
    {"barrel_adaptation","all_positive_G4_deposits_post_step_GLOBAL_z_time; no_GEANT3_mechanism22_exclusion"},
    {"grouping","legacy_last_record_same_bar_anchor_delta_z_strictly_less_1cm_unweighted_z_first_time_capped_1us"},
    {"serialization","ROOT_tables_not_HBOOK; REAL_binary32_response_preserved_as_double; raw_float64_in_input"},
    {"rng","mt19937_64_top52_midpoint_uniform_uncached_BoxMuller_cos_libm_platform_dependent_not_historical_RAND"},{"seed",seed},
    {"input_path",input.string()},{"input_md5",input_md5},{"config_path",config_path.string()},{"config_md5",config_md5},
    {"provenance_policy","native_MD5_stability_only; SHA256_authoritative_only_when_launcher_provenance_present"},
    {"source_access",storage.compact()?"immutable input retains original primaries/truth/weights and compact response inputs; source links use original sensitive indices":"all_original_primaries_weights_truth_metadata_and_raw_steps_in_immutable_referenced_input"}};
  metadata["ledger_energy_tolerance_MeV"]="1e-9 + 1e-10*max(abs(a),abs(b)); sensitive sum <= total, BGO sum equals ledger";
  out.Metadata("metadata",metadata.dump()); out.Metadata("input_summary",input_summary.dump()); out.Metadata("config_metadata",cm.dump());
  if(cf->Get("launcher_provenance")) out.Metadata("launcher_provenance",Text(*cf,"launcher_provenance"));
  bool step=Next(sr); ULong64_t total_steps=0,overflow=0; Gaussian gaussian(seed);
  for(std::size_t index=0;index<events.size();++index) {
    const auto& e=events[index]; auto bgo=storage.bgo(e.run,e.event); std::vector<legacy09::BarrelHit> barrel; std::vector<ULong64_t> source;
    ULong64_t hit_count=0; double bgo_sum=storage.omitted_bgo(e.run,e.event),sensitive_sum=bgo_sum;
    while(step) {
      const Key key{su.get(),sv.get()}; auto found=event_index.find(key); Require(found!=event_index.end(),"Orphan detector step");
      Require(found->second>=index,"Out-of-order detector event steps"); if(found->second!=index) break;
      const auto channel=inventory.find(sp.get()); Require(channel!=inventory.end(),"Unknown referenced detector path");
      const double energy=se.get(),z=sz.get(),time=st.get(); Nonnegative(energy,"step deposit"); Nonnegative(time,"post time"); Require(std::isfinite(z),"Nonfinite post z");
      for(auto& field:positive_fields) Nonnegative(field->get(),"step magnitude");
      for(auto& field:finite_fields) Require(std::isfinite(field->get()),"Nonfinite step observable");
      sensitive_sum+=energy; Nonnegative(sensitive_sum,"sensitive energy sum");
      if(channel->second.sensitive==1) bgo_sum+=energy;
      if(channel->second.sensitive==1) {bgo[channel->second.channel-1]+=energy; Nonnegative(bgo[channel->second.channel-1],"BGO sum");}
      if(channel->second.sensitive==2 && energy>0) {barrel.push_back({channel->second.channel,Real(energy/1000.),Real(z/10.),Real(time*1e-9)}); source.push_back(source_entry.get());}
      ++hit_count; ++total_steps; step=Next(sr);
    }
    Require(hit_count==storage.stored(e.run,e.event,e.hits),"Per-event hit step count mismatch");
    const auto tolerance=[](double a,double b){return 1e-9+1e-10*std::max(std::abs(a),std::abs(b));};
    Require(std::abs(bgo_sum-e.bgo)<=tolerance(bgo_sum,e.bgo),"BGO step/ledger energy mismatch");
    Require(sensitive_sum<=e.total+tolerance(sensitive_sum,e.total),"Sensitive step energy exceeds event ledger");
    std::vector<legacy09::BgoDeposit> deposits; for(int i=0;i<480;++i) if(bgo[i]>0) deposits.push_back({i+1,Real(bgo[i]/1000.)});
    const auto b=legacy09::DigitizeBgo(deposits,config); for(const auto& d:b.digits) bd.Fill({e.run,e.event,d.channel,d.adc});
    const auto grouping=legacy09::GroupBarrelSteps(barrel);
    for(std::size_t i=0;i<grouping.records.size();++i) {const auto& r=grouping.records[i];
      records.Fill({e.run,e.event,ULong64_t(i),r.channel,double(r.energy_GeV),double(r.z_cm),double(r.time_s),ULong64_t(grouping.source_indices[i].size())});
      for(auto j:grouping.source_indices[i]) links.Fill({e.run,e.event,ULong64_t(i),source.at(j)});
    }
    legacy09::BarrelResult d; std::string status="diagnostic_only";
    if(grouping.records.size()>100) {status="unsupported_barrel_record_overflow"; ++overflow;}
    else d=legacy09::DigitizeBarrel(grouping.records,config,[&](){const auto i=gaussian.draws; float g=gaussian();trace.Fill({e.run,e.event,i,double(g)});return g;});
    for(const auto& r:d.digits) dd.Fill({e.run,e.event,r.channel,r.adc,r.tdc,double(r.energy_GeV),double(r.time_s)});
    ledger.Fill({e.run,e.event,historical_run,status,e.total,e.bgo,e.steps,e.hits,0,double(b.raw_total_GeV),b.total_adc,b.soft_total_adc,int(b.digits.size()),ULong64_t(grouping.records.size()),int(d.digits.size()),ULong64_t(d.energy_draws),ULong64_t(d.time_draws),0});
  }
  Require(!step,"Orphan/out-of-order trailing detector steps");
  Require(storage.rows()==total_steps,"Input summary step count mismatch");
  Require(Digest(input)==input_md5 && Digest(config_path)==config_md5,"Input/config changed during digitization");
  Json summary={{"status","legacy09_diagnostic_complete"},{"mode","legacy09_diagnostic"},{"schema_version",1},{"events",events.size()},
    {"barrel_overflow_events",overflow},{"physics_validation",false},{"full_trigger_available",false},{"output_format","ROOT_TTree"},{"compression","ZSTD_5"},{"gaussian_draws",gaussian.draws}};
  out.Finish(summary.dump()); std::cout<<"DIAGNOSTIC_RESPONSE_COMPLETE events="<<events.size()<<" overflow="<<overflow<<'\n'; return 0;
 }catch(const std::exception& error) {std::cerr<<"ERROR: "<<error.what()<<'\n';return 1;}
}
