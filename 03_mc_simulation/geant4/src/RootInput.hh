#pragma once
#include "RootOutput.hh"
#include "TBranch.h"
#include "TLeaf.h"
#include "TMD5.h"
#include "TTreeReader.h"
#include "TTreeReaderValue.h"
#include <cmath>
#include "nlohmann/json.hpp"

// Shared strict input guards, mechanically extracted from digitize.cc.
namespace rootinput {
namespace fs = std::filesystem;
inline void Require(bool ok, const std::string& message) { if (!ok) throw std::runtime_error(message); }
inline std::string Digest(const fs::path& p) {
  std::unique_ptr<TMD5> value(TMD5::FileChecksum(p.string().c_str()));
  Require(bool(value), "Cannot digest input " + p.string()); return value->AsString();
}
inline std::unique_ptr<TFile> Open(const fs::path& p) {
  std::unique_ptr<TFile> f(TFile::Open(p.string().c_str(), "READ"));
  Require(f && !f->IsZombie() && !f->TestBit(TFile::kRecovered), "Invalid or recovered ROOT input"); return f;
}
inline std::string Text(TFile& file, const char* name) {
  auto* s = dynamic_cast<TObjString*>(file.Get(name));
  Require(s, std::string("Missing TObjString ") + name); return s->GetString().Data();
}
inline TTree& Tree(TFile& file, const char* name) {
  auto* t = dynamic_cast<TTree*>(file.Get(name));
  Require(t, std::string("Missing TTree ") + name); return *t;
}
inline void Type(TTree& tree, const char* name, const char* type) {
  auto* b = tree.GetBranch(name); auto* leaf = tree.GetLeaf(name);
  Require(b && leaf && std::string(leaf->GetTypeName()) == type && !leaf->GetLeafCount()
          && leaf->GetLenStatic() == 1, std::string("Missing/wrong scalar branch ") + tree.GetName()+"."+name);
}
template<class T> class Number {
  TTreeReaderValue<T> value;
public:
  Number(TTreeReader& reader, const char* name, const char* type): value(reader, name) { Type(*reader.GetTree(), name, type); }
  T get() {
    Require(value.GetSetupStatus() >= 0, "ROOT numeric reader setup error");
    Require(value.ProxyRead()==ROOT::Internal::TTreeReaderValueBase::kReadSuccess,"ROOT numeric basket read error");
    const auto* pointer=value.Get();
    Require(pointer && value.GetReadStatus()==ROOT::Internal::TTreeReaderValueBase::kReadSuccess,"ROOT numeric basket read error");
    return *pointer;
  }
};
class String {
  std::unique_ptr<TTreeReaderValue<std::string>> object;
public:
  String(TTreeReader& r, const char* name) {
    auto* b = r.GetTree()->GetBranch(name); Require(b, std::string("Missing string branch ")+name);
    const std::string type=b->GetClassName();
    Require(type=="string" || type=="std::string",std::string("Wrong string branch (requires native std::string) ")+name);
    object=std::make_unique<TTreeReaderValue<std::string>>(r,name);
  }
  std::string get() {
    Require(object->GetSetupStatus()>=0,"ROOT string reader setup error");
    Require(object->ProxyRead()==ROOT::Internal::TTreeReaderValueBase::kReadSuccess,"ROOT string basket read error");
    const auto* pointer=object->Get();
    Require(pointer && object->GetReadStatus()==ROOT::Internal::TTreeReaderValueBase::kReadSuccess,"ROOT string basket read error");
    return *pointer;
  }
};
inline bool Next(TTreeReader& r) {
  if(r.Next()) return true;
  Require(r.GetEntryStatus()==TTreeReader::kEntryBeyondEnd, "Unexpected ROOT read error"); return false;
}
inline void Nonnegative(double x, const char* field) { Require(std::isfinite(x) && x>=0, std::string("Nonfinite/negative ")+field); }
inline float Real(double x) { float r=static_cast<float>(x); Require(std::isfinite(r), "Outside legacy REAL range"); return r; }
inline bool CompactTransport(TFile& in) {
  const auto summary=nlohmann::json::parse(Text(in,"summary"));
  const auto& version=summary.at("hit_schema_version");
  Require(version.is_number_integer() && (version.is_number_unsigned() || version.get<Long64_t>()>=0) &&
    version.get<ULong64_t>()<=std::numeric_limits<int>::max(),"Expected JSON integer hit_schema_version in range");
  Require(version==2 || version==3,"Unsupported transport hit schema");
  if(version==2) {
    Require(!summary.contains("storage_mode") || summary.at("storage_mode")=="full","Schema2 requires full storage");
    return false;
  }
  Require(summary.at("storage_mode")=="compact" && summary.at("hit_policy")=="compact_response_inputs_v1","Invalid compact storage contract");
  const auto metadata=nlohmann::json::parse(Text(in,"storage_metadata"));
  Require(metadata.at("schema_version").is_number_integer() && metadata.at("schema_version")==1 && metadata.at("mode")=="compact" &&
    metadata.at("bgo")=="sum_per_crystal_float64" && metadata.at("source_index")=="original_sensitive_step" &&
    metadata.at("response_scope")=="current_response_no_step_quenching","Unsupported compact storage metadata");
  return true;
}
inline void TransportSchema(TFile& in) {
  const bool compact=CompactTransport(in);
  auto& channels=Tree(in,"channels");
  for(const char* key:{"sensitive","copy","legacy_channel","medium","material_id"}) Type(channels,key,"Int_t");
  // String constructors below also validate empty tables, before any Next().
  TTreeReader inventory(&channels);
  for(const char* key:{"path","detector","volume","channel_kind","material"}) { String check(inventory,key); }
  auto& steps=Tree(in,"detector_steps");
  for(const char* key:{"run","event","track","parent","track_step","pre_status","post_status","pre_boundary","post_boundary","track_status"}) Type(steps,key,"Int_t");
  for(const char* key:{"charge_e","edep_MeV","pre_time_ns","post_time_ns","pre_x_mm","pre_y_mm","pre_z_mm","post_x_mm","post_y_mm","post_z_mm"}) Type(steps,key,"Double_t");
  TTreeReader strings(&steps); String path(strings,"path");
  if(compact) Type(steps,"source_step_entry","ULong64_t");
  else {
    Type(steps,"pdg","Int_t");
    for(const char* key:{"track_weight","nonionizing_edep_MeV","step_length_mm","pre_kinetic_MeV","post_kinetic_MeV",
      "pre_local_x_mm","pre_local_y_mm","pre_local_z_mm","post_local_x_mm","post_local_y_mm","post_local_z_mm",
      "pre_dir_x","pre_dir_y","pre_dir_z","post_dir_x","post_dir_y","post_dir_z"}) Type(steps,key,"Double_t");
    for(const char* key:{"material","process","creator_process"}) {String check(strings,key);}
  }
  auto& primaries=Tree(in,"primaries");
  for(const char* key:{"run","event","vertex","particle","pdg"}) Type(primaries,key,"Int_t");
  for(const char* key:{"vertex_weight","particle_weight","x_mm","y_mm","z_mm","time_ns","px_MeV","py_MeV","pz_MeV","kinetic_MeV"}) Type(primaries,key,"Double_t");
}
} // namespace rootinput
