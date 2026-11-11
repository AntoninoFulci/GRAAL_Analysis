#include "../src/OrderedTransport.hh"
#include "TROOT.h"
#include <future>
#include <chrono>

void book(RootOutput& out, int event = -1) {
  auto& context = out.Book("cylinder_step_context", {{"run",0},{"event",0},
    {"source_step_entry",ULong64_t{0}},{"callback_index",ULong64_t{0}},{"passive_epoch",ULong64_t{0}}});
  auto& steps = out.Book("detector_steps", {{"run",0},{"event",0},{"source_step_entry",ULong64_t{0}}});
  if (event >= 0) {
    context.Fill({0,event,ULong64_t{0},ULong64_t{1},ULong64_t{1}});
    steps.Fill({0,event,ULong64_t{0}});
  }
}

int main(int argc, char** argv) {
  try {
    if (argc != 3) return 2;
    ROOT::EnableThreadSafety();
    RootOutput output(argv[1]);
    book(output);
    OrderedTransport writer(output, 2);
    writer.compact = true;
    RootOutput first(RootOutput::Buffered{}), second(RootOutput::Buffered{});
    book(first,0); book(second,1);
    auto waiting = std::async(std::launch::async, [&] {
      try { writer.Submit(1,second,{1,3,2,1,1},false); return true; }
      catch (...) { return false; }
    });
    if (waiting.wait_for(std::chrono::milliseconds(30)) != std::future_status::timeout)
      throw std::runtime_error("Later event committed before first");
    if (std::string(argv[2]) == "failure") {
      writer.Fail(std::make_exception_ptr(std::runtime_error("injected worker failure")));
      if (waiting.wait_for(std::chrono::seconds(2)) != std::future_status::ready || waiting.get())
        throw std::runtime_error("Waiting worker did not cancel");
      try { writer.Finish(); } catch (const std::runtime_error&) { return 0; }
      throw std::runtime_error("Failed writer reported completion");
    }
    writer.Submit(0,first,{2,4,2,1,1},false);
    if (!waiting.get()) throw std::runtime_error("Ordered worker failed");
    writer.Finish();
    if (writer.total.callbacks != 7 || writer.total.sensitive != 3 || writer.total.passive != 4)
      throw std::runtime_error("Wrong aggregate counters");
    output.Finish("{}");
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n'; return 1;
  }
}
