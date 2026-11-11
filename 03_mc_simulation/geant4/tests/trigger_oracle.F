C Test driver only. Archived TRIG and all COMMON includes are unmodified.
      PROGRAM TRIGGER_ORACLE
#include "tofwall_nt.inc"
#include "barrel.inc"
#include "itrig.inc"
      LOGICAL ACCEPTED
      INTEGER CASES,CASEID
      READ(*,*) CASES
      DO CASEID=1,CASES
        READ(*,*) ETOTR,ETOTSEUIL,LM1,LM2,LDE
        CALL TRIG(ACCEPTED)
        WRITE(*,*) ITRIG,MERGE(1,0,ACCEPTED)
      ENDDO
      END
