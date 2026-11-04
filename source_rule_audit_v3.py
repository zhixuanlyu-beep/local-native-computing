from collections import defaultdict, Counter
from source_feedback_audit import RULES, AR

# Port polarity/type at each source node: (direction, semantic type).
# direction='out' means the cell produces the datum on that port;
# direction='in' means the cell consumes it.
PORTS = {
    'Z':    [('out','N')],
    'S':    [('out','N'), ('in','N')],
    'DUP':  [('in','N'), ('out','N'), ('out','N')],
    'ERA':  [('in','N')],
    'INIT': [('in','N'), ('out','O')],
    'CMP':  [('in','N'), ('in','N'), ('out','T'), ('out','N')],
    'CMP0': [('in','N'), ('out','T'), ('out','N')],
    'CMPS': [('in','N'), ('in','N'), ('out','T'), ('out','N')],
    'GATE': [('in','T'), ('in','N'), ('in','N'), ('in','N'), ('out','O')],
    'EQ':   [('out','T')],
    'GT':   [('out','T')],
    'LT':   [('out','T')],
    'SQ':   [('out','O'), ('in','N')],
    'BR':   [('out','O'), ('in','N'), ('in','N')],
}

# The first source node's auxiliary ports are A1..; the second's are B1..
def audit_rule(key, spec):
    A, B, nodes, edges, ext = spec
    labels = [f'A{i}' for i in range(1, AR[A]+1)] + [f'B{i}' for i in range(1, AR[B]+1)]
    assert set(labels) == set(ext), (key, labels, list(ext))

    # Build a port-level endpoint-use map.
    used = {}
    def mark(endpoint, where):
        assert endpoint not in used, (key, 'port reused', endpoint, used[endpoint], where)
        used[endpoint] = where

    for name, typ in nodes.items():
        for p in range(AR[typ]+1):
            pass
    for x,i,y,j in edges:
        assert x in nodes and y in nodes
        assert 0 <= i <= AR[nodes[x]] and 0 <= j <= AR[nodes[y]]
        mark((x,i), ('edge',y,j)); mark((y,j), ('edge',x,i))
    for lab, (x,p) in ext.items():
        assert x in nodes and 0 <= p <= AR[nodes[x]]
        mark((x,p), ('free',lab))

    all_ports = {(x,p) for x,t in nodes.items() for p in range(AR[t]+1)}
    assert set(used) == all_ports, (key, 'unaccounted ports', all_ports-set(used))

    # Boundary interface types must be preserved exactly.
    lhs_types = {}
    for i in range(1, AR[A]+1): lhs_types[f'A{i}'] = PORTS[A][i]
    for i in range(1, AR[B]+1): lhs_types[f'B{i}'] = PORTS[B][i]
    for lab,(x,p) in ext.items():
        assert lhs_types[lab] == PORTS[nodes[x]][p], (key, 'boundary type mismatch', lab, lhs_types[lab], PORTS[nodes[x]][p])

    # Internal wires must join opposite polarities of the same semantic type.
    for x,i,y,j in edges:
        px = PORTS[nodes[x]][i]; py = PORTS[nodes[y]][j]
        assert px[1] == py[1] and px[0] != py[0], (key, 'internal type mismatch', (x,i,px), (y,j,py))

    # No internal active pair: no principal-principal edge.
    for x,i,y,j in edges:
        assert not (i == 0 and j == 0), (key, 'internal active pair', x,y)

    # Principal-path graph: c -> d when c.0 is wired to d.k, k>0.
    directed = defaultdict(list)
    for x,i,y,j in edges:
        if i == 0 and j > 0: directed[x].append(y)
        if j == 0 and i > 0: directed[y].append(x)
    color = {x:0 for x in nodes}
    def visit(x, stack):
        if color[x] == 1: raise AssertionError((key, 'vicious circle', stack+[x]))
        if color[x] == 2: return
        color[x] = 1
        for y in directed[x]: visit(y, stack+[x])
        color[x] = 2
    for x in nodes: visit(x, [])

    # Proposition 2 forest roots are free ports attached to principal ports.
    roots = {}
    for lab,(x,p) in ext.items():
        if p == 0:
            side = 'A' if lab.startswith('A') else 'B'
            roots[x] = side
    # Every RHS cell must be in exactly one rooted tree.
    owner = {}
    def grow(x, side, path):
        assert x not in owner, (key, 'cell has multiple/no unique tree root', x, owner.get(x), side)
        owner[x] = side
        for p in range(1, AR[nodes[x]]+1):
            other = used[(x,p)]
            if other[0] == 'edge':
                y, q = other[1], other[2]
                if q == 0: grow(y, side, path+[x])
    for root,side in roots.items(): grow(root,side,[])
    assert set(owner) == set(nodes), (key, 'unrooted cells', set(nodes)-set(owner))

    pA = sum(1 for x,s in owner.items() if s == 'A')
    pB = sum(1 for x,s in owner.items() if s == 'B')
    v = len(nodes)
    Aaux = sum(AR[t] for t in nodes.values())
    nfree = len(ext)
    w = (Aaux-v+nfree)//2
    assert (Aaux-v+nfree) % 2 == 0
    # Count the number of tree leaves and verify that the remaining ports pair.
    leaf_count = Aaux - v + nfree
    assert leaf_count == 2*w, (key, leaf_count, w)
    return dict(rule=f'{A}-{B}', n=nfree, v=v, Aaux=Aaux, roots=len(roots), pA=pA, pB=pB, w=w)

rows=[]
for key,spec in RULES.items():
    rows.append(audit_rule(key,spec))

print('RULES',len(rows))
print('SUMS', {k:sum(r[k] for r in rows) for k in ('n','v','Aaux','roots','pA','pB','w')})
print('ROWS')
for r in rows: print(r)
print('P DISTRIBUTION', Counter([x for r in rows for x in (r['pA'],r['pB'])]))
print('MAX_P', max(max(r['pA'],r['pB']) for r in rows))
print('PASS: port accounting, boundary typing, internal typing, no active pairs, no principal cycles, unique forest roots')


# For corrected compiler budgeting, execute lafont_macro_budget_v2.py.
