// CutMapBuilder.C
// ROOT macro to build a map of TCutG cuts based on run IDs and folder structure

#include <map>
#include <string>
#include <vector>
#include <iostream>
#include <TSystem.h>
#include <TFile.h>
#include <TCutG.h>
#include <TROOT.h>

// Global map to store cuts: [particle][detector][runID] -> TCutG*
std::map<std::string, std::map<std::string, std::map<int, TCutG*>>> gCutMap;

// Map: runID -> folder name
std::map<int, std::string> gRunToFolder;

// Helper function to extract run IDs from a folder
std::vector<int> GetRunIDsFromFolder(const std::string& folderPath) {
    std::vector<int> runIDs;
    
    void* dirp = gSystem->OpenDirectory(folderPath.c_str());
    if (!dirp) {
        std::cerr << "Cannot open directory: " << folderPath << std::endl;
        return runIDs;
    }
    
    const char* entry;
    while ((entry = gSystem->GetDirEntry(dirp))) {
        std::string filename(entry);
        
        // Look for pattern: run####.root
        if (filename.find("run") == 0 && filename.find(".root") != std::string::npos) {
            // Extract run number
            std::string runStr = filename.substr(3); // skip "run"
            runStr = runStr.substr(0, runStr.find(".root"));
            
            try {
                int runID = std::stoi(runStr);
                runIDs.push_back(runID);
            } catch (...) {
                std::cerr << "Could not parse run ID from: " << filename << std::endl;
            }
        }
    }
    
    gSystem->FreeDirectory(dirp);
    return runIDs;
}

// Helper function to extract folder name from cut filename
std::string ExtractFolderFromCutFile(const std::string& filename) {
    // Extract folder name from pattern: ParticleDetectorCut_YYYY_detector.cpp
    // Example: PionFwdCut_1999_uv.cpp -> 1999_uv
    
    // Find "Cut_" position
    size_t cutPos = filename.find("Cut_");
    size_t dotPos = filename.find(".cpp");
    
    if (cutPos != std::string::npos && dotPos != std::string::npos) {
        // Extract everything between "Cut_" and ".cpp"
        return filename.substr(cutPos + 4, dotPos - cutPos - 4);
    }
    
    return "";
}

// Main function to build the cut map
void BuildCutMap(const std::string& dataPath = "./", const std::string& cutPath = "./cuts") {
    
    std::cout << "==================================" << std::endl;
    std::cout << "Building Cut Map" << std::endl;
    std::cout << "==================================" << std::endl;
    
    // Step 1: Scan data folders and build runID -> folder mapping
    std::cout << "\nStep 1: Scanning data folders..." << std::endl;
    
    void* dirp = gSystem->OpenDirectory(dataPath.c_str());
    if (!dirp) {
        std::cerr << "ERROR: Cannot open data directory: " << dataPath << std::endl;
        return;
    }
    
    const char* entry;
    std::vector<std::string> folders;
    
    while ((entry = gSystem->GetDirEntry(dirp))) {
        std::string folderName(entry);
        
        // Skip . and ..
        if (folderName == "." || folderName == "..") continue;
        
        // Check if it's a directory
        std::string fullPath = dataPath + "/" + folderName;
        FileStat_t statbuf;
        if (gSystem->GetPathInfo(fullPath.c_str(), statbuf) == 0) {
            if (R_ISDIR(statbuf.fMode)) {
                folders.push_back(folderName);
            }
        }
    }
    gSystem->FreeDirectory(dirp);
    
    std::cout << "Found " << folders.size() << " folders" << std::endl;
    
    // For each folder, get run IDs
    for (const auto& folder : folders) {
        std::string folderPath = dataPath + "/" + folder;
        std::vector<int> runIDs = GetRunIDsFromFolder(folderPath);
        
        std::cout << "  " << folder << ": " << runIDs.size() << " runs (";
        for (size_t i = 0; i < runIDs.size() && i < 3; i++) {
            std::cout << runIDs[i];
            if (i < runIDs.size() - 1 && i < 2) std::cout << ", ";
        }
        if (runIDs.size() > 3) std::cout << ", ...";
        std::cout << ")" << std::endl;
        
        for (int runID : runIDs) {
            gRunToFolder[runID] = folder;
        }
    }
    
    std::cout << "\nTotal runs mapped: " << gRunToFolder.size() << std::endl;
    
    // Step 2: Load all cut files and map them
    std::cout << "\nStep 2: Loading cut files..." << std::endl;
    
    dirp = gSystem->OpenDirectory(cutPath.c_str());
    if (!dirp) {
        std::cerr << "ERROR: Cannot open cut directory: " << cutPath << std::endl;
        return;
    }
    
    int cutCount = 0;
    
    while ((entry = gSystem->GetDirEntry(dirp))) {
        std::string filename(entry);
        
        // Skip non-cpp files
        if (filename.find(".cpp") == std::string::npos) continue;
        if (filename == "." || filename == "..") continue;
        
        // Parse filename: ParticleDetectorCut_folder.cpp
        std::string particle, detector;
        std::string folder = ExtractFolderFromCutFile(filename);
        
        if (folder.empty()) continue;
        
        // Extract particle and detector
        if (filename.find("Proton") == 0) {
            particle = "Proton";
            if (filename.find("ProtonFwd") == 0) detector = "Fwd";
            else if (filename.find("ProtonCnt") == 0) detector = "Cnt";
        } else if (filename.find("Pion") == 0) {
            particle = "Pion";
            if (filename.find("PionFwd") == 0) detector = "Fwd";
            else if (filename.find("PionCnt") == 0) detector = "Cnt";
        } else if (filename.find("Deuteron") == 0) {
            particle = "Deuteron";
            if (filename.find("DeuteronFwd") == 0) detector = "Fwd";
            else if (filename.find("DeuteronCnt") == 0) detector = "Cnt";
        }
        
        if (particle.empty() || detector.empty()) continue;
        
        // Load the cut by executing the file
        std::string cutFilePath = cutPath + "/" + filename;
        
        // Load the macro
        int error = 0;
        TCutG* cut = (TCutG*)gROOT->ProcessLine(Form(".x %s", cutFilePath.c_str()), &error);
        
        if (error != 0) {
            std::cerr << "✗ Error loading: " << filename << std::endl;
            continue;
        }
        
        if (cut) {
            std::cout << "  Loaded: " << particle << " " << detector << " for " << folder 
                      << " (" << cut->GetName() << ", " << cut->GetN() << " points) " << cut->GetPointX(0)<< std::endl;
            
            // Map this cut to all runs in the corresponding folder
            for (const auto& runPair : gRunToFolder) {
                if (runPair.second == folder) {
                    gCutMap[particle][detector][runPair.first] = cut;
                }
            }
            cutCount++;
        } else {
            std::cout << "  WARNING: Could not find cut object for " << filename << std::endl;
        }
    }
    
    gSystem->FreeDirectory(dirp);
    
    std::cout << "\n==================================" << std::endl;
    std::cout << "Cut map built successfully!" << std::endl;
    std::cout << "Loaded " << cutCount << " cut files" << std::endl;
    std::cout << "==================================" << std::endl;
}

// Helper function to print the mapping for debugging
void PrintCutMap() {
    std::cout << "\n=== Cut Map Summary ===" << std::endl;
    std::cout << gCutMap.size() << std::endl;
    for (const auto& particleMap : gCutMap) {
        std::cout << "\nParticle: " << particleMap.first << std::endl;
        for (const auto& detectorMap : particleMap.second) {
            std::cout << "  Detector: " << detectorMap.first << std::endl;
            std::cout << "    Runs (" << detectorMap.second.size() << "): ";
            int count = 0;
            for (const auto& cutPair : detectorMap.second) {
                if (count < 5) std::cout << cutPair.first << " ";
                count++;
            }
            if (count > 5) std::cout << "...";
            std::cout << std::endl;
        }
    }
}

// Function to get a cut for a specific particle, detector, and run ID
TCutG* GetCut(const std::string& particle, const std::string& detector, int runID) {
    
    // Check if particle exists
    auto particleIt = gCutMap.find(particle);
    if (particleIt == gCutMap.end()) {
        std::cerr << "ERROR: Particle '" << particle << "' not found in cut map" << std::endl;
        std::cerr << "Available particles: ";
        for (const auto& p : gCutMap) {
            std::cerr << p.first << " ";
        }
        std::cerr << std::endl;
        return nullptr;
    }
    
    // Check if detector exists for this particle
    auto detectorIt = particleIt->second.find(detector);
    if (detectorIt == particleIt->second.end()) {
        std::cerr << "ERROR: Detector '" << detector << "' not found for particle '" << particle << "'" << std::endl;
        std::cerr << "Available detectors for " << particle << ": ";
        for (const auto& d : particleIt->second) {
            std::cerr << d.first << " ";
        }
        std::cerr << std::endl;
        return nullptr;
    }
    
    // Check if runID exists for this particle/detector combination
    auto cutIt = detectorIt->second.find(runID);
    if (cutIt == detectorIt->second.end()) {
        std::cerr << "ERROR: RunID " << runID << " not found for " << particle << " " << detector << std::endl;
        
        // Try to give helpful information about which folder this run belongs to
        auto folderIt = gRunToFolder.find(runID);
        if (folderIt != gRunToFolder.end()) {
            std::cerr << "Run " << runID << " belongs to folder: " << folderIt->second << std::endl;
            std::cerr << "But no " << particle << " " << detector << " cut exists for this folder" << std::endl;
        } else {
            std::cerr << "Run " << runID << " not found in any folder" << std::endl;
        }
        return nullptr;
    }
    
    // Return the cut
    TCutG* cut = cutIt->second;
    
    // Optional: print success message
    // std::cout << "Retrieved cut: " << cut->GetName() << " for " << particle << " " << detector << " run " << runID << std::endl;
    
    return cut;
}

// Overloaded version with verbose option
TCutG* GetCut(const std::string& particle, const std::string& detector, int runID, bool verbose) {
    TCutG* cut = GetCut(particle, detector, runID);
    
    if (cut && verbose) {
        auto folderIt = gRunToFolder.find(runID);
        std::string folder = (folderIt != gRunToFolder.end()) ? folderIt->second : "unknown";
        
        std::cout << "✓ Retrieved: " << particle << " " << detector << " cut for run " << runID 
                  << " (folder: " << folder << ")" << std::endl;
        std::cout << "  Cut name: " << cut->GetName() << std::endl;
        std::cout << "  Points: " << cut->GetN() << std::endl;
    }
    
    return cut;
}