from file_ans import *
from Subfunctions import *
import textwrap
def Dependencies_application():
    """
    生成包含依赖库和基本 Ansor 工作负载注册代码的字符串。
    """
    Dependencies_code = (
        "import tvm\n"
        "from tvm import te, auto_scheduler\n"
        "import sys\n"
        "import time\n"
        "import numpy as np\n"
        "from tvm import tir\n\n"
        "@auto_scheduler.register_workload\n"
    )
    return Dependencies_code

def function_application(function_name, params):
    # Convert the parameter list to a comma-separated string
    param_str = ", ".join(params)
    
    # Generate the function definition code
    function_code = f"def {function_name}({param_str}):\n"
    
    return function_code



def array_application(array_info):
    tvm_code = ""
    
    for array_name, size_exprs in array_info.items():
        # Convert size expressions to symbolic expressions and simplify
        size_exprs_sym = [sp.sympify(size_expr) for size_expr in size_exprs]
        size_exprs_str = [str(sp.simplify(expr)) for expr in size_exprs_sym]

        # 处理一维和多维的元组格式
        if len(size_exprs_str) == 1:
            # 一维时需要添加逗号：(x,)
            size_str = f"({size_exprs_str[0]},)"
        else:
            # 多维直接拼接：(x, y, z)
            size_str = f"({', '.join(size_exprs_str)})"

        # Generate TVM placeholder code
        code = f'\t{array_name} = te.placeholder({size_str}, name="{array_name}", dtype="float32")\n'
        tvm_code += code

    return tvm_code

def reduce_axis_application(axis_info):
    tvm_code = ""
    
    for axis_name, axis_range in axis_info.items():
        # Convert range expressions to symbolic expressions and simplify
        min_val = sp.sympify(axis_range[0])
        max_val = sp.sympify(axis_range[1]+1)

        # Generate TVM reduce_axis code
        code = f'\t{axis_name} = te.reduce_axis(({min_val}, {max_val}), name="{axis_name}")\n'
        tvm_code += code

    return tvm_code

def padding(padding_if_condition, padding_index, needpadding_arrays, statement_info):    
    tvm_code = ""
    n = sp.symbols('n')
    
    for array_name, padding_info in needpadding_arrays.items():
        new_size = padding_info['new_size']
        print('padding_if_condition',padding_if_condition)
        conditions = padding_if_condition[array_name]
        indices = padding_index[array_name]

        # Change the original array name to the new array name
        new_array_name = array_name + '1'
        # Generate multi-dimensional TVM compute code based on number of dimensions
        dims = len(new_size)  # Get the number of dimensions
        dim_indices = [f"i{d+1}" for d in range(dims)]  # Generate indices: i1, i2, i3, ...
        condition_str = f"tvm.tir.all({''.join(conditions)})"

        index_str = ', '.join(indices[:dims])  # Index string for each dimension

        # Generate TVM compute code for multi-dimensional arrays
        code = f"""
\t{new_array_name} = te.compute(
    ({', '.join(map(str, new_size))}), 
    lambda {', '.join(dim_indices)}:
        te.if_then_else(
            {condition_str}, 
            {array_name}[{index_str}], 
            0
    ), 
    name='{new_array_name}'
)
"""     
        tvm_code += code

        # Update only the right_part
        right_part = statement_info['right_part']

        # Replace the array name
        updated_right_part = right_part.replace(array_name, new_array_name)
        
        # Use regular expressions to match the array indices of new_array_name
        
        def replace_negative_indices(match):
            expr = match.group(1)
            # Parse the expression using SymPy
            sympy_expr = sp.sympify(expr)
    
            # 获取 n 的系数
            coeff_n = sympy_expr.coeff(n)
        
            # 只有当 n 的系数为负时才移除 n 项
            if coeff_n < 0:
                simplified_expr = sympy_expr - coeff_n * n
            else:
                simplified_expr = sympy_expr
        
            return f"[{simplified_expr}]"

        # Match only the index part of new_array_name and handle negative values
        updated_right_part = re.sub(
            rf'{new_array_name}\[([^\]]+)\]', 
            lambda m: f"{new_array_name}{replace_negative_indices(m)}", 
            updated_right_part
        )
        
        # Update the right_part in statement_info
        statement_info['right_part'] = updated_right_part

    return tvm_code, statement_info


# Input statement info and new array size information after shifting
def shifting(statement_info, new_array_size):
    tvm_code = ""
    n = sp.symbols('n')
    right_part = statement_info['right_part']
    
    left_part = statement_info['left_part']
    array_name, left_part_indices = list(left_part.items())[0] 
    new_left_part_indices = ', '.join(map(str, left_part_indices))

    code = f"""
\t{array_name} = te.compute(
    ({new_array_size}, 
    lambda {new_left_part_indices}:
        (
        {right_part}
    ), 
    name='{array_name}'
)
"""  
    tvm_code += code
    return tvm_code

def compute_application_nopadding(statement_info, var_range, axis_info,if_conditions):
    left_part = statement_info['left_part']
    right_part = statement_info['right_part']

    # Extract array name and indices from left_part
    array_name, indices = list(left_part.items())[0]
    indices_str = ", ".join(indices)
    
    # Get the maximum value of each index variable from var_range and simplify
    array_sizes = [sp.sympify(f"{var_range[idx][1]} + 1") for idx in indices]
    array_sizes_str = ", ".join([str(size.simplify()) for size in array_sizes])

    # Extract information from axis_info
    axis_name = list(axis_info.keys())[0]
    print(if_conditions)
    
    # Generate te.compute code
    compute_expr = f'te.sum(te.if_then_else(tvm.tir.all({if_conditions}),{right_part},0), axis={axis_name})'
    compute_code = f'\t{array_name} = te.compute(({array_sizes_str}), lambda {indices_str}: {compute_expr}, name="{array_name}")\n'
    
    return compute_code


def compute_application(statement_info, var_range, axis_info):
    left_part = statement_info['left_part']
    right_part = statement_info['right_part']

    # Extract array name and indices from left_part
    array_name, indices = list(left_part.items())[0]
    indices_str = ", ".join(indices)

    # Generate array sizes (max index + 1)
    array_sizes = [sp.sympify(f"{var_range[idx][1]} + 1") for idx in indices]
    array_sizes_list = [str(size.simplify()) for size in array_sizes]

    # 关键修改点：处理单维和多维元组格式
    if len(array_sizes_list) == 1:
        array_sizes_str = f"({array_sizes_list[0]},)"  # 单维元组需要逗号
    else:
        array_sizes_str = f"({', '.join(array_sizes_list)})"  # 多维直接拼接

    # Extract reduction axis
    axis_name = list(axis_info.keys())[0]

    # Generate te.compute code
    compute_expr = f'te.sum({right_part}, axis={axis_name})'
    compute_code = (
        f'\t{array_name} = te.compute('
        f'{array_sizes_str}, '
        f'lambda {indices_str}: {compute_expr}, '
        f'name="{array_name}")\n'
    )
    
    return compute_code

def return_array_application(array_size):
    # Extract all array names
    array_names = list(array_size.keys())
    
    # Join array names into a string to generate a return statement
    return_statement = "\treturn [" + ", ".join(array_names) + "]"
    
    return return_statement




def tuning_code_generate(arch, function_name, params,trials):
    mytunner_code = ""
    tuning_code = ""  # 确保变量已初始化
    
    if arch == "GPU":
        tuning_code = (
            "    target = tvm.target.Target('cuda')\n"
            "    ctx = tvm.gpu(0)\n"
        )
    elif arch == "CPU":
        tuning_code = (
            "    target = tvm.target.Target('llvm')\n"
            "    ctx = tvm.cpu(0)\n"
        )
    else:
        raise ValueError(f"Unsupported architecture: {arch}")  # 避免无效架构

    code = f"""
def mytuner(n):
{tuning_code}
    task = tvm.auto_scheduler.SearchTask(func={function_name}, args=({params},), target=target)
    log_file = "{function_name}.json"
    
    tune_option = auto_scheduler.TuningOptions(
        early_stopping=50,
        num_measure_trials={trials},
        measure_callbacks=[auto_scheduler.RecordToFile(log_file)],
        verbose=2,
    )
    
    task.tune(tune_option)
    sch, args = task.apply_best(log_file)
    
    print(tvm.lower(sch, args, simple_mode=True))
    func = tvm.build(sch, args, target)

if __name__ == '__main__':
    n = int(sys.argv[1])
    mytuner(n)
"""  
    mytunner_code += textwrap.dedent(code)  # 规范缩进
    return mytunner_code

