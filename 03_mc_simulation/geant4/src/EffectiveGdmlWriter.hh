#pragma once
#include "G4Element.hh"
#include "G4GDMLWriteStructure.hh"
#include "G4IonisParamMat.hh"
#include "G4Material.hh"
#include <algorithm>
#include <stdexcept>
#include <vector>

// Standard GDML export infers natural isotopes and optimizes monoisotopic
// materials into atomic <material> entries. Both can replace legacy A/Z on
// reload. Serialize native effective elements explicitly, before materials.
class EffectiveGdmlWriter final : public G4GDMLWriteStructure {
public:
  G4Transform3D TraverseVolumeTree(const G4LogicalVolume* volume,G4int depth) override {
    auto transform=G4GDMLWriteStructure::TraverseVolumeTree(volume,depth);
    // Definitions are populated during traversal, after MaterialsWrite().
    if(depth!=0)return transform;
    while(auto* child=materialsElement->getFirstChild()) {
      materialsElement->removeChild(child);
      child->release();
    }
    std::vector<const G4Element*> elements;
    for(const auto* material:materialList) {
      if(material->GetMaterialPropertiesTable())
        throw std::runtime_error("Optical material properties are outside this geometry-only export");
      for(const auto* element:*material->GetElementVector())
        if(std::find(elements.begin(),elements.end(),element)==elements.end())elements.push_back(element);
    }
    for(const auto* element:elements) {
      auto* entry=NewElement("element");
      entry->setAttributeNode(NewAttribute("name",GenerateName(element->GetName(),element)));
      entry->setAttributeNode(NewAttribute("Z",element->GetZ()));
      AtomWrite(entry,element->GetA());
      materialsElement->appendChild(entry);
    }
    for(const auto* material:materialList) {
      auto* entry=NewElement("material");
      entry->setAttributeNode(NewAttribute("name",GenerateName(material->GetName(),material)));
      const auto state=material->GetState();
      const char* stateName=state==kStateSolid?"solid":state==kStateLiquid?"liquid":state==kStateGas?"gas":"undefined";
      entry->setAttributeNode(NewAttribute("state",stateName));
      TWrite(entry,material->GetTemperature());
      PWrite(entry,material->GetPressure());
      MEEWrite(entry,material->GetIonisation()->GetMeanExcitationEnergy());
      DWrite(entry,material->GetDensity());
      for(size_t i=0;i<material->GetNumberOfElements();++i) {
        const auto* element=(*material->GetElementVector())[i];
        auto* fraction=NewElement("fraction");
        fraction->setAttributeNode(NewAttribute("n",material->GetFractionVector()[i]));
        fraction->setAttributeNode(NewAttribute("ref",GenerateName(element->GetName(),element)));
        entry->appendChild(fraction);
      }
      materialsElement->appendChild(entry);
    }
    return transform;
  }
};
