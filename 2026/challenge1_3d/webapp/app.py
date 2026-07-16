#!/usr/bin/env python3
"""Floor-Slab Opening Detection — web app.
Upload one or more construction-plan PDFs -> structured opening list (Excel) +
interactive preview. Run:  python3 app.py   then open http://localhost:5000"""
import os, uuid, traceback
from flask import Flask, request, jsonify, send_file, render_template
import pipeline

BASE=os.path.dirname(os.path.abspath(__file__))
UP=os.path.join(BASE,'uploads'); OUT=os.path.join(BASE,'outputs')
os.makedirs(UP,exist_ok=True); os.makedirs(OUT,exist_ok=True)
app=Flask(__name__); app.config['MAX_CONTENT_LENGTH']=64*1024*1024
JOBS={}

@app.route('/')
def index(): return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    files=request.files.getlist('plans')
    files=[f for f in files if f and f.filename.lower().endswith('.pdf')]
    if not files: return jsonify({'error':'Please upload at least one PDF plan.'}),400
    job=uuid.uuid4().hex[:12]; jdir=os.path.join(UP,job); os.makedirs(jdir,exist_ok=True)
    paths=[]
    for f in files:
        safe=os.path.basename(f.filename).replace(' ','_')
        p=os.path.join(jdir,safe); f.save(p); paths.append(p)
    try:
        r=pipeline.process(paths)
    except Exception as e:
        traceback.print_exc(); return jsonify({'error':'Processing failed: %s'%e}),500
    xlsx=os.path.join(OUT,'%s.xlsx'%job); pipeline.build_workbook(r,xlsx)
    JOBS[job]=xlsx
    master=r['master']; clean=r['clean']
    slab=[m for m in master if m['type']=='Ceiling']; wall=[m for m in master if m['type']=='Wall']
    rr=sum(1 for m in slab if m['geometry']=='round')
    # group detections by plan for preview overlay
    byplan={}
    for o in clean:
        byplan.setdefault(o['plan'],[]).append({'id':o['opening_id'],'label':o['label'],'type':o['type'],
                    'geom':o['geometry'],'l':o['length_cm'],'w':o['width_cm'],'d':o.get('diameter_cm', o['length_cm']),'h':o['height_cm'],'wt':o['weight_kg'],
          'x':o['x_pt'],'y':o['y_pt'],'dup':bool(o.get('is_duplicate'))})
    previews=[{'name':m['name'],'w':m['w'],'h':m['h'],'zoom':m['zoom'],'png':m['png'],
               'openings':byplan.get(m['name'],[])} for m in r['metas']]
    summary={'files':len(paths),'raw':len(clean),'unique':len(master),
             'duplicates':len(clean)-len(master),'slab':len(slab),'wall':len(wall),
             'round':rr,'rect':len(slab)-rr,'pairs':r['plan_pairs_registered'],
             'weight':round(sum(m['weight_kg'] for m in slab),1)}
    rows=[{'id':m['opening_id'],'plans':m['plans'],'np':m['appears_in_n_plans'],'label':m['label'],
            'type':m['type'],'geom':m['geometry'],'l':m['length_cm'],'w':m['width_cm'],'d':m.get('diameter_cm', m['length_cm']),
           'h':m['height_cm'],'wt':m['weight_kg']} for m in master]
    return jsonify({'job':job,'summary':summary,'rows':rows,'previews':previews})

@app.route('/download/<job>')
def download(job):
    p=JOBS.get(job)
    if not p or not os.path.exists(p): return 'expired',404
    return send_file(p,as_attachment=True,download_name='Opening_Report.xlsx')

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=False)
