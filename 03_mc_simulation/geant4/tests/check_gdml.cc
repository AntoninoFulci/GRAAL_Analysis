// Independent consumer: reload GDML, inspect materials and query placements.
#include "G4GDMLParser.hh"
#include "G4Element.hh"
#include "G4GeometryManager.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4Navigator.hh"
#include "G4SystemOfUnits.hh"
#include "G4VPhysicalVolume.hh"
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>

int main(int argc,char** argv) {
  try {
    if(argc!=4) throw std::runtime_error("Usage: graal_gdml_check geometry.gdml navigation.g3 NEW_OUTPUT_DIR");
    std::filesystem::path output(argv[3]);
    if(!std::filesystem::create_directory(output)) throw std::runtime_error("Output exists");
    G4GDMLParser parser;parser.Read(argv[1],false);
    auto* world=parser.GetWorldVolume();
    std::map<const G4LogicalVolume*,std::map<std::string,std::string>> metadata;
    for(const auto& [lv,aux]:*parser.GetAuxMap()) for(const auto& item:aux) metadata[lv][item.type]=item.value;
    const auto& root=metadata.at(world->GetLogicalVolume());
    // GDML setup stores only a logical world. Its historical physical copy
    // therefore travels as an explicit auxiliary value.
    world->SetCopyNo(root.count("geant3_world_copy")?std::stoi(root.at("geant3_world_copy")):1);
    G4GeometryManager::GetInstance()->CloseGeometry(true,false,world);
    std::map<int,const G4Material*> materials;
    int instances=0,bgo=0;
    std::function<void(G4VPhysicalVolume*)> visit=[&](G4VPhysicalVolume* pv) {
      auto* lv=pv->GetLogicalVolume();const auto& aux=metadata.at(lv);
      materials[std::stoi(aux.at("geant3_material"))]=lv->GetMaterial();
      ++instances;if(aux.at("geant3_volume")=="BGO") ++bgo;
      for(size_t i=0;i<lv->GetNoDaughters();++i) visit(lv->GetDaughter(i));
    };visit(world);
    std::ofstream props(output/"materials.json");props<<std::setprecision(17)<<"{\"instances\":"<<instances<<",\"bgo_copies\":"<<bgo<<",\"materials\":[";
    bool first=true;
    for(const auto& [id,mat]:materials) {
      if(!first)props<<',';first=false;
      props<<"{\"id\":"<<id<<",\"density\":"<<mat->GetDensity()/(g/cm3)<<",\"elements\":[";
      for(size_t i=0;i<mat->GetNumberOfElements();++i) {
        if(i)props<<',';auto* element=(*mat->GetElementVector())[i];
        props<<'['<<element->GetA()/(g/mole)<<','<<element->GetZ()<<','<<mat->GetFractionVector()[i]<<']';
      }props<<"]}";
    }props<<"]}\n";
    G4Navigator nav;nav.SetWorldVolume(world);
    std::ifstream in(argv[2]);std::ofstream out(output/"navigation.g4");out<<std::setprecision(17);
    if(!in)throw std::runtime_error("Cannot read reference points");
    std::string line;size_t points=0;
    while(std::getline(in,line)) {
      std::istringstream row(line);double x,y,z;if(!(row>>x>>y>>z))throw std::runtime_error("Invalid point");
      auto* pv=nav.LocateGlobalPointAndSetup({x*cm,y*cm,z*cm},nullptr,false,true);
      out<<x<<' '<<y<<' '<<z;
      if(!pv)out<<" 0 0\n";
      else {
        auto history=nav.CreateTouchableHistoryHandle();int depth=history->GetHistoryDepth();
        out<<' '<<metadata.at(pv->GetLogicalVolume()).at("geant3_medium")<<' '<<depth+1;
        for(int level=depth;level>=0;--level) {
          auto* placed=history->GetVolume(level);
          out<<' '<<metadata.at(placed->GetLogicalVolume()).at("geant3_volume")<<' '<<placed->GetCopyNo();
        }out<<'\n';
      }++points;
    }
    if(!out || !props || !points || bgo!=480)throw std::runtime_error("Incomplete GDML round trip");
    G4GeometryManager::GetInstance()->OpenGeometry(world);
    std::cout<<"GDML_ROUNDTRIP_COMPLETE instances="<<instances<<" points="<<points<<'\n';
    return 0;
  }catch(const std::exception& error){std::cerr<<"ERROR: "<<error.what()<<'\n';return 1;}
}
