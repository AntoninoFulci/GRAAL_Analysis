#include "../CutManager.h"

#include <iostream>

void test_cut_manager() {
    gRunToFolder.clear();
    gRunToFolder[4577] = "2005_d1";
    gRunToFolder[4584] = "2005_d1";
    gRunToFolder[4606] = "2005_d1";
    gRunToFolder[4608] = "2005_d2";

    const bool passed =
        IsForwardExcluded(4577) &&
        IsForwardExcluded(4584) &&
        IsForwardExcluded(4606) &&
        !IsForwardExcluded(4608) &&
        !IsForwardExcluded(9999);

    if (!passed) {
        std::cerr << "FAIL: charged-forward exclusion must follow the 2005_d1 folder"
                  << std::endl;
        gSystem->Exit(1);
    }

    std::cout << "PASS: charged-forward exclusion follows the 2005_d1 folder"
              << std::endl;
    gSystem->Exit(0);
}
