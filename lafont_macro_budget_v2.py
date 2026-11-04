"""Corrected static budget and Figure 6 half-net audit for Lafont 1997.

IMPORTANT: T_sigma has arity ell (#wires between phi and psi), NOT the
number of original rule boundary ports n_i+n_j.  For the 15 rules below,
ell is 0, 1, or 2. This is the standard, intentionally noncanonical split
with all same-side wiring absorbed into phi/psi and sigma=identity.

All macro counts are CONDITIONAL on this specific standard implementation
and epsilon fillers for undefined Gamma_ij entries. This is not an expanded
3-symbol IC port graph and contains no reduction certificates for 14 rules.
"""
from source_feedback_audit import RULES,AR
from lafont_sigma_width_audit import cutdata

M=len(AR)
assert M==14 and len(RULES)==15
source_cells=0; source_aux=0
sum_Mstar_gamma=0; sum_T_delta=0; sum_T_epsilon=0
sum_C_delta=0; sum_C_epsilon=0
count_ell={}; count_p={}
all_packages=[]

for spec in RULES.values():
    A,B,nodes,edges,ext=spec
    source_cells+=len(nodes)
    source_aux+=sum(AR[t] for t in nodes.values())
    ell,cross,nlocal,local,owner=cutdata(spec)
    count_ell[ell]=count_ell.get(ell,0)+1
    # Every RHS wire goes either inside an assigned half or crosses the split.
    # Crossing connections exactly form the permutation's ell strands.
    pA=[t for c,t in nodes.items() if owner[c]=='A']
    pB=[t for c,t in nodes.items() if owner[c]=='B']
    for side,t,types in (('A',A,pA),('B',B,pB)):
        p=len(types)
        a=sum(AR[x] for x in types)
        count_p[p]=count_p.get(p,0)+1
        assert (p+a+AR[t]+ell)%2==0, ('invalid phi/psi net',A,B,side,p,a,ell)
        # M*_{arity(t)+2}
        gM=AR[t]+1
        # Expansion of each original node to <alpha_k>:
        # a_k+31 gamma, 3 delta, 26 epsilon.
        gExt=31*p+a
        dExt=3*p
        eExt=26*p
        # C_p:
        dC=max(p-1,0)
        eC=int(p==0)
        # T_identity of arity ell, NOT total input interface:
        dT=max(ell-1,0)
        eT=int(ell==0)
        g=gM+gExt;d=dExt+dC+dT;e=eExt+eC+eT
        # A package has one free port, hence an ODD number of odd-degree IC cells.
        assert (g+d+e)%2==1, ('bad Gamma_ij package parity',A,B,side,g,d,e)
        assert (3*(g+d)+e+1)%2==0
        all_packages.append((A,B,side,g,d,e,p,ell))
        sum_Mstar_gamma+=gM
        sum_C_delta+=dC;sum_C_epsilon+=eC
        sum_T_delta+=dT;sum_T_epsilon+=eT

assert len(all_packages)==30 and source_cells==40 and source_aux==44
assert sum(count_ell.values())==15

# 40 expanded source cells across 30 oriented fragments.
ext_g=source_aux+31*source_cells
ext_d=3*source_cells
ext_e=26*source_cells

undefined=M*M-len(all_packages)
menu_gamma=(M+1)*(M-1)
G=sum_Mstar_gamma+ext_g+menu_gamma
D=sum_C_delta+ext_d+sum_T_delta
E=sum_C_epsilon+ext_e+sum_T_epsilon+undefined
assert G==1549 and D==147 and E==1241, (G,D,E)

def edges(g,d,e,nfree):
    count=3*(g+d)+e+nfree
    assert count%2==0
    return count//2

# Figure 8 encoding of a package with n>0 delta cells: cut delta and
# add M_n, two M_n*, and M_4, totalling 3n gamma.
codeG=G+3*D
codeE=E
print('REVISED: rule-half packages',len(all_packages),'undefined entries',undefined)
print('sigma arities:',dict(sorted(count_ell.items())),'total unoriented crossing edges',sum(k*v for k,v in count_ell.items()))
print('copier p distribution:',dict(sorted(count_p.items())))
print('each phi/psi has correct parity; each of 30 Gamma_ij packages has odd cell count: PASS')
print('gamma: M*',sum_Mstar_gamma,'extensions',ext_g,'menus',menu_gamma,'TOTAL',G)
print('delta: extensions',ext_d,'copiers',sum_C_delta,'T_sigma',sum_T_delta,'TOTAL',D)
print('epsilon: extensions',ext_e,'C0',sum_C_epsilon,'T0',sum_T_epsilon,'undefined',undefined,'TOTAL',E)
print('decoded Gamma: cells',G+D+E,'(gamma,delta,epsilon)',(G,D,E),'wires',edges(G,D,E,1))
print('cut Gamma prime: free ports',3*D+1,'(gamma,epsilon)',(G,E),'wires',edges(G,0,E,3*D+1))
print('encoded !Gamma: cells',codeG+codeE,'(gamma,delta,epsilon)',(codeG,0,codeE),'wires',edges(codeG,0,codeE,1))
print('PASS: Fig. 6 noncanonical split, conditional macro counts and all package port-parity checks.')
