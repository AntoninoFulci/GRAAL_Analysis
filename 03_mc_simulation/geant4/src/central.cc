// Measured BGO/barrel/cylinder composition. Runtime PREAN state is explicit.
#include "BgoCellular.hh"
#include "BgoMeasurements.hh"
#include "CentralAssociation.hh"
#include "TransportStorage.hh"
#include "nlohmann/json.hpp"
#include "TKey.h"
#include <map>
#include <random>
#include <set>

using namespace rootinput;
using Json = nlohmann::json;
using Key = std::pair<int,int>;
namespace {
Json Parse(const std::string& text) {
  std::vector<std::set<std::string>> keys;
  return Json::parse(text,[&](int,Json::parse_event_t event,Json& value) {
    if(event==Json::parse_event_t::object_start) keys.emplace_back();
    if(event==Json::parse_event_t::key)
      Require(keys.back().insert(value.get<std::string>()).second,"Duplicate JSON key");
    if(event==Json::parse_event_t::object_end) keys.pop_back();
    return true;
  });
}
ULong64_t UInt(const Json& object,const std::string& key,
               ULong64_t maximum=std::numeric_limits<ULong64_t>::max()) {
  const auto& value=object.at(key);
  Require(value.is_number_integer(),"Expected JSON integer: "+key);
  if(!value.is_number_unsigned())
    Require(value.get<Json::number_integer_t>()>=0,"Negative JSON integer: "+key);
  auto result=value.get<Json::number_unsigned_t>();
  Require(result<=maximum,"JSON integer outside range: "+key);
  return result;
}
void Unique(TFile& file) {
  std::set<std::string> names; TIter next(file.GetListOfKeys());
  while(auto* key=next()) Require(names.insert(key->GetName()).second,"Duplicate ROOT key/cycle");
}
std::string TextSafe(TFile& file,const char* name) {
  auto result=Text(file,name); auto* raw=dynamic_cast<TObjString*>(file.Get(name));
  Require(raw && std::size_t(raw->GetString().Length())==result.size(),"Embedded NUL metadata");
  return result;
}
bool Hash(const Json& value) {
  if(!value.is_string()) return false;
  auto hash=value.get<std::string>();
  return hash.size()==64 && hash.find_first_not_of("0123456789abcdef")==std::string::npos;
}
ULong64_t Add(ULong64_t a,ULong64_t b) {
  Require(b<=std::numeric_limits<ULong64_t>::max()-a,"Ledger count overflow");return a+b;
}
struct Configuration {
  bgomeasurements::Config bgo;
  bgomeasurements::BarrelConfig barrel;
  bgo26::CellularConfig cellular;
  centralassociation::Config association;
};
Configuration ReadConfiguration(TFile& file,Json& metadata) {
  metadata=Parse(TextSafe(file,"metadata"));
  Require(UInt(metadata,"schema",100)==1 &&
      metadata.at("mode")=="selected26_central_reconstruction_diagnostic" &&
      metadata.at("physical_validation")==false && metadata.at("physics_validation")==false &&
      metadata.at("simulation")==true && metadata.at("digit_decode_profile")=="legacy09" &&
      metadata.at("geometry_profile")=="selected26","Wrong central configuration profile");
  auto claim=metadata.at("initialization_claim").get<std::string>();
  Require(!claim.empty() && claim.find('\0')==std::string::npos,"Explicit initialized PREAN state required");
  Require(metadata.at("units")==Json{{"bgo_energy","GeV"},{"barrel_energy","MeV"},
      {"barrel_time","ns"},{"angles","degree"}},"Wrong central measurement units");
  std::set<std::string> paths;
  Require(metadata.at("sources").is_array() && !metadata.at("sources").empty(),"Missing original sources");
  for(const auto& source:metadata.at("sources")) {
    auto path=source.at("path").get<std::string>();
    Require(!path.empty() && path.find('\0')==std::string::npos &&
        paths.insert(path).second && Hash(source.at("sha256")),"Malformed source identity");
  }
  Configuration c;
  TTreeReader reader(&Tree(file,"scalars"));
  std::map<std::string,float*> fields={
    {"crystal_threshold",&c.bgo.crystal_threshold},{"cluster_threshold",&c.bgo.cluster_threshold},
    {"bgo_adc_channels",&c.bgo.bgo_adc_channels},{"bgo_adc_fullscale_gev",&c.bgo.bgo_adc_fullscale_gev},
    {"barrel_adc_channels",&c.barrel.adc_channels},{"barrel_adc_fullscale_gev",&c.barrel.adc_fullscale_gev},
    {"barrel_tdc_channels",&c.barrel.tdc_channels},{"barrel_tdc_fullscale_seconds",&c.barrel.tdc_fullscale_seconds},
    {"barrel_energy_threshold_mev",&c.barrel.energy_threshold_mev},
    {"ca_rcnt",&c.cellular.rcnt},{"ca_tde",&c.cellular.tde}};
  Require(reader.GetTree()->GetEntries()==1 &&
      reader.GetTree()->GetListOfBranches()->GetEntries()==int(fields.size()+1),"Scalar inventory mismatch");
  std::map<std::string,std::unique_ptr<Number<float>>> values;
  for(const auto& p:fields) values[p.first]=std::make_unique<Number<float>>(reader,p.first.c_str(),"Float_t");
  Number<bool> sp(reader,"enable_sp","Bool_t");
  Require(Next(reader),"Missing central scalars");
  for(const auto& p:fields) {
    float value=values.at(p.first)->get();const auto& recorded=metadata.at("scalars").at(p.first);
    Require(std::isfinite(value) && recorded.is_number() && recorded.get<double>()==value,
        "Config scalar metadata mismatch: "+p.first);*p.second=value;
  }
  Require(metadata.at("scalars").at("enable_sp").is_boolean() &&
      metadata.at("scalars").at("enable_sp").get<bool>()==sp.get(),"Config SP flag mismatch");
  c.bgo.enable_sp=c.association.enable_bgo_sp=sp.get();Require(!Next(reader),"Extra config scalars");
  // Indexed tables are read separately because JSON arrays use positional keys.
  auto indexed=[&](const char* name,int count,int origin,const std::map<std::string,float*>& targets) {
    auto& tree=Tree(file,name);
    Require(tree.GetEntries()==count && tree.GetListOfBranches()->GetEntries()==int(targets.size()+1),"Config table inventory mismatch");
    TTreeReader r(&tree);Number<int> index(r,"index","Int_t");
    std::map<std::string,std::unique_ptr<Number<float>>> columns;
    const auto& j=metadata.at(name);
    Require(j.at("index").is_array() && j.at("index").size()==std::size_t(count),"Config index metadata size");
    for(const auto& p:targets) {
      columns[p.first]=std::make_unique<Number<float>>(r,p.first.c_str(),"Float_t");
      Require(j.at(p.first).is_array() && j.at(p.first).size()==std::size_t(count),"Config table metadata size");
    }
    int row=0;
    while(Next(r)) {
      Require(index.get()==row+origin && UInt(Json{{"index",j.at("index").at(row)}},"index",480)==ULong64_t(row+origin),"Config index mismatch");
      for(const auto& p:targets) {
        float value=columns.at(p.first)->get();const auto& recorded=j.at(p.first).at(row);
        Require(std::isfinite(value) && recorded.is_number() && recorded.get<double>()==value,"Config table metadata mismatch");
        p.second[row]=value;
      }
      ++row;
    }
  };
  indexed("theta",15,1,{{"theta",c.bgo.theta.data()},{"volume",c.bgo.volume.data()}});
  indexed("phi",32,1,{{"phi",c.bgo.phi.data()},{"xba1",c.association.xba1.data()}});
  indexed("corrections",96,0,{{"a",c.bgo.correction_a.data()},{"b",c.bgo.correction_b.data()}});
  c.cellular.theta_deg=c.bgo.theta;c.cellular.phi_deg=c.bgo.phi;c.cellular.volume=c.bgo.volume;
  c.association.phi_deg=c.bgo.phi;
  auto grid=bgomeasurements::decode_bgo_digits({},c.bgo);
  Require(!grid.status && !bgomeasurements::measure(grid,{}, {},c.bgo).status &&
      !bgomeasurements::decode_barrel({},c.barrel).status,"Invalid initialized central measurement configuration");
  return c;
}
struct Event {
  int run{},event{};double total{},bgo{};ULong64_t steps{},hits{};
  int nbgo{},nbarrel{},ncylinder{};bool barrel_available{},cylinder_available{};
  std::vector<bgomeasurements::BgoDigit> bgo_digits;
  std::vector<bgomeasurements::BarrelDigit> barrel_digits;
  std::vector<centralassociation::CylinderTrack> tracks;
};
Json Product(TFile& file,const char* mode,const char* completion,const std::string& transport_md5,
             ULong64_t events) {
  auto metadata=Parse(TextSafe(file,"metadata")),summary=Parse(TextSafe(file,"summary"));
  Require(metadata.at("mode")==mode && UInt(metadata,"schema_version",100)==1 &&
      metadata.at("physics_validation")==false && metadata.at("input_md5")==transport_md5 &&
      summary.at("status")==completion && UInt(summary,"schema_version",100)==1 &&
      UInt(summary,"events")==events && summary.at("physics_validation")==false,
      "Measured product profile/source/completeness mismatch");
  auto launch=Parse(TextSafe(file,"launcher_provenance"));
  Require(launch.at("mode")==mode && Hash(launch.at("input_sha256")) &&
      Hash(launch.at("executable_sha256")) && launch.at("physics_validation")==false,
      "Measured product missing launcher provenance");
  return metadata;
}
}
int main(int argc,char** argv) {try {
  Require(argc==7,"Usage: graal_central TRANSPORT.root RESPONSE.root CYLINDERS.root CONFIG.root NEW_OUTPUT_DIR SEED");
  fs::path transport=fs::absolute(argv[1]),response=fs::absolute(argv[2]),cylinders=fs::absolute(argv[3]),
      config=fs::absolute(argv[4]),output=fs::absolute(argv[5]);
  std::string seedtext=argv[6];Require(!seedtext.empty() && seedtext.find_first_not_of("0123456789")==std::string::npos,"Invalid seed");
  std::size_t consumed=0;auto seed=std::stoull(seedtext,&consumed);Require(consumed==seedtext.size(),"Invalid seed");
  std::map<fs::path,std::string> hashes;
  for(const auto& path:{transport,response,cylinders,config}) {
    Require(path.filename().string().find(".partial")==std::string::npos,"Partial input rejected");hashes[path]=Digest(path);
  }
  auto input=Open(transport),rp=Open(response),cp=Open(cylinders),cf=Open(config);
  for(auto* file:{input.get(),rp.get(),cp.get(),cf.get()}) Unique(*file);
  TransportSchema(*input);TransportStorage storage(*input);auto source_summary=Parse(TextSafe(*input,"summary"));
  Require(source_summary.at("status")=="diagnostic_transport_only" &&
      UInt(source_summary,"aborted",1)==0 && UInt(source_summary,"events")==UInt(source_summary,"attempted_events"),"Incomplete transport");
  std::vector<Event> events;std::map<Key,std::size_t> event_index;ULong64_t steps=0,hits=0;
  TTreeReader er(&Tree(*input,"events"));Number<int> run(er,"run","Int_t"),event(er,"event","Int_t"),abort(er,"aborted","Int_t");
  Number<double> total(er,"total_edep_MeV","Double_t"),bgoenergy(er,"bgo_edep_MeV","Double_t");
  Number<ULong64_t> callback(er,"steps","ULong64_t"),sensitive(er,"hit_steps","ULong64_t");
  while(Next(er)) {
    Key key{run.get(),event.get()};
    Require(key.first>=0 && key.second>=0 && abort.get()==0 &&
        (events.empty() || Key{events.back().run,events.back().event}<key),"Invalid/reordered source event");
    Nonnegative(total.get(),"event energy");Nonnegative(bgoenergy.get(),"event BGO energy");
    Require(sensitive.get()<=callback.get() && bgoenergy.get()<=total.get()+1e-9,"Invalid source event ledger");
    Event e;e.run=key.first;e.event=key.second;e.total=total.get();e.bgo=bgoenergy.get();e.steps=callback.get();e.hits=sensitive.get();
    event_index[key]=events.size();events.push_back(e);steps=Add(steps,e.steps);hits=Add(hits,e.hits);
  }
  Require(UInt(source_summary,"events")==events.size() && UInt(source_summary,"all_callbacks")==steps &&
      UInt(source_summary,"detector_steps")==hits && UInt(source_summary,"passive_callbacks")==steps-hits,"Source ledger summary mismatch");
  auto rm=Product(*rp,"legacy09_diagnostic","legacy09_diagnostic_complete",hashes[transport],events.size());
  auto cm=Product(*cp,"selected26_old_cyl_diagnostic","selected26_old_cyl_diagnostic_complete",hashes[transport],events.size());
  auto rl=Parse(TextSafe(*rp,"launcher_provenance")),cl=Parse(TextSafe(*cp,"launcher_provenance"));
  Require(rl.at("input_sha256")==cl.at("input_sha256"),"Measured products reference different transport SHA256");
  Json configuration_metadata;auto c=ReadConfiguration(*cf,configuration_metadata);
  // Physical G4/legacy digit IDs are theta-major (32 phi copies per ring).
  // EDEPTH is theta-fast internally; that memory layout is not a channel ID.
  const auto producer_configuration=Parse(TextSafe(*rp,"config_metadata"));
  const std::map<std::string,float> decoding_scales={
    {"scbgo",c.bgo.bgo_adc_channels},{"vscbgo_GeV",c.bgo.bgo_adc_fullscale_gev},
    {"scdeb",c.barrel.adc_channels},{"vscdeb_GeV",c.barrel.adc_fullscale_gev},
    {"sdetof",c.barrel.tdc_channels},{"vdetof_s",c.barrel.tdc_fullscale_seconds}};
  for(const auto& scale:decoding_scales) {
    const auto& actual=producer_configuration.at(scale.first);
    Require(actual.is_number() && Real(actual.get<double>())==scale.second,
        "Applied producer decode scale mismatch: "+scale.first);
  }
  auto ledger=[&](TFile& file,const char* name,bool cylinder) {
    TTreeReader r(&Tree(file,name));Number<int> u(r,"run","Int_t"),v(r,"event","Int_t"),ab(r,"aborted","Int_t");
    String status(r,"status");Number<double> t(r,"total_edep_MeV","Double_t"),b(r,"bgo_edep_MeV","Double_t");
    Number<ULong64_t> st(r,"steps","ULong64_t"),hi(r,"hit_steps","ULong64_t");
    std::unique_ptr<Number<int>> nb,nd,is,rs,tu,ts;
    std::unique_ptr<Number<ULong64_t>> nt;
    if(cylinder) {
      nt=std::make_unique<Number<ULong64_t>>(r,"tracks","ULong64_t");
      is=std::make_unique<Number<int>>(r,"input_status","Int_t");rs=std::make_unique<Number<int>>(r,"response_status","Int_t");
      tu=std::make_unique<Number<int>>(r,"tracking_unsupported","Int_t");ts=std::make_unique<Number<int>>(r,"tracking_status","Int_t");
    } else {
      nb=std::make_unique<Number<int>>(r,"bgo_digits","Int_t");nd=std::make_unique<Number<int>>(r,"barrel_digits","Int_t");
    }
    for(auto& e:events) {
      Require(Next(r) && u.get()==e.run && v.get()==e.event && ab.get()==0 &&
          t.get()==e.total && b.get()==e.bgo && st.get()==e.steps && hi.get()==e.hits,"Measured event ledger mismatch");
      if(cylinder) {
        Require(is->get()>=0 && is->get()<=63 && rs->get()>=-1 && tu->get()>=-1 && ts->get()>=-1 && nt->get()<=5,"Invalid cylinder status/count");
        e.cylinder_available=is->get()==0 && rs->get()==0 && tu->get()==0 && ts->get()==0;
        e.ncylinder=int(nt->get());
        Require((status.get()=="diagnostic_complete")==e.cylinder_available &&
            (e.cylinder_available || e.ncylinder==0),"Cylinder availability mismatch");
      } else {
        e.nbgo=nb->get();e.nbarrel=nd->get();
        Require(e.nbgo>=0 && e.nbgo<=480 && e.nbarrel>=0 && e.nbarrel<=32,"Invalid response digit count");
        auto s=status.get();Require(s=="diagnostic_only" || s=="unsupported_barrel_record_overflow","Unknown response status");
        e.barrel_available=s=="diagnostic_only";
        Require(e.barrel_available || e.nbarrel==0,"Unavailable barrel has digits");
      }
    }
    Require(!Next(r),"Extra measured event");
  };
  ledger(*rp,"response_events",false);ledger(*cp,"cylinder_events",true);
  auto digits=[&](bool barrel) {
    TTreeReader r(&Tree(*rp,barrel?"barrel_digits":"bgo_digits"));
    Number<int> u(r,"run","Int_t"),v(r,"event","Int_t"),channel(r,"channel","Int_t"),adc(r,"adc","Int_t");
    std::unique_ptr<Number<int>> tdc;if(barrel) tdc=std::make_unique<Number<int>>(r,"tdc","Int_t");
    std::size_t previous=0;std::vector<std::set<int>> seen(events.size());
    while(Next(r)) {
      auto it=event_index.find({u.get(),v.get()});Require(it!=event_index.end() && it->second>=previous,"Orphan/reordered measured digit");previous=it->second;
      auto& e=events[previous];int ch=channel.get(),a=adc.get();
      Require(ch>=1 && ch<=(barrel?32:480) && a>=0 && a<=int(barrel?c.barrel.adc_channels:c.bgo.bgo_adc_channels) && seen[previous].insert(ch).second,"Invalid/duplicate measured digit");
      if(barrel) {
        Require(tdc->get()>=0 && tdc->get()<=int(c.barrel.tdc_channels) && e.barrel_digits.size()<std::size_t(e.nbarrel),"Invalid barrel digit/count");
        e.barrel_digits.push_back({ch,a,tdc->get()});
      } else {
        Require(e.bgo_digits.size()<std::size_t(e.nbgo),"BGO digit count mismatch");
        e.bgo_digits.push_back({1+(ch-1)/32,1+(ch-1)%32,a});
      }
    }
    for(const auto& e:events) Require((barrel?e.barrel_digits.size():e.bgo_digits.size())==std::size_t(barrel?e.nbarrel:e.nbgo),"Missing measured digit");
  };
  digits(false);digits(true);
  TTreeReader tr(&Tree(*cp,"cylinder_tracks"));Number<int> tu(tr,"run","Int_t"),tv(tr,"event","Int_t");
  Number<ULong64_t> ti(tr,"track_index","ULong64_t");Number<double> th(tr,"theta_deg","Double_t"),ph(tr,"phi_deg","Double_t");
  std::size_t previous=0;ULong64_t cylinder_count=0;
  while(Next(tr)) {
    auto it=event_index.find({tu.get(),tv.get()});Require(it!=event_index.end() && it->second>=previous,"Orphan/reordered cylinder track");previous=it->second;auto& e=events[previous];
    Require(e.cylinder_available && ti.get()==e.tracks.size() && e.tracks.size()<std::size_t(e.ncylinder),"Cylinder track index/count/status mismatch");
    float theta=Real(th.get()),phi=Real(ph.get());Require(theta>=0 && theta<=180,"Invalid cylinder direction");
    e.tracks.push_back({theta,phi});++cylinder_count;
  }
  for(const auto& e:events) Require(e.tracks.size()==std::size_t(e.ncylinder),"Missing measured cylinder track");
  Require(UInt(Parse(TextSafe(*cp,"summary")),"tracks")==cylinder_count,"Cylinder summary count mismatch");
  Require(fs::create_directory(output),"Output exists; refusing overwrite");RootOutput out(output,"central");
  auto& events_out=out.Book("central_events",{{"run",0},{"event",0},{"source_entry",ULong64_t{0}},{"status",std::string{}},
      {"barrel_input_available",0},{"cylinder_input_available",0},{"grid_status",0},{"ca_status",0},{"ca_source_nero",0},{"ca_called",0},
      {"bgo_status",0},{"bgo_measurements_available",0},{"barrel_status",0},{"association_available",0},{"association_status",0},
      {"bgo_digits",0},{"accepted_bgo_digits",0},{"ca_clusters",0},{"good_bgo",0},{"sp_bgo",0},{"barrel_records",0},{"cylinder_tracks",0},{"associations",0},{"uniform_draws",ULong64_t{0}}});
  auto& grid_out=out.Book("central_bgo_grid",{{"run",0},{"event",0},{"channel",0},{"digit_index",0},{"theta",0},{"phi",0},{"adc",0},{"energy_GeV",0.},{"problem",0}});
  auto& membership=out.Book("central_ca_members",{{"run",0},{"event",0},{"cluster_index",0},{"member_index",0},{"crystal_id",0},{"channel",0},{"digit_index",0}});
  auto& cluster_out=out.Book("central_bgo_clusters",{{"run",0},{"event",0},{"kind",0},{"object_index",0},{"source_cluster",0},{"multiplicity",0},{"problem_index",0},{"flag",0},{"status",0},
      {"raw_energy_GeV",0.},{"theta_deg",0.},{"phi_deg",0.},{"corrected_energy_GeV",0.},{"corrected_theta_deg",0.},{"corrected_phi_deg",0.},{"maximum_energy_GeV",0.},{"new_shape_available",0},{"old_shape_available",0},{"sx1",0.},{"sy1",0.},{"sx2",0.},{"sy2",0.}});
  auto& slots=out.Book("central_bgo_problem_slots",{{"run",0},{"event",0},{"slot",0},{"problem_index",0}});
  auto& barrel_out=out.Book("central_barrel",{{"run",0},{"event",0},{"object_index",0},{"digit_index",0},{"channel",0},{"problem_index",0},{"energy_MeV",0.},{"time_ns",0.}});
  auto& object_links=out.Book("central_object_links",{{"run",0},{"event",0},{"kind",0},{"object_index",0},{"source_index",0}});
  auto& pairs=out.Book("central_stage2",{{"run",0},{"event",0},{"pair_index",0},{"bgo",0},{"cylinder",0}});
  auto& associations=out.Book("central_associations",{{"run",0},{"event",0},{"association_index",0},{"bgo",0},{"barrel",0},{"cylinder",0},{"type",0},{"barrel_channel",0},{"barrel_problem_index",0},
      {"dedx_MeV",0.},{"barrel_time_ns",0.},{"barrel_phi_deg",0.},{"bgo_energy_GeV",0.},{"bgo_theta_deg",0.},{"bgo_phi_deg",0.},{"cylinder_theta_deg",0.},{"cylinder_phi_deg",0.},{"theta_deg",0.},{"phi_deg",0.}});
  auto& rng_out=out.Book("central_uniform_draws",{{"run",0},{"event",0},{"draw_index",ULong64_t{0}},{"value",0.}});
  auto& status_out=out.Book("central_status",{{"run",0},{"event",0},{"stage",std::string{}},{"status",0},{"reason",std::string{}}});
  std::mt19937_64 rng(seed);ULong64_t draws=0,total_associations=0,unsupported=0,source_rejected=0;
  for(std::size_t row=0;row<events.size();++row) {
    const auto& e=events[row];auto grid=bgomeasurements::decode_bgo_digits(e.bgo_digits,c.bgo);
    auto barrel=bgomeasurements::decode_barrel(e.barrel_digits,c.barrel);
    std::vector<int> barrel_channels;for(const auto& d:e.barrel_digits) barrel_channels.push_back(d.channel);
    auto uniform=[&]() {float value=(float(rng()>>41)+.5f)*0x1p-23f;rng_out.Fill({e.run,e.event,draws,double(value)});++draws;return value;};
    bgo26::CellularResult ca;bool called=grid.status==0 && grid.accepted_digits>0;
    if(called) ca=bgo26::ClusterCellular(grid.energy,c.cellular,uniform);
    bgomeasurements::Result measured;
    bool ca_available=grid.status==0 && ca.status==bgo26::CellularStatus::Valid;
    bool measurement_available=ca_available && e.barrel_available;
    if(measurement_available) measured=bgomeasurements::measure(grid,ca.clusters,barrel_channels,c.bgo,ca.source_nero);
    bool bgo_available=measurement_available && (measured.status&~bgomeasurements::UndefinedOldShape)==0;
    centralassociation::Input association_input;association_input.cylinder=e.tracks;
    if(bgo_available) {
      for(const auto& h:measured.good) association_input.good_bgo.push_back({h.corrected_theta,h.corrected_phi,h.corrected_theta,h.corrected_phi,h.corrected_energy});
      for(const auto& h:measured.sp) association_input.sp_bgo.push_back({h.corrected_theta,h.corrected_phi,h.theta,h.phi,h.raw_energy});
    }
    if(e.barrel_available && !barrel.status) for(const auto& h:barrel.records)
      association_input.barrel.push_back({h.channel,h.problem_index,h.energy,h.time});
    bool association_available=bgo_available && e.barrel_available && !barrel.status && e.cylinder_available;
    centralassociation::Result result;
    if(association_available) result=centralassociation::find_track_cbb(association_input,c.association);
    int association_status=association_available?int(result.status):-1;
    bool valid=association_available && result.status==0;
    if(!valid) ++unsupported;if(ca.source_nero) ++source_rejected;
    std::map<int,int> channel_digit;
    for(std::size_t k=0;k<e.bgo_digits.size();++k) {
      const auto& d=e.bgo_digits[k];int channel=32*(d.theta-1)+d.phi,offset=bgomeasurements::index(d.theta,d.phi);channel_digit[channel]=int(k);
      grid_out.Fill({e.run,e.event,channel,int(k),d.theta,d.phi,d.adc,double(grid.energy[offset]),grid.problem[offset]});
    }
    for(std::size_t k=0;k<ca.clusters.size();++k) for(std::size_t j=0;j<ca.clusters[k].size();++j) {
      int id=ca.clusters[k][j],channel=32*(id/100-1)+id%100;auto found=channel_digit.find(channel);
      Require(found!=channel_digit.end(),"CA member has no measured digit");
      membership.Fill({e.run,e.event,int(k),int(j),id,channel,found->second});
    }
    for(int kind=0;kind<2;++kind) {
      const auto& clusters=kind?measured.sp:measured.good;
      for(std::size_t k=0;k<clusters.size();++k) {
        const auto& h=clusters[k];bool old_shape=kind==0 && (h.status&bgomeasurements::UndefinedOldShape)==0;
        Require(h.source_cluster>=1 && std::size_t(h.source_cluster)<=ca.clusters.size(),"Bad measured source cluster");
        cluster_out.Fill({e.run,e.event,kind,int(k),h.source_cluster,h.multiplicity,h.problem_index,h.flag,int(h.status),double(h.raw_energy),double(h.theta),double(h.phi),double(h.corrected_energy),double(h.corrected_theta),double(h.corrected_phi),double(h.maximum_energy),int(kind==0),int(old_shape),double(h.sx1),double(h.sy1),double(h.sx2),double(h.sy2)});
        object_links.Fill({e.run,e.event,kind,int(k),h.source_cluster});
      }
    }
    for(int k=0;k<30;++k) slots.Fill({e.run,e.event,k,measured.problem_slots[k]});
    for(std::size_t k=0;k<barrel.records.size();++k) {
      const auto& h=barrel.records[k];barrel_out.Fill({e.run,e.event,int(k),int(k),h.channel,h.problem_index,double(h.energy),double(h.time)});
      object_links.Fill({e.run,e.event,2,int(k),int(k)});
    }
    for(std::size_t k=0;k<e.tracks.size();++k) object_links.Fill({e.run,e.event,3,int(k),int(k)});
    for(std::size_t k=0;k<result.stage2.size();++k) pairs.Fill({e.run,e.event,int(k),result.stage2[k].bgo,result.stage2[k].cylinder});
    for(std::size_t k=0;k<result.associations.size();++k) {
      const auto& a=result.associations[k];
      Require(a.bgo>=0 && std::size_t(a.bgo)<=measured.good.size()+measured.sp.size() && a.barrel>=0 &&
          std::size_t(a.barrel)<=barrel.records.size() && a.cylinder>=0 && std::size_t(a.cylinder)<=e.tracks.size(),"Bad association source pointer");
      associations.Fill({e.run,e.event,int(k),a.bgo,a.barrel,a.cylinder,a.type,a.barrel_channel,a.barrel_problem_index,double(a.dedx),double(a.barrel_time),double(a.barrel_phi_deg),double(a.bgo_energy),double(a.bgo_theta_deg),double(a.bgo_phi_deg),double(a.cylinder_theta_deg),double(a.cylinder_phi_deg),double(a.theta_deg),double(a.phi_deg)});
    }
    status_out.Fill({e.run,e.event,std::string("cellular"),int(ca.status),ca.reason});
    status_out.Fill({e.run,e.event,std::string("bgo"),measurement_available?int(measured.status):-1,std::string(measurement_available?"":"CA or barrel input unavailable")});
    status_out.Fill({e.run,e.event,std::string("association"),association_status,std::string(association_available?"":"measured dependency unavailable")});
    std::string status=valid?(ca.source_nero?"diagnostic_ca_rejected":result.associations.empty()?"diagnostic_no_object":"diagnostic_objects"):"unsupported_central";
    events_out.Fill({e.run,e.event,ULong64_t(row),status,int(e.barrel_available),int(e.cylinder_available),int(grid.status),int(ca.status),ca.source_nero,int(called),measurement_available?int(measured.status):-1,int(bgo_available),int(barrel.status),int(association_available),association_status,e.nbgo,grid.accepted_digits,int(ca.clusters.size()),int(measured.good.size()),int(measured.sp.size()),int(barrel.records.size()),int(e.tracks.size()),int(result.associations.size()),ULong64_t(ca.draws)});
    total_associations+=result.associations.size();
  }
  Json metadata={{"schema_version",1},{"mode","selected26_central_reconstruction_diagnostic"},{"physical_validation",false},{"physics_validation",false},
      {"transport_path",transport.string()},{"response_path",response.string()},{"cylinders_path",cylinders.string()},{"config_path",config.string()},
      {"transport_md5",hashes[transport]},{"response_md5",hashes[response]},{"cylinders_md5",hashes[cylinders]},{"config_md5",hashes[config]},
      {"seed",seed},{"uniform_policy","mt19937_64 top23 midpoint binary32 uniforms, diagnostic stream; draw before source scan order"},
      {"initialization_policy","caller explicitly supplies initialized STHRES/CTHRES/barrel threshold,CA RCNT/TDE,XBA1; unavailable historical INIT_CA ordering not inferred"},
      {"profiles","legacy09 ADC/TDC decoding; selected26 geometry; explicit initialized reconstruction config, no historical run parity"},
      {"units",{{"bgo_energy","GeV"},{"barrel_energy","MeV"},{"barrel_time","ns"},{"angles","degree"}}},
      {"index_policy","all rows/digit/member/object indices zero-based; source_cluster one-based; association BGO=good then SP one-based,barrel/cylinder one-based,0 absent; CA crystal100*theta+phi; physical BGO channel32*(theta-1)+phi; internal EDEPTH offsettheta-1+15*(phi-1)"},
      {"shape_policy","Only good BGO computes shapes: new_shape_available1; UndefinedOldShape=16 nonfatal with old_shape_available0 and NaN sx1/sy1; SP shape availability0; usable energies/directions retained"},
      {"nohit_policy","ANABGO no accepted digits bypasses CA,source_nero0; direct CA empty rejection is not invoked"},
      {"limitations","explicit initialized reconstruction configuration; no historical runtime equivalence claimed; no truth/four-vectors/selection"}};
  out.Metadata("metadata",metadata.dump());out.Metadata("config_metadata",configuration_metadata.dump());
  out.Metadata("response_metadata",rm.dump());out.Metadata("cylinders_metadata",cm.dump());
  out.Metadata("response_launcher_provenance",TextSafe(*rp,"launcher_provenance"));out.Metadata("cylinders_launcher_provenance",TextSafe(*cp,"launcher_provenance"));
  for(const auto& p:hashes) Require(Digest(p.first)==p.second,"Central input changed during reconstruction");
  Json summary={{"status","selected26_central_diagnostic_complete"},{"schema_version",1},{"events",events.size()},
      {"associations",total_associations},{"unsupported_events",unsupported},{"source_ca_rejected_events",source_rejected},
      {"uniform_draws",draws},{"physical_validation",false},{"physics_validation",false},{"output_format","ROOT_TTree"}};
  out.Finish(summary.dump());std::cout<<summary.dump()<<'\n';return 0;
} catch(const std::exception& error) {std::cerr<<"ERROR: "<<error.what()<<'\n';return 1;}}
