C Test driver only: routines under test are byte-for-byte copies of archived
C BGOD/DEDX/ATDEDX in a temporary mirror with an explicit GRAAL_09 pilot.
      PROGRAM LEGACY09_ORACLE
#include "nthit.inc"
#include "bgo.inc"
#include "datbgo.inc"
#include "itrig.inc"
#include "barrel.inc"
#include "datdex.inc"
#include "datvert.inc"
      REAL DRAWS(1000),AT,Z
      INTEGER NDRAW,USED,CASES,MODE,ATTFLAG,CHANNEL
      COMMON /TEST_GAUSS/ DRAWS,NDRAW,USED
      READ(*,*) CASES
      DO IC=1,CASES
        READ(*,*) SCBGO,VSCBGO,THRES,SCDEB,VSCDEB,DEBDIS,
     &    DTHRES,ZC3,SDETOF,VDETOF,DDETOF,DLIGHT,ATTFLAG
        DEDXAT = ATTFLAG.NE.0
        DO I=1,32
          READ(*,*) X1(I),X2(I),X3(I),X4(I)
        ENDDO
        TTHRES = INT(SCBGO/VSCBGO*THRES)
        READ(*,*) MODE
        IF(MODE.EQ.1)THEN
          READ(*,*) LBGO
          DO I=1,LBGO
            READ(*,*) CHANNEL,ENOUT(I)
            ITOUT(I) = (CHANNEL-1)/32+1
            IPOUT(I) = MOD(CHANNEL-1,32)+1
          ENDDO
          CALL BGOD
          WRITE(*,*) 'B',MBGO,TRANSFER(ETOTR,0),ETOT,ETOTSOFT
          DO I=1,MBGO
            WRITE(*,*) (ITBGO(I)-1)*32+IPBGO(I),EBGO(I)
          ENDDO
        ELSE IF(MODE.EQ.2)THEN
          READ(*,*) LDED
          DO I=1,LDED
            READ(*,*) NDED(I),EDED(I),ZDED(I),TDED(I)
          ENDDO
          READ(*,*) NDRAW
          IF(NDRAW.GT.0) READ(*,*) (DRAWS(I),I=1,NDRAW)
          USED = 0
          CALL DEDX
          WRITE(*,*) 'D',LDE,USED
          DO I=1,LDE
            WRITE(*,*) IPLA(I),EPLA(I),TPLA(I)
          ENDDO
        ELSE IF(MODE.EQ.3)THEN
          READ(*,*) CHANNEL,Z
          CALL ATDEDX(CHANNEL,Z,AT)
          WRITE(*,*) 'A',TRANSFER(AT,0)
        ELSE
          STOP 3
        ENDIF
      ENDDO
      END

      REAL FUNCTION EXT_GAUS()
      REAL DRAWS(1000)
      INTEGER NDRAW,USED
      COMMON /TEST_GAUSS/ DRAWS,NDRAW,USED
      USED = USED+1
      IF(USED.GT.NDRAW) STOP 4
      EXT_GAUS = DRAWS(USED)
      END
