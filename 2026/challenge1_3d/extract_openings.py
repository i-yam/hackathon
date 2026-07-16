#!/usr/bin/env python3
"""Floor-slab opening extraction engine (prototype) v2.
DDB/DB = Deckendurchbruch (slab/ceiling opening); WDB/WD = Wanddurchbruch (wall).
Dimensions: "60/45" rectangular LxW cm; "Ø13" round diameter cm. Prefix and
dimension tokens are often split (dim sits ~21pt above prefix) -> reassembled."""
import fitz, re, math, json, glob, os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SCALE = 50.0
PT_TO_MM = 25.4/72.0 * SCALE
DENSITY = 2.4
DEFAULT_SLAB_CM = 30.0
ATTACH_RADIUS_PT = 40
PREFIX = {'DDB':'Ceiling','DB':'Ceiling','WDB':'Wall','WD':'Wall'}
DIM_RE  = re.compile(r'^Ø\s*(\d+(?:\.\d+)?)$|^(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)$')
JOIN_RE = re.compile(r'^(DDB|WDB|DB|WD)\s*(?:Ø\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?))$')

def parse_dim(tok):
    t=tok.replace(' ','')
    m=DIM_RE.match(t)
    if not m: return None
    if m.group(1):
        d=float(m.group(1)); return ('round',d,d)
    return ('rectangular',float(m.group(2)),float(m.group(3)))

def weight_kg(L,W,H,geom):
    area=(math.pi/4.0*L*W) if geom=='round' else (L*W)
    return area*H*DENSITY/1000.0

def collect_levels(words):
    lv=[]
    for i,w in enumerate(words):
        m=re.search(r'RD(OK|UK)\s*=?\s*(-?\d+\.\d+)',w[4])
        if m:
            lv.append({'k':m.group(1),'v':float(m.group(2)),'x':(w[0]+w[2])/2,'y':(w[1]+w[3])/2}); continue
        t=w[4].rstrip('=')
        if t in ('RDOK','RDUK'):
            k='OK' if t.endswith('OK') else 'UK'
            for j in range(i+1,min(i+3,len(words))):
                mv=re.fullmatch(r'-?\d+\.\d+',words[j][4])
                if mv: lv.append({'k':k,'v':float(mv.group()),'x':(w[0]+w[2])/2,'y':(w[1]+w[3])/2}); break
    return lv

def slab_cm(x,y,lv):
    ok=[l for l in lv if l['k']=='OK']; uk=[l for l in lv if l['k']=='UK']
    if not ok or not uk: return DEFAULT_SLAB_CM,None
    o=min(ok,key=lambda l:(l['x']-x)**2+(l['y']-y)**2)
    u=min(uk,key=lambda l:(l['x']-x)**2+(l['y']-y)**2)
    t=abs(o['v']-u['v'])*100.0
    return (round(t),o['v']) if 8<=t<=120 else (DEFAULT_SLAB_CM,o['v'])

def fmt(v): return int(v) if float(v)%1==0 else round(v,1)

def parse_plan(path):
    d=fitz.open(path); p=d[0]; words=p.get_text('words')
    name=os.path.splitext(os.path.basename(path))[0]
    floor=name.split('_')[1] if '_' in name else '?'
    lv=collect_levels(words)
    dims=[]
    for w in words:
        pd=parse_dim(w[4])
        if pd: dims.append({'geom':pd[0],'L':pd[1],'W':pd[2],'x':(w[0]+w[2])/2,'y':(w[1]+w[3])/2,'used':False})
    raw=[]
    def emit(prefix,geom,L,W,cx,cy):
        typ=PREFIX[prefix]
        H,lvl=slab_cm(cx,cy,lv) if typ=='Ceiling' else (DEFAULT_SLAB_CM,None)
        lab=('%sØ%g'%(prefix,L)) if geom=='round' else ('%s%g/%g'%(prefix,L,W))
        raw.append({'plan':name,'floor':floor,'prefix':prefix,'type':typ,'geometry':geom,
            'length_cm':fmt(L),'width_cm':fmt(W),'height_cm':H,'label':lab,
            'weight_kg':round(weight_kg(L,W,H,geom),1),'slab_top_m':lvl,
            'x_pt':round(cx,1),'y_pt':round(cy,1),'x_mm':round(cx*PT_TO_MM),'y_mm':round(cy*PT_TO_MM),
            'page_w_pt':round(p.rect.width,1),'page_h_pt':round(p.rect.height,1)})
    for w in words:
        m=JOIN_RE.match(w[4].replace(' ',''))
        if not m: continue
        prefix=m.group(1)
        if m.group(2): geom,L,W='round',float(m.group(2)),float(m.group(2))
        else: geom,L,W='rectangular',float(m.group(3)),float(m.group(4))
        emit(prefix,geom,L,W,(w[0]+w[2])/2,(w[1]+w[3])/2)
    for w in words:
        if w[4] not in PREFIX: continue
        cx,cy=(w[0]+w[2])/2,(w[1]+w[3])/2
        best=None; bd=ATTACH_RADIUS_PT
        for dm in dims:
            if dm['used']: continue
            dist=math.hypot(dm['x']-cx,dm['y']-cy)
            pref=0 if (-32<dm['y']-cy<-8 and abs(dm['x']-cx)<14) else 8
            if dist+pref<bd: bd=dist+pref; best=dm
        if best is None: continue
        best['used']=True
        emit(w[4],best['geom'],best['L'],best['W'],cx,cy)
    d.close(); return raw

def main():
    allop=[]
    for f in sorted(glob.glob(os.path.join(DATA_DIR,'SP_*.pdf'))):
        ops=parse_plan(f); allop.extend(ops)
        nC=sum(1 for o in ops if o['type']=='Ceiling')
        print('%s: %d openings (slab %d, wall %d)'%(os.path.basename(f),len(ops),nC,len(ops)-nC))
    json.dump(allop,open(os.path.join(DATA_DIR,'_openings_raw.json'),'w'),indent=1)
    nC=sum(1 for o in allop if o['type']=='Ceiling')
    print('TOTAL raw:',len(allop),' slab(DDB):',nC,' wall(WDB):',len(allop)-nC)

if __name__=='__main__':
    main()
