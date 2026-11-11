#pragma once
#include "Compression.h"
#include "TFile.h"
#include "TObjString.h"
#include "TTree.h"
#include <filesystem>
#include <algorithm>
#include <cctype>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>

// Stable branch buffers with a checked, typed row contract. Never narrow doubles.
class RootTable {
public:
  using Value = std::variant<int, ULong64_t, double, std::string>;
  using Fields = std::initializer_list<std::pair<std::string, Value>>;
  RootTable(TFile& file, const std::string& name, Fields fields) : RootTable(&file, name, fields) {}
  RootTable(TFile* file, const std::string& name, Fields fields) {
    if (file) {
      file->cd();
      tree = new TTree(name.c_str(), name.c_str()); // Owned by the TFile.
      tree->SetDirectory(file);
      tree->SetAutoFlush(8192);
    }
    values.reserve(fields.size());
    for (const auto& field : fields) {
      const auto& label = field.first;
      labels.push_back(label);
      values.push_back(field.second);
      if (tree) std::visit([&](auto& buffer) {
        if (!tree->Branch(label.c_str(), &buffer))
          throw std::runtime_error("Cannot create ROOT branch " + label);
      }, values.back());
    }
  }
  void Fill(const std::vector<Value>& row) {
    if (row.size() != values.size()) throw std::runtime_error("ROOT row width mismatch");
    for (std::size_t i = 0; i < row.size(); ++i) {
      if (row[i].index() != values[i].index()) throw std::runtime_error("ROOT row type mismatch");
      values[i] = row[i]; // Same variant alternative: branch addresses remain stable.
    }
    if (!tree) rows.push_back(row);
    else if (tree->Fill() < 0) throw std::runtime_error("Failed writing ROOT row");
  }
  void Clear() { rows.clear(); }
  void DrainTo(RootTable& target, const std::map<std::string, ULong64_t>& offsets = {}) {
    if (tree || !target.tree || labels != target.labels || values.size() != target.values.size())
      throw std::runtime_error("Invalid buffered ROOT table drain");
    for (std::size_t i = 0; i < values.size(); ++i)
      if (values[i].index() != target.values[i].index()) throw std::runtime_error("Buffered ROOT schema mismatch");
    for (const auto& [label, offset] : offsets) {
      auto found = std::find(labels.begin(), labels.end(), label);
      if (found == labels.end()) throw std::runtime_error("Unknown buffered ROOT offset column");
      const auto i = std::size_t(found-labels.begin());
      for (auto& row : rows) {
        auto& value = std::get<ULong64_t>(row[i]);
        if (value > std::numeric_limits<ULong64_t>::max()-offset)
          throw std::runtime_error("Buffered ROOT offset overflow");
        value += offset;
      }
    }
    for (const auto& row : rows) target.Fill(row);
    Clear();
  }
  void Write() {
    if (tree->Write(tree->GetName(), TObject::kOverwrite) <= 0)
      throw std::runtime_error("Failed writing ROOT tree");
  }
private:
  TTree* tree = nullptr;
  std::vector<std::string> labels;
  std::vector<Value> values;
  std::vector<std::vector<Value>> rows;
};

class RootOutput {
public:
  // Worker-local event storage. No ROOT objects or global ROOT state are touched.
  struct Buffered {};
  explicit RootOutput(Buffered) {}
  explicit RootOutput(const std::filesystem::path& directory, const std::string& stem = "transport")
      : partial(directory / (ValidateStem(stem) + ".partial.root")), final(directory / (stem + ".root")) {
    if (std::filesystem::exists(final)) throw std::runtime_error("ROOT output exists; refusing overwrite");
    file.reset(TFile::Open(partial.string().c_str(), "CREATE"));
    if (!file || file->IsZombie()) throw std::runtime_error("Cannot create ROOT transport output");
    file->SetCompressionAlgorithm(ROOT::RCompressionSetting::EAlgorithm::kZSTD);
    file->SetCompressionLevel(5);
    TTree::SetMaxTreeSize(std::numeric_limits<Long64_t>::max()); // No implicit second file.
  }
  ~RootOutput() {
    // Preserve inspectable partial events on normal exception unwinding/soft abort.
    // Only Finish() promotes a file to the consumable name.
    if (file && file->IsOpen()) {
      try { WriteTables(); }
      catch (const std::exception& error) { std::cerr << "ERROR preserving partial ROOT: " << error.what() << '\n'; }
    }
    file.reset(); // Close/delete trees while all branch buffers are still alive, even after a write failure.
  }
  RootTable& Book(const std::string& name, RootTable::Fields fields) {
    if (tables.count(name)) throw std::runtime_error("Duplicate ROOT tree " + name);
    auto table = std::make_unique<RootTable>(file.get(), name, fields);
    auto& reference = *table;
    tables.emplace(name, std::move(table));
    return reference;
  }
  void Metadata(const std::string& name, const std::string& value) {
    if (!file) return; // Immutable metadata is published once by the master.
    file->cd();
    if (TObjString(value.c_str()).Write(name.c_str(), TObject::kOverwrite) <= 0)
      throw std::runtime_error("Failed writing ROOT metadata " + name);
    Check();
  }
  void Finish(const std::string& summary) {
    if (!file) throw std::runtime_error("Cannot finish a buffered ROOT output");
    WriteTables();
    Metadata("summary", summary);
    file->Flush();
    Check();
    file->Close();
    Check();
    if (std::filesystem::exists(final)) throw std::runtime_error("ROOT output exists; refusing overwrite");
    std::filesystem::rename(partial, final);
  }
  void Clear() {
    if (file) throw std::runtime_error("Cannot clear a file-backed ROOT output");
    for (auto& [name, table] : tables) table->Clear();
  }
  void DrainTo(RootOutput& target,
      const std::map<std::string, std::map<std::string, ULong64_t>>& offsets = {}) {
    if (file || !target.file || tables.size() != target.tables.size())
      throw std::runtime_error("Invalid buffered ROOT output drain");
    target.file->cd();
    for (auto& [name, table] : tables) {
      const auto found = offsets.find(name);
      table->DrainTo(*target.tables.at(name), found == offsets.end()
                    ? std::map<std::string, ULong64_t>{} : found->second);
    }
    target.Check();
  }
private:
  static std::string ValidateStem(const std::string& stem) {
    if (stem.empty()) throw std::runtime_error("Empty ROOT output stem");
    for (unsigned char c : stem)
      if (!std::isalnum(c) && c != '_') throw std::runtime_error("Invalid ROOT output stem");
    return stem;
  }
  void Check() const {
    if (file->TestBit(TFile::kWriteError)) throw std::runtime_error("ROOT output write error");
  }
  void WriteTables() {
    file->cd();
    for (const auto& [name, table] : tables) table->Write();
    file->Flush();
    Check();
  }
  std::filesystem::path partial, final;
  std::unique_ptr<TFile> file;
  std::map<std::string, std::unique_ptr<RootTable>> tables;
};
