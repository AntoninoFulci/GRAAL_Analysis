// Standalone ROOT reader contract regression; argument is a disposable directory.
#include "TransportStorage.hh"
#include <functional>
#include <limits>
using namespace rootinput;
using Json=nlohmann::json;

static void Fixture(const fs::path& directory,const std::string& fault) {
  fs::create_directories(directory);RootOutput out(directory);
  auto& channels=out.Book("channels",{{"sensitive",0},{"copy",0},{"legacy_channel",0},{"medium",0},{"material_id",0},
    {"path",std::string{}},{"detector",std::string{}},{"volume",std::string{}},{"channel_kind",std::string{}},{"material",std::string{}}});
  channels.Fill({1,1,1,1,1,std::string("/BGO:1"),std::string("bgo"),std::string("BGO"),std::string("legacy_scintillator"),std::string("BGO")});
  channels.Fill({1,2,2,1,1,std::string("/BGO:2"),std::string("bgo"),std::string("BGO"),std::string("legacy_scintillator"),std::string("BGO")});
  channels.Fill({2,101,1,2,2,std::string("/BAR:101"),std::string("barrel"),std::string("BAR"),std::string("legacy_scintillator"),std::string("plastic")});
  auto& steps=out.Book("detector_steps",{{"run",0},{"event",0},{"track",0},{"parent",0},{"track_step",0},{"pre_status",0},{"post_status",0},
    {"pre_boundary",0},{"post_boundary",0},{"track_status",0},{"path",std::string{}},{"source_step_entry",ULong64_t{0}},
    {"charge_e",0.},{"edep_MeV",0.},{"pre_time_ns",0.},{"post_time_ns",0.},
    {"pre_x_mm",0.},{"pre_y_mm",0.},{"pre_z_mm",0.},{"post_x_mm",0.},{"post_y_mm",0.},{"post_z_mm",0.}});
  steps.Fill({0,0,1,0,1,0,0,1,0,0,std::string(fault=="bgo_path"?"/BGO:1":"/BAR:101"),ULong64_t{1},1.,1.,0.,1.,0.,0.,0.,0.,0.,0.});
  steps.Fill({1,0,1,0,1,0,0,1,0,0,std::string("/BAR:101"),ULong64_t(fault=="out_of_range"?5:3),1.,0.,0.,1.,0.,0.,0.,0.,0.,0.});
  if(fault!="missing_step") steps.Fill({1,0,1,0,fault=="track_order"?1:2,0,0,0,fault=="boundary"?2:0,0,std::string("/BAR:101"),ULong64_t(fault=="duplicate_source"?3:4),1.,
    fault=="nonfinite"?std::numeric_limits<double>::quiet_NaN():0.25,2.,fault=="time_order"?1.:3.,0.,0.,0.,0.,0.,0.});
  out.Book("primaries",{{"run",0},{"event",0},{"vertex",0},{"particle",0},{"pdg",0},{"vertex_weight",0.},{"particle_weight",0.},
    {"x_mm",0.},{"y_mm",0.},{"z_mm",0.},{"time_ns",0.},{"px_MeV",0.},{"py_MeV",0.},{"pz_MeV",0.},{"kinetic_MeV",0.}});
  auto& events=out.Book("events",{{"run",0},{"event",0},{"aborted",0},{"steps",ULong64_t{0}},{"hit_steps",ULong64_t{0}},
    {"total_edep_MeV",0.},{"bgo_edep_MeV",0.}});
  events.Fill({0,0,0,ULong64_t{4},ULong64_t{3},fault=="energy_bound"?2.:2.5,1.5});
  events.Fill({0,1,0,ULong64_t{0},ULong64_t{0},0.,0.});
  events.Fill({1,0,0,ULong64_t{3},ULong64_t{2},0.25,0.});
  events.Fill({1,1,0,ULong64_t{1},ULong64_t{1},2.,2.});
  events.Fill({1,2,1,ULong64_t{0},ULong64_t{0},0.,0.});
  auto& storage=out.Book("storage_events",{{"run",0},{"event",0},{"stored_steps",ULong64_t{0}},{"bgo_steps",ULong64_t{0}}});
  storage.Fill({0,0,ULong64_t{1},ULong64_t(fault=="storage_counts"?3:2)});
  if(fault!="missing_empty") storage.Fill({0,1,ULong64_t{0},ULong64_t{0}});
  storage.Fill({1,0,ULong64_t{2},ULong64_t{0}});
  storage.Fill({1,1,ULong64_t{0},ULong64_t{1}});
  storage.Fill({1,2,ULong64_t{0},ULong64_t{0}});
  auto& bgo=out.Book("bgo_hits",{{"run",0},{"event",0},{"crystal",0},{"edep_MeV",0.},{"first_time_ns",0.}});
  bgo.Fill({0,0,1,0.5,fault=="bgo_time"?-1.:1.});
  bgo.Fill({0,0,fault=="bgo_duplicate"?1:2,fault=="bgo_energy"?0.75:1.,2.});
  bgo.Fill({1,1,1,2.,0.});
  Json metadata={{"schema_version",1},{"mode","compact"},{"bgo","sum_per_crystal_float64"},
    {"source_index","original_sensitive_step"},{"response_scope","current_response_no_step_quenching"}};
  if(fault=="missing_contract")metadata.erase("source_index");
  if(fault=="contract_version")metadata["schema_version"]=2;
  out.Metadata("storage_metadata",metadata.dump());
  Json summary={{"hit_schema_version",3},{"storage_mode","compact"},{"hit_policy","compact_response_inputs_v1"},
    {"detector_steps",6},{"stored_detector_steps",3},{"all_callbacks",8},{"passive_callbacks",2},{"events",4},{"attempted_events",5},{"aborted",1}};
  if(fault=="wrong_mode")summary["storage_mode"]="full";
  if(fault=="unknown_schema")summary["hit_schema_version"]=4;
  if(fault=="summary_count")summary["stored_detector_steps"]=4;
  if(fault=="fraction_count")summary["detector_steps"]=6.25;
  if(fault=="negative_count")summary["detector_steps"]=-1;
  out.Finish(summary.dump());
}
int main(int argc,char** argv) {
  if(argc!=2)return 2;const fs::path root=argv[1];
  const std::vector<std::string> faults={"valid","bgo_path","out_of_range","duplicate_source","missing_step","track_order","boundary","nonfinite","time_order",
    "energy_bound","storage_counts","missing_empty","bgo_time","bgo_duplicate","bgo_energy","missing_contract","contract_version","wrong_mode","unknown_schema","summary_count","fraction_count","negative_count"};
  for(const auto& fault:faults) {
    Fixture(root/fault,fault);bool rejected=false;
    try {
      auto file=Open(root/fault/"transport.root");TransportSchema(*file);TransportStorage storage(*file);
      if(fault=="valid") {
      Require(storage.compact() && storage.rows()==3,"Incorrect compact reader mode/count");
      Require(storage.stored(0,0,3)==1 && storage.stored(0,1,0)==0 && storage.stored(1,0,2)==2,"Incorrect per-event stored count");
      const auto crystals=storage.bgo(0,0);Require(crystals[0]==0.5 && crystals[1]==1. && storage.omitted_bgo(1,1)==2.,"BGO float64 aggregate changed");
      TTreeReader rows(&Tree(*file,"detector_steps"));SourceEntry source(rows,storage);std::vector<ULong64_t> indices;
      while(Next(rows))indices.push_back(source.get());Require(indices==std::vector<ULong64_t>({1,3,4}),"Original sparse source indices changed");
      }
    } catch(const std::exception& error) {
      rejected=true;if(fault=="valid") {std::cerr<<"Valid compact input rejected: "<<error.what()<<'\n';return 1;}
    }
    if(fault!="valid" && !rejected) {std::cerr<<"Malformed compact input accepted: "<<fault<<'\n';return 1;}
  }
  std::cout<<"Compact input checks passed: valid cross-run/empty/aborted fixture and "<<faults.size()-1<<" malformed cases\n";return 0;
}
