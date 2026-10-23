C     Geometry-only reference: no generator, transport, trigger or digitizer.
      PROGRAM GEOMETRY_REFERENCE
      PARAMETER (NWGEAN=3000000,NWPAW=3000000)
      COMMON /GCBANK/ GEANT(NWGEAN)
      COMMON /PAWC/ PAW(NWPAW)
#include "flag_comp.inc"
#include "lagtarg.inc"
#include "geant321/gcvolu.inc"
      REAL X(3)
      INTEGER MED
      CALL GZEBRA(NWGEAN)
      CALL HLIMIT(-NWPAW)
      CALL GINIT
      CALL GZINIT
C     The image card has TARG 2 2 and PDEC 0 0 0.
      ICIBLE(1)=2
      ICIBLE(2)=2
      THLENGTH=6.12
      DO J=1,3
        XYZ_DEC(J)=0.
      ENDDO
      OPEN(77,FILE='/work/geometry.g3',STATUS='NEW')
      CALL LAGMAT
      CALL LAGTMP
      CALL UGEOM
      CLOSE(77)
      OPEN(78,FILE='/work/navigation.g3',STATUS='NEW')
      OPEN(79,FILE='/work/points.txt',STATUS='OLD')
   10 READ(79,*,END=20) X
C     Reset the hint: point location must not depend on the preceding query.
      NLEVEL=0
      CALL GMEDIA(X,MED)
      WRITE(78,100) X,MED,NLEVEL,
     +             (NAMES(J),NUMBER(J),J=1,NLEVEL)
      GOTO 10
   20 CLOSE(78)
      CLOSE(79)
      PRINT *, 'GEOMETRY_REFERENCE_COMPLETE'
  100 FORMAT(3(1X,E24.16),2I8,15(1X,A4,I8))
      END
