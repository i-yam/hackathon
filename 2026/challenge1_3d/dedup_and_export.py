#!/usr/bin/env python3
"""Stage 2: collapse double-drawn labels, register overlapping plans by a common
translation offset (RANSAC-style on matching labels), merge duplicates, emit a
structured master list. Slab (DDB) openings are the fabrication target; wall
(WDB) openings are tracked separately."""
import json, os, math
from collections import defaultdict, Counter

DATA=os.path.dirname(os.path.abspath(__file__))
INTRA_TOL_PT=6; MATCH_TOL_MM=300; OFFSET_BIN_MM=300; MIN_INLIERS=3
ops=json.load(open(os.path.join(DATA,'_openings_raw.json')))

# 1. collapse intra-plan double-drawn labels (same label, near-identical pos)
byplan=defaultdict(list)
for o in ops: byplan[o['plan']].append(o)
clean=[]
for plan,lst in byplan.items():
    kept=[]
    for o in lst:
        if any(o['label']==k['label'] and abs(o['x_pt']-k['x_pt'])<INTRA_TOL_PT
               and abs(o['y_pt']-k['y_pt'])<INTRA_TOL_PT for k in kept): continue
        kept.append(o)
    clean.extend(kept)
for i,o in enumerate(clean): o['uid']=i
print('intra-plan collapse: %d -> %d'%(len(ops),len(clean)))

plans=sorted({o['plan'] for o in clean})
by=defaultdict(list)
for o in clean: by[o['plan']].append(o)

def register(A,B):
    votes=Counter(); grp=defaultdict(list)
    for a in A:
        for b in B:
            if a['label']!=b['label']: continue
            dx=a['x_mm']-b['x_mm']; dy=a['y_mm']-b['y_mm']
            key=(round(dx/OFFSET_BIN_MM),round(dy/OFFSET_BIN_MM))
            votes[key]+=1; grp[key].append((dx,dy))
    if not votes: return None
    best,n=votes.most_common(1)[0]
    if n<MIN_INLIERS: return None
    g=grp[best]; return sum(p[0] for p in g)/len(g), sum(p[1] for p in g)/len(g), n

parent=list(range(len(clean)))
def find(i):
    while parent[i]!=i: parent[i]=parent[parent[i]]; i=parent[i]
    return i
def union(i,j):
    ri,rj=find(i),find(j)
    if ri!=rj: parent[ri]=rj

regs={}
for i in range(len(plans)):
    for j in range(i+1,len(plans)):
        A,B=by[plans[i]],by[plans[j]]
        r=register(A,B)
        if not r: continue
        dx,dy,n=r; regs[(plans[i],plans[j])]=(round(dx),round(dy),n)
        for a in A:
            ax,ay=a['x_mm']-dx,a['y_mm']-dy; best=None; bd=MATCH_TOL_MM
            for b in B:
                if a['label']!=b['label']: continue
                d=math.hypot(ax-b['x_mm'],ay-b['y_mm'])
                if d<bd: bd=d; best=b
            if best is not None: union(a['uid'],best['uid'])

print('registered plan pairs:',len(regs))
for k,v in regs.items(): print('  %s<->%s off=%d,%d n=%d'%(k[0][-4:],k[1][-4:],v[0],v[1],v[2]))

clusters=defaultdict(list)
for o in clean: clusters[find(o['uid'])].append(o)
print('unique openings: %d (deduped %d)'%(len(clusters),len(clean)-len(clusters)))

def sortkey(it):
    g=it[1][0]; return (0 if g['type']=='Ceiling' else 1, g['plan'], g['y_pt'])
master=[]
for k,item in enumerate(sorted(clusters.items(),key=sortkey),start=1):
    grp=item[1]; rep=grp[0]; seen=sorted({g['plan'] for g in grp})
    oid='U1-%03d'%k
    for idx,g in enumerate(grp):
        g['opening_id']=oid; g['is_duplicate']=(idx>0); g['n_plans']=len(seen)
    master.append({'opening_id':oid,'floor':rep['floor'],
        'plans':', '.join(p.replace('SP_U1_','') for p in seen),
        'appears_in_n_plans':len(seen),'label':rep['label'],'type':rep['type'],
        'geometry':rep['geometry'],'length_cm':rep['length_cm'],'width_cm':rep['width_cm'],
        'height_cm':rep['height_cm'],'slab_top_m':rep['slab_top_m'],'weight_kg':rep['weight_kg'],
        'pos_x_mm':rep['x_mm'],'pos_y_mm':rep['y_mm'],'source_plan':rep['plan']})

json.dump({'master':master,'clean':clean,
           'registrations':{a+'|'+b:v for (a,b),v in regs.items()}},
          open(os.path.join(DATA,'_openings_processed.json'),'w'),indent=1)

slab=[m for m in master if m['type']=='Ceiling']; wall=[m for m in master if m['type']=='Wall']
print('\nMASTER: %d unique (%d slab / %d wall)'%(len(master),len(slab),len(wall)))
print('  slab round/rect: %d/%d'%(sum(1 for m in slab if m['geometry']=='round'),
                                   sum(1 for m in slab if m['geometry']=='rectangular')))
print('  slab fabrication weight: %.1f kg'%sum(m['weight_kg'] for m in slab))
print('  slab deduped across plans: %d'%sum(1 for m in slab if m['appears_in_n_plans']>1))
