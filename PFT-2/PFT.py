from function import *
from file_ans import *
from Subfunctions import *
from code_generate import *
from new_polyhedral_model import *
import argparse
import os
import sys
from P2P import *
from P2T import *
import subprocess

# Create an argument parser to parse command-line arguments
parser = argparse.ArgumentParser(description="Parse polyhedral model and array size from files and apply optimization.")
# Argument for the polyhedral model file
parser.add_argument("C_file", type=str, help="source file")
# Argument for the architecure
parser.add_argument("arch", type=str, help="The name of the architecure")
# Argument for the optimization method (p, d, mixed)
parser.add_argument("optimization_method", type=str, choices=["p", "d", "mixed"], help="The optimization method to apply")
# Argument for the optimization method (padding,shifting,none)
parser.add_argument("other_optimization", type=str, choices=["padding","shifting","none"], help="other optimization method")
# Argument for the trials number
parser.add_argument("trials", type=int, help="The number of trials for tuning")
# Parse the command-line arguments
args = parser.parse_args()
call_pluto(args.C_file)

A_Z = parse_array_sizes_from_c(args.C_file)
filename = args.C_file  # Assume the filename is in the format "example.c"
base_name = os.path.splitext(filename)[0]  # Remove the .c extension to get "example"

output_filename = f"{base_name}_polyhedral_model.txt"  # Generate a new filename
write_array_sizes(A_Z, output_filename)  # Call the function and write to the new file
# Parse the polyhedral model from the specified file and extract the function name and models
function_name,array_sizes, models = parse_polyhedral_model(output_filename)
print(models)
for model in models:
    print(type(model))
    new_model = P2P(model,args.optimization_method,args.C_file)
    
    if new_model == False:
        print("Error in P2P")
        sys.exit()
    tc = P2T(new_model,array_sizes,args.other_optimization)
    
    
 
folder_path = 'new_compute'
if not os.path.exists(folder_path):
    os.makedirs(folder_path) 
file_path = os.path.join('new_compute',function_name+'.py')
code = ""
code += Dependencies_application()
code += function_application(function_name, 'n')
code += array_application(array_sizes)
with open(file_path,'a') as f:
    print(code,file = f)
    print(tc,file = f)
return_code= return_array_application(array_sizes)
with open(file_path,'a') as f:
    print(return_code,file = f)

my_tunner_code = tuning_code_generate(args.arch, function_name, 'n', args.trials)
with open(file_path,'a') as f:
    print(my_tunner_code,file = f)

print(code)
print(models)
print(array_sizes)