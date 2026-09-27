import json
import math
import xml.etree.ElementTree as ET

import pytest

from tuba import Model
from tuba.reporting.isometry import _crosses_box, _crosses_segment, build_isometry, main, write_isometry


def model():
    m = Model('Drawing <review> & test')
    m.add_material('steel', E=200e9, nu=.3, rho=7850, alpha=1.2e-5)
    m.add_pipe_section('main', OD=.1, WT=.005)
    m.add_pipe_section('small', OD=.05, WT=.003)
    with m.pipe(section='main', material='steel', route='header') as p:
        p.start([0,0,0]); p.set_direction([1,0,0]); p.run(2)
        tee = p.last_node_id
        p.run(1); p.bend(radius=.3, angle=90, axis=[0,0,1]); p.run(1)
    with m.pipe(section='small', material='steel', route='branch') as p:
        p.start(m.nodes[tee].coords); p.set_direction([0,0,1]); p.run(1)
        p.set_direction([.6,0,.8]); p.run(5)
    m.define_tee(tee)
    m.add_support(tee, 'guide', blocked_dof=[False,True,False,False,False,False], id='guide-Y')
    m.add_support(p.last_node_id, 'spring', direction=[0,0,1], stiffness=16600, id='spring-Z')
    m.assign_attribute('node:'+p.last_node_id,'drawing_support','Hanger setting unknown')
    return m


def test_true_lengths_bends_and_continuations():
    m = model(); before = m.to_dict()
    d = build_isometry(m, elements_per_sheet=2)
    assert m.to_dict() == before
    assert len(d['elements']) == 6
    bend = next(e for e in d['elements'] if e['type']=='pipe_bend')
    assert bend['length_m'] == pytest.approx(.15*math.pi)
    assert bend['dimension']=='arc'
    assert bend['points_m'][0] == pytest.approx(m.nodes[bend['n1']].coords)
    assert bend['points_m'][-1] == pytest.approx(m.nodes[bend['n2']].coords)
    slope = d['elements'][-1]
    assert slope['length_m']==pytest.approx(5)
    assert slope['delta_m']==pytest.approx([3,0,4])
    all_ids=[e for s in d['sheets'] for e in s['elements']]
    assert sorted(all_ids)==sorted(e.id for e in m.elements)
    assert len(all_ids)==len(set(all_ids))
    for node, detail in d['nodes'].items():
        assert detail['sheets']==[s['id'] for s in d['sheets'] if node in s['nodes']]
    tee = next(iter(m.tees))
    assert len(d['nodes'][tee]['sheets'])>=2
    assert d['supports'][0]['states']==['free','fixed','free','free','free','free']
    assert d['supports'][1]['stiffness'][2]==16600
    assert len(d['annotations'])==1
    assert any('unverified' in i['message'] for i in d['issues'])


def test_svg_units_xml_escape_determinism_and_no_overwrite(tmp_path):
    m=model()
    for name in ('first','second'):
        write_isometry(m,tmp_path/name,units='in',precision=3,elements_per_sheet=2)
    first=tmp_path/'first';second=tmp_path/'second'
    assert {p.name:p.read_bytes() for p in first.iterdir()}=={p.name:p.read_bytes() for p in second.iterdir()}
    all_svg=''
    for p in first.glob('*.svg'):
        root=ET.parse(p).getroot()
        assert root.attrib['width']=='420mm'
        assert root.findall('.//{*}polyline[@class="pipe"]')
        all_svg+=p.read_text(encoding='utf-8')
    assert '196.850 C-C' in all_svg  # independent 5 m -> inches
    assert '18.553 arc' in all_svg
    assert 'Drawing &lt;review&gt; &amp; test' in all_svg
    assert 'UNSOLVED REVIEW' in all_svg
    with pytest.raises(ValueError,match='new or empty'):
        write_isometry(m,first)


def test_route_selection_exposes_outside_connections_and_rejects_bad_inputs(tmp_path):
    m=model()
    d=build_isometry(m,routes=['branch'])
    assert len(d['elements'])==2
    assert d['nodes'][next(iter(m.tees))]['outside_elements']
    for kwargs in ({'units':'cm'},{'elements_per_sheet':0},{'precision':-1},{'orientation':float('nan')},{'routes':['missing']}):
        with pytest.raises(ValueError):
            write_isometry(m,tmp_path/'bad',**kwargs)
        assert not (tmp_path/'bad').exists()
    bend=next(e for e in m.elements if e.type=='pipe_bend')
    bend.bend_geometry=None
    with pytest.raises(ValueError,match='canonical bend geometry'):
        write_isometry(m,tmp_path/'bad')


def test_cli_executes_authored_project_and_keeps_source(tmp_path):
    project=tmp_path/'project';project.mkdir()
    source="""from tuba import Model
model=Model('CLI')
model.add_material('steel',E=200e9,nu=.3,rho=7850,alpha=1e-5)
model.add_pipe_section('pipe',OD=.1,WT=.005)
with model.pipe(section='pipe',material='steel',route='line') as p:
    p.start([0,0,0])
    p.run(1)
"""
    (project/'model.py').write_text(source)
    assert main([str(project),'--output',str(tmp_path/'drawings')])==0
    assert (project/'model.py').read_text()==source
    assert not (project/'study.py').exists()
    d=json.loads((tmp_path/'drawings/manifest.json').read_text())
    assert len(d['elements'])==1
    assert not d['supports']
    assert (tmp_path/'drawings/supports.csv').read_text().startswith('id,node,type,')


def test_repeated_source_callouts_preserved_and_csv_formulas_inert(tmp_path):
    m=model(); node=m.supports[-1].node
    m.assign_attribute('node:'+node, 'drawing_support', '=1+2', source='second-sheet')
    write_isometry(m,tmp_path/'drawings')
    d=json.loads((tmp_path/'drawings/manifest.json').read_text())
    assert len(d['annotations'])==2
    assert d['annotations'][1]['description']=='=1+2'
    assert d['annotations'][1]['source']=='second-sheet'
    assert "'=1+2" in (tmp_path/'drawings/support-annotations.csv').read_text()


def test_label_line_clearance_and_collapsed_projection(tmp_path):
    box=(1,1,2,2)
    assert _crosses_box((0,0),(3,3),box)
    assert not _crosses_box((0,2),(2,4),box)
    assert not _crosses_box((3,0),(3,4),box)
    assert _crosses_box((1.5,1.5),(1.6,1.6),box)
    assert _crosses_segment((0,0),(2,2),(0,2),(2,0))
    assert not _crosses_segment((0,0),(2,2),(2,2),(3,0))
    assert not _crosses_segment((0,0),(2,0),(0,1),(2,1))
    m=Model('End-on')
    m.add_material('s',E=200e9,nu=.3,rho=7850,alpha=1e-5)
    m.add_pipe_section('s',OD=.1,WT=.005)
    with m.pipe(section='s',material='s') as p:
        p.start([0,0,0]);p.set_direction([1,1,1]);p.run(1)
    with pytest.raises(ValueError,match='projects to a point'):
        write_isometry(m,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()
    write_isometry(m,tmp_path/'good',orientation=45)


def test_offset_dimensions_keep_true_lengths_and_native_references(tmp_path):
    m=model()
    before=m.to_dict()
    write_isometry(m,tmp_path/'drawings',routes=['branch'])
    root=ET.parse(tmp_path/'drawings/ISO-001.svg').getroot()
    slope=m.elements[-1]
    dimension=root.find(f'.//{{*}}line[@data-dimension="{slope.id}"]')
    assert dimension is not None
    pipe=root.find(f'.//{{*}}polyline[@data-element="{slope.id}"]')
    a,b=[tuple(map(float,p.split(','))) for p in pipe.attrib['points'].split()]
    c=tuple(float(dimension.attrib[k]) for k in ('x1','y1'))
    d=tuple(float(dimension.attrib[k]) for k in ('x2','y2'))
    # The dimension is parallel and offset from the projected run, but its value
    # remains the independently known 3-4-5 spatial length, not screen distance.
    assert (b[0]-a[0])*(d[1]-c[1])-(b[1]-a[1])*(d[0]-c[0]) == pytest.approx(0,abs=1)
    assert math.dist(a,c)>40
    assert any('5000.0  [E2]'==t.text for t in root.findall('.//{*}text'))
    html=(tmp_path/'drawings/index.html').read_text(encoding='utf-8')
    assert f'<td>{slope.n2}</td><td>5000.0</td><td>0.0</td><td>5000.0</td>' in html
    assert m.to_dict()==before
