C Runtime invariant for the exact historical GTGAMA object in CERNLIB.
C A photon above CUTGAM, with processes disabled and zero requested step,
C must remain alive with unchanged energy. A below-cut photon must stop.
C No detector geometry, event generation, or experimental data needed.
      PROGRAM CUTPROBE
#include "geant321/gccuts.inc"
#include "geant321/gctrak.inc"
#include "geant321/gcphys.inc"
#include "geant321/gctmed.inc"
#include "geant321/gcjloc.inc"
#include "geant321/gcbank.inc"
      DPHYS1=1.
      CUTGAM=1.E-5
      IUPD=1
      STEMAX=0.
      SAFETY=1.
      IPAIR=0
      ICOMP=0
      IPHOT=0
      IRAYL=0
      JPFIS=0
      JSTAK=0
      DO I=1,2
        GEKIN=.1
        IF(I.EQ.2)GEKIN=1.E-6
        GETOT=GEKIN
        VECT(7)=GEKIN
        ISTOP=0
        SLENG=0.
        CALL GTGAMA
        WRITE(*,*) 'TRANSPORT PROBE',I,GEKIN,CUTGAM,ISTOP,SLENG
        IF(I.EQ.1.AND.(GEKIN.NE..1.OR.ISTOP.NE.0))CALL EXIT(1)
        IF(I.EQ.2.AND.(GEKIN.NE.0..OR.ISTOP.NE.2))CALL EXIT(2)
      ENDDO
      WRITE(*,*) 'TRANSPORT PROBE PASS'
      END
