"""Construct and reconstruct all 15 Figure-6 phi/psi/sigma source decompositions.

Noncanonical but exact split: assign each RHS cell to its forest root side;
retain same-side wiring, cut every cross-side edge and number cross wires
1..ell, then choose sigma=identity under these cut-port labels.

Produces 15 source-level port graphs, NOT their pure IC macro expansions.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path
from source_feedback_audit import RULES, AR
from lafont_sigma_width_audit import cutdata


def ep_node(node,port): return f'{node}.{port}'


def decomp(spec):
    A,B,nodes,edges,ext=spec
    ell,_,_,_,owned=cutdata(spec)
    source=[(ep_node(x,i),ep_node(y,j)) for x,i,y,j in edges]
    source += [(lab,ep_node(x,p)) for lab,(x,p) in ext.items()]
    side={f'A{i}':'A' for i in range(1,AR[A]+1)}
    side.update({f'B{i}':'B' for i in range(1,AR[B]+1)})
    for c,t in nodes.items():
        for p in range(AR[t]+1):side[ep_node(c,p)]=owned[c]

    h={'A':{'nodes':{},'boundary':[], 'cuts':[], 'edges':[]},
       'B':{'nodes':{},'boundary':[], 'cuts':[], 'edges':[]}}
    for c,t in nodes.items():h[owned[c]]['nodes'][c]={'type':t,'arity':AR[t]}
    for i in range(1,AR[A]+1):h['A']['boundary'].append(f'A{i}')
    for i in range(1,AR[B]+1):h['B']['boundary'].append(f'B{i}')

    across=[]
    for x,y in source:
        sx,sy=side[x],side[y]
        if sx==sy:
            h[sx]['edges'].append([x,y])
        else:
            ix=len(across)+1
            cA=f'cutA{ix}';cB=f'cutB{ix}'
            h['A']['cuts'].append(cA);h['B']['cuts'].append(cB)
            if sx=='A':
                h['A']['edges'].append([x,cA])
                h['B']['edges'].append([y,cB])
                across.append({'index':ix,'A_endpoint':x,'B_endpoint':y,'A_cut':cA,'B_cut':cB})
            else:
                h['A']['edges'].append([y,cA])
                h['B']['edges'].append([x,cB])
                across.append({'index':ix,'A_endpoint':y,'B_endpoint':x,'A_cut':cA,'B_cut':cB})
    assert len(across)==ell

    for s in ('A','B'):
        ports=set(h[s]['boundary']+h[s]['cuts'])
        for c,info in h[s]['nodes'].items():
            ports.update(ep_node(c,p) for p in range(info['arity']+1))
        used=[port for edge in h[s]['edges'] for port in edge]
        assert set(used)==ports and len(used)==len(set(used)),(A,B,s,ports,set(used),len(used))

    # Re-glue the halves via sigma = identity on numbered cross-port pairs;
    # each cut port is 2-valent (half edge + sigma edge), all other ports 1-valent.
    g=defaultdict(list)
    for s in ('A','B'):
        for x,y in h[s]['edges']:
            g[x].append(y);g[y].append(x)
    for cross in across:
        x,y=cross['A_cut'],cross['B_cut']
        g[x].append(y);g[y].append(x)
    cutports=set(h['A']['cuts']+h['B']['cuts'])
    assert all(len(g[x])==2 for x in cutports)
    assert all(len(g[x])==1 for x in g if x not in cutports)

    visited=set();rejoined=set()
    for x in g:
        if x in visited:continue
        stack=[x];component=set()
        while stack:
            q=stack.pop()
            if q in component:continue
            component.add(q);stack.extend(z for z in g[q] if z not in component)
        visited.update(component)
        endpoints=sorted(t for t in component if t not in cutports)
        assert len(endpoints)==2,(A,B,endpoints,component)
        rejoined.add(tuple(endpoints))
    orig={tuple(sorted(pair)) for pair in source}
    assert rejoined==orig,(A,B,'cannot reconstruct source RHS',rejoined^orig)
    assert len(rejoined)==len(source)

    return {'lhs':[A,B], 'arity':[AR[A],AR[B]], 'phi':h['A'],'psi':h['B'],
            'sigma':{'permutation':'identity','width':ell,'strands':across},
            'source_rhs_nodes':len(nodes),'source_rhs_edges':len(source),
            'reconstructed_exactly':True}


def main():
    items=[]
    for spec in RULES.values():items.append(decomp(spec))
    counts=Counter(x['sigma']['width'] for x in items)
    assert counts=={0:10,1:4,2:1}
    path=Path(__file__).with_name('lafont_15_rules_phi_psi_split.json')
    path.write_text(json.dumps({'description':'Source-level exact Figure 6 noncanonical split, NOT an IC expansion',
                                'rules':items},indent=2,ensure_ascii=False)+'\n')
    print('PASS: 15 noncanonical splits reconstructed exactly; sigma arity distribution',dict(counts))
    print('Source cells:',sum(x['source_rhs_nodes'] for x in items))
    print('Source half-cell counts:',sum(len(x[s]['nodes']) for x in items for s in ('phi','psi')))
    print('Cross side strands:',sum(x['sigma']['width'] for x in items))
    print('Wrote',path)

if __name__=='__main__':main()
