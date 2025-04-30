import re
import sympy
import numpy as np
from sympy import symbols, sympify
from generate_all_schedule import *
import subprocess
import time
import sympy as sp


def parse_array_sizes_from_c(file_path):
    arraysize = {}
    in_declaration = False

    # 捕获括号内的内容
    pattern = re.compile(r'\(([^)]+)\)')

    with open(file_path, 'r') as f:
        for line in f:
            stripped_line = line.strip()

            if stripped_line == "#pragma declarations":
                in_declaration = True
                continue
            if stripped_line == "#pragma enddeclarations":
                in_declaration = False
                break

            if in_declaration:
                match = pattern.search(stripped_line)
                if match:
                    content = match.group(1)
                    parts = [p.strip() for p in content.split(',')]
                    if len(parts) >= 2:
                        array_name = parts[0]
                        dims = parts[1:]  # 直接保留各个维度
                        arraysize[array_name] = dims

    return arraysize

def write_array_sizes(arraysize, output_file):
    # 'a' 模式为追加写入
    with open(output_file, 'a') as f:
        f.write("Array size:\n")
        for array, dims in arraysize.items():
            dim_str = ', '.join(dims)
            f.write(f"{array}: {dim_str}\n")
        f.write("//\n")

def is_access_list_within_iterators(access_list, iterators):
    for expr_str in access_list:
        expr = sympify(expr_str)
        symbols_in_expr = {str(s) for s in expr.free_symbols}
        if not symbols_in_expr.issubset(iterators):
            return False
    return True

def extract_g_coefficient_matrix(expr_dict, iter_vars):
    sym_vars = symbols(iter_vars)
    coeff_matrix = []
    processed_expr_list = []

    for expr_list in expr_dict.values():
        for expr_str in expr_list:
            expr = sympify(expr_str).expand()  # 展开表达式，方便处理
            processed_expr_list.append(str(expr))  # 保持字符串格式方便看
            coeffs = []
            for var in sym_vars:
                coeff = expr.coeff(var)
                coeffs.append(int(coeff))
            coeff_matrix.append(coeffs)

    return np.array(coeff_matrix), tuple(processed_expr_list)

def is_full_rank(matrix):
    """判断矩阵是否满秩"""
    rank = np.linalg.matrix_rank(matrix)
    min_dim = min(matrix.shape)
    return rank == min_dim

def is_unimodular(matrix):
    """
    判断矩阵是否为幺模矩阵（unimodular）。
    如果不是方阵，则截取成 min(m, n) 的方阵进行判断。
    幺模矩阵定义：整系数方阵，行列式为 ±1。
    """
    rows, cols = matrix.shape
    min_dim = min(rows, cols)
    square_matrix = matrix[:min_dim, :min_dim]  # 截取左上角子矩阵
    det = int(round(np.linalg.det(square_matrix)))
    return abs(det) == 1


def unimodular_generator(G):
    file_path = "valid_constraints.txt"
    constraints = extract_constraints(file_path)
    print("Constraints:", constraints)
    # 输入前 n-1 行
    #n_minus_1_rows = load_n_minus_1_rows("schedule_0.txt")
    # 查找所有满足条件的幺模矩阵
    all_unimodular_matrices = find_all_unimodular_matrices(G, constraints)

    # 保存所有满足条件的矩阵到 sch 文件夹
    save_matrices(all_unimodular_matrices)

    return all_unimodular_matrices

def call_pluto(source_file):
    """
    只调用 polycc 运行 Pluto，忽略输出内容。

    参数：
        source_file (str): C 源代码文件路径。
    """
    polycc_file = "/home/tree/lqz/pluto-0.11.4/polycc"
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Source file {source_file} not found.")

    cmd = [polycc_file, source_file]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print("Error running polycc:", e.stderr)

def coefficient_matrix_to_expressions(coeff_matrix, iter_vars):
    expressions = []
    for row in coeff_matrix:
        terms = []
        for coeff, var in zip(row, iter_vars):
            if coeff == 0:
                continue
            elif coeff == 1:
                terms.append(f"{var}")
            elif coeff == -1:
                terms.append(f"-{var}")
            else:
                terms.append(f"{coeff}*{var}")
        expr_str = ' + '.join(terms).replace('+ -', '- ')
        expressions.append(expr_str)
    return tuple(expressions)

def extract_coefficient_matrix(schedule, iter_vars):
    """
    提取调度表达式的系数矩阵
    :param schedule: tuple，如 ('i + j', 'n - j')
    :param iter_vars: list，迭代变量顺序，如 ['i', 'j']
    :return: 系数矩阵 list of list
    """
    # 将原始的 iter_vars 中的变量转化为 sympy 的 Symbol 对象
    variables = [sp.Symbol(var) for var in iter_vars]
    # 检查是否有额外的变量（如 n），并将其添加到变量列表中
    extra_vars = sorted(set().union(*(sp.sympify(expr).free_symbols for expr in schedule)) - set(variables), key=str)
    
    # 如果没有额外的变量（如 n），手动在最后添加 n，并将系数初始化为 0
    if not extra_vars:
        n = sp.Symbol('n')
        variables.append(n)
    else:
        # 如果有额外变量，将其加入变量列表
        variables.extend(extra_vars)

    matrix = []
    for expr in schedule:
        sym_expr = sp.sympify(expr)
        # 对每个变量提取系数，如果变量没有出现在表达式中，则系数为 0
        row = [int(sym_expr.coeff(var)) for var in variables]
        matrix.append(row)
    
    return matrix

def run_and_test_schedule(c_file, model,sch):
    """
    整合流程：提取系数 -> 写入txt -> Pluto生成 -> 编译运行 -> 返回运行时间和sch
    """
    polycc_path = "/home/tree/lqz/pluto-0.11.4/polycc"
    input_folder = "sch"
    output_folder = "after_pluto"
    os.makedirs(input_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)

    # 1. 提取系数矩阵
    matrix = extract_coefficient_matrix(sch,model['iterators'])
    print(f"提取的系数矩阵: {matrix}")

    # 2. 写入txt
    txt_file = os.path.join(input_folder, "temp_schedule.txt")
    with open(txt_file, 'w') as f:
        for row in matrix:
            f.write(' '.join(map(str, row)) + '\n')

    # 3. Pluto生成代码
    c_base_name = os.path.splitext(os.path.basename(c_file))[0]
    c_base_name = f"{c_base_name}_temp_schedule"   # 加上 temp_schedule
    output_c_file = os.path.join(output_folder, f"{c_base_name}.pluto.c")
    cmd = [polycc_path, c_file, "--inputfilename", txt_file, "-o", output_c_file]
    print(f"执行Pluto命令: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Pluto 生成成功 -> {output_c_file}")
    except subprocess.CalledProcessError as e:
        print(f"Pluto 执行失败:\n{e.stderr}")
        return None, sch

    # 4. 编译
    exe_file = os.path.join(output_folder, f"{c_base_name}.pluto")
    cmd_compile = ["gcc", "-O2", output_c_file, "-o", exe_file]
    print(f"编译命令: {' '.join(cmd_compile)}")
    try:
        subprocess.run(cmd_compile, check=True)
        print(f"编译成功 -> {exe_file}")
    except subprocess.CalledProcessError as e:
        print(f"编译失败:\n{e.stderr}")
        return None, sch

    # 5. 运行并计时
    input_size = 10
    cmd_run = [exe_file, str(input_size), str(input_size)]
    print(f"运行命令: {' '.join(cmd_run)}")
    try:
        start_time = time.time()
        result = subprocess.run(cmd_run, check=True, capture_output=True, text=True)
        end_time = time.time()
        exec_time = end_time - start_time
        print(f"运行输出:\n{result.stdout}")
        print(f"运行时间: {exec_time:.4f} 秒")
    except subprocess.CalledProcessError as e:
        print(f"运行失败:\n{e.stderr}")
        return None, sch
    return exec_time, sch




# 示例用法
if __name__ == "__main__":
    c_file = "1.c"           # 你的C文件路径
    output_txt = "arraysize.txt"   # 输出的txt文件
    result = parse_array_sizes_from_c(c_file)
    write_array_sizes(result, output_txt)
    print(f"数组信息已追加写入 {output_txt}")
