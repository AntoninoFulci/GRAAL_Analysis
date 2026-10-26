#pragma once
#include "G4Element.hh"
#include "G4GDMLParser.hh"
#include "G4Isotope.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4NistManager.hh"
#include "G4SystemOfUnits.hh"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <map>
#include <stdexcept>

// Runtime-only material interpretation of reference/geometry.g3. Never export
// these definitions over the geometry-equivalence GDML or historical snapshot.
// Effective STESA components are the snapshot's EPOXIDE (20) and GLASS (21);
// GASMAGIC's first component is ETHANE (15). Expand their mass fractions before
// asking Geant4 to build atomic/HP tables. AIR uses NIST composition as an
// explicit diagnostic assumption. All densities remain those of the snapshot.
inline void ApplyTransportMaterials(G4GDMLParser& parser, const std::string& report) {
  auto* nist = G4NistManager::Instance();
  std::map<int, G4Material*> replacements;
  for (const auto& [volume, auxiliary] : *parser.GetAuxMap()) {
    int id = 0;
    for (const auto& item : auxiliary)
      if (item.type == "geant3_material") id = std::stoi(item.value);
    if (!id) throw std::runtime_error("Missing GEANT3 material identity");
    if (!replacements.count(id)) {
      auto* legacy = volume->GetMaterial();
      const auto density = legacy->GetDensity();
      const auto label = "GRAAL_transport_" + std::to_string(id);
      G4Material* material = nullptr;
      if (id == 1) {
        if (legacy->GetNumberOfElements() != 1 ||
            std::abs((*legacy->GetElementVector())[0]->GetZ() - 1.) > 1.e-8 ||
            std::abs((*legacy->GetElementVector())[0]->GetA() / (g/mole) - 2.01) > 1.e-5 ||
            std::abs(density / (g/cm3) - .162) > 1.e-6)
          throw std::runtime_error("Expected frozen deuterium target; declare a new material policy for another target");
        auto* isotope = new G4Isotope("GRAAL_deuterium", 1, 2);
        auto* element = new G4Element("GRAAL_deuterium", "D", 1);
        element->AddIsotope(isotope, 100. * perCent);
        material = new G4Material(label, density, 1, kStateLiquid);
        material->AddElement(element, 1.);
      } else if (id == 7) {
        material = new G4Material(label, density, 1, kStateGas);
        material->AddMaterial(nist->FindOrBuildMaterial("G4_AIR"), 1.);
      } else {
        std::map<int, double> fractions;
        const auto* weights = legacy->GetFractionVector();
        if (id == 18 || id == 22) {
          if (legacy->GetNumberOfElements() != 2)
            throw std::runtime_error("Unexpected legacy composite material");
          const auto* elements = legacy->GetElementVector();
          const double z0 = id == 18 ? 4.992686271667480 : 6.083225727081299;
          const double z1 = id == 18 ? 18. : 10.80479240417480;
          if (std::abs((*elements)[0]->GetZ() - z0) > 1.e-5 ||
              std::abs((*elements)[1]->GetZ() - z1) > 1.e-5)
            throw std::runtime_error("Unrecognized effective material composition");
          auto expand = [&](double outer, std::map<int, double> inner) {
            double sum = 0;
            for (const auto& [z, fraction] : inner) sum += fraction;
            for (const auto& [z, fraction] : inner) fractions[z] += outer * fraction / sum;
          };
          if (id == 18) {
            expand(weights[0], {{6, .7985372543334961}, {1, .2014627605676651}});
            fractions[18] += weights[1];
          } else {
            expand(weights[0], {{6, .7404599189758301}, {1, .06226496770977974},
                                 {8, .1972751468420029}});
            expand(weights[1], {{14, .4674654603004456}, {8, .5325345396995544}});
          }
        } else {
          for (size_t i = 0; i < legacy->GetNumberOfElements(); ++i) {
            const double z = (*legacy->GetElementVector())[i]->GetZ();
            if (std::abs(z - std::round(z)) > 1.e-8)
              throw std::runtime_error("Unsupported effective element in " + std::to_string(id));
            fractions[static_cast<int>(std::round(z))] += weights[i];
          }
        }
        material = new G4Material(label, density, static_cast<int>(fractions.size()),
                                  id == 18 ? kStateGas : kStateSolid);
        for (const auto& [z, fraction] : fractions)
          material->AddElement(nist->FindOrBuildElement(z), fraction);
      }
      replacements[id] = material;
    }
    volume->SetMaterial(replacements.at(id));
  }
  if (report.empty()) return;
  std::ofstream out(report);
  out << std::setprecision(17) << "{\"policy\":\"diagnostic_materials_v1\",\"materials\":[";
  bool first = true;
  for (const auto& [id, material] : replacements) {
    if (!first) out << ',';
    first = false;
    out << "{\"id\":" << id << ",\"density_g_cm3\":" << material->GetDensity() / (g/cm3)
        << ",\"elements\":[";
    for (size_t i = 0; i < material->GetNumberOfElements(); ++i) {
      if (i) out << ',';
      const auto* element = (*material->GetElementVector())[i];
      out << "{\"Z\":" << element->GetZ() << ",\"fraction\":" << material->GetFractionVector()[i]
          << ",\"isotopes\":[";
      for (size_t j = 0; j < element->GetNumberOfIsotopes(); ++j) {
        if (j) out << ',';
        out << "{\"A\":" << (*element->GetIsotopeVector())[j]->GetN()
            << ",\"abundance\":" << element->GetRelativeAbundanceVector()[j] << '}';
      }
      out << "]}";
    }
    out << "]}";
  }
  out << "]}\n";
  out.close();
  if (!out) throw std::runtime_error("Failed writing transport material report");
}
