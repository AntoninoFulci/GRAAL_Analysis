#ifndef GRAAL_RAW_TRACK_CONTRACT_H
#define GRAAL_RAW_TRACK_CONTRACT_H

#include <stdexcept>
#include <string>
#include <TTree.h>
#include <TLeaf.h>

namespace graal_raw_tracks {

inline void CheckTaggerCount(int count) {
    if (count < 0 || count > 128)
        throw std::runtime_error("Raw tagger count outside PreAnalysis array capacity");
}

inline void CheckCounts(int central, int forward, int associations) {
    if (central < 0 || central > 291 || forward < 0 || forward > 90 ||
        associations < 0 || associations > 90)
        throw std::runtime_error("Raw-track count outside PreAnalysis array capacity");
}

// Preserve the existing zero -> first association behavior until its physical
// meaning is confirmed. This function checks memory safety, not track quality.
inline int LegacyAssociationIndex(unsigned char raw, int count) {
    const int index = raw == 0 ? 0 : raw - 1;
    if (index >= count)
        throw std::runtime_error("Index_trf lookup outside Iass_trf; raw sentinel definition required");
    return index;
}

inline void CheckSchema(TTree *tree) {
    struct Field { const char *name; const char *type; const char *count; };
    for (const auto &field : {
             Field{"Ncstrip", "Int_t", ""},
             Field{"Eg_tag_strip", "Float_t", "Ncstrip"},
             Field{"Xstrip", "Float_t", "Ncstrip"},
             Field{"Nass_3", "Int_t", ""}, Field{"Nparf", "Int_t", ""},
             Field{"N_traf", "Int_t", ""}, Field{"Nparf_strange", "UChar_t", ""},
             Field{"Itipo_track", "Int_t", "Nass_3"},
             Field{"Index_trf", "UChar_t", "Nparf"},
             Field{"Iass_trf", "UChar_t", "N_traf"}}) {
        auto *leaf = tree->GetLeaf(field.name);
        if (!leaf || !tree->GetBranchStatus(field.name) ||
            std::string(leaf->GetTypeName()) != field.type || leaf->GetLenStatic() != 1 ||
            std::string(leaf->GetLeafCount() ? leaf->GetLeafCount()->GetName() : "") != field.count)
            throw std::runtime_error(std::string("Missing/disabled/incompatible raw-track branch: ") + field.name);
    }
}

} // namespace graal_raw_tracks
#endif
