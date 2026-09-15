# Final owner-review Wave A fix round 1

Base: `91bd349`

Resolved findings:

- aligned S4 artifact-inventory validation with canonical
  `write_fit_evidence`/`validate_fit_evidence` basename records inside the
  exact fit-release directory; canonical serialization fixtures now reject
  the former repository-relative record paths;
- rejected lexical parent components before any N2 inventory output
  directory or file is created;
- replaced path-based N2 staging/publication with repository-anchored
  directory descriptors opened using `O_DIRECTORY|O_NOFOLLOW`, relative
  `mkdir`/`open`/`link`/`unlink`, and parent device/inode revalidation before
  staging, before publication, and after publication;
- preserved exclusive hard-link no-replace and byte-identical reuse while
  failing closed for dangling links, swapped parents, and foreign
  destinations; cleanup addresses only the owned random staging name through
  its retained directory descriptor.

TDD evidence:

- canonical S4 basename fixtures failed against the old repository-relative
  expectation;
- lexical `nested/../inventory.json` and escaping `../` outputs were accepted
  before the fix;
- deterministic parent replacement during publication reached path-based
  source/destination names before the fix;
- focused inventory suites pass after the fix, including parent replacement
  during directory creation, staging, and hard-link publication.

Verification:

- focused inventory suites: 43 passed;
- coupled inventory/reco/end-to-end/fit-evidence suites: 75 passed;
- `make verify`: 360 common/MC/BDT and 471 polarization passed, artifact
  inventory verification passed;
- `make test`: 959 passed with PyROOT;
- `git diff --check`: clean.

No Wave B work and no physics artifact publication performed.
