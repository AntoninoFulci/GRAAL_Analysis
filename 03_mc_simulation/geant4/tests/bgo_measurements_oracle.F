C Harness: routines and BLOCKDATA are compiled unchanged from archived source.
      PROGRAM BGO_MEASUREMENTS_ORACLE
      READ(*,*) NCASES
      DO I=1,NCASES
        CALL BGO_CASE
      ENDDO
      END
      SUBROUTINE BGO_CASE
#include "coeff.inc"
#include "bgo.inc"
#include "barrel.inc"
#include "barrel_calibr.inc"
#include "clus.inc"
#include "pm_b_b.inc"
#include "lflag.inc"
      COMMON /MEMBERS/ NCL,NERROR,COUNTS(480)
      INTEGER COUNTS
      LDATA=.FALSE.
      LSIMUL=.TRUE.
      LCLUS_C=.TRUE.
      LCLUS_F=.FALSE.
      READ(*,*) MBGO,NCL,LDE,NERROR,STHRES,CTHRES,SCBGO,VSCBGO,
     & SCDEB,VSCDEB,SDETOF,VDETOF,ABGIU
      STTHRES=INT((SCBGO/VSCBGO)*STHRES)
      DO I=1,MBGO
        READ(*,*) ITBGO(I),IPBGO(I),EBGO(I)
      ENDDO
      DO I=1,NCL
        READ(*,*) COUNTS(I),(ISTACK_P(I,J),J=1,COUNTS(I))
      ENDDO
      DO I=1,LDE
        READ(*,*) IPLA(I),EPLA(I),TPLA(I)
      ENDDO
      CALL ANABGO
      CALL ANABAR
      WRITE(*,*) 0,NBCLUS,NBCLUS_SP,NBAR
      WRITE(*,*) (IND_BGO(I),I=1,30)
      DO I=1,NBCLUS
        WRITE(*,*) MCLUS(I),ECLUS(I),TETCLUS(I),PHICLUS(I),
     &    ECLUSC(I),TETCLUSC(I),PHICLUSC(I),SX1(I),SY1(I),
     &    SX2(I),SY2(I),IFL(I)
      ENDDO
      DO I=1,NBCLUS_SP
        WRITE(*,*) MCLUS_SP(I),ECLUS_SP(I),TETCLUS_SP(I),
     &    PHICLUS_SP(I),ECLUSC_SP(I),TETCLUSC_SP(I),
     &    PHICLUSC_SP(I),0.,0.,0.,0.,0
      ENDDO
      DO I=1,NBAR
        WRITE(*,*) IBAR(I),IND_BAR(I),EBAR(I),TIMBAR(I)
      ENDDO
      END
      SUBROUTINE COUNT_CLUSTER_CA(NC,NCR,NERR)
      INTEGER NCR(480),COUNTS(480)
      COMMON /MEMBERS/ NCL,NERROR,COUNTS
      NC=NCL
      NERR=NERROR
      DO I=1,NC
        NCR(I)=COUNTS(I)
      ENDDO
      END
      SUBROUTINE COUNT_CLUSTER_FR(NC,NCR,NERR)
      INTEGER NCR(480)
      CALL COUNT_CLUSTER_CA(NC,NCR,NERR)
      END
