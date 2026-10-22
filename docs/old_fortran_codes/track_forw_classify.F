#include "GRAAL_machine.h"
#include "../pilot.h"
C*********************************************************
      SUBROUTINE TRACK_FORW_CLASSIFY(LTRACK_FORW)
C*********************************************************
#include "event.inc"
#include "track.inc"
#include "trackforw.inc"
#include "lflag_sd.inc"
#include "etadeu_const.inc"
#include "pc_cor.inc"
#include "out_russ_wall.inc"

**************************************************************************
*  IFORW_CLASS(K) = 1                                                    *
* NEUTRON:                                                               *
* 1) AFTER THE TOF CUT IT CAN BE IDENTIFIED AS THE NEUTRON IN            *
*    COINCIDENCE WITH A GOOD ETA INVARIANT MASS                          *
* ==> NFORW_NEUTRON  IFO_NEUTRON                                         *
*                                                                        * 
*   IASS_TRF = 1  (RW)                                                   *
*                                                                        * 
**************************************************************************


**************************************************************************
*  IFORW_CLASS(K) = 2                                                    *
* PROTON:                                                                *
* 1) AFTER THE BIDIM. CUT DE_TRF%TOF_TRF IT CAN BE IDENTIFIED            *
*    AS THE PROTON IN COINCIDENCE WITH A GOOD ETA INVARIANT MASS         * 
* ==> NFORW_PROTON  IFO_PROTON                                           *
*                                                                        * 
*   IASS_TRF = 6 (PC-OW) OR 7 (PC-OW-RW)                                 *
*                                                                        * 
**************************************************************************


**************************************************************************
*  IFORW_CLASS(K) = 3                                                    *
* PION:                                                                  *
* 1) AFTER THE BIDIM. CUT DE_TRF%TOF_TRF IT CAN BE IDENTIFIED            *
*    AS THE PROTON IN COINCIDENCE WITH A GOOD ETA INVARIANT MASS         * 
* ==> NFORW_PION  IFO_PION                                               *
*                                                                        * 
*   IASS_TRF = 6 (PC-OW) OR 7 (PC-OW-RW)                                 *
*                                                                        * 
**************************************************************************


**************************************************************************
*  IFORW_CLASS(K) = 4                                                    *
* PHOTON:                                                                *
* 1) AFTER THE TOF CUT IT CAN BE IDENTIFIED AS A PHOTON                  *
* ==> NFORW_PHOTON  IFO_PHOTON                                           *
*                                                                        * 
*   IASS_TRF = 1 (RW)                                                    *
*                                                                        * 
**************************************************************************


**************************************************************************
*  IFORW_CLASS(K) = 5                                                    *
* CHARGED NOISE:                                                         *
* 1) AFTER THE BIDIM. CUT DE_TRF%TOF_TRF IT CAN BE IDENTIFIED            *
*    AS CHARGED NOISE                                                    * 
* ==> NFORW_CNOISE  IFO_CNOISE                                           *
*                                                                        * 
*   IASS_TRF = 6 (PC-OW) OR 7 (PC-OW-RW)                                 *
*                                                                        * 
**************************************************************************


**************************************************************************
*  IFORW_CLASS(K) = 6                                                    *
* NOISE:                                                                 *
* 1) IT CAN BE IDENTIFIED AS NOISE                                       * 
* ==> NFORW_NOISE  IFO_NOISE                                             *
*                                                                        * 
*  NPARF_STRANGE                                                         * 
**************************************************************************

      LOGICAL LTRACK_FORW
      LOGICAL CHECK_CUT_2D_FW

      N_FORW        = 0
      NFORW_NEUTRON = 0  
      NFORW_PROTON  = 0
      NFORW_PION    = 0
      NFORW_PHOTON  = 0
      NFORW_CNOISE  = 0
      NFORW_NOISE   = 0

      NCOUNT = 0
      DO K = 1,NPARF
         IFO_NEUTRON(K) = 0   
         IFO_PROTON(K)  = 0
         IFO_PION(K)    = 0
         IFO_PHOTON(K)  = 0                                          
         IFO_CNOISE(K)  = 0
         IFO_NOISE(K)   = 0
         IFORW_CLASS(K) = 0
      ENDDO

      DO K = 1,NPARF
         INDEX_TRACCIAF(K)  = 0
         IASS_TRACCIAF(K)   = 0
         ECLUSC_TRACCIAF(K) = -1.
         THETA_TRACCIAF(K)  = -2.
         PHI_TRACCIAF(K)    = -2.
         TOF_TRACCIAF(K)    = -2.
         DEDX_TRACCIAF(K)   = -2.
      ENDDO

      LTRACK_FORW   = .FALSE.

*      PRINT*,' '
*      PRINT*,'****************************'
*      PRINT*,'****************************'
*      PRINT*,' '

* Loop on the best tracks (1,6 or 7)

      DO K = 1,NPARF
         N_FORW = N_FORW + 1 
         II     = INDEX_TRF(K)
         ITRACK = IASS_TRF(II) 
         IIRW   = IND_TRAF(3,II)
        
         INDEX_TRACCIAF(K)  = INDEX_TRF(K)
         IASS_TRACCIAF(K)   = IASS_TRF(II)
         THETA_TRACCIAF(K)  = THETA_TRF(K)
         PHI_TRACCIAF(K)    = PHI_TRF(K)
         TOF_TRACCIAF(K)    = TOF_TRF(K)

*         PRINT*,'TRACCIA N.       =',N_FORW
*         PRINT*,'TIPO DI TRACCIA N.',ITRACK
*         PRINT*,'THETA_TRACCIAF   =',THETA_TRACCIAF(K)
*         PRINT*,'PHI_TRACCIAF     =',PHI_TRACCIAF(K)
*         PRINT*,'TOF_TRACCIAF     =',TOF_TRACCIAF(K)
*         PRINT*,'DEDX_TRACCIAF    =',DEDX_TRACCIAF(K)
        
         IF(ITRACK.EQ.1)THEN    
            DEDX_TRACCIAF(K)   = ESHOW(IIRW)*1000.*COS_TRF(3,K)
            BB  = TOF_TRF(K)*CLIGHT*1.E-09           
            IF(TOF_TRF(K).GE.13.5)THEN
c NEUTRONS 
               NFORW_NEUTRON              = NFORW_NEUTRON + 1
               IFO_NEUTRON(NFORW_NEUTRON) = N_FORW
               IFORW_CLASS(K)             = 1
            ELSE
c PHOTONS                 
               NFORW_PHOTON               = NFORW_PHOTON + 1
               IFO_PHOTON(NFORW_PHOTON)   = N_FORW
               IFORW_CLASS(K)             = 4
            ENDIF
         ENDIF
         
c PROTONS AND PIONS (GRAPHICAL CUT DEDX VS. TOF) 

         IF((ITRACK.EQ.6).OR.(ITRACK.EQ.7))THEN

            DEDX_TRACCIAF(K)   = DE_TRF(K)

#if defined(FPROTON_CUT)
            XX = TOF_TRF(K)
            YY = DE_TRF(K)
            IF(CHECK_CUT_2D_FW(XX,YY,2))THEN
c PIONS
               NFORW_PION               = NFORW_PION + 1
               IFO_PION(NFORW_PION)     = N_FORW
               IFORW_CLASS(K)           = 3
            ELSE
               AA  = TOF_TRF(K)*CLIGHT*1.E-09
               IF(AA.GT.301.53)THEN            
                  IF(CHECK_CUT_2D_FW(XX,YY,1))THEN
c     PROTONS
                     NFORW_PROTON             = NFORW_PROTON + 1
                     IFO_PROTON(NFORW_PROTON) = N_FORW
                     IFORW_CLASS(K)           = 2
                  ELSE
c     CHARGED NOISE
                
                     NFORW_CNOISE             = NFORW_CNOISE + 1
                     IFO_CNOISE(NFORW_CNOISE) = N_FORW
                     IFORW_CLASS(K)           = 5
                  ENDIF
               ELSE
              
c CHARGED NOISE
                  NFORW_CNOISE             = NFORW_CNOISE + 1
                  IFO_CNOISE(NFORW_CNOISE) = N_FORW
                  IFORW_CLASS(K)           = 5
               ENDIF
            ENDIF
#endif

#if !defined(FPROTON_CUT)
c     PROTONS
            NFORW_PROTON             = NFORW_PROTON + 1
            IFO_PROTON(NFORW_PROTON) = N_FORW
            IFORW_CLASS(K)           = 2
#endif
         ENDIF
      ENDDO		

c NOISE       

*      PRINT*,' ' 
*      PRINT*,'NFORW_NEUTRON=',NFORW_NEUTRON
*      PRINT*,'NFORW_PHOTON=',NFORW_PHOTON
*      PRINT*,'NFORW_PROTON=',NFORW_PROTON
*      PRINT*,'NFORW_PION=',NFORW_PION
*      PRINT*,'NFORW_CNOISE=',NFORW_CNOISE
*      PRINT*,' ' 

      NFORW_NOISE                 = NPARF_STRANGE
      LTRACK_FORW = .TRUE.
      RETURN
      END
