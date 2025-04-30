from file_ans import *
import sympy as sp
import re
from sympy import symbols, parse_expr

def parse_domain_constraints(polyhedral_model):

    n = sp.symbols('n')
    I = sp.symbols('I', real=True)
    # List of constraint strings
    iterators = polyhedral_model['iterators']

    iter_symbols = [sp.Symbol(var) for var in iterators]
    
    inequalities = []
    for constraint in polyhedral_model['domain_constraints']:
        constraint_expr = sp.sympify(constraint)
        if any(symbol in constraint_expr.free_symbols for symbol in iter_symbols): 
            # Remove extra spaces from the string,remove the n>0
            clean_constraint = constraint.replace(" ", "")
            lhs, rhs = clean_constraint.split(">=")
            lhs_expr = sp.sympify(lhs)
            rhs_expr = sp.sympify(rhs)
            inequalities.append(sp.Ge(lhs_expr, rhs_expr))
    # Define two parts
    part1 = []
    part2 = []
    # Classify the inequalities
    for inequality in inequalities:
        lhs = inequality.lhs
        # Extract variables in the inequality (excluding n)
        vars_in_inequality = lhs.free_symbols - {n}
        # Check if it only contains one variable and its coefficient is ±1
        if len(vars_in_inequality) == 1:
            var = list(vars_in_inequality)[0]
            coeff = lhs.as_coefficients_dict().get(var, 0)
            if coeff == 1 or coeff == -1:
                part1.append(inequality)
            else:
                part2.append(inequality)
        else:
            part2.append(inequality)

    part1_str = [f"{ineq.lhs} >= {ineq.rhs}" for ineq in part1]
    part2_str = [f"{ineq.lhs} >= {ineq.rhs}" for ineq in part2]
    return part1_str, part2_str

def Determine_scope(part1_str):
    range_dict = {}
    for constraint in part1_str:
        # Parse constraints in the form of "+i >= 0" or "-i +n -1 >= 0"
        match = re.match(r"(?:\s*)([+-]?)([a-zA-Z])(?:\s*)([+-]?)(.*?)(?:\s*)([><=]+)(?:\s*)(\d+)", constraint)
        if match:
            sign, var, op0, minmax, op1, value = match.groups()

            if var not in range_dict:
                range_dict[var] = [float('inf'), float('-inf')]  # Initialize minimum and maximum values
            if sign == '-':
                range_dict[var][1] = minmax  
            else:
                if op0 == "":
                    range_dict[var][0] = value
                elif op0 == '-':
                    range_dict[var][0] = minmax
                elif op0 == '+':
                    range_dict[var][0] = '-' + minmax              
    return range_dict

def determine_reduce_axis(polyhedral_model, range_dict):
    axes = set()
    axis_ranges = {}

    # Extract all iterators from the model info
    all_iterators = set(polyhedral_model['iterators'])
        
    # Extract the write array information
    write_array = polyhedral_model['writes']

    # Iterate over the write arrays to collect used axes
    reax = set()
    for value_list in write_array.values():
        reax.update(value_list)

        # Determine the reduce axes by finding the difference
    axes.update(all_iterators - reax)

    for axe in axes:
        if axe in range_dict:  # Ensure the axis is present in range_dict
            axis_ranges[axe] = range_dict[axe]

    # Return the reduce axis names and their ranges
    return axis_ranges

def determine_new_reduce_axis(new_statement_info, new_var_range):
    # Extract variable names from left_part (parse index expressions)
    left_part_vars = set()
    for array_name, indices in new_statement_info['left_part'].items():
        for index_expr in indices:
            # Convert index expression to a sympy expression
            expr = sp.sympify(index_expr)
            # Extract variables from the expression
            left_part_vars.update([str(v) for v in expr.free_symbols])

    # Calculate new_reduce_axis
    new_reduce_axis = {var: range_ for var, range_ in new_var_range.items() if var not in left_part_vars}

    return new_reduce_axis    

def parse_range(range_str):
    # Parse a single range string and convert it into a computable range
    range_str = range_str.replace(' ', '')
    match = re.match(r'([^\-]+)-(.+)', range_str)
    if not match:
        raise ValueError(f"Invalid range format: {range_str}")
    start, end = match.groups()
    start = sp.sympify(start)
    end = sp.sympify(end)
    return start, end

# Calculate new variable intervals based on the schedule
def interval_operation(ranges, expressions, results):
    # Create symbolic variables
    variables = {var: sp.Symbol(var) for var in ranges.keys()}
    n = sp.Symbol('n')
    
    # Calculate result intervals
    for expression in expressions:
        # Parse the expression
        expr = sp.sympify(expression, locals=variables)
        min_vals = {}
        max_vals = {}
        for var, (start, end) in ranges.items():
    # 提取当前变量的系数
            coeff = expr.coeff(variables[var])
    
    # 根据变量的系数是否为负数决定最值的取值方向
            if coeff < 0:  # 如果当前变量的系数为负
                min_vals[variables[var]] = end  # 交换最小值和最大值
                max_vals[variables[var]] = start
            else:  # 如果当前变量的系数为非负
                min_vals[variables[var]] = start
                max_vals[variables[var]] = end

        
        result_min = expr.subs(min_vals)
        result_max = expr.subs(max_vals)

        #oppsite_min = -result_min
        final_min = sp.simplify(result_min)
        final_max = sp.simplify(result_max)
        
        results.append((final_min, final_max))
    # Return result intervals
    return results

def generate_variable_names(count, prefix='t'):
    return [f"{prefix}{i+1}" for i in range(count)]

def create_new_variables(intervals,model,sch):
    ranges = {}
    new_variables = {}
    mapping = {}
    for var, range_str in intervals.items():

        ranges[var] = parse_range(range_str[0] + "-" + range_str[1])

    expressions = sch

    # n-j
    interval_results = interval_operation(ranges, expressions, [])

    # Generate new variable names
    variable_names = generate_variable_names(len(expressions))
    for idx, (result_min, result_max) in enumerate(interval_results):
        new_variables[variable_names[idx]] = (result_min, result_max)
        mapping[expressions[idx]] = variable_names[idx]
    

    return new_variables, mapping

def inverse_mapping(expressions, mapping, variables):
    # Create symbolic variables
    symbols = {var: sp.Symbol(var) for var in variables}
    new_symbols = {mapping[expr]: sp.Symbol(mapping[expr]) for expr in expressions}
    
    # Build the system of equations
    equations = []
    for expr in expressions:
        lhs = sp.sympify(expr, locals=symbols)
        rhs = sp.sympify(mapping[expr], locals=new_symbols)
        equations.append(sp.Eq(lhs, rhs))
    
    # Solve the system of equations
    solutions = sp.solve(equations, list(symbols.values()))
    
    # Construct the inverse mapping dictionary
    inverse_mapping_dict = {}
    for var in variables:
        inverse_mapping_dict[var] = str(solutions[symbols[var]])
    
    return inverse_mapping_dict



# Extracts the statement and divides it into left and right parts
def parse_statement(polyhedral_info):
    result = {}
    
    statement = polyhedral_info['statement']
    # Split the statement at the '=' sign
    if isinstance(statement,dict):
        left_dict = statement['left_part']
        right_part = statement['right_part']
    else:
        left_part, right_part = statement.split('=')
    # elif  in statement:
    #     left_part, right_part = statement.split('=')
    # Remove leading and trailing whitespace
        left_part = left_part.strip()
        right_part = right_part.strip()
    
    # Initialize dictionaries for left part
        left_dict = {}
    
        # Match array name and loop variables in the left part
        if '][' not in left_part:
            pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\[(.*?)\]'
            match = re.match(pattern, left_part)
            if match:
                array_name = match.group(1)
                index = match.group(2)
                left_dict={array_name: [index]}
            else:
                raise ValueError("The input string format is incorrect")
        else:
            # Extract multi-dimensional array index part
            pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\[(.+)\]'
            match = re.match(pattern, left_part)
            if match:
                array_name = match.group(1)
                indices_part = match.group(2)
                # Split the index part
                indices = indices_part.split('][')
                left_dict ={array_name: indices}
            else:
                raise ValueError("The input string format is incorrect")
       
    result['left_part'] = left_dict
    result['right_part'] = right_part
    return result


# def replace_variables(statement_info, old_to_new_mapping):
#     def replace_expression(expression, mapping):
#         sorted_mapping = sorted(mapping.items(), key=lambda x: -len(x[0]))
#         for old_var, new_var in sorted_mapping:
#             expression = re.sub(r'\b{}\b'.format(re.escape(old_var)), f'({new_var})', expression)
#         return expression
    
#     def simplify_expression(expression):
#         try:
#             # Use regular expressions to extract all sub-expressions
#             pattern = re.compile(r'(\w+)\[([^\[\]]+)\]')
#             matches = pattern.findall(expression)
            
#             simplified_expression = expression
#             for var, sub_expr in matches:
#                 simplified_sub_expr = sp.simplify(sub_expr)
#                 simplified_expression = simplified_expression.replace(sub_expr, str(simplified_sub_expr))
            
#             # Simplify the entire expression
#             sympy_expr = sp.sympify(simplified_expression)
#             simplified_expr = sp.simplify(sympy_expr)
#             return str(simplified_expr)
#         except Exception as e:
#             print(f"Error simplifying expression {expression}: {e}")
#             return expression
    
#     new_statement_info = {'left_part': {}, 'right_part': ''}

#     # Replace and simplify the left part
#     new_left_part = {}
#     for key, value in statement_info['left_part'].items():
#         new_key = old_to_new_mapping.get(key, key)
#         new_value = [simplify_expression(replace_expression(v, old_to_new_mapping)) for v in value]
#         new_left_part[new_key] = new_value
        
#     new_statement_info['left_part'] = new_left_part

#     # Replace and simplify the right part
#     right_part = replace_expression(statement_info['right_part'], old_to_new_mapping)
#     simplified_right_part = right_part
    
#     # Use regular expressions to extract all sub-expressions and simplify
#     pattern = re.compile(r'(\w+)\[([^\[\]]+)\]')
#     matches = pattern.findall(right_part)
    
#     for var, sub_expr in matches:
#         simplified_sub_expr = str(sp.simplify(sub_expr))
#         simplified_right_part = simplified_right_part.replace(sub_expr, simplified_sub_expr)

#     new_statement_info['right_part'] = simplified_right_part

#     return new_statement_info
def replace_variables(statement_info, old_to_new_mapping):
    def replace_expression(expression, mapping):
        # 排序映射，确保长的变量名先被替换，避免冲突
        sorted_mapping = sorted(mapping.items(), key=lambda x: -len(x[0]))
        for old_var, new_var in sorted_mapping:
            expression = re.sub(r'\b{}\b'.format(re.escape(old_var)), f'({new_var})', expression)
        return expression

    def simplify_expression(expression):
        try:
            # 使用 sympy 化简表达式
            sympy_expr = sp.sympify(expression)
            simplified_expr = sp.simplify(sympy_expr)
            return str(simplified_expr)
        except Exception as e:
            print(f"Error simplifying expression {expression}: {e}")
            return expression

    # 提取索引并化简的辅助函数
    def extract_indices_only(statement):
        pattern = r'\[(.*?)\]'
        matches = re.findall(pattern, statement)
        return matches
    def simplify_indices(indices):
        simplified_indices = []
        for index in indices:
            try:
                # 将索引表达式用 sympy 进行化简
                simplified_expr = sp.simplify(index)
                simplified_indices.append(str(simplified_expr))
            except Exception as e:
                print(f"Error simplifying index {index}: {e}")
                simplified_indices.append(index)
        return simplified_indices

    new_statement_info = {'left_part': {}, 'right_part': ''}

    # 替换并化简左侧部分
    new_left_part = {}
    for key, value in statement_info['left_part'].items():
        new_key = old_to_new_mapping.get(key, key)
        new_value = [simplify_expression(replace_expression(v, old_to_new_mapping)) for v in value]
        new_left_part[new_key] = new_value
    new_statement_info['left_part'] = new_left_part

    # 替换并处理右侧部分
    right_part = replace_expression(statement_info['right_part'], old_to_new_mapping)

    # 提取和化简数组索引部分
    def simplify_array_indices(expression):
        # 提取所有的索引部分
        indices = extract_indices_only(expression)
        # 对每个索引进行化简
        simplified_indices = simplify_indices(indices)

        # 替换原有索引为化简后的索引
        for original, simplified in zip(indices, simplified_indices):
            expression = expression.replace(f'[{original}]', f'[{simplified}]')
        return expression

    # 化简右侧的数组索引
    simplified_right_part = simplify_array_indices(right_part)
    new_statement_info['right_part'] = simplified_right_part

    return new_statement_info
     
# 代解决     
def calculate_array_size(new_statement_info, new_var_range):

    def get_max_size(indices, var_ranges):
        exprs = [sp.sympify(idx) for idx in indices.split(',')]
        min_sizes = []
        max_sizes = []
        
        for expr in exprs:
            min_expr = expr
            max_expr = expr
            
            for var, (min_val, max_val) in var_ranges.items():
                var_sym = sp.symbols(var)

                coeff = expr.coeff(var_sym)
                if coeff > 0:
                    min_expr = min_expr.subs(var_sym, min_val)
                    max_expr = max_expr.subs(var_sym, max_val)
                elif coeff<0:
                    min_expr = min_expr.subs(var_sym, max_val)
                    max_expr = max_expr.subs(var_sym, min_val)

                    
            min_sizes.append(min_expr)
            max_sizes.append(max_expr)
        
        max_sizes = [sp.simplify(max_expr - min_expr + 1) for max_expr, min_expr in zip(max_sizes, min_sizes)]
        return max_sizes

    left_part = new_statement_info['left_part']
    right_part = new_statement_info['right_part']
    
    pattern = re.compile(r'(\w+)\[([^\]]+)\]')
    matches = pattern.findall(right_part.replace('][', ','))
    
    Arrays_Indices = {}
    new_array_size = {}
    
    for array, indices in matches:
        indices = indices.strip()
        Arrays_Indices[array] = indices
        new_array_size[array] = get_max_size(indices, new_var_range)
    
    for var, indices_list in left_part.items():
        indices = ', '.join(indices_list)
        Arrays_Indices[var] = indices
        new_array_size[var] = get_max_size(indices, new_var_range)

    return Arrays_Indices, new_array_size

def find_which_array_needpadding(array_size, new_array_size, Arrays_Indices):
    print('333',array_size)
    print(Arrays_Indices)
    old_array_size = array_size
    print(new_array_size)
    print(old_array_size)

    # 将字符串转换为符号表达式
    for key, size_str in old_array_size.items():
        # 分割逗号，并将每个部分转化为符号表达式
        size_list = [sp.sympify(s.strip()) for s in size_str.split(',')]
        old_array_size[key] = size_list
        
    for key in old_array_size:
        if isinstance(old_array_size[key], list) and isinstance(old_array_size[key][0], tuple):
            # 将元组列表转换为普通列表
            old_array_size[key] = list(old_array_size[key][0])

    arrays_need_padding = {}

    n = sp.symbols('n')

    for array_name, old_size in old_array_size.items():
        if array_name in new_array_size:
            new_size = new_array_size[array_name]

            if isinstance(old_size, list) and isinstance(new_size, list):
                old_size = [sp.sympify(os) for os in old_size]
                new_size = [sp.sympify(ns) for ns in new_size]
                
                if len(old_size) != len(new_size) or any(sp.simplify(os - ns) != 0 for os, ns in zip(old_size, new_size)):
                    arrays_need_padding[array_name] = {
                        'indices': Arrays_Indices[array_name],
                        'new_size': new_size
                    }
            else:
                old_size = sp.sympify(old_size)
                new_size = sp.sympify(new_size)
                if sp.simplify(old_size - new_size) != 0:
                    arrays_need_padding[array_name] = {
                        'indices': Arrays_Indices[array_name],
                        'new_size': new_size
                    }
    print('444',array_size)
    return arrays_need_padding

def array_index_convert_if_condition_two_dim(array_name, info, var_range):
    range_dict = {}

    # 如果 info['indices'] 是列表，遍历每个维度的索引表达式
    if isinstance(info['indices'], list):
        indices_expr_list = [sp.sympify(expr) for expr in info['indices']]
    else:
        # 如果是单一表达式，转换为列表以便统一处理
        indices_expr_list = [sp.sympify(info['indices'])]

    # 初始化存储不同维度的 min_val 和 max_val
    min_ranges = []
    max_ranges = []

    # 遍历每个维度的索引表达式
    for indices_expr in indices_expr_list:
        min_val = indices_expr
        max_val = indices_expr

        # 遍历 var_range 中的变量及其取值范围
        for var, (start, end) in var_range.items():
            var_symbol = sp.Symbol(var)
            coeff = indices_expr.coeff(var_symbol)

            # 根据系数符号更新最小值和最大值
            if coeff >= 0:
                # 系数为正：min使用start，max使用end
                min_val = min_val.subs(var_symbol, start)
                max_val = max_val.subs(var_symbol, end)
            else:
                # 系数为负：min使用end，max使用start
                min_val = min_val.subs(var_symbol, end)
                max_val = max_val.subs(var_symbol, start)

        # 计算该维度的最小范围和最大范围
        min_ranges.append(sp.simplify(min_val))
        max_ranges.append(sp.simplify(max_val))

    # 将所有维度的最小/最大范围打包进 range_dict
    range_dict[array_name] = list(zip(min_ranges, max_ranges))
    
    return range_dict

def find_padding_if_conditon(oldsize, needpadding_arrays, statement_info,new_ranges):
    
    n = sp.symbols('n')
    padding_if_condition = {}
    padding_index = {}
    for array_name, padding_info in needpadding_arrays.items():
        indices = padding_info['indices']
        new_sizes = padding_info['new_size']
        index_exprs = [sp.sympify(idx) for idx in indices.split(', ')]
        #result = [expr for expr in index_exprs[0]]
        print('index_exprs',index_exprs)
        conditions = []
        index_expressions = []

        for index_expr, old_size in zip(index_exprs, oldsize[array_name]):
            coeff_n = index_expr.coeff(n)
            old_size = sp.sympify(f"{old_size}-1")
            if coeff_n != 0:
                if coeff_n > 0:
                    if coeff_n == 1:
                        condition = f"0 <= i + n <= {old_size}"
                        index_expr_str = f"i +n"
                    else:    
                        condition = f"0 <= i + {coeff_n}*n <= {old_size}"
                        index_expr_str = f"i + {coeff_n}*n"
                else:
                    if coeff_n == -1:
                        condition = f"0 <= i - n <= {old_size}"
                        index_expr_str = f"i - n"
                    else:
                        condition = f"0 <= i - {abs(coeff_n)}*n <= {old_size}"
                        index_expr_str = f"i - {abs(coeff_n)}*n"
            else:
                range_dict = array_index_convert_if_condition_two_dim(array_name,padding_info,new_ranges)
                print('range_dictrange_dict',range_dict)
                for arrray_name,(min_range,max_range) in range_dict.items():
                    if min_range ==0:
                        condition = f"0 <= i <= {old_size}"
                        index_expr_str = f"i"
                    else:
                        condition = f"{-min_range}<= i <= {max_range}"
                        index_expr_str = f"i-{-min_range}"
                        index_expr_str = str(sp.sympify(index_expr_str))
                        ringht_part = statement_info['right_part']
                        new_indexs = f"{indices}-({min_range})"
                        new_indexs = str(sp.sympify(new_indexs))

                        ringht_part = ringht_part.replace(indices,new_indexs)
                        statement_info['right_part'] = ringht_part
            conditions.append(condition)
            index_expressions.append(index_expr_str)
            
        if conditions:
            padding_if_condition[array_name] = ' and '.join(conditions)
            padding_index[array_name] = index_expressions
    
    return padding_if_condition, padding_index    

def split_inequality(inequality):
        # 使用正则表达式匹配任意连续不等式的格式 "lower_bound <= expr <= upper_bound"
    match = re.match(r"(.+?) <= (.+?) <= (.+)", inequality)
    if not match:
        raise ValueError("Input inequality format is incorrect. Expected format: lower_bound <= expr <= upper_bound")
    
    # 提取表达式和上界
    lower_bound = match.group(1).strip()
    expr = match.group(2).strip()
    upper_bound = match.group(3).strip()
    
    split_inequality_str = f"{lower_bound} <= {expr} ,{expr} <= {upper_bound}"
    
    return split_inequality_str 

def replace_indices_once(expression, old_index, new_index,replaced):
    """
    对字符串表达式进行替换，每个索引子表达式只替换一次。
    
    Args:
        expression (str): 原始字符串表达式。
        replacements (list of tuples): 每个元组包含 (old_index, new_index)。
        
    Returns:
        str: 替换后的表达式。
    """
    print('replaced',replaced)
    print(old_index)
    if old_index not in replaced:
        # 确保只替换未处理过的索引
        expression = expression.replace(old_index, new_index)
        replaced.append(old_index)  # 标记为已替换

    return expression

def find_padding_if_conditon_two_dim(oldsize, needpadding_arrays, statement_info,new_ranges):
    n = sp.symbols('n')
    padding_if_condition = {}
    padding_index = {}
    replaced=[]
    for array_name, padding_info in needpadding_arrays.items():
        indices = padding_info['indices']

        new_sizes = padding_info['new_size']
        dimensions = [dim.strip() for dim in indices.split(',')]
        
        
        index_exprs = [sp.sympify(idx) for idx in indices.split(', ')]

        # 判断是否为一维情况
        if len(index_exprs) == 1 and isinstance(index_exprs[0], sp.Expr):
        # 如果是单个表达式，直接将其作为结果
            result = index_exprs
        elif len(index_exprs) == 1 and isinstance(index_exprs[0], (tuple, list)):
        # 如果是元组或列表，解包处理
            result = [expr for expr in index_exprs[0]]
        padding_info['indices'] = result
        conditions = []
        index_expressions = []
        dims = len(new_ranges) -1
        for dim, expr in enumerate(result):
            conditions_for_expr = []  # 存储该表达式的所有维度条件
            index_exprs_for_expr = []  # 存储该表达式的索引表达式
            var = f"i{dim+1}" 
            if new_sizes[dim] == oldsize[array_name][dim]:
                condition = ""
                index_expr_str = f"{var}"
                
            else:    
                coeff_n = expr.coeff(n)
                old_size_dim = sp.sympify(f"{oldsize[array_name][dim]} - 1") 
                if coeff_n != 0:
                    if coeff_n > 0:
                        if coeff_n == 1:
                            condition = f"0 <= {var} + n <= {old_size_dim}"
                            index_expr_str = f"{var} +n"
                        else:    
                            condition = f"0 <= {var} + {coeff_n}*n <= {old_size_dim}"
                            index_expr_str = f"{var} + {coeff_n}*n"
                        if condition:
                                    condition = split_inequality(condition)
                                    conditions.append(condition)
                    else:
                        if coeff_n == -1:
                            condition = f"0 <= {var} - n <= {old_size_dim}"
                            index_expr_str = f"{var} - n"

                        else:
                            condition = f"0 <= {var} - {abs(coeff_n)}*n <= {old_size_dim}"
                            index_expr_str = f"{var} - {abs(coeff_n)}*n"
                        if condition:
                            condition = split_inequality(condition)
                            conditions.append(condition)
                else:

                    # 调用 array_index_convert_if_condition 之后
                    range_dict = array_index_convert_if_condition_two_dim(array_name, padding_info, new_ranges)

                    
                    # 遍历 range_dict 时，区分一维和多维情况
                    for array_name, ranges in range_dict.items():
                        # 检查 ranges 是否为单维度
                        if isinstance(ranges[0], tuple):
                            # 多维的情况，逐个解包 (min_range, max_range)
                            (min_range, max_range) = ranges[dim]
                            if min_range == 0:
                                condition = f"0 <= {var} <= {old_size_dim}"
                                index_expr_str = f"{var}"
                                print('problemproblem')
                            else:
                                rigtht_bound = str(sp.sympify(f"({-min_range})+{old_size_dim}"))
                                condition = f"{-min_range} <= {var} <= {rigtht_bound}"

                                index_expr_str = f"{var} + ({min_range})"
                                index_expr_str = str(sp.sympify(index_expr_str))


                                # 更新 right_part 中的索引
                                ringht_part = statement_info['right_part']

                                #dimensions[dim] = dimensions[dim].strip()
                                new_indexs = f"{dimensions[dim]} - ({min_range})"

                                new_indexs = str(sp.sympify(new_indexs))
                                # ringht_part =ringht_part.replace(dimensions[dim], new_indexs)
                                
                                # print('ringht_part2',ringht_part)
                                # statement_info['right_part'] = ringht_part
                                statement_info['right_part'] = replace_indices_once(ringht_part,dimensions[dim],new_indexs,replaced)

                            if condition:
                                    condition = split_inequality(condition)
                                    conditions.append(condition)

                        else:
                            # 一维情况，直接解包 (min_range, max_range)
                            min_range, max_range = ranges[0]
                            if min_range == 0:
                                condition = f"0 <= {var} <= {old_size_dim}"
                                index_expr_str = f"{var}"
                            else:
                                condition = f"{-min_range} <= {var} <= {max_range}"
                                index_expr_str = f"{var} - {-min_range}"
                                index_expr_str = str(sp.sympify(index_expr_str))

                                # 更新 right_part 中的索引
                                ringht_part = statement_info['right_part']
                                new_indexs = f"{indices} - ({min_range})"
                                new_indexs = str(sp.sympify(new_indexs))

                                ringht_part.replace(indices, new_indexs)
                                statement_info['right_part'] = ringht_part

                                if condition:
                                    condition = split_inequality(condition)
                                    
                                    conditions.append(condition)
                                
            index_expressions.append(index_expr_str)

        if conditions:
            padding_if_condition[array_name] = ','.join(conditions)
            padding_index[array_name] = index_expressions

    return padding_if_condition, padding_index  

def find_nominal_if_conditions(statement_info):
    right_part = statement_info.get('right_part', '')
    n = symbols('n')  # 定义符号n

    # 正则表达式匹配 [] 中的内容
    pattern = r'\[([^\[\]]+)\]'  # 匹配方括号中的内容
    matches = re.findall(pattern, right_part)
    
    index_expressions = set()  # 使用集合去重
    for match in matches:
        try:
            expr = parse_expr(match)  # 使用 SymPy 解析为表达式
            index_expressions.add(expr)
        except Exception as e:
            print(f"Error parsing index: {match}. Error: {e}")
    
    # 生成条件
    conditions = []
    for expr in index_expressions:
        conditions.append(f"{expr} >= 0")
        conditions.append(f"{expr} < {n}")
    
    condition_str = ",".join(conditions)
    return condition_str
    
def find_shifting_size(statement_info, array_sizes):
    array_sizes0 = {key: (sp.symbols('n'), sp.symbols('n')) for key in array_sizes}
    
    right_part = statement_info['right_part']
    
    left_part = statement_info['left_part']
    
    array_name, left_part_indices = list(left_part.items())[0] 

    
    array_size = array_sizes0[array_name]

    num_dimensions = len(array_size)
    updated_size = list(array_size) 
    max_neg_list = [0] * num_dimensions
    
    for dim in range(num_dimensions):
        index = left_part_indices[dim]
        
        # Regular expression to match all +n and -n operations for the current dimension
        pattern = re.compile(rf'\b{index}\s*([\+\-]\s*\d+)')
        matches = pattern.findall(right_part)
        
        max_neg = 0  # Record the maximum negative value for the current dimension
        max_pos = 0  # Record the maximum positive value for the current dimension
        
        for match in matches:
            offset = match.replace(' ', '')  # Remove spaces
            if offset.startswith('-'):
                num = int(offset[1:])  # Get the absolute value
                max_neg = max(max_neg, num)  # Update the maximum negative value
            elif offset.startswith('+'):
                num = int(offset[1:])  # Get the absolute value
                max_pos = max(max_pos, num)  # Update the maximum positive value

        max_neg_list[dim] = max_neg

        # Update size
        if max_neg > 0:
            updated_size[dim] -= max_neg  # Subtract for the maximum negative value
        if max_pos > 0:
            updated_size[dim] -= max_pos  # Subtract for the maximum positive value
    
    return tuple(updated_size), max_neg_list
def shift_replace_variables(statement_info, max_n):
    # Parse the left-side variables
    left_part = statement_info['left_part']
    
    array_name, left_part_indices = list(left_part.items())[0] 
    # Extract the offset amounts

    # Get the right-side part
    right_part = statement_info['right_part']
    for i in range(len(max_n)):
        right_part_str =f'({max_n[i]} + {left_part_indices[i]})'
        right_part = right_part.replace(left_part_indices[i], right_part_str)
        
    # Perform string replacement
    # modified_right_part = right_part.replace('i', f'({offset_i} + i)').replace('j', f'({offset_j} + j)')


    # Create the new statement
    new_statement = {
        'left_part': left_part,
        'right_part': str(right_part)
    }
    
    return new_statement



def update_domain_constraints(new_ranges,if_condition,inverse_map,new_variables):
    inequalities = []
    replaced_conditions = []
    simplified_conditions = []
    n = sp.Symbol('n') # Define symbolic variable 'n'
    variables = {name: sp.Symbol(name) for name in new_variables}  # Create new symbolic variables
    
    for var, (lower, upper) in new_ranges.items():
        # Generate inequalities for lower and upper bounds
        lower_bound = f"{var} >= {lower}"
        upper_bound = f"-{var} + {upper} >= 0"

    # Append the inequalities to the list
        inequalities.append(lower_bound)
        inequalities.append(upper_bound)
    
    for condition in if_condition:
        # Perform string replacement for each variable in inverse_map
        replaced_condition = condition
        for old_var, new_expr in inverse_map.items():
            replaced_condition = replaced_condition.replace(old_var, new_expr)
        
        replaced_conditions.append(replaced_condition)
    

    # Parse and simplify each replaced condition
    for condition in replaced_conditions:
        # Convert the replaced string condition into a symbolic expression
        expr = sp.sympify(condition, locals=variables)
        # Simplify the expression
        simplified_expr = sp.simplify(expr)
        # Append the simplified expression to the list
        simplified_conditions.append(simplified_expr)
    return inequalities,simplified_conditions

def update_array_access_index(model, new_model, inverse_map):
    """
    更新数组访问索引的变量替换和表达式化简
    
    参数:
        model: 原始模型数据
        new_model: 待更新的新模型
        inverse_map: 变量映射字典 {旧变量名: 新表达式}
    """
    def safe_simplify(expr_str):
        """安全化简表达式，失败时返回原字符串"""
        try:
            return str(sp.simplify(sp.sympify(expr_str)))
        except Exception as e:
            print(f"Warning: Could not simplify expression '{expr_str}': {e}")
            return expr_str

    # 按变量名长度降序排序，确保长变量名优先替换
    sorted_mapping = sorted(inverse_map.items(), key=lambda x: -len(x[0]))

    for access_type in ['reads', 'writes']:
        for array_name, indices in model[access_type].items():
            updated_indices = []
            for index_expr in indices:
                # 步骤1: 变量替换（使用正则确保完整单词匹配）
                updated_expr = index_expr
                for old_var, new_expr in sorted_mapping:
                    # 使用正则替换，避免部分匹配（如替换i时不影响index）
                    updated_expr = re.sub(
                        r'\b{}\b'.format(re.escape(old_var)), 
                        f'({new_expr})',  # 添加括号确保运算优先级
                        updated_expr
                    )
                
                # 步骤2: 表达式化简
                simplified_expr = safe_simplify(updated_expr)
                
                # 步骤3: 移除多余的括号（可选）
                simplified_expr = simplified_expr.replace('((', '(').replace('))', ')')
                updated_indices.append(simplified_expr)
            
            # 更新到新模型
            new_model[access_type][array_name] = updated_indices


def convert_array_sizes_inplace(array_size):
    """
    原地将数组尺寸字典从字符串格式转换为SymPy符号格式
    
    参数:
        array_size (dict): 输入字典，会被直接修改
                          格式如 {'A': 'n, n', 'B': '5*n-4, 2*n-1'}
    """
    # 确保符号n存在（如果表达式中使用）
    if not hasattr(convert_array_sizes_inplace, '_n_defined'):
        sp.symbols('n')  # 定义符号n
        convert_array_sizes_inplace._n_defined = True
    
    for array_name in list(array_size.keys()):  # 使用list()避免修改字典大小
        size_str = array_size[array_name]
        
        # 分割字符串并去除空白字符
        size_parts = [s.strip() for s in size_str.split(',')]
        
        # 将每个部分转换为SymPy表达式
        symbol_list = [sp.sympify(expr) for expr in size_parts]
        
        # 原地修改字典值
        array_size[array_name] = symbol_list
   