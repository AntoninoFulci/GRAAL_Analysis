C     Exact HBOOK axes and bin contents; run in pinned legacy image.
      PROGRAM EXPORT_TAGGER
      PARAMETER (NWPAWC=2000000)
      COMMON /PAWC/ H(NWPAWC)
      REAL CONTENTS(100000),XMIN,XMAX,YMIN,YMAX
      CHARACTER*80 TITLE
      CALL HLIMIT(NWPAWC)
      CALL HRGET(0,
     + '/repo/docs/reference/fortran/prog/data/simul_beam/tag.hist',
     + ' ')
      OPEN(20,FILE='/work/tagger_histograms.txt',STATUS='NEW')
      DO ID=101,117
        CALL HGIVE(ID,TITLE,NX,XMIN,XMAX,NY,YMIN,YMAX,NWT,LOC)
        IF(NX.LE.0.OR.NX.GT.100000.OR.NY.NE.0)STOP 'BAD AXIS'
        CALL HUNPAK(ID,CONTENTS,' ',0)
        WRITE(20,'(2I10,2E25.17)') ID,NX,XMIN,XMAX
        WRITE(20,'(2E25.17)') HI(ID,0),HI(ID,NX+1)
        DO I=1,NX
          WRITE(20,'(I10,E25.17)') I,CONTENTS(I)
        ENDDO
      ENDDO
      CLOSE(20)
      END
