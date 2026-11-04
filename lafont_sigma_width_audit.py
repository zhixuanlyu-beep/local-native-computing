"""Compute the number of links crossing the two sides of Lafont's Fig. 6 split.

A cut edge between the part originating from A auxiliaries and that from B
auxiliaries is represented in the middle permutation sigma. Edges entirely
inside a half are absorbed in phi/psi; sigma arity is number of cross edges,
not the left rule interface ni+nj.
"""
from source_feedback_audit import RULES, AR
from collections import Counter


def cutdata(spec):
    A,B,nodes,edges,ext=spec
    lookup={}
    for x,i,y,j in edges:
        assert (x,i) not in lookup and (y,j) not in lookup
        lookup[(x,i)]=(y,j);lookup[(y,j)]=(x,i)
    for lab,ep in ext.items():
        assert ep not in lookup
        lookup[ep]=(lab,0)
    def owner(c):
        visited=set()
        while True:
            if c in visited:raise AssertionError('principal cycle')
            visited.add(c)
            y,j=lookup[(c,0)]
            if y not in nodes:
                assert y[0] in ('A','B')
                return y[0]
            assert j>0
            c=y
    owned={c:owner(c) for c in nodes}
    cross=[];local=[]
    for x,i,y,j in edges:
        if i==0 or j==0:continue
        kind='cross' if owned[x]!=owned[y] else 'local'
        (cross if kind=='cross' else local).append((x,i,y,j))
    for lab,(x,p) in ext.items():
        if p==0: continue
        kind='cross' if lab[0]!=owned[x] else 'local'
        (cross if kind=='cross' else local).append((lab,x,p))
    return len(cross),cross,len(local),local,owned

if __name__=='__main__':
    totcut=0
    for spec in RULES.values():
        A,B,nodes,edges,ext=spec
        ell,cross,locals_,local,own=cutdata(spec)
        r=AR[A]+AR[B]
        totcut+=ell
        print(f'{A:5s}-{B:5s} external={r} sigma_width={ell} cross_wires={cross}')
    print('TOTAL_SIGMA_WIDTH',totcut)
