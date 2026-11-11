// Native ROOT diagnostic: all-callback central transport -> OLD_CYL ADC -> digit-only tracking.
#include "LegacyCylinderInput.hh"
#include "LegacyCylinderResponse.hh"
#include "CylinderTracking.hh"
#include "TransportStorage.hh"
#include "nlohmann/json.hpp"
#include "TKey.h"
#include <algorithm>
#include <map>
#include <random>
#include <set>
using namespace rootinput;
using Json=nlohmann::json;
using Key=std::pair<int,int>;
namespace fs=std::filesystem;
namespace {
Json Parse(const std::string& text) {
  std::vector<std::set<std::string>> objects;
  return Json::parse(text,[&](int,Json::parse_event_t event,Json& value) {
    if(event==Json::parse_event_t::object_start) objects.emplace_back();
    if(event==Json::parse_event_t::key) Require(objects.back().insert(value.get<std::string>()).second,"Duplicate JSON key");
    if(event==Json::parse_event_t::object_end) objects.pop_back();
    return true;
  });
}
ULong64_t UInt(const Json& object,const std::string& key,
                ULong64_t maximum=std::numeric_limits<ULong64_t>::max()) {
  const auto& value=object.at(key);
  Require(value.is_number_integer(),"Expected nonnegative JSON integer: "+key);
  // nlohmann numeric get<T>() can truncate floats or wrap signed negatives.
  // Validate the stored JSON category and sign before any unsigned conversion.
  if(!value.is_number_unsigned())
    Require(value.get<Json::number_integer_t>()>=0,"Negative JSON integer: "+key);
  const auto result=value.get<Json::number_unsigned_t>();
  Require(result<=maximum,"JSON integer outside range: "+key);
  return static_cast<ULong64_t>(result);
}
void UniqueKeys(TFile& file) {
  std::set<std::string> names;TIter next(file.GetListOfKeys());
  while(auto* key=next()) Require(names.insert(key->GetName()).second,"Duplicate ROOT object key/cycle");
}
ULong64_t Add(ULong64_t a,ULong64_t b) {
  Require(b<=std::numeric_limits<ULong64_t>::max()-a,"Callback/count overflow");return a+b;
}
struct Event {int run,event;double total,bgo;ULong64_t steps,hits,begin,end,passive_begin,passive_end;};
struct Channel {int role;};
class Gaussian {
  std::mt19937_64 engine;
public:
  ULong64_t draws=0;
  explicit Gaussian(ULong64_t seed):engine(seed){}
  float operator()() {
    const double u1=(double(engine()>>12)+.5)*0x1.0p-52;
    const double u2=(double(engine()>>12)+.5)*0x1.0p-52;
    ++draws;return Real(std::sqrt(-2.*std::log(u1))*std::cos(6.283185307179586476925286766559*u2));
  }
};
legacy_cylinder::Config Configuration(TFile& file,Json& metadata) {
  metadata=Parse(Text(file,"metadata"));
  Require(UInt(metadata,"schema",std::numeric_limits<int>::max())==1 && metadata.at("mode")=="selected26_old_cyl_diagnostic" &&
    metadata.at("baseline")==Json::array({"GRAAL_26","GRAAL_NEW_PLAN","GRAAL_OLD_CYL"}) &&
    metadata.at("physics_validation")==false && metadata.at("physical_validation")==false,
    "Wrong selected26 OLD_CYL configuration");
  Require(metadata.at("tracking_profile").at("mode")=="INITIALISATION_CYLINDRES_OLD_CYL_LSIMUL" &&
    metadata.at("tracking_profile").at("half_lengths_cm")==Json::array({19.5,24.75}),"Wrong tracking profile");
  // Deliberately bounded source-backed selected26 support. Changing the database
  // requires a separately declared profile, not an accidental response retune.
  const Json expected=Json::parse(R"SCALARS({"angle1_deg": 33.86000061035156, "angle2_deg": -41.0099983215332, "angle3_deg": 41.0099983215332, "angle4_deg": -46.630001068115234, "angle5_deg": -45.0, "be1_cm": 0.05001342296600342, "be2_cm": 0.05004391074180603, "be3_cm": 0.05004388093948364, "be4_cm": 0.05000928044319153, "bl_cm": 0.3499999940395355, "cang1": 0.8304014801979065, "cang2": 0.7545951008796692, "cang3": 0.7545951008796692, "cang4": 0.6867069602012634, "conv": 160000000000.0, "cythre": 6000.0, "dfca_cm": 0.4000000059604645, "effcyc1": 1.0, "effcyc2": 1.0, "gas_floor_GeV": 1.0000000116860974e-07, "nb1": 60, "nb2": 64, "nb3": 96, "nb4": 96, "nbord": 2, "nf1": 320, "nf2": 384, "nfc1": 128, "nfc2": 192, "pc1_cm": 0.8999999761581421, "pc2_cm": 0.8999999761581421, "rc1_cm": 5.0, "rc2_cm": 8.5, "re1_cm": 5.400000095367432, "re2_cm": 8.899999618530273, "ri1_cm": 4.599999904632568, "ri2_cm": 8.100000381469727, "sang1": 0.5571655035018921, "sang2": -0.6561907529830933, "sang3": 0.6561907529830933, "sang4": -0.7269343733787537, "sccat": 1024.0, "sigce1": 2300.0, "sigce2": 2300.0, "sigce3": 2300.0, "sigce4": 2300.0, "sigct": 0.12999999523162842, "ucf1_cm": 31.415925979614258, "ucf2_cm": 53.407073974609375, "vsccat": 400000.0, "xbl1_cm": 24.000804901123047, "xbl2_cm": 25.60280990600586, "xbl3_cm": 38.404212951660156, "xbl4_cm": 38.4008903503418, "zc1_cm": 20.0, "zc2_cm": 25.25})SCALARS");
  const std::set<std::string> integers={"nf1","nf2","nfc1","nfc2","nb1","nb2","nb3","nb4","nbord"};
  auto& tree=Tree(file,"scalars");Require(tree.GetEntries()==1,"Config scalars require one row");
  Require(tree.GetListOfBranches()->GetEntries()==int(expected.size()),"Unexpected configuration scalar inventory");
  TTreeReader reader(&tree);
  std::map<std::string,std::unique_ptr<Number<int>>> iv;
  std::map<std::string,std::unique_ptr<Number<double>>> dv;
  for(auto it=expected.begin();it!=expected.end();++it) {
    if(integers.count(it.key())) iv[it.key()]=std::make_unique<Number<int>>(reader,it.key().c_str(),"Int_t");
    else dv[it.key()]=std::make_unique<Number<double>>(reader,it.key().c_str(),"Double_t");
  }
  Require(Next(reader),"Missing config scalars");
  for(auto it=expected.begin();it!=expected.end();++it) {
    const bool integer=integers.count(it.key());
    const double value=integer?double(iv.at(it.key())->get()):dv.at(it.key())->get();
    if(integer) Require(UInt(metadata,it.key(),std::numeric_limits<int>::max())==ULong64_t(iv.at(it.key())->get()),
      "Mismatched integer configuration metadata: "+it.key());
    Require(metadata.at(it.key()).is_number() && std::isfinite(value) && metadata.at(it.key()).get<double>()==value && it.value().get<double>()==value,
      "Unsupported/mismatched selected26 scalar: "+it.key());
  }
  Require(!Next(reader),"Extra config row");
  bool gustep=false,tracking=false;
  for(const auto& source:metadata.at("sources")) {
    if(source.at("path")=="laggen/src/gustep.F") gustep=source.at("sha256")=="e5fb4bb8474ec8f657241b678f1c0661a0a30a7617a8a31136ed64f9141ec660";
    if(source.at("path")=="prean/src/initialisation_cylindres.F") tracking=source.at("sha256")==cylindertracking::configuration_sha256;
  }
  Require(gustep&&tracking,"Wrong source identity in cylinder config");
  auto f=[&](const std::string& key){return Real(expected.at(key).get<double>());};
  auto i=[&](const std::string& key){return expected.at(key).get<int>();};
  legacy_cylinder::Config c;
  c.rc={f("rc1_cm"),f("rc2_cm")};c.zc={f("zc1_cm"),f("zc2_cm")};c.pc={f("pc1_cm"),f("pc2_cm")};
  c.nfc={i("nfc1"),i("nfc2")};c.nb={i("nb1"),i("nb2"),i("nb3"),i("nb4")};
  c.bl=f("bl_cm");c.dfca=f("dfca_cm");c.sccat=f("sccat");c.vsccat=f("vsccat");c.conv=f("conv");c.cythre=f("cythre");
  c.sigce={f("sigce1"),f("sigce2"),f("sigce3"),f("sigce4")};c.sigct=f("sigct");
  c.angle_deg={f("angle1_deg"),f("angle2_deg"),f("angle3_deg"),f("angle4_deg")};c.effcyc={f("effcyc1"),f("effcyc2")};c.nbord=i("nbord");return c;
}
}
int main(int argc,char** argv) {
 try {
  Require(argc==5,"Usage: graal_cylinders INPUT.root CONFIG.root NEW_OUTPUT_DIR SEED");
  const fs::path input=fs::absolute(argv[1]),config_path=fs::absolute(argv[2]),output=fs::absolute(argv[3]);
  const std::string seed_text=argv[4];Require(!seed_text.empty()&&seed_text.find_first_not_of("0123456789")==std::string::npos,"Invalid seed");
  std::size_t used=0;const auto seed=std::stoull(seed_text,&used);Require(used==seed_text.size(),"Invalid seed");
  Require(input.filename().string().find(".partial.")==std::string::npos,"Partial transport rejected");
  const auto input_md5=Digest(input),config_md5=Digest(config_path);auto in=Open(input),cf=Open(config_path);
  UniqueKeys(*in);UniqueKeys(*cf);TransportSchema(*in);TransportStorage storage(*in);const auto summary=Parse(Text(*in,"summary"));
  const auto summary_events=UInt(summary,"events"),attempted_events=UInt(summary,"attempted_events"),
    summary_callbacks=UInt(summary,"all_callbacks"),summary_passive=UInt(summary,"passive_callbacks"),
    summary_hits=UInt(summary,"detector_steps"),summary_context=UInt(summary,"cylinder_context_rows");
  Require(summary.at("status")=="diagnostic_transport_only" &&
    UInt(summary,"aborted",std::numeric_limits<int>::max())==0 && summary_events==attempted_events &&
    UInt(summary,"cylinder_context_schema",std::numeric_limits<int>::max())==1,"Incomplete/schema-incompatible central transport");
  const auto context_metadata=Parse(Text(*in,"cylinder_context_metadata"));
  if(storage.compact()) Require(context_metadata.at("source_index")=="original_sensitive_step","Compact cylinder source identity mismatch");
  Require(UInt(context_metadata,"schema_version",std::numeric_limits<int>::max())==1 && context_metadata.at("scope")=="all_central_sensitive_steps" &&
    context_metadata.at("source_tree")=="detector_steps" && UInt(context_metadata,"source_entry_origin")==0 &&
    UInt(context_metadata,"callback_origin")==0 && context_metadata.at("passive_epoch_origin")=="0_unknown" &&
    context_metadata.at("counter_scope")=="output_stream_across_tracks_events_runs" &&
    context_metadata.at("reset_rule")=="every_callback_with_sensitivity_outside_1_to_14" &&
    context_metadata.at("legacy_source")=="laggen/src/gustep.F" &&
    context_metadata.at("legacy_source_sha256")=="e5fb4bb8474ec8f657241b678f1c0661a0a30a7617a8a31136ed64f9141ec660" &&
    context_metadata.at("physical_validation")==false,"Wrong cylinder context capability/source identity");
  Json config_metadata;const auto config=Configuration(*cf,config_metadata);
  std::map<std::string,Channel> inventory;std::set<std::string> central_volumes;
  const std::map<std::string,int> expected_volumes={{"CYL1",6},{"CYL2",7},{"CYG1",10},{"CYG2",10},{"CYG3",11},{"CYG4",11}};
  static const std::array<const char*,15> roles={"","bgo","barrel","tof_h","tof_v","shower","cyl_surface_1","cyl_surface_2","plane_1","plane_2","cyl_gas_1","cyl_gas_2","disk_1","disk_2","bc448"};
  TTreeReader ir(&Tree(*in,"channels"));String path(ir,"path"),detector(ir,"detector"),volume(ir,"volume"),kind(ir,"channel_kind");
  Number<int> role(ir,"sensitive","Int_t"),copy(ir,"copy","Int_t"),channel(ir,"legacy_channel","Int_t");
  while(Next(ir)) {
    const auto p=path.get(),v=volume.get();const int r=role.get();
    Require(!p.empty() && r>=1&&r<=14 && detector.get()==roles[r],"Invalid channel role/path");
    const auto suffix="/"+v+":"+std::to_string(copy.get());
    Require(p.size()>=suffix.size()&&p.compare(p.size()-suffix.size(),suffix.size(),suffix)==0,"Path/copy inventory mismatch");
    Require(inventory.emplace(p,Channel{r}).second,"Duplicate inventory path");
    if(r==6||r==7||r==10||r==11) {
      const auto found=expected_volumes.find(v);
      Require(found!=expected_volumes.end()&&found->second==r&&copy.get()==1&&channel.get()==1&&
        kind.get()==((r==6||r==7)?"chamber_surface":"gas_volume")&&central_volumes.insert(v).second,"Invalid selected central inventory");
    }
  }
  Require(central_volumes.size()==6,"Incomplete selected central inventory");
  std::vector<Event> events;std::map<Key,std::size_t> event_index;ULong64_t callbacks=0,passive=0,hits=0;
  TTreeReader er(&Tree(*in,"events"));Number<int> ru(er,"run","Int_t"),ev(er,"event","Int_t"),ab(er,"aborted","Int_t");
  Number<double> et(er,"total_edep_MeV","Double_t"),eb(er,"bgo_edep_MeV","Double_t");Number<ULong64_t> es(er,"steps","ULong64_t"),eh(er,"hit_steps","ULong64_t");
  while(Next(er)) {
    const Key key{ru.get(),ev.get()};Require(key.first>=0&&key.second>=0&&ab.get()==0,"Aborted/invalid event");
    Require(events.empty()||Key{events.back().run,events.back().event}<key,"Duplicate/reordered event ledger");
    Nonnegative(et.get(),"event energy");Nonnegative(eb.get(),"event BGO energy");Require(eh.get()<=es.get()&&eb.get()<=et.get()+1e-9,"Invalid event ledger");
    Event e{key.first,key.second,et.get(),eb.get(),es.get(),eh.get(),callbacks,Add(callbacks,es.get()),passive,Add(passive,es.get()-eh.get())};
    event_index.emplace(key,events.size());events.push_back(e);callbacks=e.end;passive=e.passive_end;hits=Add(hits,e.hits);
  }
  Require(summary_events==events.size()&&summary_callbacks==callbacks &&
    summary_passive==passive&&summary_hits==hits&&Add(hits,passive)==callbacks,"Summary/event callback count mismatch");
  TTreeReader xr(&Tree(*in,"cylinder_step_context"));Number<int> xr_run(xr,"run","Int_t"),xr_event(xr,"event","Int_t");
  Number<ULong64_t> xr_source(xr,"source_step_entry","ULong64_t"),xr_callback(xr,"callback_index","ULong64_t"),xr_epoch(xr,"passive_epoch","ULong64_t");
  TTreeReader sr(&Tree(*in,"detector_steps")); SourceEntry source_entry(sr,storage);Number<int> sr_run(sr,"run","Int_t"),sr_event(sr,"event","Int_t"),track(sr,"track","Int_t"),parent(sr,"parent","Int_t"),track_step(sr,"track_step","Int_t"),boundary(sr,"pre_boundary","Int_t"),post_boundary(sr,"post_boundary","Int_t");String step_path(sr,"path");
  Number<double> edep(sr,"edep_MeV","Double_t"),charge(sr,"charge_e","Double_t"),px(sr,"pre_x_mm","Double_t"),py(sr,"pre_y_mm","Double_t"),pz(sr,"pre_z_mm","Double_t"),pretime(sr,"pre_time_ns","Double_t"),posttime(sr,"post_time_ns","Double_t");
  std::vector<std::unique_ptr<Number<double>>> positive_fields,finite_fields;
  for(const char* k:{"track_weight","nonionizing_edep_MeV","step_length_mm","pre_kinetic_MeV","post_kinetic_MeV"}) if(!storage.compact() || sr.GetTree()->GetBranch(k)) positive_fields.push_back(std::make_unique<Number<double>>(sr,k,"Double_t"));
  for(const char* k:{"post_x_mm","post_y_mm","post_z_mm","pre_local_x_mm","pre_local_y_mm","pre_local_z_mm","post_local_x_mm","post_local_y_mm","post_local_z_mm","pre_dir_x","pre_dir_y","pre_dir_z","post_dir_x","post_dir_y","post_dir_z"}) if(!storage.compact() || sr.GetTree()->GetBranch(k)) finite_fields.push_back(std::make_unique<Number<double>>(sr,k,"Double_t"));
  legacy_cylinder::Accumulator accumulator;bool step=Next(sr),context=Next(xr);ULong64_t context_rows=0,source_rows=0;
  for(std::size_t index=0;index<events.size();++index) {
    const auto& e=events[index];accumulator.begin_event(e.run,e.event);ULong64_t count=0;double bgo=storage.omitted_bgo(e.run,e.event),energy=bgo;std::map<int,int> track_steps;
    while(step) {
      const auto found=event_index.find({sr_run.get(),sr_event.get()});Require(found!=event_index.end(),"Orphan detector step");Require(found->second>=index,"Reordered detector event steps");if(found->second!=index) break;
      const auto ch=inventory.find(step_path.get());Require(ch!=inventory.end(),"Unknown detector path");
      Require(track.get()>0&&parent.get()>=0&&track_step.get()>track_steps[track.get()],"Invalid/reordered track steps");track_steps[track.get()]=track_step.get();
      Require((boundary.get()==0||boundary.get()==1)&&(post_boundary.get()==0||post_boundary.get()==1),"Invalid boundary flag");
      Nonnegative(edep.get(),"step energy");Nonnegative(pretime.get(),"pre time");Nonnegative(posttime.get(),"post time");Require(posttime.get()>=pretime.get(),"Time order mismatch");
      for(auto& f:positive_fields) Nonnegative(f->get(),"step magnitude");for(auto& f:finite_fields) Require(std::isfinite(f->get()),"Nonfinite step field");
      for(double v:{charge.get(),px.get(),py.get(),pz.get()}) Require(std::isfinite(v),"Nonfinite step observable");
      energy+=edep.get();Nonnegative(energy,"sensitive sum");if(ch->second.role==1)bgo+=edep.get();
      const auto source=source_entry.get();const int r=ch->second.role;const bool central=r==6||r==7||r==10||r==11;
      if(context) Require(xr_source.get()>=source,"Extra/duplicate/reordered central context");
      if(central) {
        Require(context&&xr_source.get()==source,"Missing central context");
        Require(xr_run.get()==e.run&&xr_event.get()==e.event,"Context event mismatch");
        Require(xr_callback.get()==Add(source,xr_epoch.get())&&xr_callback.get()>=e.begin&&xr_callback.get()<e.end&&
          xr_epoch.get()>=e.passive_begin&&xr_epoch.get()<=e.passive_end,"Context callback/passive ledger mismatch");
        legacy_cylinder::Step s;s.role=r;s.charged=charge.get()!=0;s.entrance=boundary.get()!=0;
        s.xyz_cm={Real(px.get()/10.),Real(py.get()/10.),Real(pz.get()/10.)};s.edep_GeV=Real(edep.get()/1000.);
        s.source_row=source;s.callback_index=xr_callback.get();s.passive_epoch=xr_epoch.get();accumulator.observe(s);++context_rows;context=Next(xr);
      } else Require(!context||xr_source.get()!=source,"Context references noncentral step");
      ++count;++source_rows;step=Next(sr);
    }
    const auto tolerance=[](double a,double b){return 1e-9+1e-10*std::max(std::abs(a),std::abs(b));};
    Require(count==storage.stored(e.run,e.event,e.hits)&&std::abs(bgo-e.bgo)<=tolerance(bgo,e.bgo)&&energy<=e.total+tolerance(energy,e.total),"Event step count/energy ledger mismatch");accumulator.end_event();
  }
  Require(!step&&!context&&source_rows==storage.rows()&&context_rows==summary_context,"Trailing context/step or context count mismatch");accumulator.finish(passive);
  Require(fs::create_directory(output),"Output exists; refusing overwrite");RootOutput out(output,"cylinders");
  auto& ledger=out.Book("cylinder_events",{{"run",0},{"event",0},{"status",std::string{}},{"steps",ULong64_t{0}},{"hit_steps",ULong64_t{0}},{"passive_callbacks",ULong64_t{0}},{"total_edep_MeV",0.},{"bgo_edep_MeV",0.},{"aborted",0},{"raw_inner",ULong64_t{0}},{"raw_outer",ULong64_t{0}},{"retained_inner",ULong64_t{0}},{"retained_outer",ULong64_t{0}},{"input_status",0},{"source_state_known",0},{"legacy_eligible",0},{"response_status",0},{"tracking_unsupported",0},{"tracking_status",0},{"wire_digits",ULong64_t{0}},{"cathode_digits",ULong64_t{0}},{"tracks",ULong64_t{0}},{"normal_draws",ULong64_t{0}},{"efficiency_draws",ULong64_t{0}},{"gas_input_GeV",0.},{"discarded_pending_GeV",0.},{"unsupported_gas_GeV",0.},{"cross_event_assigned_GeV",0.},{"imported_pending_GeV",0.}});
  auto& crossings=out.Book("cylinder_crossings",{{"run",0},{"event",0},{"source_crossing",ULong64_t{0}},{"chamber",0},{"crossing_index",ULong64_t{0}},{"source_step_entry",ULong64_t{0}},{"callback_index",ULong64_t{0}},{"passive_epoch",ULong64_t{0}},{"x_cm",0.},{"y_cm",0.},{"z_cm",0.},{"raw_gas_GeV",0.},{"digitizer_GeV",0.},{"floor_applied",0},{"source_retained",0},{"contribution_count",ULong64_t{0}}});
  auto& gas=out.Book("cylinder_gas_links",{{"run",0},{"event",0},{"chamber",0},{"source_step_entry",ULong64_t{0}},{"callback_index",ULong64_t{0}},{"passive_epoch",ULong64_t{0}},{"energy_GeV",0.},{"disposition",0},{"target_valid",0},{"target_crossing",ULong64_t{0}},{"target_event_index",ULong64_t{0}},{"target_run",0},{"target_event",0}});
  auto& wires=out.Book("cylinder_wires",{{"run",0},{"event",0},{"chamber",0},{"digit_index",ULong64_t{0}},{"wire",0}});
  auto& cathodes=out.Book("cylinder_cathodes",{{"run",0},{"event",0},{"cathode",0},{"digit_index",ULong64_t{0}},{"strip",0},{"adc",0}});
  auto& wire_links=out.Book("cylinder_wire_links",{{"run",0},{"event",0},{"source_crossing",ULong64_t{0}},{"chamber",0},{"wire",0},{"digit_index",0},{"state",0}});
  auto& charge_links=out.Book("cylinder_charge_links",{{"run",0},{"event",0},{"source_crossing",ULong64_t{0}},{"cathode",0},{"strip",0},{"charge",0.}});
  auto& strips=out.Book("cylinder_strip_charges",{{"run",0},{"event",0},{"cathode",0},{"strip",0},{"charge",0.},{"read_flag",0}});
  auto& draws=out.Book("cylinder_normal_draws",{{"run",0},{"event",0},{"draw_index",ULong64_t{0}},{"value",0.}});
  auto& clusters=out.Book("cylinder_clusters",{{"run",0},{"event",0},{"cathode",0},{"cluster_index",ULong64_t{0}},{"multiplicity",0},{"center_cm",0.},{"charge",0.}});
  auto& cluster_links=out.Book("cylinder_cluster_links",{{"run",0},{"event",0},{"cathode",0},{"cluster_index",ULong64_t{0}},{"digit_index",ULong64_t{0}}});
  auto& groups=out.Book("cylinder_wire_groups",{{"run",0},{"event",0},{"chamber",0},{"group_index",ULong64_t{0}},{"digit_index",ULong64_t{0}},{"multiplicity",0},{"phi_deg",0.}});
  auto& associations=out.Book("cylinder_associations",{{"run",0},{"event",0},{"chamber",0},{"association_index",ULong64_t{0}},{"cathode1",0},{"cathode2",0},{"wire_group",0},{"multiplicity1",0},{"multiplicity2",0},{"charge1",0.},{"charge2",0.},{"dz_cm",0.},{"z_cm",0.},{"phi_deg",0.}});
  auto& tracks=out.Book("cylinder_tracks",{{"run",0},{"event",0},{"track_index",ULong64_t{0}},{"inner_association",0},{"outer_association",0},{"inner_x_cm",0.},{"inner_y_cm",0.},{"inner_z_cm",0.},{"outer_x_cm",0.},{"outer_y_cm",0.},{"outer_z_cm",0.},{"dz_inner_cm",0.},{"dz_outer_cm",0.},{"dphi_deg",0.},{"theta_deg",0.},{"phi_deg",0.},{"z_vertex_cm",0.}});
  auto& statuses=out.Book("cylinder_reconstruction_status",{{"run",0},{"event",0},{"stage",std::string{}},{"component",0},{"status",0}});
  Json metadata={{"schema_version",1},{"mode","selected26_old_cyl_diagnostic"},{"physics_validation",false},{"physical_validation",false},{"input_path",input.string()},{"input_md5",input_md5},{"config_path",config_path.string()},{"config_md5",config_md5},{"seed",seed},{"source_access",storage.compact()?"immutable input retains original primaries/truth/weights and compact response inputs; source links use original sensitive indices":"immutable referenced input retains original primaries/truth/weights/raw rows"},{"boundary_convention","G4 pre_boundary and charge!=0; global pre mm/10 -> binary32 cm; edep MeV/1000 -> binary32 GeV once"},{"initialization","safe zero extension; source state unknown until passive epoch; shared SAVE persists across events"},{"tracker_input","wire identifiers and strip ADC only; old_cyl_simulation_config independent geometry"},{"rng","mt19937_64_top52_midpoint_uniform_uncached_BoxMuller_cos_libm_platform_dependent_not_historical_RAND"},{"efficiency_policy","selected26 constants equal1; injected HRNDM returns1; histogram call counts retained"},{"provenance_policy","native MD5 stability; authoritative SHA256 in launcher provenance"},{"gas_disposition",{{"1","assigned"},{"2","discarded_passive"},{"3","unsupported"},{"4","zero"},{"5","unresolved_end"}}},{"indices","chamber/cathode/digit/crossing/cluster/group/track zero based; association references cathode1,cathode2,wire_group and track association fields one based"}};
  out.Metadata("metadata",metadata.dump());out.Metadata("input_summary",summary.dump());out.Metadata("cylinder_context_metadata",context_metadata.dump());out.Metadata("config_metadata",config_metadata.dump());
  if(cf->Get("launcher_provenance"))out.Metadata("launcher_provenance",Text(*cf,"launcher_provenance"));
  for(std::size_t i=0;i<accumulator.crossings().size();++i) {const auto& c=accumulator.crossings()[i];const auto& e=events[c.event_index];
    crossings.Fill({e.run,e.event,ULong64_t(i),c.chamber,ULong64_t(c.crossing_index),ULong64_t(c.source_row),ULong64_t(c.callback_index),ULong64_t(c.passive_epoch),double(c.xyz_cm[0]),double(c.xyz_cm[1]),double(c.xyz_cm[2]),double(c.raw_gas_GeV),double(c.digitizer_GeV),int(c.floor_applied),int(c.source_retained),ULong64_t(c.contribution_count)});}
  for(const auto& l:accumulator.gas_links()) {Require(l.state!=legacy_cylinder::GasState::Pending,"Unresolved gas terminal disposition");const auto& e=events[l.event_index];
    int tr=-1,te=-1;if(l.target_event_index>=0){const auto& t=events.at(std::size_t(l.target_event_index));tr=t.run;te=t.event;}
    gas.Fill({e.run,e.event,l.chamber,ULong64_t(l.source_row),ULong64_t(l.callback_index),ULong64_t(l.passive_epoch),double(l.energy_GeV),int(l.state),int(l.crossing>=0),l.crossing<0?ULong64_t{0}:ULong64_t(l.crossing),l.target_event_index<0?ULong64_t{0}:ULong64_t(l.target_event_index),tr,te});}
  Gaussian gaussian(seed);ULong64_t track_count=0,unsupported_events=0,wire_count=0,cathode_count=0;
  for(std::size_t index=0;index<events.size();++index) {
    const auto& e=events[index];const auto& raw=accumulator.events()[index];legacy_cylinder::DigitResult d;cylindertracking::Reconstruction r;
    int response_status=-1,tracking_unsupported=-1,tracking_status=-1;std::string status="unsupported_input";
    if(raw.legacy_eligible()) {
      std::vector<legacy_cylinder::CrossingInput> hits;
      for(std::size_t i=raw.crossing_begin;i<raw.crossing_end;++i){const auto& c=accumulator.crossings()[i];hits.push_back({c.chamber,c.xyz_cm,c.digitizer_GeV,i});}
      d=legacy_cylinder::digitize(hits,config,[&](){const auto j=gaussian.draws;const float value=gaussian();draws.Fill({e.run,e.event,j,double(value)});return value;},[](int){return 1.f;});response_status=int(d.status);status="unsupported_response";
      if(d.status==0) {
        cylindertracking::Digits digits;digits.wires=d.wires;
        for(int p=0;p<4;++p)for(const auto& digit:d.cathodes[p])digits.cathodes[p].push_back({digit.strip,digit.adc});
        r=cylindertracking::reconstruct(digits,cylindertracking::old_cyl_simulation_config());tracking_unsupported=int(r.unsupported);tracking_status=r.legacy_status;
        status=(r.unsupported||r.legacy_status)?"unsupported_tracking":"diagnostic_complete";
      }
    }
    if(status!="diagnostic_complete"){++unsupported_events;r.tracks.clear();}
    ULong64_t nw=0,nc=0;
    for(int ch=0;ch<2;++ch)for(std::size_t j=0;j<d.wires[ch].size();++j){wires.Fill({e.run,e.event,ch,ULong64_t(j),d.wires[ch][j]});++nw;}
    for(int p=0;p<4;++p)for(std::size_t j=0;j<d.cathodes[p].size();++j){const auto& v=d.cathodes[p][j];cathodes.Fill({e.run,e.event,p,ULong64_t(j),v.strip,v.adc});++nc;}
    for(const auto& a:d.associations)wire_links.Fill({e.run,e.event,ULong64_t(a.source_crossing),a.chamber,a.wire,a.digit_index,int(a.state)});
    for(const auto& a:d.charge_links)charge_links.Fill({e.run,e.event,ULong64_t(a.source_crossing),a.cathode,a.strip,double(a.charge)});
    for(int p=0;p<4;++p)for(std::size_t j=0;j<d.charges[p].size();++j)strips.Fill({e.run,e.event,p,int(j+1),double(d.charges[p][j]),int(d.read_flags[p][j])});
    for(int p=0;p<4;++p){statuses.Fill({e.run,e.event,std::string("cathode"),p,r.cathode_status[p]});for(std::size_t j=0;j<r.clusters[p].size();++j){const auto& v=r.clusters[p][j];clusters.Fill({e.run,e.event,p,ULong64_t(j),v.multiplicity,double(v.center_cm),double(v.charge)});for(auto digit:v.digit_indices)cluster_links.Fill({e.run,e.event,p,ULong64_t(j),ULong64_t(digit)});}}
    for(int ch=0;ch<2;++ch){statuses.Fill({e.run,e.event,std::string("wire"),ch,r.wire_status[ch]});statuses.Fill({e.run,e.event,std::string("association"),ch,r.association_status[ch]});
      for(std::size_t j=0;j<r.groups[ch].size();++j){const auto& v=r.groups[ch][j];groups.Fill({e.run,e.event,ch,ULong64_t(j),ULong64_t(v.digit_index),v.multiplicity,double(v.phi_deg)});}
      for(std::size_t j=0;j<r.associations[ch].size();++j){const auto& v=r.associations[ch][j];associations.Fill({e.run,e.event,ch,ULong64_t(j),v.cathode1,v.cathode2,v.wire_group,v.multiplicity1,v.multiplicity2,double(v.charge1),double(v.charge2),double(v.dz_cm),double(v.z_cm),double(v.phi_deg)});}}
    statuses.Fill({e.run,e.event,std::string("track"),0,r.track_status});
    for(std::size_t j=0;j<r.tracks.size();++j){const auto& v=r.tracks[j];tracks.Fill({e.run,e.event,ULong64_t(j),v.inner_association,v.outer_association,double(v.inner_cm[0]),double(v.inner_cm[1]),double(v.inner_cm[2]),double(v.outer_cm[0]),double(v.outer_cm[1]),double(v.outer_cm[2]),double(v.dz_inner_cm),double(v.dz_outer_cm),double(v.dphi_deg),double(v.theta_deg),double(v.phi_deg),double(v.z_vertex_cm)});}
    ledger.Fill({e.run,e.event,status,e.steps,e.hits,e.steps-e.hits,e.total,e.bgo,0,ULong64_t(raw.raw_counts[0]),ULong64_t(raw.raw_counts[1]),ULong64_t(raw.retained_counts[0]),ULong64_t(raw.retained_counts[1]),int(raw.status),int(raw.source_state_known),int(raw.legacy_eligible()),response_status,tracking_unsupported,tracking_status,nw,nc,ULong64_t(r.tracks.size()),ULong64_t(d.normal_draws),ULong64_t(d.efficiency_histograms.size()),raw.gas_input_GeV,raw.discarded_pending_GeV,raw.unsupported_gas_GeV,raw.cross_event_assigned_GeV,raw.imported_pending_GeV});
    track_count+=r.tracks.size();wire_count+=nw;cathode_count+=nc;
  }
  Require(Digest(input)==input_md5&&Digest(config_path)==config_md5,"Input/config changed during cylinder reconstruction");
  const Json result={{"status","selected26_old_cyl_diagnostic_complete"},{"schema_version",1},{"events",events.size()},{"unsupported_events",unsupported_events},{"crossings",accumulator.crossings().size()},{"gas_links",accumulator.gas_links().size()},{"wire_digits",wire_count},{"cathode_digits",cathode_count},{"tracks",track_count},{"normal_draws",gaussian.draws},{"physics_validation",false},{"physical_validation",false},{"output_format","ROOT_TTree"}};
  out.Finish(result.dump());std::cout<<"DIAGNOSTIC_CYLINDERS_COMPLETE "<<result.dump()<<'\n';return 0;
 }catch(const std::exception& error){std::cerr<<"ERROR: "<<error.what()<<'\n';return 1;}
}
