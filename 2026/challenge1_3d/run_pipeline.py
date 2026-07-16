#!/usr/bin/env python3
"""One-shot orchestrator: extract -> dedup/register -> export Excel/CSV + viewer data.
Usage:  python3 run_pipeline.py
Outputs: U1_Opening_Report.xlsx, U1_Slab_Openings.csv, viewer/data.js"""
import subprocess, sys, os, json
D=os.path.dirname(os.path.abspath(__file__))
def run(s): print('\n>>',s); subprocess.check_call([sys.executable,os.path.join(D,s)])
run('extract_openings.py'); run('dedup_and_export.py'); run('build_excel.py')
# refresh viewer payload
proc=json.load(open(os.path.join(D,'_openings_processed.json')))
meta=json.load(open(os.path.join(D,'viewer','tiles','_meta.json')))
from collections import defaultdict
byplan=defaultdict(list)
for o in proc['clean']:
    byplan[o['plan']].append({'id':o['opening_id'],'label':o['label'],'type':o['type'],
      'geom':o['geometry'],'l':o['length_cm'],'w':o['width_cm'],'h':o['height_cm'],
      'wt':o['weight_kg'],'x':o['x_pt'],'y':o['y_pt'],'dup':bool(o.get('is_duplicate')),'np':o.get('n_plans',1)})
plans=[{'name':n,'img':'tiles/'+n+'.png','w':meta[n]['w'],'h':meta[n]['h'],'openings':byplan.get(n,[])} for n in sorted(meta)]
payload={'plans':plans,'master_count':len(proc['master']),'raw_count':len(proc['clean']),
         'slab_count':sum(1 for m in proc['master'] if m['type']=='Ceiling'),
         'wall_count':sum(1 for m in proc['master'] if m['type']=='Wall')}
open(os.path.join(D,'viewer','data.js'),'w').write('window.OPENING_DATA='+json.dumps(payload)+';')
print('\nDONE — open viewer/Slab_Opening_Viewer.html')
