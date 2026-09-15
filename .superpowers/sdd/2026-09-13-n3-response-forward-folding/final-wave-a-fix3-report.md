# Final owner-review Wave A fix round 3

Base: `da08d90`

Resolved finding:

- removed post-link destination rollback by name from N2 reconstruction
  inventory publication; inode comparison followed by `unlink(name)` was
  vulnerable to replacement between the final `stat` and `unlink`;
- retained anchored cleanup only for the random owned staging name and closed
  all file descriptors on success and failure;
- retained fail-closed parent identity validation after hard-link creation;
  canonical replacement paths are never accepted and no outside path is
  written;
- documented the namespace-safety tradeoff: when the parent is detached after
  linking, an owned destination link can remain in that detached directory and
  requires operator inspection. Automatic deletion cannot be made safe without
  an atomic conditional unlink primitive.

TDD evidence:

- new deterministic race replaced the destination after ownership `stat` but
  before rollback `unlink`; before the fix, the foreign replacement was
  deleted and the regression test failed;
- after the fix, publication never performs the vulnerable destination
  ownership-stat/rollback sequence;
- direct replacement after the hard link survives; parent-swap failure leaves
  canonical path absent, writes nothing outside the anchored directory, cleans
  the owned staging name, and reports possible detached owned link.

Verification:

- focused inventory builder suite: 13 passed;
- full `08_polarization` suite: 480 passed;
- `make verify`: 360 common/MC/BDT and 473 polarization passed; artifact
  inventory verification passed;
- `make test`: 961 passed with PyROOT;
- `git diff --check`: clean.

No Wave B work and no physics artifact publication performed.
