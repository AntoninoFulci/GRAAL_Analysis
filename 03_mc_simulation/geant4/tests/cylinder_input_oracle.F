C Specification replay driver; extracted GUSTEP branch fixture is appended by
C test_cylinder_input.py. This is NOT compilation of the full GUSTEP routine.
      PROGRAM CYLINDER_INPUT_ORACLE
#include "nthit.inc"
      INTEGER NEVENT,IEVENT,N,ISVOL,IC,IE
      REAL XYZ(3),DE
      READ(*,*) NEVENT
      DO IEVENT=1,NEVENT
C LAGRESET event-array semantics; GUSTEP SAVE deliberately persists.
        MULT1=0
        MULT2=0
        DO I=1,20
          DECI(I)=0.
          DECE(I)=0.
        ENDDO
        READ(*,*) N
        DO I=1,N
          READ(*,*) ISVOL,IC,IE,XYZ(1),XYZ(2),XYZ(3),DE
          CALL GUSTEP_CENTRAL_EXTRACT(ISVOL,FLOAT(IC),IE,XYZ,DE)
        ENDDO
        WRITE(*,*) MULT1,MULT2
        DO I=1,MULT1
          E=DECI(I)
          IF(E.EQ.0.)E=1.E-7
          WRITE(*,*) (TRANSFER(XCI(J,I),1),J=1,3),
     &      TRANSFER(DECI(I),1),TRANSFER(E,1)
        ENDDO
        DO I=1,MULT2
          E=DECE(I)
          IF(E.EQ.0.)E=1.E-7
          WRITE(*,*) (TRANSFER(XCE(J,I),1),J=1,3),
     &      TRANSFER(DECE(I),1),TRANSFER(E,1)
        ENDDO
      ENDDO
      END
