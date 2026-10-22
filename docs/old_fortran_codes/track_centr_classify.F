#include "GRAAL_machine.h"
#include "../pilot.h"
C*********************************************************
      SUBROUTINE TRACK_CENTR_CLASSIFY(LTRACK_CENTR)
C*********************************************************
#include "event.inc"
#include "pm_b_b.inc"
#include "lflag_sd.inc"

#if defined(GRAAL_ASSOCIA_CYLBGO_BAR)
#include "ass_cylbgobar.inc"
#endif
#if defined(GRAAL_ASSOCIA_CYLBAR_BGO)
#include "ass_cylbarbgo.inc"
#endif
#include "trackcentr.inc"
#include "etadeu_const.inc"

c check if we need these!
#include "count.inc"

c           
c                                 AFTER PREAN    AFTER CUTS
c                                                  ETADEU     
c                                                (PM-BGO-CYL)
c
c TOTAL TRACKS                                      2466447    
c                   
c
c   N_CENTR = NCENTR_NEUTRAL + NCENTR_PROTON + NCENTR_PION + 
c                  NCENTR_DPHOTON + NCENTR_DPROTON1 + NCENTR_DPROTON2 +  
c                  NCENTR_DNEUTRON1 + NCENTR_DNEUTRON2 +
c                  NCENTR_DIS + NCENTR_NOISE
c
**************************************************************************
*  ICENTR_CLASS(K) = 1                                                   *
* NEUTRAL PARTICLE:                                                      *
* 1) IT IS USED TO BUILD THE ETA INVARIANT MASS                          *
* 2) OTHERWISE AFTER THE CUT ON MULTIPLICITY < 5 IT CAN BE IDENTIFIED    *
*    WITH THE NEUTRON IN COINCIDENCE WITH A GOOD ETA INVARIANT MASS      *
*    (CHECK COPLANARITY WITH ETA AND THETA WITH THETA_MISS_ETA)          *
* ==> NCENTR_NEUTRAL  IC_NEUTRAL                                         * 
*                                                                        * 
*    11      ! (0,0,1)                                                   * 
*                                                                        * 
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 2                                                   *
* PROTON:                                                                *
* 1) AFTER THE BIDIM. CUT DEDX_TRACK%ECLUSC_TRACK IT CAN BE IDENTIFIED   *
*    AS THE PROTON IN COINCIDENCE WITH A GOOD ETA INVARIANT MASS         * 
* ==> NCENTR_PROTON  IC_PROTON                                           *
*                                                                        * 
*    13      ! (0,1,1)  INSIDE PROTON CUT                                *
*    14      ! (1,1,1)  INSIDE PROTON CUT                                *
*                                                                        * 
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 3                                                   *
* PION:                                                                  *
* 1) AFTER THE BIDIM. CUT DEDX_TRACK%ECLUSC_TRACK IT CAN BE IDENTIFIED   *
*    AS A PION                                                           * 
* ==> NCENTR_PION  IC_PION                                               *
*                                                                        * 
*    13      ! (0,1,1)  INSIDE PION CUT                                  *
*    14      ! (1,1,1)  INSIDE PION CUT                                  *
*                                                                        * 
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 4                                                   *
* DOUBTFUL PHOTONS:                                                      *
* 1) AFTER THE CUT ON MULTIPLICITY > 3 IT IS USED TO BUILD THE ETA       * 
*    INVARIANT MASS TOGETHER WITH A GOOD NEUTRAL (0-0-1)                 *
* ==> NCENTR_DPHOTON  IC_DPHOTON                                         *
*     13      ! (0,1,1) OUT OF PROTON AND PION CUTS                      *
*     17      ! (0,3,1)                                                  *
*     19      ! (0,4,1)                                                  *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 5                                                   *
* DOUBTFUL PROTON 1:                                                     *
* 1) AFTER THE CUT ON MULTIPLICITY<5 AND THE BIDIM. CUT                  *
*    DEDX_TRACK%ECLUSC_TRACK (ONLY FOR 15 AND 16) IT CAN BE IDENTIFIED   *
*    AS A DOUBTFUL PROTON IN COINCIDENCE WITH A GOOD ETA INVARIANT MASS  * 
* ==> NCENTR_DPROTON1  IC_DPROTON1                                       *
*     12      ! (1,0,1)                                                  *
*     15      ! (0,2,1)  (CUT DEDX%E)                                    *
*     16      ! (1,2,1)  (CUT DEDX%E)                                    * 
*     18      ! (1,3,1)                                                  *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 6                                                   *
* DOUBTFUL PROTON 2:                                                     *
* 1)IT COULD BE IDENTIFIED WITH A PROTON BECAUSE OF ITS COPLANARITY      *
*   WITH ETA BUT WE DON'T HAVE ENERGY NEITHER THETA                      *
* ==> NCENTR_DPROTON2  IC_DPROTON2                                       *
*     3      ! (0,1,0)                                                  *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 7                                                   *
* DOUBTFUL NEUTRON1                                                      *
* 1) IT CAN BE IDENTIFIED AS A DOUBTFUL NEUTRON IN COINCIDENCE WITH A    *
*    GOOD ETA INVARIANT MASS (BGO UNDER THRESHOLD)                       *
*    (CHECK COPLANARITY WITH ETA AND THETA WITH THETA_MISS_ETA)          *
* ==> NCENTR_DNEUTRON1  IC_DNEUTRON1                                     *
*    21      ! (0,0,2)                                                   *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 8                                                   *
* DOUBTFUL NEUTRON2                                                      *
* 1) AFTER THE CUT ON MULTIPLICITY < 4 (FOR CASE 19)                     *
*    AND CUT DEDX_TRACK % ECLUSC_TRACK (FOR CASE 15)                     *
*    IT CAN BE IDENTIFIED AS A  DOUBTFUL NEUTRON IN COINCIDENCE          *
*    WITH A GOOD ETA INVARIANT MASS                                      *
*    (CHECK COPLANARITY WITH ETA AND THETA WITH THETA_MISS_ETA)          *
* ==> NCENTR_DNEUTRON2  IC_DNEUTRON2                                     *
*     15      ! (0,2,1)                                                  *
*     19      ! (0,4,1)                                                  *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 9                                                   *
* MISSED PROTON                                                          *
* 1) AFTER THE CUT THET_CENTR_TRACK<=35,                                 *
*    IT CAN BE IDENTIFIED AS A PROTON EMITTED AT ANGLES 25-35 DEGREES    *
*    THAT WAS DETECTED ONLY BY CYL                                       *
* ==> NCENTR_MISSPROTON  IC_MISSPROTON                                   * 
*     2      ! (1,0,0)   THETA<=35                                       *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 10                                                  *
* DISAPPEARED PROTON                                                     *
* 1) IT CAN BE IDENTIFIED AS A SLOW CHARGED PARTICLE WHICH STOPPED       *
*    BEFORE BGO AND THEN AS A DISAPPEARED PROTON                         *
*    IT IS DISTRIBUTED ALL OVER THE BGO                                  * 
* ==> NCENTR_DISPROTON  IC_DISPROTON                                     * 
*     4      ! (1,1,0)                                                   *
*    24      ! (1,1,2)                                                   *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 11                                                  *
* NOISE WITHOUT A SIGNAL IN THE BGO                                      *
* 1) IT CAN BE ACCEPTED IN COINCIDENCE WITH A GOOD ETA INVARIANT MASS    *
* ==> NCENTR_NOISE_NO_BGO  IC_NOISE_NO_BGO                               * 
*     2      ! (1,0,0) THETA>35                                          *
*     5      ! (0,2,0)                                                   *
*     6      ! (1,2,0)                                                   * 
*     7      ! (0,3,0)                                                   *
*     8      ! (1,3,0)                                                   *
*     9      ! (0,4,0)                                                   *
*    10      ! (1,4,0)                                                   *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 12                                                  *
* NOISE WITH A GOOD  SIGNAL IN THE BGO ( ECLUSC_TRACK ABOVE THRESHOLD)   *
* 1) THE EVENT MUST BE REJECTED IF THE ENERGY IS TOO HIGH                *
* ==> NCENTR_NOISE_BGO  IC_NOISE_BGO                                     * 
*    12      ! (1,0,1) MULT > 4                                          * 
*    13      ! (0,1,1) OUT OF PROTON AND PION CUTS AND MULT<4            *
*    14      ! (1,1,1) OUT OF PROTON AND PION CUTS                       *
*    16      ! (1,2,1) OUT OF DOUBTFUL PROTON1 CUT                       * 
*    17      ! (0,3,1) MULT < 4                                          * 
*    18      ! (1,3,1) MULT > 4                                          *
*    20      ! (1,4,1)                                                   *
**************************************************************************


**************************************************************************
*  ICENTR_CLASS(K) = 13                                                  *
* NOISE WITH A SP  SIGNAL IN THE BGO ( ECLUSC_TRACK BELOW THRESHOLD)     *
* 1) IT CAN BE ACCEPTED  IN COINCIDENCE WITH A GOOD ETA INVARIANT MASS   *
* ==> NCENTR_NOISE_SP   IC_NOISE_SP                                      * 
*    22      ! (1,0,2)                                                   *
*    23      ! (0,1,2)                                                   *
*    25      ! (0,2,2)                                                   *
*    26      ! (1,2,2)                                                   *
*    27      ! (0,3,2)                                                   *
*    28      ! (1,3,2)                                                   *
*    29      ! (0,4,2)                                                   *
*    30      ! (1,4,2)                                                   *
**************************************************************************
 
      LOGICAL LTRACK_CENTR
      LOGICAL CHECK_CUT_2D_BGO

#if !defined(GRAAL_ASSOCIA_CYLBGO_BAR)
#if !defined(GRAAL_ASSOCIA_CYLBAR_BGO)
      WRITE(*,*)'You cannot run this version of etadeu if you dont have
     &           GRAAL_ASSOCIA_CYLBGO_BAR or GRAAL_ASSOCIA_CYLBAR_BGO'
      STOP
#endif
#endif

c   N_CENTR = NCENTR_NEUTRAL + NCENTR_PROTON + NCENTR_PION + 
c             NCENTR_DPHOTON + 
C             NCENTR_DPROTON1 + NCENTR_DPROTON2 +  
c             NCENTR_DNEUTRON1 + NCENTR_DNEUTRON2 + 
C             NCENTR_MISSPROTON + NCENTR_DISPROTON + 
C             NCENTR_NOISE_NO_BGO + NCENTR_NOISE_BGO + NCENTR_NOISE_SP

      N_CENTR                 = 0
      NCENTR_NEUTRAL          = 0
      NCENTR_PROTON           = 0
      NCENTR_PION             = 0
      NCENTR_DPHOTON          = 0
      NCENTR_DPROTON1         = 0
      NCENTR_DPROTON2         = 0
      NCENTR_DNEUTRON1        = 0
      NCENTR_DNEUTRON2        = 0
      NCENTR_MISSPROTON       = 0
      NCENTR_DISPROTON        = 0
      NCENTR_NOISE_NO_BGO     = 0
      NCENTR_NOISE_BGO        = 0
      NCENTR_NOISE_SP         = 0
      
      DO K=1,NASS_3
        IC_NEUTRAL(K)     = 0
        IC_PROTON(K)      = 0
        IC_PION(K)        = 0
        IC_DPHOTON(K)     = 0
        IC_DPROTON1(K)    = 0
        IC_DPROTON2(K)    = 0
        IC_DNEUTRON1(K)   = 0
        IC_DNEUTRON2(K)   = 0
        IC_MISSPROTON(K)  = 0
        IC_DISPROTON(K)   = 0
        IC_NOISE_NO_BGO(K)= 0
        IC_NOISE_BGO(K)   = 0
        IC_NOISE_SP(K)    = 0
        ICENTR_CLASS(K)   = 0
      ENDDO  
      
      DO K = 1,NASS_3
        ITIPO_TRACCIA(K)       = 0
        MULT_TRACCIA(K)        = -1.
        EMAXCLUS_TRACCIA(K)    = -1.
        ECLUSC_TRACCIA(K)      = -1.   
        TETCLUSC_TRACCIA(K)    = -1.
        PHICLUSC_TRACCIA(K)    = -1.
        ECLUS_TRACCIA(K)       = -1.
        TETCLUS_TRACCIA(K)     = -1.
        PHICLUS_TRACCIA(K)     = -1.
        DEDX_TRACCIA(K)        = -1.   
        THET_CENTR_TRACCIA(K)  = -1.
        PHI_CENTR_TRACCIA(K)   = -1.
      ENDDO
      
      LTRACK_CENTR   = .FALSE.

*      PRINT*,' '
*      PRINT*,'****************************'
*      PRINT*,'****************************'
*      PRINT*,' '

      DO K=1,NASS_3
        
        N_CENTR  = N_CENTR + 1 
        
        K_BGO    = IASS_3(1,N_CENTR)
        
        IF(K_BGO.GT.0)THEN
          IF(K_BGO.LE.NBCLUS)THEN
            MULT_TRACCIA(N_CENTR)        = MCLUS(K_BGO)
            EMAXCLUS_TRACCIA(N_CENTR)    = EMAX(K_BGO)
            SX1_TRACCIA(N_CENTR)         = SX1(K_BGO)
            SY1_TRACCIA(N_CENTR)         = SY1(K_BGO)
            SX2_TRACCIA(N_CENTR)         = SX2(K_BGO)
            SY2_TRACCIA(N_CENTR)         = SY2(K_BGO)
            IFL_TRACCIA(N_CENTR)         = IFL(K_BGO)
            
* Modified by Rachele 28/03/06
* I recover the not corrected variables for energy-theta-phi in BGO
            ECLUS_TRACCIA(N_CENTR)       = ECLUS(K_BGO)
            TETCLUS_TRACCIA(N_CENTR)     = TETCLUS(K_BGO)
            PHICLUS_TRACCIA(N_CENTR)     = PHICLUS(K_BGO)

* I recover the corrected variables for energy-theta-phi in BGO
            ECLUSC_TRACCIA(N_CENTR)      = ECLUSC(K_BGO)
            TETCLUSC_TRACCIA(N_CENTR)    = TETCLUSC(K_BGO)
            PHICLUSC_TRACCIA(N_CENTR)    = PHICLUSC(K_BGO)

          ELSEIF(K_BGO.GT.NBCLUS)THEN
            K_SP = K_BGO-NBCLUS
            MULT_TRACCIA(N_CENTR)        = MCLUS_SP(K_SP)
            EMAXCLUS_TRACCIA(N_CENTR)    = -1.
            SX1_TRACCIA(N_CENTR)         = SX1(K_SP)
            SY1_TRACCIA(N_CENTR)         = SY1(K_SP)
            SX2_TRACCIA(N_CENTR)         = SX2(K_SP)
            SY2_TRACCIA(N_CENTR)         = SY2(K_SP)
            IFL_TRACCIA(N_CENTR)         = IFL(K_SP)

* Modified by Rachele 28/03/06
* Not corrected variables for energy-theta-phi in BGO
            ECLUS_TRACCIA(N_CENTR)       = ECLUS_SP(K_SP)
            TETCLUS_TRACCIA(N_CENTR)     = TETCLUS_SP(K_SP)
            PHICLUS_TRACCIA(N_CENTR)     = PHICLUS_SP(K_SP)

* Corrected variables for energy-theta-phi in BGO
            ECLUSC_TRACCIA(N_CENTR)      = ECLUSC_SP(K_SP)
            TETCLUSC_TRACCIA(N_CENTR)    = TETCLUSC_SP(K_SP)
            PHICLUSC_TRACCIA(N_CENTR)    = PHICLUSC_SP(K_SP)

          ENDIF
        ENDIF

        THET_CENTR_TRACCIA(N_CENTR)  = THET_CENTR_TRACK(N_CENTR)
        PHI_CENTR_TRACCIA(N_CENTR)   = PHI_CENTR_TRACK(N_CENTR)
        DEDX_TRACCIA(N_CENTR)        = DEDX_TRACK(N_CENTR)
        ITRACK                       = ITIPO_TRACK(N_CENTR)

*        PRINT*,'***'
*        PRINT*,'TRACCIA N.',N_CENTR
*        PRINT*,'ITIPO_TRACCIA=',ITIPO_TRACK(N_CENTR)
*        PRINT*,'MOLTEPLICITA=',MULT_TRACCIA(N_CENTR)
*        PRINT*,'               NON CORRETTO         CORRETTO'
*        PRINT*,'TETBGO_TRACCIA=',TETCLUS_TRACCIA(N_CENTR),'        ',
*     +         TETCLUSC_TRACCIA(N_CENTR),'     DIFF =',
*     +         TETCLUS_TRACCIA(N_CENTR)-TETCLUSC_TRACCIA(N_CENTR)
*        PRINT*,'PHIBGO_TRACCIA=',PHICLUS_TRACCIA(N_CENTR),'        ',
*     +         PHICLUSC_TRACCIA(N_CENTR),'       DIFF =',
*     +         PHICLUS_TRACCIA(N_CENTR)-PHICLUSC_TRACCIA(N_CENTR)
*        PRINT*,'EBGO_TRACCIA  =',ECLUS_TRACCIA(N_CENTR)*1000.,'       ',
*     +         ECLUSC_TRACCIA(N_CENTR)*1000.,'     DIFF =',
*     +         (ECLUS_TRACCIA(N_CENTR)-ECLUSC_TRACCIA(N_CENTR))*1000.
*        PRINT*,' ' 
*        PRINT*,'THET_CENTR_TRACCIA=',THET_CENTR_TRACCIA(N_CENTR)
*        PRINT*,'PHI_CENTR_TRACCIA =',PHI_CENTR_TRACCIA(N_CENTR)
*        PRINT*,' '
*        PAUSE

        IF((ITRACK.EQ.4).OR.(ITRACK.EQ.6).OR.
     +       (ITRACK.EQ.13).OR.(ITRACK.EQ.14).OR.
     +       (ITRACK.EQ.15).OR.(ITRACK.EQ.16).OR.
     +       (ITRACK.EQ.23).OR.(ITRACK.EQ.24).OR.
     +       (ITRACK.EQ.25).OR.(ITRACK.EQ.26))THEN
          
          IF((DEDX_TRACK(K).LE.2.).AND.(DEDX_TRACK(K).GT.-1.)) THEN
            ITIPO_TRACK(K) = ITIPO_TRACK(K) + 4
          ENDIF
        ENDIF
        
        ITRACK                 = ITIPO_TRACK(K)
        ITIPO_TRACCIA(K)       = ITIPO_TRACK(K)
        IF(ITRACK.EQ.1) THEN
          GOTO 999
        ENDIF
        
        IF(ITRACK.EQ.2)THEN
          IF(THET_CENTR_TRACCIA(K).LE.35.)THEN
C MISSED PROTON
            NCENTR_MISSPROTON  = NCENTR_MISSPROTON +1
            IC_MISSPROTON(NCENTR_MISSPROTON) = K
            ICENTR_CLASS(K)        = 9
          ELSE
C NOISE NO BGO
            NCENTR_NOISE_NO_BGO  = NCENTR_NOISE_NO_BGO +1  
            IC_NOISE_NO_BGO(NCENTR_NOISE_NO_BGO) = K
            ICENTR_CLASS(K)        = 11
          ENDIF
        ENDIF
c DOUBTFUL PROTON2
        IF(ITRACK.EQ.3)THEN
          NCENTR_DPROTON2            = NCENTR_DPROTON2 + 1   
          IC_DPROTON2(NCENTR_DPROTON2) = K
          ICENTR_CLASS(K)            = 6
        ENDIF
c DISAPPEARED PROTON
        IF(ITRACK.EQ.4)THEN
          NCENTR_DISPROTON  = NCENTR_DISPROTON + 1   
          IC_DISPROTON(NCENTR_DISPROTON)= K
          ICENTR_CLASS(K) = 8
        ENDIF
c NOISE NO BGO
        IF((ITRACK.EQ.5).OR.
     &       (ITRACK.EQ.6).OR.
     &       (ITRACK.EQ.7).OR.
     &       (ITRACK.EQ.8).OR.
     &       (ITRACK.EQ.9).OR.
     &       (ITRACK.EQ.10))THEN
          NCENTR_NOISE_NO_BGO    = NCENTR_NOISE_NO_BGO + 1   
          IC_NOISE_NO_BGO(NCENTR_NOISE_NO_BGO) = K
          ICENTR_CLASS(K)        = 11
        ENDIF
c NEUTRALS
        IF(ITRACK.EQ.11)THEN
          NCENTR_NEUTRAL             = NCENTR_NEUTRAL + 1
          IC_NEUTRAL(NCENTR_NEUTRAL) = K
          ICENTR_CLASS(K)            = 1
        ENDIF
        
        IF (ITRACK.EQ.12) THEN
          IF(MULT_TRACCIA(K).LE.4)THEN
c DOUBTFUL PROTON1
            NCENTR_DPROTON1             = NCENTR_DPROTON1 + 1   
            IC_DPROTON1(NCENTR_DPROTON1) = K
            ICENTR_CLASS(K)            = 5
          ELSE
c NOISE BGO
            NCENTR_NOISE_BGO    = NCENTR_NOISE_BGO + 1   
            IC_NOISE_BGO(NCENTR_NOISE_BGO) = K
            ICENTR_CLASS(K)        = 12
          ENDIF
        ENDIF

c CHARGED --> PROTONS - PIONS - NOISE (FOLLOWING THE GRAPHICAL CUT)
cc 20/08/05 Rimetto un taglio largo sui protoni e i pioni

        IF((ITRACK.EQ.13).OR.(ITRACK.EQ.14))THEN
#if defined(CPROTON_CUT)
           XX = ECLUSC_TRACK(K)
           YY = DEDX_TRACK(K)
          
           IF(CHECK_CUT_2D_BGO(XX,YY,1))THEN
c PROTONS
              NCENTR_PROTON            = NCENTR_PROTON + 1   
              IC_PROTON(NCENTR_PROTON) = K
              ICENTR_CLASS(K)          = 2               
           ELSEIF(CHECK_CUT_2D_BGO(XX,YY,2))THEN
c PIONS
              NCENTR_PION          = NCENTR_PION + 1   
              IC_PION(NCENTR_PION) = K
              ICENTR_CLASS(K)      = 3               
           ELSE
              IF(ITRACK.EQ.14)THEN
c NOISE BGO 
                 NCENTR_NOISE_BGO  = NCENTR_NOISE_BGO + 1   
                 IC_NOISE_BGO(NCENTR_NOISE_BGO) = K
                 ICENTR_CLASS(K)        = 12
              ELSEIF(ITRACK.EQ.13)THEN
                 IF(MULT_TRACCIA(K).GE.4)THEN
c DOUBTFUL PHOTON
                    NCENTR_DPHOTON             = NCENTR_DPHOTON + 1   
                    IC_DPHOTON(NCENTR_DPHOTON) = K
                    ICENTR_CLASS(K)            = 4
                 ELSE
C NOISE BGO
                    NCENTR_NOISE_BGO  = NCENTR_NOISE_BGO + 1   
                    IC_NOISE_BGO(NCENTR_NOISE_BGO) = K
                    ICENTR_CLASS(K)        = 12
                 ENDIF      
              ENDIF
           ENDIF
#endif
           
#if !defined(CPROTON_CUT)
c     PROTONS
           NCENTR_PROTON            = NCENTR_PROTON + 1   
           IC_PROTON(NCENTR_PROTON) = K
           ICENTR_CLASS(K)          = 2               
#endif
        ENDIF

        
        IF(ITRACK.EQ.15)THEN
          
          XX = ECLUSC_TRACK(K)
          YY = DEDX_TRACK(K)
          
          IF(CHECK_CUT_2D_BGO(XX,YY,1))THEN
c DOUBTFUL PROTON1  
            NCENTR_DPROTON1    = NCENTR_DPROTON1 + 1   
            IC_DPROTON1(NCENTR_DPROTON1) = K
            ICENTR_CLASS(K)            = 5
          ELSE
c DOUBTFUL NEUTRON2  
            NCENTR_DNEUTRON2    = NCENTR_DNEUTRON2 + 1   
            IC_DNEUTRON2(NCENTR_DNEUTRON2) = K
            ICENTR_CLASS(K) = 8
          ENDIF
        ENDIF
           
        IF(ITRACK.EQ.16)THEN
          
          XX = ECLUSC_TRACK(K)
          YY = DEDX_TRACK(K)
          
          IF(CHECK_CUT_2D_BGO(XX,YY,1))THEN
c DOUBTFUL PROTON1  
            NCENTR_DPROTON1    = NCENTR_DPROTON1 + 1   
            IC_DPROTON1(NCENTR_DPROTON1) = K
            ICENTR_CLASS(K)            = 5
          ELSE
c NOISE BGO 
            NCENTR_NOISE_BGO    = NCENTR_NOISE_BGO + 1   
            IC_NOISE_BGO(NCENTR_NOISE_BGO) = K
            ICENTR_CLASS(K)        = 12
          ENDIF
        ENDIF
        
        IF(ITRACK.EQ.17)THEN
          IF(MULT_TRACCIA(K).GE.4)THEN
c DOUBTFUL PHOTONS
            NCENTR_DPHOTON            = NCENTR_DPHOTON + 1   
            IC_DPHOTON(NCENTR_DPHOTON) = K
            ICENTR_CLASS(K)           = 4
          ELSE
c NOISE BGO 
            NCENTR_NOISE_BGO = NCENTR_NOISE_BGO + 1   
            IC_NOISE_BGO(NCENTR_NOISE_BGO) = K
            ICENTR_CLASS(K)                = 12
          ENDIF
        ENDIF
        
        IF(ITRACK.EQ.18)THEN
          IF(MULT_TRACCIA(K).LE.4)THEN
c DOUBTFUL PROTON1
            NCENTR_DPROTON1             = NCENTR_DPROTON1 + 1   
            IC_DPROTON1(NCENTR_DPROTON1) = K
            ICENTR_CLASS(K)            = 5
          ELSE
c NOISE BGO
            NCENTR_NOISE_BGO    = NCENTR_NOISE_BGO + 1   
            IC_NOISE_BGO(NCENTR_NOISE_BGO) = K
            ICENTR_CLASS(K)        = 12
          ENDIF
        ENDIF
           
        IF(ITRACK.EQ.19)THEN
          IF(MULT_TRACCIA(K).GE.4)THEN
c DOUBTFUL PHOTONS
            NCENTR_DPHOTON            = NCENTR_DPHOTON + 1   
            IC_DPHOTON(NCENTR_DPHOTON) = K
            ICENTR_CLASS(K)           = 4
          ELSE
c DOUBTFUL NEUTRON 2
            NCENTR_DNEUTRON2 = NCENTR_DNEUTRON2 + 1   
            IC_DNEUTRON2(NCENTR_DNEUTRON2) = K
            ICENTR_CLASS(K)                = 8
          ENDIF
        ENDIF
           
C NOISE BGO
           
        IF(ITRACK.EQ.20)THEN
          NCENTR_NOISE_BGO    = NCENTR_NOISE_BGO + 1   
          IC_NOISE_BGO(NCENTR_NOISE_BGO) = K
          ICENTR_CLASS(K)        = 12
        ENDIF
        
c DOUBTFUL NEUTRON1
        
        IF(ITRACK.EQ.21)THEN   
          NCENTR_DNEUTRON1  = NCENTR_DNEUTRON1 + 1   
          IC_DNEUTRON1(NCENTR_DNEUTRON1) = K
          ICENTR_CLASS(K)                = 7
        ENDIF
           
C NOISE SP

        IF((ITRACK.EQ.22).OR.
     &       (ITRACK.EQ.23))THEN
          NCENTR_NOISE_SP  = NCENTR_NOISE_SP +1  
          IC_NOISE_SP(NCENTR_NOISE_SP) = K
          ICENTR_CLASS(K)        = 13
        ENDIF
           
C DISAPPEARED PROTON
           
        IF(ITRACK.EQ.24)THEN
          NCENTR_DISPROTON  = NCENTR_DISPROTON + 1   
          IC_DISPROTON(NCENTR_DISPROTON)= K
          ICENTR_CLASS(K) = 8
        ENDIF
           
C NOISE SP
           
        IF((ITRACK.EQ.25).OR.
     &       (ITRACK.EQ.26).OR.
     &       (ITRACK.EQ.27).OR.
     &       (ITRACK.EQ.28).OR.
     &       (ITRACK.EQ.29).OR.
     &       (ITRACK.EQ.30)) THEN
          NCENTR_NOISE_SP  = NCENTR_NOISE_SP +1  
          IC_NOISE_SP(NCENTR_NOISE_SP) = K
          ICENTR_CLASS(K)        = 13
        ENDIF
      ENDDO
      
*      PRINT*,'******************************'
*      PRINT*,'******************************'

      
 999  LTRACK_CENTR = .TRUE.

      RETURN
      END
