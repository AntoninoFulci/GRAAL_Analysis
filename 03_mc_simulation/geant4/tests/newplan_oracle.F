C Test driver only: archived kernels and COMMON includes remain unmodified.
      PROGRAM NEWPLAN_ORACLE
      INTEGER MODE,CASES,CASEID
      READ(*,*) CASES
      DO CASEID=1,CASES
        READ(*,*) MODE
        IF(MODE.EQ.1) CALL DIGIT_CASE
        IF(MODE.EQ.2) CALL TRACK_CASE
        IF(MODE.EQ.3) CALL SORT_CASE
      ENDDO
      END

      SUBROUTINE DIGIT_CASE
#include "digit/nthit.inc"
#include "digit/chamber_inter.inc"
#include "digit/lagvert.inc"
#include "digit/datvert.inc"
#include "gconsp.inc"
      REAL DRAWS(80)
      INTEGER NDRAW,USED,HIST(80),P,N
      COMMON /TEST_DRAWS/ DRAWS,NDRAW,USED,HIST
      READ(*,*) XP1,XP2,ZP1,ZP2,NF1,NF2,ANGLE
      ANG(5)=ANGLE*DEGRAD
      SANG(5)=SIN(ANG(5))
      CANG(5)=COS(ANG(5))
      MULT3=0
      MULT4=0
      MULT5=0
      MULT6=0
      READ(*,*) N
      DO I=1,N
        READ(*,*) P,XX,YY
        IF(P.EQ.0) THEN
          MULT3=MULT3+1
          XPU(1,MULT3)=XX
          XPU(2,MULT3)=YY
        ELSEIF(P.EQ.1) THEN
          MULT4=MULT4+1
          XPV(1,MULT4)=XX
          XPV(2,MULT4)=YY
        ELSEIF(P.EQ.2) THEN
          MULT5=MULT5+1
          XPX(1,MULT5)=XX
          XPX(2,MULT5)=YY
        ELSE
          MULT6=MULT6+1
          XPY(1,MULT6)=XX
          XPY(2,MULT6)=YY
        ENDIF
      ENDDO
      READ(*,*) NDRAW
      IF(NDRAW.GT.0) READ(*,*) (DRAWS(I),I=1,NDRAW)
      USED=0
      CALL PLCH
      WRITE(*,*) MPCU,MPCV,MPCX,MPCY,USED
      WRITE(*,*) (HIST(I),I=1,USED)
      WRITE(*,*) (WUV(I,1),I=1,MPCU)
      WRITE(*,*) (WUV(I,2),I=1,MPCV)
      WRITE(*,*) (WXY(I,1),I=1,MPCX)
      WRITE(*,*) (WXY(I,2),I=1,MPCY)
      END

      REAL FUNCTION HRNDM(ID)
      REAL DRAWS(80)
      INTEGER NDRAW,USED,HIST(80)
      COMMON /TEST_DRAWS/ DRAWS,NDRAW,USED,HIST
      USED=USED+1
      IF(USED.GT.NDRAW) STOP 22
      HRNDM=DRAWS(USED)
      HIST(USED)=ID-1003
      END

      SUBROUTINE TRACK_CASE
#include "track/chamber.inc"
#include "track/dime.inc"
#include "track/cham_geom.inc"
#include "track/prean_const.inc"
      REAL U(20),V(20),X(20),Y(20)
      INTEGER CL(20),CLTOT,NTRA
      INTEGER MU_RED,MV_RED,MX_RED,MY_RED
      COMMON/MULRED/MU_RED,MV_RED,MX_RED,MY_RED
      READ(*,*) XP1,XP2,ZP1,ZP2,NF1,NF2,ANGLE
      ANG(5)=ANGLE*DEGRAD
      SANG(5)=SIN(ANG(5))
      CANG(5)=COS(ANG(5))
      READ(*,*) MPCU,MPCV,MPCX,MPCY
      IF(MPCU.GT.0) READ(*,*) (WU(I),I=1,MPCU)
      IF(MPCV.GT.0) READ(*,*) (WV(I),I=1,MPCV)
      IF(MPCX.GT.0) READ(*,*) (WX(I),I=1,MPCX)
      IF(MPCY.GT.0) READ(*,*) (WY(I),I=1,MPCY)
C Sentinel initialization makes undefined legacy count paths detectable;
C callers MUST NOT compare endpoint goldens for such cases.
      DO I=1,20
        U(I)=-123456.
        V(I)=-123456.
        X(I)=-123456.
        Y(I)=-123456.
        CL(I)=-999
      ENDDO
      MU_RED=0
      MV_RED=0
      MX_RED=0
      MY_RED=0
      CALL ANAPLN4(U,V,X,Y,CL,NTRA,CLTOT)
      WRITE(*,*) NTRA,CLTOT,MU_RED,MV_RED,MX_RED,MY_RED
      DO I=1,NTRA
        WRITE(*,*) CL(I),TRANSFER(U(I),0),TRANSFER(V(I),0),
     &   TRANSFER(X(I),0),TRANSFER(Y(I),0)
      ENDDO
      END

      SUBROUTINE SORT_CASE
      REAL VALUES(256)
      INTEGER INDICES(256),N
      READ(*,*) N
      IF(N.GT.0) READ(*,*) (VALUES(I),I=1,N)
      CALL SORTZV(VALUES,INDICES,N,1,0,0)
      WRITE(*,*) (INDICES(I)-1,I=1,N)
      END
