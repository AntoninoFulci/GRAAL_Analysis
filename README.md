# GRAAL Analysis

This repository contains analysis code for the GRAAL experiment.

## Overview
This codebase provides tools for processing raw data, performing particle identification, and reconstructing physics events using the ROOT framework.

## Repository Structure

- `pre_analysis/`: Core analysis code for event processing and particle reconstruction
  - `PreAnalysis.C`: Main analysis script for reading TTree data and identifying particles
  - `CutManager.h`: Dynamic cut management system for particle identification
  - `cuts/`: Collection of graphical cuts (TCutG) for different particles and detector regions

## Prerequisites

- ROOT framework (version 6.x)
- C++ compiler
- Access to GRAAL data files

## Usage

1. Set up ROOT environment
2. Navigate to `pre_analysis/`
3. Run the pre-analysis:
   ```bash
   root
   .L PreAnalysis.C
   AnalyzeAll()
   ```