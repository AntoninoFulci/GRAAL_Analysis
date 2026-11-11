      PROGRAM FORWARD_ORACLE
#include "nthit.inc"
#include "corr.inc"
#include "tofwall.inc"
#include "russ_wall_nt.inc"
      REAL DRAW(10000)
      INTEGER NDRAW,CURSOR,WCOUNT,SCOUNT,FLAG
      COMMON /RNG/ DRAW,NDRAW,CURSOR
      READ(*,*) PEDESTALS,TDCCAL,GAINCARDS,TIMEWALK,TDCOFFSET,GAINPMS
      READ(*,*) NCASES
      DO IC=1,NCASES
        READ(*,*) LWAH,LWAV,LCAL
        DO I=1,LWAH
          READ(*,*) NWAH(I),EWAH(I),XWAH(I),TWAH(I)
        ENDDO
        DO I=1,LWAV
          READ(*,*) NWAV(I),EWAV(I),XWAV(I),TWAV(I)
        ENDDO
        DO I=1,LCAL
          READ(*,*) NCAL(I),ECAL(I),XCAL(I),TCAL(I)
        ENDDO
        READ(*,*) NDRAW
        READ(*,*) (DRAW(I),I=1,NDRAW)
        CURSOR=0
        TP1=-777
        TP2=-777
        CALL WALL
        WCOUNT=CURSOR
        CALL SHOW
        SCOUNT=CURSOR-WCOUNT
        WRITE(*,*) WCOUNT,SCOUNT
        WRITE(*,*) LM1
        DO I=1,LM1
          FLAG=0
          IF(TP1(I,1).EQ.-777.OR.TP1(I,2).EQ.-777) THEN
            FLAG=4
            TP1(I,1)=0
            TP1(I,2)=0
          ENDIF
          WRITE(*,*) IP1(I),EP1(I,1),EP1(I,2),TP1(I,1),TP1(I,2),FLAG
        ENDDO
        WRITE(*,*) LM2
        DO I=1,LM2
          FLAG=0
          IF(TP2(I,1).EQ.-777.OR.TP2(I,2).EQ.-777) THEN
            FLAG=4
            TP2(I,1)=0
            TP2(I,2)=0
          ENDIF
          WRITE(*,*) IP2(I),EP2(I,1),EP2(I,2),TP2(I,1),TP2(I,2),FLAG
        ENDDO
        WRITE(*,*) MSHO
        DO I=1,MSHO
          WRITE(*,*) IP3(I),EP3U(I),EP3D(I),TP3U(I),TP3D(I),0
        ENDDO
      ENDDO
      END
      SUBROUTINE NORRAN(R)
      REAL R,DRAW(10000)
      INTEGER NDRAW,CURSOR
      COMMON /RNG/ DRAW,NDRAW,CURSOR
      CURSOR=CURSOR+1
      IF(CURSOR.GT.NDRAW) STOP 11
      R=DRAW(CURSOR)
      END
