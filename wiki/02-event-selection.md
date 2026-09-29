# 02 — Event Selection

Event selection reads pre-analysis `h80` trees and retains events that can feed
two-meson reconstruction. It validates the required metadata and vector
branches before writing selected events as `h85` trees.

This page covers filtering, multithreading, output validation, atomic directory
replacement, and protection against stale selected data.
