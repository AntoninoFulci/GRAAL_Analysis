// Geometry-only migration. No physics list, event generator or digitization.
#include "EffectiveGdmlWriter.hh"
#include "G4Box.hh"
#include "G4Cons.hh"
#include "G4Element.hh"
#include "G4GDMLParser.hh"
#include "G4GDMLReadStructure.hh"
#include "G4GeometryManager.hh"
#include "G4GenericTrap.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4MultiUnion.hh"
#include "G4Navigator.hh"
#include "G4PVPlacement.hh"
#include "G4Polyhedra.hh"
#include "G4Polyhedron.hh"
#include "G4SystemOfUnits.hh"
#include "G4SubtractionSolid.hh"
#include "G4Tubs.hh"
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
struct Volume { std::string name, shape; int medium; std::vector<double> p; };
struct Placement {
  std::string name, mother, mode;
  int copy, rotation;
  G4ThreeVector position;
  std::vector<double> p;
};
struct Component { double a, z, weight; };
struct Material { std::string name; double density; std::vector<Component> components; };
struct Medium { int material, sensitive; };

size_t shapeSize(const std::string& shape) {
  const std::map<std::string,size_t> sizes={{"BOX",3},{"TUBE",3},{"TUBS",5},{"TRAP",11},{"CONS",7},{"PGON",10}};
  if(!sizes.count(shape)) throw std::runtime_error("Unsupported shape: "+shape);
  return sizes.at(shape);
}

void validateShape(const Volume& v) {
  const auto& p=v.p;
  if(p.size()!=shapeSize(v.shape)) throw std::runtime_error("Invalid parameter count for "+v.name);
  bool valid=true;
  if(v.shape=="BOX")valid=p[0]>0&&p[1]>0&&p[2]>0;
  else if(v.shape=="TUBE"||v.shape=="TUBS") {
    valid=p[0]>=0&&p[1]>p[0]&&p[2]>0;
    if(v.shape=="TUBS")valid=valid&&p[4]>p[3]&&p[4]-p[3]<=360.00001;
  }else if(v.shape=="CONS")valid=p[0]>0&&p[1]>=0&&p[2]>p[1]&&p[3]>=0&&p[4]>p[3]&&p[6]>p[5]&&p[6]-p[5]<=360.00001;
  else if(v.shape=="TRAP")valid=p[0]>0&&p[3]>0&&p[4]>0&&p[5]>0&&p[7]>0&&p[8]>0&&p[9]>0;
  else if(v.shape=="PGON")valid=p[2]==4&&p[3]==2&&p[4]<p[7]&&p[5]>=0&&p[6]>p[5]&&p[8]>=0&&p[9]>p[8];
  if(!valid)throw std::runtime_error("Invalid dimensions for "+v.name);
}

struct Snapshot {
  std::map<std::string, Volume> volumes;
  std::map<int, Material> materials;
  std::map<int, Medium> media;
  std::map<int, G4RotationMatrix> rotations;
  std::map<std::string, std::vector<Placement>> children;

  explicit Snapshot(const fs::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("Cannot read snapshot: " + path.string());
    std::string line;
    size_t lineNumber = 0;
    while (std::getline(input, line)) {
      ++lineNumber;
      std::istringstream in(line);
      std::string tag;
      if (!(in >> tag)) continue;
      auto reals = [&](int n) {
        if (n < 0 || n > 100) throw std::runtime_error("Invalid parameter count");
        std::vector<double> values(n);
        for (double& x : values) {
          if (!(in >> x) || !std::isfinite(x)) throw std::runtime_error("Invalid numeric field");
        }
        return values;
      };
      if (tag == "V") {
        Volume v; int count;
        if (!(in >> v.name >> v.shape >> v.medium >> count)) throw std::runtime_error("Invalid volume");
        v.p = reals(count);
        if (!volumes.emplace(v.name, v).second) throw std::runtime_error("Duplicate volume " + v.name);
      } else if (tag == "P") {
        Placement p; double x,y,z; int count;
        if (!(in >> p.name >> p.copy >> p.mother >> x >> y >> z >> p.rotation >> p.mode >> count))
          throw std::runtime_error("Invalid placement");
        if (!std::isfinite(x+y+z) || (p.mode != "ONLY" && p.mode != "MANY"))
          throw std::runtime_error("Invalid placement transform/mode");
        p.position = G4ThreeVector(x*cm,y*cm,z*cm);
        p.p = reals(count);
        children[p.mother].push_back(p);
      } else if (tag == "R") {
        int id; if (!(in >> id)) throw std::runtime_error("Invalid rotation ID");
        auto a = reals(6);
        auto axis = [&](int i) {
          const double t=a[i]*deg, p=a[i+1]*deg;
          return G4ThreeVector(std::sin(t)*std::cos(p),std::sin(t)*std::sin(p),std::cos(t));
        };
        G4RotationMatrix rotation(axis(0),axis(2),axis(4));
        if (!rotations.emplace(id,rotation).second) throw std::runtime_error("Duplicate rotation");
      } else if (tag == "M") {
        int id; Material m; double a,z;
        if (!(in >> id >> m.name >> a >> z >> m.density)) throw std::runtime_error("Invalid material");
        m.components.push_back({a,z,1.});
        if (!materials.emplace(id,m).second) throw std::runtime_error("Duplicate material");
      } else if (tag == "X") {
        int id,count; Material m;
        if (!(in >> id >> m.name >> m.density >> count) || count<1 || count>100)
          throw std::runtime_error("Invalid mixture");
        auto c = reals(3*count);
        for (int i=0;i<count;++i) m.components.push_back({c[3*i],c[3*i+1],c[3*i+2]});
        if (!materials.emplace(id,m).second) throw std::runtime_error("Duplicate mixture");
      } else if (tag == "T") {
        int id,field; Medium m;
        if (!(in >> id >> m.material >> m.sensitive >> field)) throw std::runtime_error("Invalid medium");
        reals(6); // Retained in snapshot; no transport enabled in this program.
        if (!media.emplace(id,m).second) throw std::runtime_error("Duplicate medium");
      } else throw std::runtime_error("Unsupported record at line " + std::to_string(lineNumber));
      std::string extra;
      if (in >> extra) throw std::runtime_error("Unexpected field at line " + std::to_string(lineNumber));
    }
    if (!volumes.count("LAGR")) throw std::runtime_error("World LAGR missing");
    for (const auto& [name,v]:volumes) {
      shapeSize(v.shape);
      if(!v.p.empty())validateShape(v);
      if (!media.count(v.medium) || !materials.count(media.at(v.medium).material))
        throw std::runtime_error("Unresolved medium/material for " + name);
    }
    for (const auto& [mother,items]:children) {
      if (!volumes.count(mother)) throw std::runtime_error("Unknown mother " + mother);
      std::set<std::pair<std::string,int>> copies;
      for (const auto& p:items) {
        if (!volumes.count(p.name) || (p.rotation && !rotations.count(p.rotation)))
          throw std::runtime_error("Unresolved placement " + p.name);
        if (!copies.emplace(p.name,p.copy).second) throw std::runtime_error("Duplicate placement identity");
        auto resolved=volumes.at(p.name);
        if(!p.p.empty())resolved.p=p.p;
        validateShape(resolved);
      }
    }
  }
};

class Geometry {
public:
  const Snapshot& data;
  std::map<int,G4Material*> materials;
  std::map<G4LogicalVolume*,Volume> metadata;
  std::vector<G4VPhysicalVolume*> placements;
  std::map<std::string,G4LogicalVolume*> cache;
  std::set<std::string> active;
  int suppressed=0;
  explicit Geometry(const Snapshot& s):data(s) {
    for (const auto& [id,m]:data.materials) {
      if (!std::isfinite(m.density) || m.density<=0) throw std::runtime_error("Invalid density");
      auto* mat=new G4Material("G3_"+std::to_string(id)+"_"+m.name,m.density*g/cm3,int(m.components.size()));
      double sum=0;
      for (auto c:m.components) {
        if (!std::isfinite(c.a+c.z+c.weight) || c.a<=0 || c.z<1 || c.weight<=0)
          throw std::runtime_error("Invalid effective element");
        sum+=c.weight;
      }
      if (std::abs(sum-1.)>1.e-5) throw std::runtime_error("Mixture fractions not normalized");
      int index=0;
      for (auto c:m.components) {
        auto label="G3_"+std::to_string(id)+"_E"+std::to_string(++index);
        auto* e=new G4Element(label,label,c.z,c.a*g/mole);
        mat->AddElement(e,c.weight/sum);
      }
      materials[id]=mat;
    }
  }

  G4VSolid* solid(const Volume& v, const std::string& label) {
    const auto& p=v.p;
    validateShape(v);
    if (v.shape=="BOX") return new G4Box(label,p[0]*cm,p[1]*cm,p[2]*cm);
    if (v.shape=="TUBE" || v.shape=="TUBS")
      return new G4Tubs(label,p[0]*cm,p[1]*cm,p[2]*cm,p.size()==5?p[3]*deg:0.,p.size()==5?(p[4]-p[3])*deg:360*deg);
    if (v.shape=="CONS")
      return new G4Cons(label,p[1]*cm,p[2]*cm,p[3]*cm,p[4]*cm,p[0]*cm,p[5]*deg,(p[6]-p[5])*deg);
    if (v.shape=="TRAP") {
      // Rounded legacy dimensions give slightly twisted side faces. Preserve
      // all eight vertices instead of changing lengths to satisfy G4Trap.
      std::vector<G4TwoVector> vertices;
      const double tx=std::tan(p[1]*deg)*std::cos(p[2]*deg);
      const double ty=std::tan(p[1]*deg)*std::sin(p[2]*deg);
      for (int face=0;face<2;++face) {
        int i=face?7:3;
        const double z=(face?1.:-1.)*p[0];
        const double dy=p[i],dx1=p[i+1],dx2=p[i+2],ta=std::tan(p[i+3]*deg);
        for (auto xy:std::vector<G4TwoVector>{{-dx1-dy*ta,-dy},{-dx2+dy*ta,dy},{dx2+dy*ta,dy},{dx1-dy*ta,-dy}})
          vertices.emplace_back((xy.x()+z*tx)*cm,(xy.y()+z*ty)*cm);
      }
      return new G4GenericTrap(label,p[0]*cm,vertices);
    }
    if (p[2]!=4 || p[3]!=2) throw std::runtime_error("Unsupported PGON segmentation");
    double z[]={p[4]*cm,p[7]*cm}, rmin[]={p[5]*cm,p[8]*cm}, rmax[]={p[6]*cm,p[9]*cm};
    return new G4Polyhedra(label,p[0]*deg,p[1]*deg,4,2,z,rmin,rmax);
  }

  G4VSolid* effectiveSolid(const Volume& v,const std::string& label) {
    auto* result=solid(v,label);
    if (v.name!="ENVM" && v.name!="TROM" && v.name!="TROC") return result;
    // Priorities measured with independent GEANT3 point queries. The source
    // uses overlapping siblings, which are not a valid GEANT4 partition.
    // Remove only portions hidden by higher-priority volumes in GEANT3.
    const auto& siblings=data.children.at("LAGR");
    std::vector<Placement> own;
    for(const auto& p:siblings) if(p.name==v.name) own.push_back(p);
    if(own.size()!=1) throw std::runtime_error("Priority rule requires one placement of " + v.name);
    G4RotationMatrix rOwn;
    if(own[0].rotation) rOwn=data.rotations.at(own[0].rotation);
    if(v.name=="ENVM" || v.name=="TROM") {
      // These cutters span the full radial cross-section. Exact interval
      // subtraction produces disjoint annular/cylindrical pieces, which
      // G4MultiUnion can visualize without coincident Boolean faces.
      if(own[0].rotation) throw std::runtime_error("Unexpected rotation in axial priority rule");
      std::vector<std::pair<double,double>> intervals={{-v.p[2]*cm,v.p[2]*cm}};
      int cutCount=0;
      for(const auto& p:siblings) {
        bool higher=(v.name=="ENVM" && p.name=="FEN3" && p.copy==2)
          || (v.name=="TROM" && (p.name=="WAL1" || p.name=="WAL2"));
        if(!higher) continue;
        ++cutCount;
        if(p.rotation) throw std::runtime_error("Unexpected cutter rotation");
        auto cutter=data.volumes.at(p.name);
        if(!p.p.empty())cutter.p=p.p;
        validateShape(cutter);
        const auto delta=p.position-own[0].position;
        if(std::abs(delta.x())>1.e-9*mm || std::abs(delta.y())>1.e-9*mm)
          throw std::runtime_error("Axial cutter has unexpected transverse displacement");
        bool spanning=cutter.shape=="BOX" ? std::min(cutter.p[0],cutter.p[1])>=v.p[1]
          : cutter.shape=="TUBE" && cutter.p[0]<=v.p[0] && cutter.p[1]>=v.p[1];
        if(!spanning)throw std::runtime_error("Axial cutter does not span the tube cross-section");
        double center=(p.position-own[0].position).z();
        double low=center-cutter.p[2]*cm,high=center+cutter.p[2]*cm;
        std::vector<std::pair<double,double>> remainder;
        for(auto [a,b]:intervals) {
          if(high<=a || low>=b) remainder.emplace_back(a,b);
          else { if(low>a) remainder.emplace_back(a,low); if(high<b) remainder.emplace_back(high,b); }
        }
        intervals=std::move(remainder);
      }
      if(cutCount!=(v.name=="ENVM"?1:2) || intervals.empty())throw std::runtime_error("Incomplete axial priority rule");
      auto* pieces=new G4MultiUnion(label+"_effective");
      int i=0;
      for(auto [a,b]:intervals) {
        auto* tube=new G4Tubs(label+"_piece_"+std::to_string(++i),v.p[0]*cm,v.p[1]*cm,(b-a)/2,0.,360*deg);
        pieces->AddNode(*tube,G4Transform3D(G4RotationMatrix(),G4ThreeVector(0,0,(a+b)/2)));
      }
      pieces->Voxelize();
      return pieces;
    }
    int cuts=0;
    for(const auto& p:siblings) {
      bool higher=(v.name=="ENVM" && p.name=="FEN3" && p.copy==2)
        || (v.name=="TROM" && (p.name=="WAL1" || p.name=="WAL2"))
        || (v.name=="TROC" && (p.name=="CASC" || p.name=="FE1" || p.name=="FE2"));
      if(!higher) continue;
      auto other=data.volumes.at(p.name);
      if(!p.p.empty()) other.p=p.p;
      auto cutLabel=label+"_cut_"+std::to_string(++cuts);
      auto* cutter=solid(other,cutLabel);
      G4RotationMatrix rOther;
      if(p.rotation) rOther=data.rotations.at(p.rotation);
      result=new G4SubtractionSolid(label+"_effective_"+std::to_string(cuts),result,cutter,
          G4Transform3D(rOwn.inverse()*rOther,rOwn.inverse()*(p.position-own[0].position)));
    }
    if(cuts!=18)throw std::runtime_error("TROC rule requires sixteen modules and two iron plates");
    return result;
  }

  void validateHiddenHole(const Placement& hole) const {
    if(hole.copy!=1&&hole.copy!=2)throw std::runtime_error("Unexpected TROU copy");
    auto tube=data.volumes.at(hole.name);if(!hole.p.empty())tube.p=hole.p;
    validateShape(tube);
    if(tube.shape!="TUBE" || hole.rotation)throw std::runtime_error("Unexpected TROU solid/rotation");
    std::vector<Placement> gas;
    for(const auto& p:data.children.at("LAGR"))if(p.name=="PLG"+std::to_string(hole.copy))gas.push_back(p);
    if(gas.size()!=1)throw std::runtime_error("TROU matching chamber missing");
    auto box=data.volumes.at(gas[0].name);if(!gas[0].p.empty())box.p=gas[0].p;
    validateShape(box);
    G4RotationMatrix r;if(gas[0].rotation)r=data.rotations.at(gas[0].rotation);
    if(box.shape!="BOX" || (gas[0].position-hole.position).mag()>1.e-9*mm
        || std::abs(r.zx())>1.e-10 || std::abs(r.zy())>1.e-10
        || tube.p[1]>std::min(box.p[0],box.p[1]) || tube.p[2]>box.p[2]
        || tube.medium!=box.medium)throw std::runtime_error("TROU is not fully hidden by its chamber");
  }

  G4LogicalVolume* volume(const std::string& name,const std::vector<double>& parameters={}) {
    Volume v=data.volumes.at(name);
    if (!parameters.empty()) v.p=parameters;
    std::ostringstream key; key << name << std::setprecision(17);
    for (double x:v.p) key << '/' << x;
    if (active.count(name)) throw std::runtime_error("Geometry cycle at " + name);
    if (cache.count(key.str())) return cache.at(key.str());
    active.insert(name);
    auto label=name+"__"+std::to_string(cache.size());
    auto* lv=new G4LogicalVolume(effectiveSolid(v,label),materials.at(data.media.at(v.medium).material),label);
    cache[key.str()]=lv; metadata[lv]=v;
    auto found=data.children.find(name);
    if (found!=data.children.end()) for (const auto& p:found->second) {
      // TROU is fully contained in PLG1/PLG2. GEANT3 always selects the
      // chamber, including its sensitive planes, in this occupied region.
      // Its declared shape remains in the immutable source snapshot.
      if(p.name=="TROU") {validateHiddenHole(p);++suppressed;continue;}
      auto* child=volume(p.name,p.p);
      G4RotationMatrix r;
      if (p.rotation) r=data.rotations.at(p.rotation);
      placements.push_back(new G4PVPlacement(G4Transform3D(r,p.position),child,p.name,lv,false,p.copy));
    }
    active.erase(name);
    return lv;
  }

  void scene(G4VPhysicalVolume* world,const fs::path& file) const {
    std::ofstream out(file); out << std::setprecision(12) << '[';
    bool first=true;
    std::function<void(G4VPhysicalVolume*,G4Transform3D,std::string)> visit;
    visit=[&](G4VPhysicalVolume* pv,G4Transform3D parent,std::string path) {
      auto transform=parent*G4Transform3D(pv->GetObjectRotationValue(),pv->GetObjectTranslation());
      auto* lv=pv->GetLogicalVolume();
      const auto& v=metadata.at(lv);
      path+='/'+pv->GetName()+':'+std::to_string(pv->GetCopyNo());
      auto* poly=lv->GetSolid()->GetPolyhedron();
      if (!poly) throw std::runtime_error("No mesh for " + path);
      if (!first) out << ',';
      first=false;
      out << "\n{\"name\":" << std::quoted(v.name) << ",\"path\":" << std::quoted(path)
          << ",\"copy\":" << pv->GetCopyNo() << ",\"medium\":" << v.medium
          << ",\"material\":" << data.media.at(v.medium).material << ",\"vertices\":[";
      for (int i=1;i<=poly->GetNoVertices();++i) {
        if(i>1) out << ',';
        auto p=transform*poly->GetVertex(i);
        out << '[' << p.x()/cm << ',' << p.y()/cm << ',' << p.z()/cm << ']';
      }
      out << "],\"triangles\":[";
      bool firstFace=true;
      for (int face=1;face<=poly->GetNoFacets();++face) {
        int n,vertices[4]; poly->GetFacet(face,n,vertices);
        for (int j=1;j<n-1;++j) {
          if(!firstFace) out << ',';
          firstFace=false;
          out << '[' << vertices[0]-1 << ',' << vertices[j]-1 << ',' << vertices[j+1]-1 << ']';
        }
      }
      out << "]}";
      for (size_t i=0;i<lv->GetNoDaughters();++i) visit(lv->GetDaughter(i),transform,path);
    };
    visit(world,G4Transform3D(),""); out << "\n]\n";
    if (!out) throw std::runtime_error("Scene write failed");
  }

  void navigate(G4VPhysicalVolume* world,const fs::path& input,const fs::path& output) const {
    G4Navigator nav; nav.SetWorldVolume(world);
    std::ifstream in(input); std::ofstream out(output);
    if (!in) throw std::runtime_error("Cannot read navigation reference");
    out << std::setprecision(17);
    std::string line;
    while(std::getline(in,line)) {
      std::istringstream row(line); double x,y,z;
      if (!(row>>x>>y>>z)) throw std::runtime_error("Malformed navigation point");
      auto* located=nav.LocateGlobalPointAndSetup(G4ThreeVector(x*cm,y*cm,z*cm),nullptr,false,true);
      out << x << ' ' << y << ' ' << z;
      if (!located) out << " 0 0\n";
      else {
        auto history=nav.CreateTouchableHistoryHandle();
        int depth=history->GetHistoryDepth();
        out << ' ' << metadata.at(located->GetLogicalVolume()).medium << ' ' << depth+1;
        for (int level=depth;level>=0;--level) {
          auto* pv=history->GetVolume(level);
          out << ' ' << pv->GetName() << ' ' << pv->GetCopyNo();
        }
        out << '\n';
      }
    }
    if (!out) throw std::runtime_error("Navigation write failed");
  }
};

int main(int argc,char** argv) {
  try {
    if (argc!=3 && argc!=4) throw std::runtime_error("Usage: graal_geometry geometry.g3 NEW_OUTPUT_DIR [navigation.g3]");
    Snapshot snapshot(argv[1]);
    fs::path output(argv[2]);
    if (!fs::create_directory(output)) throw std::runtime_error("Output exists; refusing overwrite");
    Geometry geometry(snapshot);
    auto* world=new G4PVPlacement(nullptr,G4ThreeVector(),geometry.volume("LAGR"),"LAGR",nullptr,false,1);
    G4GeometryManager::GetInstance()->CloseGeometry(true,false,world);
    int overlaps=0;
    // REAL*4 legacy placements leave sub-micrometre contact discrepancies.
    // This is an explicit audit tolerance, not a modification of dimensions.
    for (auto* pv:geometry.placements) if(pv->CheckOverlaps(10000,0.001*mm,true,1)) ++overlaps;
    G4GDMLParser gdml(new G4GDMLReadStructure,new EffectiveGdmlWriter);
    for(const auto& [lv,v]:geometry.metadata) {
      gdml.AddVolumeAuxiliary({"geant3_volume",v.name,"",nullptr},lv);
      gdml.AddVolumeAuxiliary({"geant3_medium",std::to_string(v.medium),"",nullptr},lv);
      gdml.AddVolumeAuxiliary({"geant3_material",std::to_string(snapshot.media.at(v.medium).material),"",nullptr},lv);
    }
    gdml.AddVolumeAuxiliary({"geant3_world_copy","1","",nullptr},world->GetLogicalVolume());
    gdml.Write((output/"geometry.gdml").string(),world,false);
    geometry.scene(world,output/"scene.json");
    if(argc==4) geometry.navigate(world,argv[3],output/"navigation.g4");
    int bgo=0,recordCount=0;
    for(const auto& [name,items]:snapshot.children) for(const auto& p:items) { ++recordCount; if(p.name=="BGO") ++bgo; }
    std::ofstream summary(output/"summary.json");
    summary << "{\"status\":\"" << (overlaps?"converted_with_unresolved_overlaps":"converted_requires_navigation_comparison")
            << "\",\"bgo_copies\":" << bgo << ",\"placement_records\":" << recordCount
            << ",\"logical_volumes\":" << geometry.metadata.size() << ",\"overlap_volumes\":" << overlaps
            << ",\"overlap_tolerance_mm\":0.001,\"overlap_samples_per_placement\":10000,\"suppressed_placements\":"<<geometry.suppressed<<"}\n";
    if(!summary) throw std::runtime_error("Summary write failed");
    std::cout << "GEOMETRY_CONVERSION_COMPLETE overlap_volumes=" << overlaps << '\n';
    G4GeometryManager::GetInstance()->OpenGeometry(world);
    return overlaps?2:0;
  } catch(const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << '\n'; return 1;
  }
}
