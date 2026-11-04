"""An actual 3-symbol IC reduction: delta duplicates a delta-free gamma/epsilon tree.

All graph changes are local IC active-pair rewrites. No source-language
DUP node, global scheduler instructions, or hardcoded output trees.
"""
import random
from ic_primitive_port_verifier import Net


def build_tree(n,depth):
    if depth == 0:
        return n.cell('e')
    root=n.cell('g')
    l=build_tree(n,depth-1)
    r=build_tree(n,depth-1)
    n.link((root,1),(l,0))
    n.link((root,2),(r,0))
    return root


def decode_tree(net, from_port, seen):
    neighbor=net.adj[from_port]
    c,p=neighbor
    assert p==0 and c in net.nodes, ('unexpected root',neighbor)
    assert c not in seen, ('sharing or cycle',c)
    seen.add(c)
    kind=net.nodes[c]
    assert kind in ('g','e'), ('non copied combinator',kind)
    if kind=='e': return ('e',)
    return ('g',decode_tree(net,(c,1),seen),decode_tree(net,(c,2),seen))


def expected(depth):
    if depth==0: return ('e',)
    t=expected(depth-1)
    return ('g',t,t)


def run(depth,seed=0):
    net=Net()
    tree=build_tree(net,depth)
    d=net.cell('d')
    net.link((tree,0),(d,0))
    out1=net.boundary('out1');out2=net.boundary('out2')
    net.link((d,1),out1);net.link((d,2),out2)
    initial_cells=len(net.nodes)
    rng=random.Random(seed)
    steps=0;peak=len(net.nodes)
    while net.active():
        choices=net.active()
        a,b=rng.choice(choices)
        net.reduce(a,b)
        steps+=1;peak=max(peak,len(net.nodes))
    seen=set()
    copied1=decode_tree(net,out1,seen)
    copied2=decode_tree(net,out2,seen)
    assert copied1==expected(depth)==copied2
    assert len(seen)==len(net.nodes)
    assert all(t in ('g','e') for t in net.nodes.values())
    assert net.cycles==0
    orig_nodes=2**(depth+1)-1
    assert initial_cells==orig_nodes+1
    assert steps==orig_nodes
    assert len(net.nodes)==2*orig_nodes
    return steps,len(net.nodes),peak


if __name__=='__main__':
    for depth in range(7):
        samples=[run(depth,i) for i in range(20)]
        assert len({x[:2] for x in samples})==1
        step,final,peak=samples[0]
        print('depth=%d original=%d interactions=%d final=%d peak=%d..%d (20 randomized schedules)' %
              (depth,2**(depth+1)-1,step,final,min(x[2] for x in samples),max(x[2] for x in samples)))
    print('PASS: all reductions are primitive gamma-delta, delta-epsilon, with arbitrary local schedules')


def build_shape(n,shape):
    if shape==('e',): return n.cell('e')
    assert shape[0]=='g' and len(shape)==3
    root=n.cell('g')
    l=build_shape(n,shape[1]);r=build_shape(n,shape[2])
    n.link((root,1),(l,0));n.link((root,2),(r,0))
    return root


def random_shape(rng,maxdepth):
    if maxdepth==0 or rng.random()<0.3: return ('e',)
    return ('g',random_shape(rng,maxdepth-1),random_shape(rng,maxdepth-1))


def nodes_shape(shape):
    return 1 if shape[0]=='e' else 1+nodes_shape(shape[1])+nodes_shape(shape[2])


def copy_shape(shape,seed):
    net=Net()
    r=build_shape(net,shape);d=net.cell('d');net.link((r,0),(d,0))
    a=net.boundary('left');b=net.boundary('right')
    net.link((d,1),a);net.link((d,2),b)
    rng=random.Random(seed);steps=0
    while net.active():
        net.reduce(*rng.choice(net.active()));steps+=1
    seen=set()
    assert decode_tree(net,a,seen)==shape
    assert decode_tree(net,b,seen)==shape
    assert len(net.nodes)==len(seen)==2*nodes_shape(shape)
    assert steps==nodes_shape(shape)
    assert net.cycles==0


def test_irregular():
    rng=random.Random(20261104)
    for i in range(200):
        shp=random_shape(rng,6)
        copy_shape(shp,i)
    print('PASS: 200 irregular/asymmetric gamma-epsilon trees copied exactly (ordered ports preserved)')


def parallel_layers(depth):
    n=Net();t=build_tree(n,depth);d=n.cell('d');n.link((t,0),(d,0))
    for s in ('out1','out2'):
        f=n.boundary(s)
        n.link((d,1 if s=='out1' else 2),f)
    layers=[]
    while n.active():
        pairs=n.active()
        layers.append(len(pairs))
        for a,b in pairs:
            n.reduce(a,b)
    assert layers==[2**k for k in range(depth+1)],layers
    return layers


if __name__=='__main__':
    test_irregular()
    print('balanced tree depth=6 causal layers:',parallel_layers(6))
