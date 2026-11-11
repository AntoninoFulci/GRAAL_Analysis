#include "RootReplay.hh"
#include <iostream>

int main(int argc, char** argv) {
  try {
    if (argc != 2) throw std::runtime_error("Expected truth ROOT path");
    const rootreplay::Input input(argv[1]);
    nlohmann::json result = nlohmann::json::array();
    for (const auto& event : input.events()) {
      nlohmann::json particles = nlohmann::json::array();
      for (const auto& p : event.primaries)
        particles.push_back({p.pdg, p.px, p.py, p.pz, p.energy, p.mass});
      result.push_back({{"energy", event.energy}, {"primaries", particles}});
    }
    std::cout << result.dump() << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
