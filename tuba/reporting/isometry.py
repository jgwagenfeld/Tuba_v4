"""Deterministic, unsolved piping review drawings (SVG, HTML, CSV and JSON).

Run ``python -m tuba.reporting.isometry PROJECT --output DIRECTORY``.
Dimensions describe authored centerlines, never fabrication cut lengths.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
from html import escape
import json
import math
from pathlib import Path
import textwrap
import xml.etree.ElementTree as ET

from tuba.model import PipeSection, TubaModel, sample_bend_geometry
from tuba.physical import element_length


def project_point(point, orientation=0):
    """Orthographic isometric projection; orientation rotates about global Z."""
    x, y, z = map(float, point)
    angle = math.radians(orientation)
    x, y = x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)
    return ((x - y) * math.sqrt(3) / 2, (x + y) / 2 - z)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def build_isometry(model: TubaModel, *, units="mm", precision=1, elements_per_sheet=8,
                   orientation=0, routes=None, revision="unissued"):
    """Build a drawing record without changing the model or running a solver.

    Sheet boundaries partition authored elements, not mesh subdivisions. Native
    IDs and full model coordinates survive projection and pagination unchanged.
    """
    if units not in ("mm", "m", "in"):
        raise ValueError("units must be mm, m or in")
    if type(precision) is not int or not 0 <= precision <= 6:
        raise ValueError("precision must be an integer from 0 to 6")
    if type(elements_per_sheet) is not int or not 1 <= elements_per_sheet <= 8:
        raise ValueError("elements_per_sheet must be an integer from 1 to 8")
    if not math.isfinite(orientation):
        raise ValueError("orientation must be finite degrees about global Z")
    model.validate()
    # Serializing also rejects non-finite model data before any output is written.
    fingerprint = hashlib.sha256(_json(model.to_dict()).encode()).hexdigest()
    selected = set(routes) if routes is not None else None
    records, grouped, node_ids, issues = [], defaultdict(list), set(), []
    for e in model.elements:
        route = e.route_id or "unrouted"
        if selected is not None and route not in selected:
            continue
        if e.type not in ("pipe_straight", "pipe_bend") or not isinstance(model.sections[e.section], PipeSection):
            raise ValueError(f"Unsupported drawing element {e.id}: {e.type}; select piping routes explicitly")
        p1, p2 = model.nodes[e.n1].coords, model.nodes[e.n2].coords
        if e.type == "pipe_bend" and e.bend_geometry is None:
            raise ValueError(f"Bend {e.id} has no canonical bend geometry")
        points = (sample_bend_geometry(p1, e.bend_geometry, n_segments=24).tolist()
                  if e.type == "pipe_bend" else [p1.tolist(), p2.tolist()])
        attrs = {k: a.value for k, a in model.get_attribute_assignments(f"element:{e.id}").items()}
        sec = model.sections[e.section]
        delta = [float(b - a) for a, b in zip(p1, p2)]
        row = dict(id=e.id, type=e.type, route=route, n1=e.n1, n2=e.n2,
                   section=e.section, material=e.material, od_m=sec.OD, wall_m=sec.WT,
                   length_m=element_length(model, e), dimension="arc" if e.type == "pipe_bend" else "C-C",
                   radius_m=e.bend_radius, angle_deg=e.bend_angle,
                   delta_m=delta, points_m=points, attributes=attrs)
        if row["length_m"] <= 0:
            raise ValueError(f"Element {e.id} must have positive length")
        if attrs.get("geometry_note"):
            issues.append(dict(ref=f"element:{e.id}", message=str(attrs["geometry_note"])))
        records.append(row)
        grouped[route].append(e.id)
        node_ids.update((e.n1, e.n2))
    if not records:
        raise ValueError("No piping elements selected")
    if selected is not None and selected - grouped.keys():
        raise ValueError(f"Unknown or empty routes: {sorted(selected - grouped.keys())}")
    sheets = []
    by_id = {r["id"]: r for r in records}
    for route, ids in grouped.items():
        for start in range(0, len(ids), elements_per_sheet):
            subset = ids[start:start + elements_per_sheet]
            nodes = sorted({by_id[e][n] for e in subset for n in ("n1", "n2")})
            sheets.append(dict(id=f"ISO-{len(sheets) + 1:03d}", route=route, elements=subset, nodes=nodes))
    node_sheets = defaultdict(list)
    for sheet in sheets:
        for node in sheet["nodes"]:
            node_sheets[node].append(sheet["id"])
    nodes = {}
    selected_ids = set(by_id)
    outside = defaultdict(list)
    for e in model.elements:
        if e.id not in selected_ids:
            for n in (e.n1, e.n2):
                outside[n].append(e.id)
    for nid in sorted(node_ids):
        attrs = {k: a.value for k, a in model.get_attribute_assignments(f"node:{nid}").items()}
        nodes[nid] = dict(coords_m=model.nodes[nid].coords.tolist(), attributes=attrs,
                          sheets=node_sheets[nid], outside_elements=outside[nid],
                          tee=model.tees[nid].to_dict() if nid in model.tees else None)
    supports = []
    for sup in model.supports:
        if sup.node in node_ids:
            restraint = sup.restraint()
            supports.append(dict(id=sup.id, node=sup.node, type=sup.type,
                                 states=list(restraint.states), stiffness=list(restraint.spring_stiffness),
                                 settings=sup.to_dict(), sheets=node_sheets[sup.node]))
    # Retain every assignment: effective attributes collapse repeated callouts.
    annotations = [dict(node=a.target.id, description=a.value, source=a.source, sheets=node_sheets[a.target.id])
                   for a in model.attributes if a.key == "drawing_support" and a.target.kind == "node" and a.target.id in node_ids]
    if annotations:
        issues.append(dict(ref="supports", message=f"{len(annotations)} source support annotations; native restraint reconciliation unverified"))
    if not supports:
        issues.append(dict(ref="supports", message="No native supports in selected piping"))
    for name, group in model.groups.items():
        if selected_ids.intersection(group.get("elements", [])):
            for key, a in model.get_attribute_assignments(f"group:{name}").items():
                if key == "open_tie_in":
                    issues.append(dict(ref=f"group:{name}", message=f"Open tie-in: {_json(a.value).strip()}"))
    result = dict(schema="tuba.isometry.v1", project=model.project_name, revision=str(revision),
                  model_sha256=fingerprint, status="UNSOLVED REVIEW - NOT FOR FABRICATION",
                  units=units, precision=precision, orientation_deg=orientation,
                  sheet_format="A3 landscape", elements_per_sheet=elements_per_sheet,
                  dimensions="True model centerline lengths; arc lengths for bends. No cut lengths.",
                  standards_claim="None; project drafting conventions require separate review.",
                  elements=records, nodes=nodes, supports=supports, annotations=annotations,
                  sheets=sheets, issues=issues)
    _json(result)
    return result


def _crosses_box(a, b, box):
    """Segment/rectangle intersection, including contact at the boundary."""
    low, high = 0.0, 1.0
    for axis in (0, 1):
        delta = b[axis] - a[axis]
        if abs(delta) < 1e-12:
            if not box[axis] <= a[axis] <= box[axis+2]:
                return False
        else:
            t1, t2 = sorted(((box[axis]-a[axis])/delta, (box[axis+2]-a[axis])/delta))
            low, high = max(low,t1), min(high,t2)
            if low > high:
                return False
    return True


def _factor(data):
    return {"mm": 1000, "m": 1, "in": 1 / 0.0254}[data["units"]]


def _crosses_segment(a, b, c, d):
    """Interior intersection; dimension strings may meet at a common endpoint."""
    def side(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return side(a,b,c)*side(a,b,d) < -1e-5 and side(c,d,a)*side(c,d,b) < -1e-5


def _fmt(data, value):
    return f"{float(value) * _factor(data):.{data['precision']}f}"


def _svg(data, sheet):
    """A3 review sheet with a drawing field, offset dimensions and title block."""
    root = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width="420mm", height="297mm", viewBox="0 0 1680 1188")
    ET.SubElement(root, "title").text = f"{data['project']} / {sheet['id']} / {sheet['route']}"
    def tag(kind, **attrs):
        if attrs.get('class_') == 'dim':
            attrs = dict(stroke='#555', stroke_width=1, fill='none', **attrs)
        if attrs.get('class_') == 'pipe':
            attrs = dict(stroke='#111', stroke_width=4, fill='none', stroke_linecap='round', **attrs)
        return ET.SubElement(root, kind, {k.rstrip('_').replace('_', '-'): str(v) for k, v in attrs.items()})
    def text(x, y, value, **attrs):
        style = dict(font_family='Arial, sans-serif', font_size=14 if attrs.get('class_')=='small' else 17, fill='#111')
        style.update(attrs)
        tag("text", x=x, y=y, **style).text = str(value)
    def line(a, b, **attrs):
        tag("line", x1=a[0], y1=a[1], x2=b[0], y2=b[1], **attrs)
    def wrapped(x, y, value, width=65, limit=2, **attrs):
        chunks = textwrap.wrap(str(value), width=width) or [""]
        for i, chunk in enumerate(chunks[:limit]):
            text(x, y + 20 * i, chunk + (" ... [see manifest]" if i == limit - 1 and len(chunks) > limit else ""), **attrs)
    tag("rect", x=0, y=0, width=1680, height=1188, fill="white")
    tag("rect", x=24, y=24, width=1632, height=1140, fill="none", stroke="#111", stroke_width=2)
    wrapped(45, 65, sheet['route'], width=65, limit=1, font_size=28, font_weight='bold')
    text(45, 90, f"PIPING ISOMETRIC / {sheet['id']} / CENTERLINE REVIEW", class_='small')
    line((24,110),(1656,110),stroke='#111')
    line((1135,24),(1135,1164),stroke='#111')
    line((24,1015),(1656,1015),stroke='#111')
    elems = {e["id"]: e for e in data["elements"]}
    rows = [elems[e] for e in sheet["elements"]]
    projected = [project_point(p, data["orientation_deg"]) for e in rows for p in e["points_m"]]
    lo = [min(p[i] for p in projected) for i in (0, 1)]
    hi = [max(p[i] for p in projected) for i in (0, 1)]
    span = max(hi[0] - lo[0], hi[1] - lo[1])
    if span < 1e-10:
        raise ValueError(f"{sheet['id']} projects to a point; choose another orientation")
    scale = min(810 / max(hi[0] - lo[0], span * .01), 650 / max(hi[1] - lo[1], span * .01))
    def pos(p):
        a, b = project_point(p, data["orientation_deg"])
        return (565 + (a - (lo[0] + hi[0]) / 2) * scale, 560 + (b - (lo[1] + hi[1]) / 2) * scale)
    segments = []
    for e in rows:
        pts = list(map(pos,e['points_m']))
        segments.extend(zip(pts,pts[1:]))
        path = " ".join(f"{x:.3f},{y:.3f}" for x, y in map(pos, e["points_m"]))
        shape = tag("polyline", points=path, class_="pipe", data_element=e["id"])
        ET.SubElement(shape, "title").text = f"{e['id']}: {_fmt(data,e['length_m'])} {data['units']} {e['dimension']}"
    # Labels use page-space boxes, independent of physical dimensions.
    occupied = [(970,125,1120,245),(45,125,960,185)]
    text(45,140,f"REFERENCE COORDINATES [{data['units']}]",font_size=12)
    for j,nid in enumerate(dict.fromkeys((rows[0]['n1'],rows[-1]['n2']))):
        xyz=' / '.join(f'{axis} {_fmt(data,v)}' for axis,v in zip('XYZ',data['nodes'][nid]['coords_m']))
        text(45,160+j*20,f"P{sheet['nodes'].index(nid)+1} ({nid}): {xyz}",class_='small')
    def clear(box):
        return (45 <= box[0] and box[2] <= 1115 and 125 <= box[1] and box[3] <= 995
                and not any(box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1] for b in occupied)
                and not any(_crosses_box(a,b,box) for a,b in segments))
    def label(anchor, value, preferred=0):
        w, h = len(value) * 8.5 + 10, 22
        candidates = [(12, -12), (12, 28), (-w - 12, -12), (-w - 12, 28)]
        for ring in range(12):
            for k in range(4):
                dx, dy = candidates[(k + preferred) % 4]
                x, y = anchor[0] + dx, anchor[1] + dy + (ring * 25 * (1 if dy > 0 else -1))
                box = (x - 3, y - 18, x + w, y + 4)
                if not clear(box):
                    continue
                occupied.append(box)
                line(anchor, (x, y - 6), class_="dim")
                tag("rect", x=box[0], y=box[1], width=w+3, height=h, fill="white", fill_opacity=".94")
                text(x, y, value, class_="small")
                return
        raise ValueError(f"Cannot place labels on {sheet['id']}; reduce elements_per_sheet or change orientation")
    for i, e in sorted(enumerate(rows, 1), key=lambda pair: pair[1]['length_m'], reverse=True):
        pts = e["points_m"]
        mid = pts[len(pts)//2] if len(pts)>2 else [(a+b)/2 for a,b in zip(*pts)]
        flag = '*' if e['attributes'].get('geometry_note') else ''
        value = f"{_fmt(data,e['length_m'])}  [E{i}{flag}]"
        a,b = pos(pts[0]),pos(pts[-1])
        length = math.dist(a,b)
        placed = False
        # ponytail: bounded greedy lanes; congested/short runs use leader callouts.
        if e['type']=='pipe_straight' and length > len(value)*8 + 35:
            ux,uy = (b[0]-a[0])/length,(b[1]-a[1])/length
            nx,ny = -uy,ux
            angle = math.degrees(math.atan2(uy,ux))
            if angle > 90: angle -= 180
            if angle < -90: angle += 180
            w,h = len(value)*8+12,24
            bw = abs(ux)*w+abs(uy)*h
            bh = abs(uy)*w+abs(ux)*h
            for offset in (55,-55,90,-90,125,-125,160,-160):
                da=(a[0]+nx*offset,a[1]+ny*offset)
                db=(b[0]+nx*offset,b[1]+ny*offset)
                cx,cy=(da[0]+db[0])/2,(da[1]+db[1])/2
                box=(cx-bw/2,cy-bh/2,cx+bw/2,cy+bh/2)
                if not clear(box) or any(_crosses_box(da,db,old) for old in occupied):
                    continue
                if any(_crosses_segment(da,db,start,end) for start,end in segments):
                    continue
                if not all(45 <= p[0] <= 1115 and 125 <= p[1] <= 995 for p in (da,db)):
                    continue
                sign=1 if offset>0 else -1
                extensions=[((end[0]+nx*sign*7,end[1]+ny*sign*7),
                             (d[0]+nx*sign*8,d[1]+ny*sign*8)) for end,d in ((a,da),(b,db))]
                if any(_crosses_box(start,end,old) for start,end in extensions for old in occupied):
                    continue
                occupied.append(box)
                for start,end in extensions:
                    line(start,end,class_='dim')
                line(da,db,class_='dim',data_dimension=e['id'])
                segments.extend([(da,db),*extensions])
                for end,sign in ((da,1),(db,-1)):
                    tip=(end[0]+sign*ux*10,end[1]+sign*uy*10)
                    tag('polygon',points=f'{end[0]},{end[1]} {tip[0]+nx*3},{tip[1]+ny*3} {tip[0]-nx*3},{tip[1]-ny*3}',fill='#555')
                transform=f'rotate({angle} {cx} {cy})'
                tag('rect',x=cx-w/2,y=cy-12,width=w,height=24,fill='white',transform=transform)
                text(cx,cy+5,value,font_size=16,text_anchor='middle',transform=transform)
                placed=True
                break
        if not placed:
            value = (f"E{i}{flag}: R{_fmt(data,e['radius_m'])} / {e['angle_deg']:.2f} deg"
                     if e['type']=='pipe_bend' else f"E{i}{flag}: {_fmt(data,e['length_m'])} C-C")
            label(pos(mid), value, preferred=1)
    for i, nid in enumerate(sheet["nodes"], 1):
        node = data["nodes"][nid]
        xy = pos(node["coords_m"])
        tag("circle", cx=xy[0], cy=xy[1], r=4, fill="#111", data_node=nid)
        marks = ("/T" if node["tee"] else "") + ("/S" if any(s["node"] == nid for s in data["supports"]) else "") + ("/A" if "drawing_support" in node["attributes"] else "")
        label(xy, f"P{i}{marks}")
    text(1160,57,'SEGMENT SCHEDULE',font_weight='bold')
    text(1160,82,f"Model dimensions [{data['units']}] / not a fabrication BOM",class_='small')
    for i,e in enumerate(rows,1):
        y=140+(i-1)*69
        flag='*' if e['attributes'].get('geometry_note') else ''
        point=lambda nid: f"P{sheet['nodes'].index(nid)+1} ({nid})"
        text(1160,y,f"E{i}{flag}  {e['id']}",font_size=15,font_weight='bold')
        text(1635,y,f"{_fmt(data,e['length_m'])} {e['dimension']}",text_anchor='end',class_='small')
        text(1160,y+19,f"{point(e['n1'])} - {point(e['n2'])} | OD {_fmt(data,e['od_m'])} x {_fmt(data,e['wall_m'])}",class_='small')
        bend=f"R {_fmt(data,e['radius_m'])} / {e['angle_deg']:.2f} deg; " if e['radius_m'] else ''
        text(1160,y+38,f"{bend}dZ {_fmt(data,e['delta_m'][2])}",class_='small')
        line((1150,y+48),(1640,y+48),stroke='#ccc')
    continuations = [(n, [s for s in data['nodes'][n]['sheets'] if s != sheet['id']]) for n in sheet['nodes']]
    continuations = [f"P{sheet['nodes'].index(n)+1} ({n}) -> {', '.join(s)}" for n,s in continuations if s]
    continuations += [f"P{sheet['nodes'].index(n)+1} ({n}) -> outside selection" for n in sheet['nodes'] if data['nodes'][n]['outside_elements']]
    text(1160,715,'CONTINUATIONS / NATIVE NODES',font_size=15,font_weight='bold')
    wrapped(1160, 738, "; ".join(continuations) or "No sheet continuations", width=58, limit=3, class_="small")
    text(1160, 809, "SUPPORT / FITTING REFERENCES",font_size=15,font_weight='bold')
    details = [f"{s['id']} @ {s['node']}: {'/'.join(s['states'])}" for s in data['supports'] if s['node'] in sheet['nodes']]
    details += [f"A @ {a['node']}: {a['description']}" for a in data['annotations'] if a['node'] in sheet['nodes']]
    details += [f"T @ {n}: {data['nodes'][n]['tee']['type']}" for n in sheet['nodes'] if data['nodes'][n]['tee']]
    wrapped(1160, 833, "; ".join(details) or "No native supports or explicit tees on sheet", width=58, limit=8, class_="small")
    # Explicit orientation reference; never infer north or flow.
    for vec,name in [((1,0,0),"X"),((0,1,0),"Y"),((0,0,1),"Z")]:
        px,py=project_point(vec,data['orientation_deg'])
        end=(1030+px*38,190+py*38)
        line((1030,190),end,stroke="#111",stroke_width=1.5)
        text(end[0]+4,end[1],name,class_="small")
    text(45,1042,'DRAWING NOTES',font_size=15,font_weight='bold')
    text(45,1066,'Dimensions: true node-to-node lengths; bends: R / angle, arc length in schedule. NTS.',class_='small')
    text(45,1086,'Dots = native nodes, not welds. Unmarked crossings are not joins. * = geometry caveat.',class_='small')
    text(45,1106,'S = native restraint; A = source annotation only; T = explicit tee. No standards compliance claim.',class_='small')
    text(45,1126,f"XYZ coordinates, full settings and {len(data['issues'])} notices: manifest.json / CSV schedules.",class_='small')
    text(45,1146,'Model SHA256: '+data['model_sha256'],font_size=12)
    wrapped(1160,1040,data['project'],width=62,limit=1,class_='small')
    text(1160,1066,data['status'],font_size=14,font_weight='bold')
    line((1135,1080),(1656,1080),stroke='#111')
    text(1160,1105,sheet['id'],font_size=22,font_weight='bold')
    text(1635,1105,f"SHEET {data['sheets'].index(sheet)+1} / {len(data['sheets'])}",text_anchor='end',class_='small')
    wrapped(1160,1130,f"Rev: {data['revision']} | Approval: UNISSUED",width=60,limit=1,class_='small')
    text(1160,1150,f"A3 | {data['units']} | Z up | Z rotation {data['orientation_deg']:g} deg | NTS",class_='small')
    return ET.tostring(root, encoding="unicode", xml_declaration=False)


def _csv(rows, fields=None):
    from io import StringIO
    out = StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(rows[0]) if rows else fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        values = {k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()}
        # CSV quoting does not neutralize spreadsheet formulas in source labels.
        writer.writerow({k: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r','\n')) else v for k,v in values.items()})
    return out.getvalue()


def write_isometry(model: TubaModel, path, **options):
    """Write a new review bundle; refuse a nonempty directory to protect files.

    Returns the manifest path. SVG geometry and all numbers share one record.
    """
    data = build_isometry(model, **options)
    root = Path(path)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("Output must be a new or empty directory")
    # Render first: unsupported or congested sheets leave no partial output.
    files = {f"{s['id']}.svg": _svg(data,s) for s in data['sheets']}
    files["manifest.json"] = _json(data)
    files["elements.csv"] = _csv([{k:v for k,v in e.items() if k != "points_m"} for e in data['elements']])
    files["supports.csv"] = _csv(data['supports'], ['id','node','type','states','stiffness','settings','sheets'])
    files["support-annotations.csv"] = _csv(data['annotations'], ['node','description','source','sheets'])
    notices = "".join(f"<li><b>{escape(i['ref'])}</b>: {escape(i['message'])}</li>" for i in data['issues'])
    sheets = []
    route_links = {}
    for s in data['sheets']:
        route_links.setdefault(s['route'],s['id'])
        coords = ''.join(f"<tr><td>P{i}</td><td>{escape(n)}</td>"
                         + ''.join(f'<td>{_fmt(data,v)}</td>' for v in data['nodes'][n]['coords_m']) + '</tr>'
                         for i,n in enumerate(s['nodes'],1))
        sheets.append(f"<section id='{s['id']}'><h2>{s['id']} - {escape(s['route'])}</h2>"
                      f"<a href='{s['id']}.svg'>{files[s['id']+'.svg']}</a>"
                      f"<details class='coordinates'><summary>All node coordinates [{data['units']}]</summary>"
                      '<table><thead><tr><th>Point</th><th>Native ID</th><th>X</th><th>Y</th><th>Z</th></tr></thead>'
                      f'<tbody>{coords}</tbody></table></details></section>')
    navigation = ' '.join(f"<a href='#{sid}'>{escape(route)}</a>" for route,sid in route_links.items())
    files['index.html'] = ("<!doctype html><html lang='en'><meta charset='utf-8'>"
        f"<title>{escape(data['project'])} - piping isometries</title>"
        "<style>body{font:16px Arial;background:#e9eef1;color:#162b36;margin:24px auto;padding:0 20px;max-width:1400px}svg{width:100%;height:auto;background:white}section{margin:32px 0}"
        "a{color:#245f75}.intro,.coordinates{background:white;padding:24px}nav{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}nav a{border:1px solid #ccd4d8;padding:6px}"
        "td,th{padding:6px 20px;text-align:right} @page{size:A3 landscape;margin:0}"
        "@media print{body{margin:0;padding:0;max-width:none;background:white}.intro,h2,.coordinates{display:none}section{margin:0;break-after:page}section:last-child{break-after:auto}svg{display:block;width:420mm;height:297mm}}</style>"
        f"<div class='intro'><h1>{escape(data['project'])}</h1><p>{data['status']}</p>"
        f"<p>{len(data['sheets'])} sheets; {len(data['elements'])} model segments; {len(data['supports'])} native supports; {len(data['annotations'])} source support annotations.</p>"
        "<p>True centerline dimensions with offset dimension lines and short-segment callouts; no cut list, manufacturing BOM or standards compliance claim. "
        "Support states are X/Y/Z/RX/RY/RZ; full settings and materials are in the schedules. Print using A3 landscape.</p>"
        "<p><a href='manifest.json'>Manifest</a> | <a href='elements.csv'>Elements</a> | <a href='supports.csv'>Native supports</a> | "
        "<a href='support-annotations.csv'>Source annotations</a></p>"
        f"<details><summary>{len(data['issues'])} review notices</summary><ul>{notices}</ul></details>"
        f"<nav aria-label='Routes'>{navigation}</nav></div>{''.join(sheets)}</html>")
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (root/name).write_text(content, encoding="utf-8", newline="\n")
    return root / 'manifest.json'


def main(argv=None):
    from tuba.project import load_project
    from tuba.project.script import project_on_path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--units", choices=("mm","m","in"), default="mm")
    parser.add_argument("--precision", type=int, default=1)
    parser.add_argument("--elements-per-sheet", type=int, default=8)
    parser.add_argument("--orientation", type=float, default=0)
    parser.add_argument("--route", action="append", dest="routes")
    parser.add_argument("--revision", default="unissued")
    args = parser.parse_args(argv)
    try:
        project = load_project(args.project)
        with project_on_path(project.root):
            model = project.run_model()["model"]
        opts = vars(args).copy()
        opts.pop("project"); output = opts.pop("output")
        manifest = write_isometry(model, output, **opts)
    except (ValueError, FileNotFoundError, TypeError) as exc:
        parser.error(str(exc))
    print(manifest.parent / "index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
