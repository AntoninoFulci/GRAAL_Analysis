"""Use native macOS OpenGL for the Geant4 Qt viewer, even with XQuartz installed."""

from spack_repo.builtin.packages.geant4.package import Geant4 as BuiltinGeant4


class Geant4(BuiltinGeant4):
    def cmake_args(self):
        args = super().cmake_args()
        if self.spec.satisfies("platform=darwin +qt"):
            # Spack defaults to LAST; FindOpenGL then picks XQuartz's libGL.
            # Qt's Cocoa contexts need Apple's native OpenGL framework.
            args.append(self.define("CMAKE_FIND_FRAMEWORK", "FIRST"))
        return args
