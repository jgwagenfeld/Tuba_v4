"""Dimensioned section plates using Tuba's existing section geometry."""

from html import escape
import math

from tuba.geometry.section_mesh import section_loops
from tuba.model import BarSection, CableSection, IBeamSection, PipeSection, RectangularSection
from tuba.sections.properties import _outline_loops


def section_svg(row, index):
    """Render the actual scheduled section, with the viewer's drafting conventions.

    A section plate describes authored geometry, never a solver result. Reuse
    the native outlines, including rolled I-section fillets and hollow bores.
    """
    name, kind = str(row['section']), row['section_type']
    if kind in {'pipe', 'bar'}:
        cls = PipeSection if kind == 'pipe' else BarSection
        section = cls(name, row['outer_diameter_m'], row['wall_thickness_m'])
        width = height = section.OD
        width_label, height_label = f'Ø {width * 1000:g}', ''
        note = f't {section.WT * 1000:g}' if section.WT else 'Solid'
    elif kind == 'cable':
        section = CableSection(name, row['radius_m'])
        width = height = 2 * section.radius
        width_label, height_label, note = f'Ø {width * 1000:g}', '', 'Cable'
    elif kind == 'rectangular':
        section = RectangularSection(name, row['height_y_m'], row['height_z_m'],
                                     row['thickness_y_m'], row['thickness_z_m'])
        width, height = section.height_y, section.height_z
        width_label, height_label = f'Y {width * 1000:g}', f'Z {height * 1000:g}'
        note = f'tY {section.thickness_y * 1000:g} · tZ {section.thickness_z * 1000:g}'
    elif kind == 'ibeam':
        section = IBeamSection(name, row.get('profile_name') or name, dict(row.get('properties') or {}))
        width, height = section.properties['B'], section.properties['H']
        width_label, height_label = f'B {width * 1000:g}', f'H {height * 1000:g}'
        note = f"tw {section.properties['Tw'] * 1000:g} · tf {section.properties['Tf'] * 1000:g} · R {section.properties.get('R', 0) * 1000:g}"
    else:
        raise ValueError(f'No section plate for section type {kind!r}.')
    if not all(math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError(f'Section {name!r} needs positive finite dimensions.')
    loops = _outline_loops(section) if kind in {'ibeam', 'rectangular'} else section_loops(section, n_sides=96)
    scale = 140 / max(width, height)
    def point(pair):
        y, z = pair
        return (120 + z * scale, 114 - y * scale) if kind == 'ibeam' else (120 + y * scale, 114 - z * scale)
    outlines = ['M ' + ' L '.join(f'{x:.3f},{y:.3f}' for x, y in map(point, loop)) + ' Z' for loop in loops]
    left, right = 120 - width * scale / 2, 120 + width * scale / 2
    top, bottom = 114 - height * scale / 2, 114 + height * scale / 2
    title_id, hatch_id = f'profile-title-{index}', f'profile-hatch-{index}'
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" class="profile-diagram" viewBox="0 0 240 240" role="img" aria-labelledby="{title_id}">',
             f'<title id="{title_id}">{escape(name)} cross-section; dimensions in millimetres</title>',
             f'<defs><pattern id="{hatch_id}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">',
             '<path d="M0,0 V6" class="profile-hatch"/></pattern></defs>',
             f'<path class="profile-material" fill="url(#{hatch_id})" fill-rule="evenodd" d="{" ".join(outlines)}"/>',
             f'<path class="profile-object" d="{outlines[0]}"/>']
    for outline in outlines[1:]:
        parts.append(f'<path class="profile-bore" d="{outline}"/>')
    parts.extend((f'<path class="profile-centreline" d="M{left-9:.3f},114 H{right+9:.3f} M120,{top-9:.3f} V{bottom+9:.3f}"/>',
                  f'<path class="profile-extension" d="M{left:.3f},{bottom:.3f} V{bottom+20:.3f} M{right:.3f},{bottom:.3f} V{bottom+20:.3f}"/>',
                  f'<path class="profile-dimension" d="M{left:.3f},{bottom+17:.3f} H{right:.3f}"/>',
                  f'<text class="profile-dimension-label" x="120" y="{bottom+34:.3f}" text-anchor="middle">{escape(width_label)}</text>',
                  f'<text class="profile-dimension-note" x="120" y="21" text-anchor="middle">{escape(note)}</text>'))
    if height_label:
        x = left - 18
        parts.extend((f'<path class="profile-extension" d="M{left:.3f},{top:.3f} H{x-3:.3f} M{left:.3f},{bottom:.3f} H{x-3:.3f}"/>',
                      f'<path class="profile-dimension" d="M{x:.3f},{top:.3f} V{bottom:.3f}"/>',
                      f'<text class="profile-dimension-label" transform="translate({x-7:.3f},114) rotate(-90)" text-anchor="middle">{escape(height_label)}</text>'))
    parts.append('</svg>')
    return ''.join(parts)
