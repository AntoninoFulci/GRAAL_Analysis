C Driver only. All response routines and includes compiled unchanged.
      PROGRAM CYLINDER_RESPONSE_ORACLE
#include "nthit.inc"
#include "chamber_inter.inc"
#include "lagvert.inc"
#include "datvert.inc"
#include "datcyc.inc"
#include "c_strip.inc"
      REAL GN(10000),GE(10000)
      INTEGER NG,NE,UG,UE,HIST(10000),NCASE,ICASE,N,CH
      COMMON /TEST_RANDOM/ GN,GE,NG,NE,UG,UE,HIST
      READ(*,*) NCASE
      DO ICASE=1,NCASE
        READ(*,*) RC1,RC2,ZC1,ZC2,PC1,PC2,NFC1,NFC2,
     &    NB1,NB2,NB3,NB4,BL,DFCA,SCCAT,VSCCAT,CONV,CYTHRE,
     &    SIGCE(1),SIGCE(2),SIGCE(3),SIGCE(4),SIGCT,
     &    ANG(1),ANG(2),ANG(3),ANG(4),EFFCYC(1),EFFCYC(2),NBORD
        ANG(5)=0.
        UC(5)=1.
        CALL LAGFILL
        MULT1=0
        MULT2=0
        READ(*,*) N
        DO I=1,N
          READ(*,*) CH,X,Y,Z,E
          IF(CH.EQ.0)THEN
            MULT1=MULT1+1
            XCI(1,MULT1)=X
            XCI(2,MULT1)=Y
            XCI(3,MULT1)=Z
            DECI(MULT1)=E
          ELSE
            MULT2=MULT2+1
            XCE(1,MULT2)=X
            XCE(2,MULT2)=Y
            XCE(3,MULT2)=Z
            DECE(MULT2)=E
          ENDIF
        ENDDO
        READ(*,*) NG
        IF(NG.GT.0) READ(*,*) (GN(I),I=1,NG)
        READ(*,*) NE
        IF(NE.GT.0) READ(*,*) (GE(I),I=1,NE)
        UG=0
        UE=0
        CALL CYCH_OLD
        WRITE(*,*) MCCI,MCCE,UG,UE
        WRITE(*,*) (HIST(I),I=1,UE)
        WRITE(*,*) (WCI(I),I=1,MCCI)
        WRITE(*,*) (WCE(I),I=1,MCCE)
        DO J=1,2
          IF(J.EQ.1)THEN
            NBJ=NB1
          ELSE
            NBJ=NB2
          ENDIF
          WRITE(*,*) MBCI(J)
          WRITE(*,*) (IBCI(I,J),CBCI(I,J),I=1,MBCI(J))
          WRITE(*,*) (TRANSFER(BCI(I,J),1),I=1,NBJ)
          WRITE(*,*) (INT_M(READI(I,J)),I=1,NBJ)
        ENDDO
        DO J=1,2
          IF(J.EQ.1)THEN
            NBJ=NB3
          ELSE
            NBJ=NB4
          ENDIF
          WRITE(*,*) MBCE(J)
          WRITE(*,*) (IBCE(I,J),CBCE(I,J),I=1,MBCE(J))
          WRITE(*,*) (TRANSFER(BCE(I,J),1),I=1,NBJ)
          WRITE(*,*) (INT_M(READE(I,J)),I=1,NBJ)
        ENDDO
      ENDDO
      END

      INTEGER FUNCTION INT_M(L)
      LOGICAL L
      INT_M=0
      IF(L)INT_M=1
      END

      SUBROUTINE NORRAN(VALUE)
      REAL GN(10000),GE(10000),VALUE
      INTEGER NG,NE,UG,UE,HIST(10000)
      COMMON /TEST_RANDOM/ GN,GE,NG,NE,UG,UE,HIST
      UG=UG+1
      IF(UG.GT.NG)STOP 21
      VALUE=GN(UG)
      END

      REAL FUNCTION HRNDM(ID)
      REAL GN(10000),GE(10000)
      INTEGER NG,NE,UG,UE,HIST(10000)
      COMMON /TEST_RANDOM/ GN,GE,NG,NE,UG,UE,HIST
      UE=UE+1
      IF(UE.GT.NE)STOP 22
      HRNDM=GE(UE)
      HIST(UE)=ID
      END
