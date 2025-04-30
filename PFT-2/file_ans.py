import re
import os

def parse_polyhedral_model(filepath):
    polyhedral_info = []
    array_sizes = {}

    # Extract the function name from the filename
    filename = os.path.basename(filepath)
    function_name_match = re.match(r"(\w+)_polyhedral_model\.txt", filename)
    function_name = function_name_match.group(1) if function_name_match else "UnknownFunction"

    # Read the content of the file
    with open(filepath, 'r') as file:
        content = file.read()

    array_size_pattern = r"Array size:\n(.*?)\n//"
    array_size_match = re.search(array_size_pattern, content, re.DOTALL)
    if array_size_match:
        array_size_block = array_size_match.group(1).strip()
        # 每行形如 A:n 或 B:2*n-1
        for line in array_size_block.split('\n'):
            if ':' in line:
                array_name, size_expr = line.split(':', 1)
                array_sizes[array_name.strip()] = size_expr.strip()

    # Split the content into blocks for each statement using a line of dashes as the delimiter
    statement_blocks = re.split('-{40,}', content)
    for block in statement_blocks:
        # Parse iterators for the current statement
        iterators_pattern = r"Statement \d+ Iterators:\n(.*?)\n//"
        iterators_match = re.search(iterators_pattern, block, re.DOTALL)
        iterators = iterators_match.group(1).split() if iterators_match else []

        # Parse the parameters of the polyhedral model
        par_pattern = r"Par \d+:\n(.*?)\n//"
        par_match = re.search(par_pattern, block, re.DOTALL)
        par = par_match.group(1).split() if par_match else []

        # Parse the actual statement
        statement_pattern = r"Statement \d+: (.*?);\n//"
        statement_match = re.search(statement_pattern, block, re.DOTALL)
        statement = statement_match.group(1).strip() if statement_match else ""

        # Parse the domain constraints for the statement
        domain_pattern = r"Domain \d+: \[.*?\n(.*?)\n//"
        domain_match = re.search(domain_pattern, block, re.DOTALL)
        domain_constraints = domain_match.group(1).strip().split('\n') if domain_match else []

        # Parse the reads (arrays being read from)
        reads_pattern = r"Reads \d+:\n(.*?)\n//"
        reads_match = re.search(reads_pattern, block, re.DOTALL)
        reads_content = reads_match.group(1).strip() if reads_match else ""
        reads = {item.split(':')[0].strip(): item.split(':')[1].strip().split() for item in reads_content.split('\n') if item and ':' in item}

        # Parse the writes (arrays being written to)
        writes_pattern = r"Writes \d+:\n(.*?)\n//"
        writes_match = re.search(writes_pattern, block, re.DOTALL)
        writes_content = writes_match.group(1).strip() if writes_match else ""
        writes = {item.split(':')[0].strip(): item.split(':')[1].strip().split() for item in writes_content.split('\n') if item and ':' in item}

        # Parse the schedule for the current statement
        schedule_pattern = r"Schedule \d+:\n(.*?)\n"
        schedule_match = re.search(schedule_pattern, block, re.DOTALL)
        schedule_content = schedule_match.group(1).strip() if schedule_match else ""
        schedule = schedule_content.split()

        # Construct the polyhedral model dictionary
        polymodel = { 
            'iterators': iterators,
            'par': par,
            'statement': statement,
            'domain_constraints': domain_constraints,
            'reads': reads,
            'writes': writes,
            'schedule': schedule
        }
        polyhedral_info.append(polymodel)
    
    # Return the function name and the list of polyhedral model information
    return function_name, array_sizes,polyhedral_info


def parse_array_size(filepath):
    array_sizes = {}
    filename = os.path.basename(filepath)

    # Read the content of the file
    with open(filepath, 'r') as file:
        content = file.read()

    # Extract the array sizes
    array_size_pattern = r"Array size:\n(.*)"
    array_size_match = re.search(array_size_pattern, content, re.DOTALL)
    
    if array_size_match:
        array_size_content = array_size_match.group(1).strip()
        array_size_lines = array_size_content.split('\n')
        for line in array_size_lines:
            array, size = line.split(':')
            array_sizes[array.strip()] = [size.strip()]

    # Return the dictionary of array sizes
    return array_sizes
