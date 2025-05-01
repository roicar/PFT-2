# PFT Project Overview

In PFT-2, there are a total of 2 subdirectories:
- **PFT-2**: Implementation of the PFT algorithm.
- **src_replace**: Used to replace Pluto's core functionality to enable Pluto to generate the polyhedral information required by PFT.

## Prerequisites

Ensure your Python environment includes all required dependencies:
- `sympy`
- `numpy`
- `scipy`
- `argparse`
- (and any other necessary libraries).

## Usage Steps

1. Use functions in `src_replace` to modify the core functionality of Pluto, and recompile the modified Pluto to generate the polyhedral information required for PFT.
2. Use PFT.sh in  `PFT-2` to process the input polyhedron file for automatic generation of TVM compute.
3. In `PFT-2/new_compute`, after step 2, we obtain the TVM kernel. Use TVM Ansor for automatic tuning and generating the executible code on cpu and gpu.
