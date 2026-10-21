"""Dependency-free, headless SVG of validated offline IF ROC results."""
import argparse
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from security.experiments.analyze_roc import SCOPE


def render(result):
    if not isinstance(result,dict) or result.get('schema')!='ids-roc-result-v1' or result.get('scope')!=SCOPE \
            or result.get('environment') not in ('synthetic','vcan','physical-can'):
        raise ValueError('offline IF ROC result required; do not plot trial rates as ROC')
    panels=[]
    for index,split in enumerate(('calibration','evaluation')):
        points=result.get(split+'_roc');auc=result.get(split+'_auc')
        if not isinstance(points,list) or not 2<=len(points)<=20001:raise ValueError('invalid ROC points')
        previous=(-1,-1)
        for point in points:
            if not isinstance(point,dict) or any(type(point.get(k)) not in (int,float) or not math.isfinite(point[k])
                    or not 0<=point[k]<=1 for k in ('fpr','tpr')):
                raise ValueError('invalid ROC rate')
            value=(point['fpr'],point['tpr'])
            if value[0]<previous[0] or value[1]<previous[1]:raise ValueError('ROC must be monotonic')
            previous=value
        area=sum((b['fpr']-a['fpr'])*(a['tpr']+b['tpr'])/2 for a,b in zip(points,points[1:]))
        if (points[0]['fpr'],points[0]['tpr'])!=(0,0) or (points[-1]['fpr'],points[-1]['tpr'])!=(1,1):
            raise ValueError('complete ROC endpoints required')
        if type(auc) not in (int,float) or not math.isfinite(auc) or not math.isclose(area,auc,abs_tol=1e-9):
            raise ValueError('ROC/AUC mismatch')
        x=75+index*435;y=80;size=340
        grid=[]
        for tick in (0,.25,.5,.75,1):
            px=x+size*tick;py=y+size*(1-tick)
            grid.extend([f'<path d="M {px} {y} V {y+size} M {x} {py} H {x+size}" stroke="#e2e8f0"/>',
                         f'<text x="{px}" y="{y+size+20}" text-anchor="middle">{tick:g}</text>',
                         f'<text x="{x-12}" y="{py+4}" text-anchor="end">{tick:g}</text>'])
        line=' '.join(f'{x+size*p["fpr"]:.3f},{y+size*(1-p["tpr"]):.3f}' for p in points)
        panels.append(f'<g>{"".join(grid)}<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="none" stroke="#64748b"/>'
            f'<path d="M {x} {y+size} L {x+size} {y}" stroke="#94a3b8" stroke-dasharray="5 5"/>'
            f'<polyline points="{line}" fill="none" stroke="#2563eb" stroke-width="2.5"/>'
            f'<text x="{x+size/2}" y="{y-18}" text-anchor="middle" font-size="16">{split}: AUC {auc:.4f}</text>'
            f'<text x="{x+size/2}" y="{y+size+48}" text-anchor="middle">False positive rate</text>'
            f'<text transform="translate({x-48},{y+size/2}) rotate(-90)" text-anchor="middle">True positive rate</text></g>')
    label=escape(str(result.get('environment')))
    status=escape(str(result.get('status')))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="920" height="535" viewBox="0 0 920 535">' \
        f'<rect width="920" height="535" fill="white"/><g font-family="sans-serif" font-size="12" fill="#0f172a">' \
        f'<text x="460" y="28" text-anchor="middle" font-size="19">Offline Isolation Forest ROC — {label}</text>' \
        f'{"".join(panels)}<text x="460" y="494" text-anchor="middle">{status}; threshold chosen only on calibration, fixed on evaluation</text>' \
        '<text x="460" y="517" text-anchor="middle">1s nonoverlapping windows; not live 0x200 FPR or official trial acceptance</text></g></svg>\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        if Path(args.output).suffix!='.svg':raise ValueError('output must be .svg')
        svg=render(json.loads(Path(args.input).read_text()))
        with Path(args.output).open('x',encoding='utf-8') as output:output.write(svg)
        print(json.dumps({'status':'RENDERED','output':args.output,'official_acceptance':False}));return 0
    except (OSError,ValueError,TypeError,KeyError) as error:
        print(json.dumps({'status':'INVALID','reason':str(error)}));return 2


if __name__=='__main__':raise SystemExit(main())
