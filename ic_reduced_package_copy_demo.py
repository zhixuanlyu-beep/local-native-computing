"""Actual Lafont IC copying of delta-free REDUCED PACKAGES WITH INTERNAL WIRING.

Extends the gamma/epsilon constructor tree demonstration: delta-delta annihilation
copies internal free-leaf wiring. Each original gamma, epsilon, and wiring pair
causes exactly one active-pair interaction. No non-IC nodes are used.
"""
import random
from ic_primitive_port_verifier import Net,isomorphic

HOLE='H'

def build_package(net,shape,holes):
    assert shape!=HOLE
    typ=shape[0]
    assert typ in ('g','e')
    root=net.cell(typ)
    if typ=='g':
        for p,sub in ((1,shape[1]),(2,shape[2])):
            if sub==HOLE:holes.append((root,p))
            else:
                child=build_package(net,sub,holes)
                net.link((root,p),(child,0))
    return root


def make_pkg(net,shape,matching):
    holes=[]
    root=build_package(net,shape,holes)
    assert len(holes)==2*len(matching)
    used=[]
    for x,y in matching:
        assert x!=y
        used.extend((x,y))
        net.link(holes[x],holes[y])
    assert sorted(used)==list(range(len(holes)))
    return root


def test(shape,matching,seed=0):
    net=Net();root=make_pkg(net,shape,matching)
    orig_nodes=len(net.nodes);w=len(matching)
    d=net.cell('d');net.link((d,0),(root,0))
    o1=net.boundary('out1');o2=net.boundary('out2')
    net.link((d,1),o1);net.link((d,2),o2)
    rng=random.Random(seed)
    steps=0
    while net.active():
        pair=rng.choice(net.active());net.reduce(*pair);steps+=1
    assert steps==orig_nodes+w,(steps,orig_nodes,w)
    assert len(net.nodes)==2*orig_nodes
    assert all(t in ('g','e') for t in net.nodes.values())
    assert net.cycles==0
    expected=Net()
    eroot1=make_pkg(expected,shape,matching)
    eroot2=make_pkg(expected,shape,matching)
    a=expected.boundary('out1');b=expected.boundary('out2')
    expected.link((eroot1,0),a);expected.link((eroot2,0),b)
    assert isomorphic(net,expected),'wrong output package topology'
    return steps


def random_shape(rng,depth):
    if depth==0:
        return HOLE if rng.random()<0.55 else ('e',)
    if rng.random()<0.15: return ('e',)
    return ('g',random_shape(rng,depth-1),random_shape(rng,depth-1))


def count_holes(shape):
    if shape==HOLE:return 1
    if shape[0]=='e':return 0
    return count_holes(shape[1])+count_holes(shape[2])


def random_matching(rng,n):
    xs=list(range(n));rng.shuffle(xs)
    return list(zip(xs[0::2],xs[1::2]))


if __name__=='__main__':
    # One gamma cell with its two auxiliaries linked: not a tree.
    shape=('g',HOLE,HOLE)
    for seed in range(10):assert test(shape,[(0,1)],seed)==2
    print('one self-wired gamma package: 1 gamma + 1 internal wire, 2 IC steps, 2 copies')
    # Three gamma nodes, internal wiring crosses between two subtrees.
    shape=('g',('g',HOLE,HOLE),('g',HOLE,HOLE))
    for seed in range(20):assert test(shape,[(0,2),(1,3)],seed)==5
    print('three gamma nodes with 2 cross-branch wires: 5 IC steps, 2 copies')
    rng=random.Random(2211)
    passed=0
    attempts=0
    while passed<200 and attempts<3000:
        attempts+=1
        shape=random_shape(rng,5)
        n=count_holes(shape)
        if n%2:continue
        mat=random_matching(rng,n)
        test(shape,mat,passed)
        passed+=1
    assert passed==200
    print('PASS: 200 randomized delta-free reduced packages with wiring (ordered ports, topology and resource formula)')
