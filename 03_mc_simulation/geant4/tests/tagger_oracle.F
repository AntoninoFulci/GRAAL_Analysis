C     Link unchanged TAG, ANASTRIP_TAG, SWAP_STRIP and EG_TAG_SIM.
      PROGRAM TAGGER_ORACLE
#include "m_strip.inc"
#include "tag_strip_calibr.inc"
#include "event.inc"
#include "coeff.inc"
#include "lflag.inc"
#include "tag_strip.inc"
      COMMON /HEAD/ IDRUNH,IDEVTH,IPOLH,EGAMH
      COMMON /INJECTED/ DISPLACEMENT
      LOGICAL ACCEPTED
      XOFFMS=24.02
      LENMS=38.4
      PITCHMS=300./1000.
      XS_0=XOFFMS
      EE=6.040
      A0=159.92
      LDATA=.FALSE.
      LSIMUL=.TRUE.
   10 READ(*,*,END=20) IDRUN,EGAMH,DISPLACEMENT
      MTGC2=0
      CALL TAG(ACCEPTED)
      IDIGIT=-1
      IF(ACCEPTED)IDIGIT=ITGC2(1)
      CALL ANASTRIP_TAG
      WRITE(*,'(3I10,2E25.17)') INT((EGAMH*1000.-250.)/100.)+101,
     + IDIGIT,NCSTRIP,XSTRIP(1),EG_TAG_STRIP(1)
      GOTO 10
   20 CONTINUE
      END

      REAL FUNCTION HRNDM1(ID)
      COMMON /INJECTED/ DISPLACEMENT
      HRNDM1=DISPLACEMENT
      END

      SUBROUTINE MULTIPLE_CLUS(FLAG)
      LOGICAL FLAG
      STOP 'unexpected data-only MULTIPLE_CLUS call'
      END
