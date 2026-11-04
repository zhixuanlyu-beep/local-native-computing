"""A literal 3-symbol/6-rule Interaction Combinator port-graph reducer.

Gamma-gamma: A1--B2, A2--B1 (cell port indices, not visual left/right).
Delta-delta: A1--B1, A2--B2.
Gamma-delta: standard rectangular gamma-delta commutation.
Epsilon annihilation/erasure: the three other rules.

Implements interface splicing, including direct boundary-to-boundary wires,
auxiliary wiring to active-pair context, and cyclic wires.
Only demonstrates primitive IC mechanics, NOT a Lafont compilation of a source program.
"""
from collections import defaultdict
import networkx as nx

AR = {'g':2,'d':2,'e':0}

# Rhs node declarations and lines: endpoint notation 'A1','B2' or (node_name, port_no)
RULES = {
    ('g','g'):( {}, [('A1','B2'),('A2','B1')] ),
    ('d','d'):( {}, [('A1','B1'),('A2','B2')] ),
    ('e','e'):( {}, [] ),
    ('g','e'):( {'e1':'e','e2':'e'}, [('A1',('e1',0)),('A2',('e2',0))] ),
    ('d','e'):( {'e1':'e','e2':'e'}, [('A1',('e1',0)),('A2',('e2',0))] ),
    ('g','d'):( {'d1':'d','d2':'d','g1':'g','g2':'g'}, [
        ('A1',('d1',0)),('A2',('d2',0)),
        ('B1',('g1',0)),('B2',('g2',0)),
        (('d1',1),('g1',1)),(('d1',2),('g2',1)),
        (('d2',1),('g1',2)),(('d2',2),('g2',2)),
    ]),
}


class Net:
    def __init__(self):
        self.nodes = {}
        self.free = set()
        self.adj = {}
        self.next = 0
        self.cycles = 0

    def cell(self, kind):
        assert kind in AR
        name = 'c'+str(self.next); self.next += 1
        self.nodes[name]=kind
        for p in range(AR[kind]+1): self.adj[(name,p)] = None
        return name

    def boundary(self, label):
        key=('F',label)
        assert key not in self.adj
        self.free.add(key)
        self.adj[key]=None
        return key

    def link(self, x, y):
        assert x!=y and x in self.adj and y in self.adj
        assert self.adj[x] is None and self.adj[y] is None, (x,y,self.adj[x],self.adj[y])
        self.adj[x] = y
        self.adj[y] = x

    def check(self):
        assert len(self.adj)==sum(AR[t]+1 for t in self.nodes.values())+len(self.free)
        for x,y in self.adj.items():
            assert y is not None and y in self.adj and self.adj[y]==x, (x,y)
        assert self.cycles>=0

    def active(self):
        pairs=[]
        for c in self.nodes:
            oth=self.adj[(c,0)]
            if oth[1]==0 and oth[0] in self.nodes and c<oth[0]:
                pairs.append((c,oth[0]))
        return pairs

    def reduce(self, u, v):
        assert (u,v) in self.active() or (v,u) in self.active()
        if (self.nodes[u],self.nodes[v]) in RULES:
            a,b=u,v
        else:
            a,b=v,u
        ta,tb=self.nodes[a],self.nodes[b]
        new_types, rhs = RULES[(ta,tb)]
        bound={}
        for i in range(1,AR[ta]+1): bound['A'+str(i)]=(a,i)
        for i in range(1,AR[tb]+1): bound['B'+str(i)]=(b,i)
        old_to_label={port:lab for lab,port in bound.items()}

        # H is the path graph of the two contexts plus the local RHS,
        # with boundary labels as 2-valent connection points.
        H=defaultdict(list)
        def put(x,y):
            assert x!=y or x[0]=='B', (x,y)
            H[x].append(y); H[y].append(x)
        for lab,port in bound.items():
            z=self.adj[port]
            if z in old_to_label:
                lab2=old_to_label[z]
                # Only add context edge once
                if lab<lab2: put(('B',lab),('B',lab2))
            else:
                put(('B',lab),('T',z))

        names={}
        for name,kind in new_types.items(): names[name]=self.cell(kind)
        def target(ep):
            if isinstance(ep,str):
                assert ep in bound
                return ('B',ep)
            name,port=ep
            assert 0<=port<=AR[new_types[name]]
            return ('T',(names[name],port))
        for x,y in rhs: put(target(x),target(y))

        assert all(len(H[('B',lab)])==2 for lab in bound), ('invalid interface',ta,tb,H)
        terminals={x for x in H if x[0]=='T'}
        assert all(len(H[x])==1 for x in terminals), ('invalid RHS port use',ta,tb)

        # Delete LHS pair after recording connections.
        for c in (a,b):
            for p in range(AR[self.nodes[c]]+1):
                key=(c,p)
                other=self.adj[key]
                if other in self.adj and self.adj[other]==key: self.adj[other]=None
                del self.adj[key]
            del self.nodes[c]

        # Resolve paths through the spliced boundary connectors.
        visited=set()
        for s in list(H):
            if s in visited: continue
            comp=set(); stack=[s]
            while stack:
                x=stack.pop()
                if x in comp: continue
                comp.add(x); stack.extend(y for y in H[x] if y not in comp)
            visited.update(comp)
            ends=[x[1] for x in comp if x[0]=='T']
            if len(ends)==0:
                self.cycles += 1
            else:
                assert len(ends)==2, ('bad splicing',ta,tb,ends)
                self.link(*ends)
        self.check()

    def signature(self):
        self.check()
        G=nx.Graph()
        for c,kind in self.nodes.items():
            h=('cell',c)
            G.add_node(h, kind='cell:'+kind)
            for p in range(AR[kind]+1):
                port=('port',c,p)
                G.add_node(port,kind='port:'+str(p))
                G.add_edge(h,port)
        for f in self.free:
            G.add_node(('free',f[1]),kind='free:'+str(f[1]))
        def to_node(p):
            if p[0]=='F': return ('free',p[1])
            return ('port',p[0],p[1])
        seen=set()
        for a,b in self.adj.items():
            if a not in seen:
                G.add_edge(to_node(a),to_node(b))
                seen.add(a);seen.add(b)
        return G


def isomorphic(a,b):
    return a.cycles==b.cycles and nx.is_isomorphic(a.signature(),b.signature(),node_match=lambda x,y: x['kind']==y['kind'])


def pair(kind_a,kind_b):
    net=Net(); a=net.cell(kind_a); b=net.cell(kind_b)
    net.link((a,0),(b,0))
    bd={}
    for x,kind,tag in ((a,kind_a,'A'),(b,kind_b,'B')):
        for p in range(1,AR[kind]+1):
            port=net.boundary(tag+str(p));net.link((x,p),port);bd[tag+str(p)]=port
    return net,a,b,bd


def connection(net,x,y):
    return net.adj[x]==y and net.adj[y]==x


def simple_tests():
    for a,b in RULES:
        net,u,v,bd=pair(a,b)
        assert len(net.active())==1
        net.reduce(u,v)
        assert not net.active()
        assert len(net.nodes)==len(RULES[(a,b)][0])
        if (a,b)==('g','g'):
            assert connection(net,bd['A1'],bd['B2'])
            assert connection(net,bd['A2'],bd['B1'])
        if (a,b)==('d','d'):
            assert connection(net,bd['A1'],bd['B1'])
            assert connection(net,bd['A2'],bd['B2'])
        print('%s-%s: 1-step correct; RHS nodes %s; edges %s' % (a,b,len(net.nodes),len(net.adj)//2))

    # A formerly difficult context: both pairs annihilate but the two RHS
    # wirings differ. Make a connected component with TWO disjoint active pairs.
    def construct():
        net=Net(); g1=net.cell('g'); g2=net.cell('g'); d1=net.cell('d');d2=net.cell('d')
        net.link((g1,0),(g2,0));net.link((d1,0),(d2,0))
        # auxiliary ports connect the redexes in a nontrivial way
        net.link((g1,1),(d1,1));net.link((g1,2),(d2,2))
        net.link((g2,1),(d1,2));net.link((g2,2),(d2,1))
        net.check()
        return net,(g1,g2),(d1,d2)
    a,gg,dd=construct();b,gg2,dd2=construct()
    a.reduce(*gg);a.reduce(*dd)
    b.reduce(*dd2);b.reduce(*gg2)
    assert isomorphic(a,b)
    print('commuting two linked disjoint redexes: identical normal form; cycles',a.cycles)

    # A boundary-only loop can turn into a cyclic wire without a crash.
    # Connect all four external gamma-gamma auxiliaries pairwise in a way
    # that creates a closed cycle on the right-hand wiring.
    cyc=Net();g1=cyc.cell('g');g2=cyc.cell('g')
    cyc.link((g1,0),(g2,0))
    cyc.link((g1,1),(g2,2))
    cyc.link((g1,2),(g2,1))
    cyc.reduce(g1,g2)
    assert len(cyc.nodes)==0 and cyc.cycles==2
    print('cyclic-wire production handled:',cyc.cycles)
    print('PASS: six primitive IC rewrite rules, fully paired port graphs, graph splicing, local diamond sample.')


if __name__=='__main__': simple_tests()


def pairings(xs):
    if not xs:
        yield []
        return
    x=xs[0]
    for i in range(1,len(xs)):
        y=xs[i]
        for rest in pairings(xs[1:i]+xs[i+1:]):
            yield [(x,y)]+rest


def exhaustive_two_redex_diamonds():
    from itertools import product
    tested=0
    for (s1,t1),(s2,t2) in product(RULES,RULES):
        def construct(pairs):
            n=Net()
            a=n.cell(s1);b=n.cell(t1);c=n.cell(s2);d=n.cell(t2)
            n.link((a,0),(b,0));n.link((c,0),(d,0))
            aux=[(k,p) for k,typ in ((a,s1),(b,t1),(c,s2),(d,t2)) for p in range(1,AR[typ]+1)]
            assert len(aux)%2==0
            for i,j in pairs:n.link(aux[i],aux[j])
            n.check()
            return n,(a,b),(c,d)
        auxcnt=AR[s1]+AR[t1]+AR[s2]+AR[t2]
        for ps in pairings(list(range(auxcnt))):
            n,p,q=construct(ps)
            nn,pp,qq=construct(ps)
            n.reduce(*p);n.reduce(*q)
            nn.reduce(*qq);nn.reduce(*pp)
            assert isomorphic(n,nn), ((s1,t1),(s2,t2),ps,n.cycles,nn.cycles)
            tested+=1
    print('PASS: exhaustive 2-redex one-step diamonds;',tested,'paired contexts across 36 rule combinations')


if __name__=='__main__': exhaustive_two_redex_diamonds()
