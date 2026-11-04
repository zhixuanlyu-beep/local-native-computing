"""Actual Lafont IC erasure of a finite constructor tree made from gamma,delta,epsilon.

A single epsilon at the root propagates locally, erasing all cells. There is
no outside branch-pruning instruction or global clock.
"""
import random
from ic_primitive_port_verifier import Net


def construct(n,shape):
    typ=shape[0]
    assert typ in ('g','d','e')
    c=n.cell(typ)
    if typ in ('g','d'):
        assert len(shape)==3
        left=construct(n,shape[1]);right=construct(n,shape[2])
        n.link((c,1),(left,0));n.link((c,2),(right,0))
    return c


def count(shape):
    return 1 if shape[0]=='e' else 1+count(shape[1])+count(shape[2])


def random_tree(rng,maxdepth):
    if maxdepth==0 or rng.random()<0.35: return ('e',)
    return (rng.choice(('g','d')),random_tree(rng,maxdepth-1),random_tree(rng,maxdepth-1))


def erase(shape,seed):
    n=Net();root=construct(n,shape);eraser=n.cell('e');n.link((root,0),(eraser,0))
    rng=random.Random(seed);steps=0
    while n.active():
        n.reduce(*rng.choice(n.active()))
        steps+=1
    assert steps==count(shape),(shape,steps,count(shape))
    assert len(n.nodes)==0 and n.cycles==0
    return steps


if __name__=='__main__':
    rng=random.Random(1447)
    for i in range(200):
        shape=random_tree(rng,7)
        erase(shape,i)
    print('PASS: 200 random gamma/delta/epsilon trees, erased by only original IC rules')
    for d in range(7):
        def full(k):
            return ('e',) if k==0 else ('g' if k%2 else 'd',full(k-1),full(k-1))
        tree=full(d)
        print('depth',d,'tree cells',count(tree),'eraser interactions',erase(tree,seed=d))
