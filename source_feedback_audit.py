from collections import defaultdict
import random

AR = {'Z':0,'S':1,'DUP':2,'ERA':0,'INIT':1,'CMP':3,'CMP0':2,'CMPS':3,'GATE':4,'EQ':0,'GT':0,'LT':0,'SQ':1,'BR':2}

# Rule schema: A,B, RHS node map, internal edges, boundary-port map.
RULES = {}
FRESH = [0]
def connect(adj,x,y):
    assert adj[x] is None and adj[y] is None, (x,y,adj[x],adj[y])
    adj[x]=y; adj[y]=x

def rule(A,B,nodes,edges,ext):
    RULES[frozenset((A,B))]=(A,B,nodes,edges,ext)

rule('INIT','Z', {'sq':'SQ','z':'Z'}, [('sq',1,'z',0)], {'A1':('sq',0)})
rule('INIT','S', {'c':'CMP','g':'GATE','sb':'S','za':'Z','zb':'Z','zc':'Z'},
     [('c',1,'za',0),('c',2,'g',0),('c',3,'g',1),('g',2,'sb',0),('sb',1,'zb',0),('g',3,'zc',0)],
     {'A1':('g',4),'B1':('c',0)})
rule('CMP','Z', {'c0':'CMP0'}, [], {'A1':('c0',0),'A2':('c0',1),'A3':('c0',2)})
rule('CMP','S', {'cs':'CMPS'}, [], {'A1':('cs',0),'A2':('cs',2),'A3':('cs',3),'B1':('cs',1)})
rule('CMP0','Z', {'e':'EQ','z':'Z'}, [], {'A1':('e',0),'A2':('z',0)})
rule('CMP0','S', {'l':'LT','sn':'S'}, [], {'A1':('l',0),'A2':('sn',0),'B1':('sn',1)})
rule('CMPS','Z', {'g':'GT','sn':'S'}, [], {'A1':('sn',1),'A2':('g',0),'A3':('sn',0)})
rule('CMPS','S', {'c':'CMP'}, [], {'A1':('c',0),'A2':('c',2),'A3':('c',3),'B1':('c',1)})
rule('GATE','EQ', {'q':'SQ','s':'S','ea':'ERA','eb':'ERA'}, [('q',1,'s',0)], {'A1':('ea',0),'A2':('eb',0),'A3':('s',1),'A4':('q',0)})
rule('GATE','GT', {'c':'CMP','g':'GATE','d':'DUP','sa1':'S','sa2':'S','sb1':'S','sb2':'S','sk':'S'},
     [('c',1,'sa2',0),('sa2',1,'sa1',0),('sa1',1,'d',1),
      ('g',2,'sb2',0),('sb2',1,'sb1',0),('sb1',1,'d',2),
      ('c',2,'g',0),('c',3,'g',1),('g',3,'sk',0)],
     {'A1':('c',0),'A2':('d',0),'A3':('sk',1),'A4':('g',4)})
rule('GATE','LT', {'b':'BR','d':'DUP','s':'S','ea':'ERA','eb':'ERA'},
     [('d',1,'b',1),('d',2,'s',1),('s',0,'b',2)],
     {'A1':('ea',0),'A2':('eb',0),'A3':('d',0),'A4':('b',0)})
rule('DUP','Z', {'z1':'Z','z2':'Z'}, [], {'A1':('z1',0),'A2':('z2',0)})
rule('DUP','S', {'s1':'S','s2':'S','d':'DUP'}, [('d',1,'s1',1),('d',2,'s2',1)], {'A1':('s1',0),'A2':('s2',0),'B1':('d',0)})
rule('ERA','Z', {}, [], {})
rule('ERA','S', {'e':'ERA'}, [], {'B1':('e',0)})


def make_sim(N, seed=0):
    types={}; adj={}; nextid=0
    def new(t):
        nonlocal nextid
        i=f'n{nextid}'; nextid+=1; types[i]=t
        for p in range(AR[t]+1): adj[(i,p)]=None
        return i
    init=new('INIT')
    if N==0:
        z=new('Z'); connect(adj,(init,0),(z,0))
    else:
        outer=None; prev=None
        for _ in range(N):
            s=new('S')
            if outer is None: outer=s
            if prev is not None: connect(adj,(prev,1),(s,0))
            prev=s
        z=new('Z'); connect(adj,(prev,1),(z,0))
        connect(adj,(init,0),(outer,0))
    # Output boundary
    adj[('OUT',0)]=None
    connect(adj,('OUT',0),(init,1))
    return types,adj


def apply(types,adj,u,v):
    A=types[u]; B=types[v]
    spec=RULES[frozenset((A,B))]
    ra,rb,rnodes,redges,rext=spec
    # Normalize order to rule order
    if (A,B)==(ra,rb): left,right=u,v
    elif (A,B)==(rb,ra): left,right=v,u
    else: raise AssertionError((A,B,ra,rb))
    # Map old LHS auxiliary ports to canonical boundary labels
    old_to_label={}
    for i in range(1,AR[ra]+1): old_to_label[(left,i)]=f'A{i}'
    for j in range(1,AR[rb]+1): old_to_label[(right,j)]=f'B{j}'
    # Record what each boundary wire was connected to
    boundary_neighbor={lab:adj[port] for port,lab in old_to_label.items()}
    # New RHS nodes
    fresh={}
    for name,t in rnodes.items():
        nid=f'r{FRESH[0]}_{name}'
        FRESH[0]+=1
        fresh[name]=nid; types[nid]=t
        for p in range(AR[t]+1): adj[(nid,p)]=None
    # Internal RHS edges
    for x,i,y,j in redges:
        connect(adj,(fresh[x],i),(fresh[y],j))
    # Remove old active pair principal connection and old nodes' ports
    # First clear every old port edge from adjacency of its neighbor.
    old_nodes={left,right}
    for node in old_nodes:
        for p in range(AR[types[node]]+1):
            key=(node,p); other=adj[key]
            if other is not None and other in adj and adj[other]==key:
                adj[other]=None
            del adj[key]
        del types[node]
    # Reconnect old boundary contexts to new RHS boundary ports.
    # If two old boundary ports were wired together, connect their RHS images once.
    handled=set()
    for lab, rhs_port in rext.items():
        old_other=boundary_neighbor[lab]
        if old_other is None: raise AssertionError(('unconnected old boundary',lab))
        new_port=(fresh[rhs_port[0]],rhs_port[1])
        if old_other in old_to_label:
            lab2=old_to_label[old_other]
            if lab2 in handled: continue
            rhs2=rext[lab2]
            new2=(fresh[rhs2[0]],rhs2[1])
            connect(adj,new_port,new2)
            handled.add(lab2); handled.add(lab)
        else:
            # old_other can be external boundary endpoint or another surviving node port
            if old_other not in adj:
                raise AssertionError(('context endpoint missing',lab,old_other))
            connect(adj,new_port,old_other)
            handled.add(lab)
    if len(handled)!=len(rext):
        raise AssertionError(('boundary not handled',handled,rext))


def active_pairs(types,adj):
    pairs=[]
    for node,t in list(types.items()):
        other=adj[(node,0)]
        if isinstance(other,tuple) and len(other)==2 and other[1]==0 and other[0] in types:
            if node < other[0]: pairs.append((node,other[0]))
    return pairs


def decode(types,adj,port):
    # port is an endpoint (node,aux) whose neighbor should be principal of Z or S
    cur=adj[port]
    n=0; seen=set()
    while True:
        if cur is None or not isinstance(cur,tuple) or cur[0] not in types or cur[1]!=0:
            raise AssertionError(('bad numeral link',port,cur))
        node=cur[0]; t=types[node]
        if node in seen: raise AssertionError('cycle in numeral')
        seen.add(node)
        if t=='Z': return n
        if t!='S': raise AssertionError(('not numeral node',t,node))
        n+=1
        cur=adj[(node,1)]


def run(N, seed=0, maxsteps=1000000):
    FRESH[0]=0
    types,adj=make_sim(N,seed)
    rng=random.Random(seed); steps=0; peak=len(types)
    while True:
        pairs=active_pairs(types,adj)
        if not pairs: break
        if steps>=maxsteps: raise RuntimeError('step limit')
        u,v=rng.choice(pairs)
        apply(types,adj,u,v)
        steps+=1
        peak=max(peak,len(types))
    out=adj[('OUT',0)]
    if not isinstance(out,tuple) or out[0] not in types or out[1]!=0:
        raise AssertionError(('bad output',out))
    node=out[0]; typ=types[node]
    if typ=='SQ': result=('SQ',decode(types,adj,(node,1)))
    elif typ=='BR': result=('BR',decode(types,adj,(node,1)),decode(types,adj,(node,2)))
    else: raise AssertionError(('unexpected output type',typ))
    return steps,result,len(types),len(active_pairs(types,adj)),peak

def expected_source_steps(N):
    if N == 0:
        return 1
    m = int(N ** 0.5)
    while (m + 1) * (m + 1) <= N:
        m += 1
    while m * m > N:
        m -= 1
    if m * m == N:
        return 3 * m * m + 4 * m
    r = N - m * m
    return 3 * m * m + 9 * m + r + 7


if __name__ == '__main__':
    for N in range(201):
        steps, result, final_nodes, active, peak = run(N, seed=N)
        m = int(N ** 0.5)
        while (m + 1) * (m + 1) <= N:
            m += 1
        while m * m > N:
            m -= 1
        expected = ('SQ', m) if m * m == N else ('BR', m, m + 1)
        assert result == expected, (N, result, expected)
        assert steps == expected_source_steps(N), (N, steps, expected_source_steps(N))
        assert active == 0, (N, active)
    print('PASS: source-system inputs N=0..200')
    for N in (9, 80, 81, 82, 100):
        samples = [run(N, seed=s) for s in range(100)]
        invariants = {(x[0], x[1], x[2]) for x in samples}
        assert len(invariants) == 1, (N, invariants)
        peaks = [x[4] for x in samples]
        print('N=%d steps=%d result=%s final_nodes=%d sampled_peak=%d..%d' %
              (N, samples[0][0], samples[0][1], samples[0][2], min(peaks), max(peaks)))
    print('PASS: 100 random reduction orders per selected input')
    print('NOTE: this simulates the 14-symbol source interaction system, not compiled IC.')