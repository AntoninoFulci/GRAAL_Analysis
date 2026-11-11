      PROGRAM COMPACTION_ORACLE
#include "lagcoor.inc"
#include "lagmult.inc"
      INTEGER ROLE,NUMBER(1),LMEC(1),NMEC,NLEVEL
      COMMON /RAWSTEP/ DESTEP,VECT(3),TOFG,ROLE,NUMBER,NLEVEL,LMEC,NMEC
      READ(*,*) NCASES
      NMEC=1
      LMEC(1)=0
      NLEVEL=1
      DO IC=1,NCASES
        LWAH=0
        LWAV=0
        LCAL=0
        READ(*,*) ROLE,NSTEP
        DO I=1,NSTEP
          READ(*,*) NUMBER(1),DESTEP,POS,TOFG
          VECT(1)=POS
          VECT(2)=POS
          CALL COMPACT_STEP
        ENDDO
        CALL COMPACT_FINISH
        IF(ROLE.EQ.3) THEN
          WRITE(*,*) LWAH
          DO I=1,LWAH
            WRITE(*,*) NWAH(I),TRANSFER(EWAH(I),0),
     &        TRANSFER(XWAH(I),0),TRANSFER(TWAH(I),0)
          ENDDO
        ELSEIF(ROLE.EQ.4) THEN
          WRITE(*,*) LWAV
          DO I=1,LWAV
            WRITE(*,*) NWAV(I),TRANSFER(EWAV(I),0),
     &        TRANSFER(XWAV(I),0),TRANSFER(TWAV(I),0)
          ENDDO
        ELSE
          WRITE(*,*) LCAL
          DO I=1,LCAL
            WRITE(*,*) NCAL(I),TRANSFER(ECAL(I),0),
     &        TRANSFER(XCAL(I),0),TRANSFER(TCAL(I),0)
          ENDDO
        ENDIF
      ENDDO
      END
