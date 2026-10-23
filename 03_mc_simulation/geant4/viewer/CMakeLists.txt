cmake_minimum_required(VERSION 3.16)
project(graal_native_viewer LANGUAGES CXX)

find_package(Geant4 11.4 REQUIRED gdml qt vis_all)
if(NOT Geant4_qt_FOUND)
  message(FATAL_ERROR "This viewer requires Geant4 built with Qt enabled")
endif()
get_filename_component(geant4_prefix "${Geant4_DIR}/../../.." ABSOLUTE)
set(example "${geant4_prefix}/share/Geant4/examples/extended/persistency/gdml/G01")
if(NOT EXISTS "${example}/load_gdml.cc")
  message(FATAL_ERROR "Install Geant4 with examples enabled to build the G01 viewer")
endif()

# Reuse the installed official example. Adapt only its generated build copy:
# input is already validated locally; neither network schema lookup nor an
# additional zero-tolerance overlap scan belongs to opening a viewer.
# Restore the world physical copy from the same auxiliary used by our checker.
file(COPY "${example}/" DESTINATION "${CMAKE_CURRENT_BINARY_DIR}/G01-source")
set(main "${CMAKE_CURRENT_BINARY_DIR}/G01-source/load_gdml.cc")
file(READ "${main}" source)
if(NOT source MATCHES "parser.Read\\(argv\\[1\\]\\);")
  message(FATAL_ERROR "G01 input reader changed; review the offline adaptation")
endif()
string(REPLACE "parser.SetOverlapCheck(true);" "parser.SetOverlapCheck(false);" source "${source}")
string(REPLACE "parser.Read(argv[1]);" [=[parser.Read(argv[1], false);
  for (const auto& aux : parser.GetVolumeAuxiliaryInformation(
         parser.GetWorldVolume()->GetLogicalVolume())) {
    if (aux.type == "geant3_world_copy") {
      parser.GetWorldVolume()->SetCopyNo(std::stoi(aux.value));
    }
  }]=] source "${source}")
file(WRITE "${main}" "${source}")
add_subdirectory("${CMAKE_CURRENT_BINARY_DIR}/G01-source" G01-build)
configure_file(vis.mac "${CMAKE_CURRENT_BINARY_DIR}/vis.mac" COPYONLY)
configure_file(check-overlaps.mac "${CMAKE_CURRENT_BINARY_DIR}/check-overlaps.mac" COPYONLY)
