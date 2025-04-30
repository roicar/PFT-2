from function import *
from P2S import *
from new_polyhedral_model import *
from convert_to_compute import *
import os
def P2P(model,method,source_file):
    print(method)
    S = P2S(model,method)
    print(S)
    T=100
    best_sch=()
    best_model={}
    for sch in S:
        print(model)
        new_model = new_polyhedral_model(model,sch)
        print('new_model1:',new_model)
        #提取语句中的索引值
        iterators = tuple(new_model['iterators'])
        
        g_matrix,g_0 = extract_g_coefficient_matrix(new_model['writes'],new_model['iterators'])
        print('g0',g_0)
        print(iterators)
        if set(g_0).issubset(set(iterators)):
            t,sch = run_and_test_schedule(source_file,model,sch)
            if t<T:
                T=t
                best_sch=sch
                print('best_sch:',best_sch)
                best_model = new_model
        #提取语句中的参数
    if T==0:
        return False
    print('best_sch:',best_sch)
    print('best_model:',best_model)
    return best_model


