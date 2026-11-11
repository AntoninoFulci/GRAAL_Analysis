C Driver only. Production association routines are copied byte-for-byte.
      PROGRAM CENTRAL_ASSOCIATION_ORACLE
      INTEGER CASES
      READ(*,*) CASES
      DO I=1,CASES
         CALL CENTRAL_CASE
      ENDDO
      END
      SUBROUTINE CENTRAL_CASE
#include "angle.inc"
#include "pm_b_b.inc"
#include "parametres_cylindres.inc"
#include "traces_cylindres.inc"
#include "ass_cbb.inc"
#include "coeff.inc"
      INTEGER ISP,IAA
      READ(*,*) NBCLUS,NBCLUS_SP,NBAR,NB_TRACES_CYL,ISP
      DO I=1,32
         READ(*,*) PHI(I),XBA1(I)
      ENDDO
      DO I=1,NBCLUS
         READ(*,*) TETCLUSC(I),PHICLUSC(I),TETCLUS(I),
     &    PHICLUS(I),ECLUSC(I)
      ENDDO
      DO I=1,NBCLUS_SP
         READ(*,*) TETCLUSC_SP(I),PHICLUSC_SP(I),TETCLUS_SP(I),
     &    PHICLUS_SP(I),ECLUS_SP(I)
      ENDDO
      DO I=1,NBAR
         READ(*,*) IBAR(I),IND_BAR(I),EBAR(I),TIMBAR(I)
      ENDDO
      DO I=1,NB_TRACES_CYL
         READ(*,*) TETA_TRACE_CYL(I),PHI_TRACE_CYL(I)
      ENDDO
C Source-defined configuration from read_option.F:164-181. No gains guessed.
      BAR_PROB(-6)=4
      BAR_PROB(-5)=3
      BAR_PROB(-4)=-10
      BAR_PROB(-3)=-10
      BAR_PROB(-2)=-10
      BAR_PROB(-1)=2
      BAR_PROB(0)=1
      IAA=0
      DO K=0,2
         DO I=0,4
            DO J=0,1
               IAA=IAA+1
               TYPE_ARRAY(J,I,K)=IAA
            ENDDO
         ENDDO
      ENDDO
C Never execute the undefined IOUT_TET input domain.
      IF((NBCLUS+NBCLUS_SP.GT.0).AND.(NBAR.GT.0).AND.
     &   (NB_TRACES_CYL.EQ.0)) STOP 91
      CALL FIND_TRACK_CBB
      WRITE(*,*) 0,NASS_2,NASS_3,
     & NBCLUS+NBCLUS_SP+NBAR+NB_TRACES_CYL
      DO I=1,NASS_2
         WRITE(*,*) IASS_2(1,I),IASS_2(2,I)
      ENDDO
      DO I=1,NASS_3
         WRITE(*,*) IASS_3(1,I),IASS_3(2,I),IASS_3(3,I),
     &    ITIPO_TRACK(I),I_BAR_TRACK(I),IND_BAR_TRACK(I),
     &    TRANSFER(DEDX_TRACK(I),0),TRANSFER(T_BAR_TRACK(I),0),
     &    TRANSFER(PHI_BAR_TRACK(I),0),TRANSFER(ECLUSC_TRACK(I),0),
     &    TRANSFER(THET_BGO_TRACK(I),0),TRANSFER(PHI_BGO_TRACK(I),0),
     &    TRANSFER(THET_CYL_TRACK(I),0),TRANSFER(PHI_CYL_TRACK(I),0),
     &    TRANSFER(THET_CENTR_TRACK(I),0),TRANSFER(PHI_CENTR_TRACK(I),0)
      ENDDO
      END
