      PROGRAM ORACLE
#include "corr.inc"
#include "tofwall.inc"
#include "lflag.inc"
#include "pm_b_b.inc"
#include "event.inc"
#include "dime.inc"
#include "att_wall.inc"
#include "tofclus_ale.inc"
#include "rus_wall_nt.inc"
#include "russwall_calibr.inc"
#include "out_russ_wall.inc"
#include "rwur.inc"
#include "out_plan_ch.inc"
#include "track.inc"
#include "pc_cor.inc"
      REAL U(20),V(20),X(20),Y(20)
      INTEGER CL(20),CLTOT,MODE,SIM,NP,IOPT,IOPT1,ICHECK,L1,L2
      READ(*,*) PEDESTALS,TDCCAL,GAINCARDS,TIMEWALK,TDCOFFSET,GAINPMS
      READ(*,*) RT,RB,AY,BY,BT,AE
      READ(*,*) ATTN,ATTS,ATTH
      READ(*,*) ZP1,ZP2,ZP3,IDRUN,IND_BUNCH_RF,SIM
      LDATA=SIM.EQ.0
      LSIMUL=SIM.NE.0
      READ(*,*) MODE,LM1,LM2,MSHO,NP
      DO I=1,LM1
       READ(*,*) IP1(I),EP1(I,1),EP1(I,2),TP1(I,1),TP1(I,2)
      ENDDO
      DO I=1,LM2
       READ(*,*) IP2(I),EP2(I,1),EP2(I,2),TP2(I,1),TP2(I,2)
      ENDDO
      DO I=1,MSHO
       READ(*,*) IP3(I),EP3U(I),EP3D(I),TP3U(I),TP3D(I)
      ENDDO
      NTRA=NP
      DO I=1,NP
       READ(*,*) U(I),V(I),X(I),Y(I),CL(I)
       A1(I)=U(I)
       A2(I)=V(I)
       A3(I)=ZP1
       B1(I)=X(I)
       B2(I)=Y(I)
       B3(I)=ZP2
      ENDDO
      IF(MODE.EQ.5)THEN
       READ(*,*) IOPT,IOPT1
       LM_1=2
       LM_2=2
       DO I=1,3
        IP1_COR(I)=8
        IP2_COR(I)=8
        X_W1(I)=0
        Y_W1(I)=0
        X_W2(I)=0
        Y_W2(I)=0
        A_TOF1(I)=20
        A_TOF2(I)=20
        A_DE1(I)=10
        A_DE2(I)=10
        ENE_L(I)=20
        ENE_R(I)=20
        ENE_U(I)=20
        ENE_D(I)=20
        IASS_W1(I)=0
        IASS_W2(I)=0
        IASS_TRACK(I)=0
        WAL_PAR(:,I)=0
        IND_PAR(:,I)=0
        THETA_W(I)=0
        PHI_W(I)=0
       ENDDO
       IND_WAL=0
       M_WAL=IOPT1
       ICHECK=0
       L1=2
       L2=2
       CALL DOUBLE_BAR(IOPT,1,2,1,IOPT1,ICHECK,L1,L2)
       WRITE(*,*) 'D',ICHECK,M_WAL
       DO I=IOPT1+1,M_WAL
        WRITE(*,*) 'DC',WAL_PAR(:,I),IND_PAR(:,I),THETA_W(I),
     &       PHI_W(I),IASS_TRACK(I)
       ENDDO
      ENDIF
      IF(MODE.EQ.1.OR.MODE.EQ.4)THEN
       CALL WALL_CLUS
       DO I=1,M_WAL
        WAL_PAR(1,I)=MAX(-200.,MIN(200.,WAL_PAR(1,I)))
        WAL_PAR(2,I)=MAX(-200.,MIN(200.,WAL_PAR(2,I)))
       ENDDO
       WRITE(*,*) 'W',M_WAL,LM_1,LM_2,IND_WAL
       DO I=1,M_WAL
        WRITE(*,*) 'WC',WAL_PAR(:,I),IND_PAR(:,I),THETA_W(I),
     &       PHI_W(I),IASS_TRACK(I)
       ENDDO
       DO I=1,LM_1
        WRITE(*,*) 'WH',IP1_COR(I),IASS_W1(I),X_W1(I),Y_W1(I),
     &       A_TOF1(I),A_DE1(I),ENE_L(I),ENE_R(I),TOF_L(I),TOF_R(I)
       ENDDO
       DO I=1,LM_2
        WRITE(*,*) 'WV',IP2_COR(I),IASS_W2(I),X_W2(I),Y_W2(I),
     &       A_TOF2(I),A_DE2(I),ENE_U(I),ENE_D(I),TOF_U(I),TOF_D(I)
       ENDDO
      ENDIF
      IF(MODE.EQ.2.OR.MODE.EQ.4)THEN
       CALL RUSSWALL
       IF(LSIMUL)THEN
        DO I=1,NSHOW
         PHISHOW(I)=180.-PHISHOW(I)
         IF(PHISHOW(I).LT.0)PHISHOW(I)=PHISHOW(I)+360.
         IF(PHISHOW(I).GT.360)PHISHOW(I)=PHISHOW(I)-360.
        ENDDO
       ENDIF
       WRITE(*,*) 'S',NSHOW,N_UR
       DO I=1,NSHOW
        WRITE(*,*) 'SC',XSHOW(I),YSHOW(I),TSHOW(I),ESHOW(I),
     &       TETSHOW(I),PHISHOW(I),TSHPC(I),PSHPC(I),TYPESHOW(I)
       ENDDO
       DO I=1,N_UR
        WRITE(*,*) 'SU',NSH_UR(I),ESH_UR(I),TSH_UR(I)
       ENDDO
      ENDIF
      IF(MODE.EQ.3)THEN
       READ(*,*) M_WAL,NSHOW
       DO I=1,M_WAL
        READ(*,*) WAL_PAR(:,I),IASS_TRACK(I)
       ENDDO
       DO I=1,NSHOW
        READ(*,*) XSHOW(I),YSHOW(I),TSHOW(I),ESHOW(I),PHISHOW(I)
       ENDDO
      ENDIF
      IF(MODE.EQ.3.OR.MODE.EQ.4)THEN
       CLTOT=0
       CALL ANA_WAL(U,V,X,Y,CL,NP,CLTOT)
       WRITE(*,*) 'A',N_TRAF,NPARF,NPARF_C,NPARF_N,
     &       NPARF_STRANGE,IFORW_C,IFORW_N,NPPLN2
       DO I=1,N_TRAF
        WRITE(*,*) 'AM',IASS_TRF(I),IND_TRAF(:,I)
       ENDDO
       DO I=1,NPARF
        WRITE(*,*) 'AP',COS_TRF(:,I),THETA_TRF(I),PHI_TRF(I),
     &       TOF_TRF(I),DE_TRF(I),INDEX_TRF(I),INFO_WAL(I)
       ENDDO
      ENDIF
      END
