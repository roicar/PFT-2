from function import *

def P2S(model,method):
    S = set()
    print(method)
    if method == 'p' or method == 'mixed':
        #call pluto generate the schedule sch
        sch =tuple(model['schedule'])
        I = tuple(model['iterators'])
        matrix = np.array(extract_coefficient_matrix(sch,model['iterators']))
        print(model['iterators'])
        print(matrix)
        if is_unimodular(matrix):
            print('HELLO')
            print(sch)
            return  S.add(sch)

        else:

            S = set()
        if method == 'p':
            return sch
    else:
        S = set()

    G,g_0 = extract_g_coefficient_matrix(model['writes'],model['iterators'])
    if not is_full_rank(G):
        return S.add(tuple(model['iterators']))
    
    elif np.linalg.matrix_rank(G)==len(model['iterators']):
        if not is_unimodular(G):
            return S.add(I)
        else:
            sch = g_0
            S.add(sch)
            return S
    print(G)
    all_matrixs = unimodular_generator(G)
    
    print("all_matrixs:",all_matrixs)
    for matrix in all_matrixs:
        S.add(coefficient_matrix_to_expressions(matrix,model['iterators']))  
    print(S)
    return S
    