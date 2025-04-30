#!/bin/bash

# ========================
# PFT.py invocation script
# ========================
# 1. Specify the Python interpreter path
# 2. Set the path to the PFT.py script
# 3. Specify the input file
# 4. Set the hardware architecture (arch)
# 5. Set the optimization method (optimization)
# 6. Set the strategy (method)
# 7. Invoke PFT.py and pass parameters

# Specify the Python interpreter path
PYTHON_PATH="path/to/your/python3"  # Please modify to your Python interpreter path
# Path to the PFT.py script
PFT_SCRIPT="path/to/your/PFT.py"  # Please modify to your PFT.py script path
# Input file path
INPUT_FILE="path/to/your/kernel.c"  # Please modify to your input file path
# Target hardware architecture
ARCH="CPU"  # For example, GPU, CPU, etc.
# Strategy selection
METHOD="d"  # For example, p, d, mixed, etc.
# Optimization method
OPTIMIZATION="none"  # For example, padding, shifting, none, etc.
# Number of trials
TRIALS="1000"  # Default trials is 200, you can modify as needed
# Run PFT.py and pass parameters
$PYTHON_PATH $PFT_SCRIPT $INPUT_FILE $ARCH $METHOD $OPTIMIZATION $TRIALS
# ========================
# Code requirements
# ========================
# In the code, use the following `#pragma` directives:
# 1. `#pragma declarations` and `#pragma enddeclarations` should enclose array size declarations.
# 2. `#pragma scop` and `#pragma endscop` should mark loop bodies.