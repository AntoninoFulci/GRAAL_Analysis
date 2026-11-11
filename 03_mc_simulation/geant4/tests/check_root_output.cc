// Exercise the real writer across basket flushes and OS-level storage failures.
#include "../src/RootOutput.hh"
#include <random>

int main(int argc, char** argv) {
  try {
    if (argc != 2) return 2;
    RootOutput output(argv[1]);
    auto& rows = output.Book("rows", {{"id", ULong64_t{0}}, {"energy", 0.}, {"name", std::string{}}});
    std::mt19937_64 random(20261109);
    std::uniform_real_distribution<double> energy(0., 1000.);
    for (ULong64_t i = 0; i < 20000; ++i)
      rows.Fill({(ULong64_t{1} << 53) + i, energy(random), std::string("channel")});
    output.Finish("{\"status\":\"writer_test_complete\"}");
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "ERROR: " << error.what() << '\n';
    return 1;
  }
}
