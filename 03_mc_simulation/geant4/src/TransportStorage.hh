#pragma once
#include "RootInput.hh"
#include <array>
#include <set>

namespace rootinput {
// Storage-only integrity checks. Full-mode response validation stays in its
// established readers; compact mode validates every retained row even when a
// consumer (e.g. central reconstruction) uses only the event ledger.
class TransportStorage {
  using Key=std::pair<int,int>;
  using Json=nlohmann::json;
  struct Event {
    Key key;
    ULong64_t begin=0,end=0,stored=0,bgo_steps=0,seen=0;
    double total=0,bgo=0,retained_energy=0,aggregate_energy=0;
    std::map<int,double> crystals;
  };
  bool compact_;
  ULong64_t rows_=0;
  std::vector<Event> events_;
  std::map<Key,std::size_t> index_;
  static ULong64_t Add(ULong64_t a,ULong64_t b) {
    Require(b<=std::numeric_limits<ULong64_t>::max()-a,"Storage count overflow"); return a+b;
  }
  static ULong64_t Count(const Json& value,const char* key) {
    const auto& n=value.at(key);
    Require(n.is_number_unsigned() || (n.is_number_integer() && n.get<Long64_t>()>=0),std::string("Expected nonnegative JSON integer storage count ")+key);
    return n.get<ULong64_t>();
  }
  static double Tolerance(double a,double b) {return 1e-9+1e-10*std::max(std::abs(a),std::abs(b));}
  Event& Find(int run,int event,std::size_t& previous) {
    const auto it=index_.find({run,event});
    Require(it!=index_.end() && it->second>=previous,"Orphan/reordered compact event row");
    previous=it->second; return events_[previous];
  }
public:
  explicit TransportStorage(TFile& in):compact_(CompactTransport(in)) {
    auto& steps=Tree(in,"detector_steps"); rows_=steps.GetEntries();
    const auto summary=Json::parse(Text(in,"summary"));
    if(!compact_) {
      Require(Count(summary,"detector_steps")==rows_,"Full detector row count mismatch");
      if(summary.contains("stored_detector_steps")) Require(Count(summary,"stored_detector_steps")==rows_,"Full stored row count mismatch");
      return;
    }
    Require(Count(summary,"stored_detector_steps")==rows_,"Compact stored row count mismatch");
    std::map<std::string,int> roles; std::set<int> crystals;
    {
      TTreeReader r(&Tree(in,"channels")); String path(r,"path");
      Number<int> role(r,"sensitive","Int_t"),copy(r,"copy","Int_t"),channel(r,"legacy_channel","Int_t");
      while(Next(r)) {
        const auto p=path.get(); Require(!p.empty() && p.find('\0')==std::string::npos && role.get()>=1 && role.get()<=14 && roles.emplace(p,role.get()).second,"Invalid compact channel inventory");
        if(role.get()==1) Require(copy.get()>=1 && copy.get()<=480 && channel.get()==copy.get() && crystals.insert(copy.get()).second,"Invalid compact BGO inventory");
      }
    }
    ULong64_t raw=0,callbacks=0,aborted=0,stored=0;
    {
      TTreeReader r(&Tree(in,"events")),s(&Tree(in,"storage_events"));
      Number<int> run(r,"run","Int_t"),event(r,"event","Int_t"),abort(r,"aborted","Int_t"),su(s,"run","Int_t"),sv(s,"event","Int_t");
      Number<ULong64_t> hits(r,"hit_steps","ULong64_t"),calls(r,"steps","ULong64_t"),ss(s,"stored_steps","ULong64_t"),sb(s,"bgo_steps","ULong64_t");
      Number<double> total(r,"total_edep_MeV","Double_t"),bgo(r,"bgo_edep_MeV","Double_t");
      while(Next(r)) {
        const Key key{run.get(),event.get()};
        Require(key.first>=0 && key.second>=0 && (events_.empty() || events_.back().key<key),"Invalid/reordered compact event ledger");
        Require(abort.get()==0 || abort.get()==1,"Invalid compact aborted flag");
        Require(Next(s) && su.get()==key.first && sv.get()==key.second,"Compact storage/event identity mismatch");
        Require(Add(ss.get(),sb.get())==hits.get() && hits.get()<=calls.get(),"Compact storage/event counts mismatch");
        Nonnegative(total.get(),"event energy"); Nonnegative(bgo.get(),"BGO event energy");
        Require(bgo.get()<=total.get()+Tolerance(total.get(),bgo.get()),"Compact BGO exceeds event energy");
        Event e; e.key=key;e.begin=raw;e.end=Add(raw,hits.get());e.stored=ss.get();e.bgo_steps=sb.get();e.total=total.get();e.bgo=bgo.get();
        index_.emplace(key,events_.size());events_.push_back(std::move(e));
        raw=Add(raw,hits.get());callbacks=Add(callbacks,calls.get());stored=Add(stored,ss.get());aborted=Add(aborted,abort.get());
      }
      Require(!Next(s),"Trailing compact storage event");
    }
    Require(stored==rows_ && raw==Count(summary,"detector_steps") && callbacks==Count(summary,"all_callbacks") &&
      callbacks-raw==Count(summary,"passive_callbacks") && events_.size()==Count(summary,"attempted_events") &&
      aborted==Count(summary,"aborted") && events_.size()-aborted==Count(summary,"events"),"Compact summary/event accounting mismatch");
    {
      TTreeReader r(&Tree(in,"bgo_hits")); Number<int> run(r,"run","Int_t"),event(r,"event","Int_t"),crystal(r,"crystal","Int_t");
      Number<double> energy(r,"edep_MeV","Double_t"),time(r,"first_time_ns","Double_t");
      std::size_t previous=0;
      while(Next(r)) {
        auto& e=Find(run.get(),event.get(),previous);const double value=energy.get();
        Nonnegative(value,"BGO aggregate energy");Nonnegative(time.get(),"BGO aggregate time");
        Require(value>0 && crystals.count(crystal.get()) && e.crystals.emplace(crystal.get(),value).second,"Invalid/duplicate compact BGO crystal");
        e.aggregate_energy+=value;Nonnegative(e.aggregate_energy,"BGO aggregate sum");
        Require(e.crystals.size()<=e.bgo_steps,"More BGO crystals than original BGO steps");
      }
    }
    {
      TTreeReader r(&steps);Number<int> run(r,"run","Int_t"),event(r,"event","Int_t"),track(r,"track","Int_t"),parent(r,"parent","Int_t"),step(r,"track_step","Int_t");
      Number<int> pre(r,"pre_boundary","Int_t"),post(r,"post_boundary","Int_t"),pres(r,"pre_status","Int_t"),posts(r,"post_status","Int_t"),status(r,"track_status","Int_t");
      Number<ULong64_t> source(r,"source_step_entry","ULong64_t");String path(r,"path");
      Number<double> energy(r,"edep_MeV","Double_t"),pretime(r,"pre_time_ns","Double_t"),posttime(r,"post_time_ns","Double_t");
      std::vector<std::unique_ptr<Number<double>>> finite;
      for(const char* k:{"charge_e","pre_x_mm","pre_y_mm","pre_z_mm","post_x_mm","post_y_mm","post_z_mm"}) finite.push_back(std::make_unique<Number<double>>(r,k,"Double_t"));
      std::size_t previous=0;ULong64_t prior=0;bool first=true;std::map<int,int> track_steps;
      while(Next(r)) {
        const auto old=previous;auto& e=Find(run.get(),event.get(),previous);if(previous!=old)track_steps.clear();
        const auto ch=roles.find(path.get());Require(ch!=roles.end() && ch->second!=1,"Compact step has unknown/BGO path");
        Require(source.get()>=e.begin && source.get()<e.end && (first || source.get()>prior),"Invalid/reordered original sensitive index");
        first=false;prior=source.get();
        Require(track.get()>0 && parent.get()>=0 && step.get()>track_steps[track.get()],"Invalid/reordered compact track step");track_steps[track.get()]=step.get();
        Require((pre.get()==0 || pre.get()==1) && (post.get()==0 || post.get()==1) && pres.get()>=0 && pres.get()<=7 && posts.get()>=0 && posts.get()<=7 && status.get()>=0 && status.get()<=5,"Invalid compact step status");
        Nonnegative(energy.get(),"compact deposit");Nonnegative(pretime.get(),"compact pre time");Nonnegative(posttime.get(),"compact post time");
        Require(posttime.get()>=pretime.get(),"Reversed compact step time");for(auto& f:finite)Require(std::isfinite(f->get()),"Nonfinite compact observable");
        ++e.seen;e.retained_energy+=energy.get();Nonnegative(e.retained_energy,"compact sensitive energy");
      }
    }
    for(const auto& e:events_) {
      Require(e.seen==e.stored,"Compact per-event stored row mismatch");
      Require(std::abs(e.aggregate_energy-e.bgo)<=Tolerance(e.aggregate_energy,e.bgo),"Compact BGO aggregate/ledger mismatch");
      const double sensitive=e.retained_energy+e.aggregate_energy;Nonnegative(sensitive,"compact total sensitive energy");
      Require(sensitive<=e.total+Tolerance(sensitive,e.total),"Compact sensitive energy exceeds event ledger");
    }
  }
  bool compact() const {return compact_;}
  ULong64_t rows() const {return rows_;}
  ULong64_t stored(int run,int event,ULong64_t full_count) const {return compact_?events_.at(index_.at({run,event})).stored:full_count;}
  double omitted_bgo(int run,int event) const {return compact_?events_.at(index_.at({run,event})).aggregate_energy:0.;}
  std::array<double,480> bgo(int run,int event) const {
    std::array<double,480> result{};
    if(compact_) for(const auto& item:events_.at(index_.at({run,event})).crystals)result[item.first-1]=item.second;
    return result;
  }
};
class SourceEntry {
  TTreeReader& reader_;
  std::unique_ptr<Number<ULong64_t>> original_;
public:
  SourceEntry(TTreeReader& reader,const TransportStorage& storage):reader_(reader) {
    if(storage.compact())original_=std::make_unique<Number<ULong64_t>>(reader,"source_step_entry","ULong64_t");
  }
  ULong64_t get() {return original_?original_->get():ULong64_t(reader_.GetCurrentEntry());}
};
} // namespace rootinput
