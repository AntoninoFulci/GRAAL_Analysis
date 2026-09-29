# Architecture

GRAAL Analysis is a set of numbered processing stages connected by persisted
scientific artifacts. Shared physics and I/O contracts live in `00_common/`,
while stage packages own their orchestration, validation, and outputs.

This page explains system boundaries and dependencies. See the
[workflow](workflow) for execution order and [data and artifacts](data-and-artifacts)
for persisted formats.
