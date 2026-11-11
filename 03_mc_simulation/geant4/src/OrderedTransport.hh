#pragma once
#include "RootOutput.hh"
#include <condition_variable>
#include <exception>
#include <mutex>

// Commit event-local transport tables in source order. Waiting workers retain
// at most their current event; no campaign-sized hit collection or shard merge.
class OrderedTransport {
public:
  struct Counts {
    ULong64_t sensitive = 0, callbacks = 0, passive = 0, stored = 0, cylinder = 0;
  };
  OrderedTransport(RootOutput& output, int expected) : output(output), expected(expected) {}
  void Fail(std::exception_ptr error) {
    std::lock_guard<std::mutex> lock(mutex);
    if (!failure) failure = error;
    ready.notify_all();
  }
  void Check() const {
    std::lock_guard<std::mutex> lock(mutex);
    if (failure) std::rethrow_exception(failure);
  }
  void Submit(int event, RootOutput& buffer, const Counts& count, bool aborted) {
    std::unique_lock<std::mutex> lock(mutex);
    try {
      if (event < next || event >= expected) throw std::runtime_error("Invalid MT event identity");
      ready.wait(lock, [&] { return failure || event <= next; });
      if (failure) std::rethrow_exception(failure);
      if (event != next) throw std::runtime_error("Duplicate MT event identity");
      if (count.callbacks < count.sensitive || count.passive != count.callbacks-count.sensitive
          || count.stored > count.sensitive || count.cylinder > count.stored)
        throw std::runtime_error("Invalid MT event counters");
      Counts sum{Add(total.sensitive,count.sensitive), Add(total.callbacks,count.callbacks),
                 Add(total.passive,count.passive), Add(total.stored,count.stored), Add(total.cylinder,count.cylinder)};
      std::map<std::string,std::map<std::string,ULong64_t>> offsets{
        {"cylinder_step_context", {{"source_step_entry",total.sensitive},
                                  {"callback_index",total.callbacks},{"passive_epoch",total.passive}}}};
      if (compact) offsets["detector_steps"] = {{"source_step_entry",total.sensitive}};
      buffer.DrainTo(output, offsets);
      total = sum;
      ++next;
      if (aborted) ++aborts;
      ready.notify_all();
    } catch (...) {
      if (!failure) failure = std::current_exception();
      ready.notify_all();
      throw;
    }
  }
  void Finish() const {
    Check();
    if (next != expected) throw std::runtime_error("MT replay event count mismatch");
  }
  // Read on the master only after BeamOn has joined all workers.
  Counts total;
  int next = 0, aborts = 0;
  bool compact = false;
private:
  static ULong64_t Add(ULong64_t a, ULong64_t b) {
    if (a > std::numeric_limits<ULong64_t>::max()-b) throw std::runtime_error("MT stream counter overflow");
    return a+b;
  }
  RootOutput& output;
  int expected;
  mutable std::mutex mutex;
  std::condition_variable ready;
  std::exception_ptr failure;
};
