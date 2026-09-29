# Architectural Decisions

The current structure separates shared contracts, numerical cores, ROOT
adapters, command entry points, and persisted artifacts. These boundaries are
enforced by package layout and tests rather than by a central service.

This page records decisions visible in current code, their consequences, and
the invariants maintainers must preserve when extending the analysis.
