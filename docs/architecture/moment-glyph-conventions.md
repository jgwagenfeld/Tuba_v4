# Moment glyph conventions

Date: 2026-09-01

Scope: primary-source review of 3D applied/reaction moment glyphs. This is a
visualization recommendation, not solver validation.

## Recommendation

Use the CAESAR II compound convention for applied and reaction moments:

- a straight arrow along the signed moment-vector axis; and
- a curved arrow around that axis, with its sense following the right-hand
  rule.

This keeps both facts visible in 3D: the axis/sign of the moment pseudovector
and the associated rotational sense. A curved arrow alone can hide its axis;
a straight arrow alone looks like force. Do not use two arrows pointing away
from a common midpoint: that reads as an unsigned axis or bidirectional load,
not a signed moment.

The compact alternative is the Abaqus convention: one straight shaft with two
**co-directional arrowheads at its signed end**. It is established FEA
shorthand, but it communicates rotation less directly than CAESAR II's
compound glyph.

Scale reaction-force and reaction-moment families independently. Default to
length proportional to magnitude, cap the largest glyph relative to the
viewport, and offer constant-length display only as a dense-scene inspection
mode. The moment legend should state the unit, current scale mode, and the
maximum/reference magnitude; exact vector components remain available on
selection.

## Primary-source findings

| Product | Glyph and sign convention | Scaling and legend practice |
| --- | --- | --- |
| CAESAR II | Hexagon documents a directional arrow for force and a **directional arrow plus curved arrow** for moment; the curved arrow follows the right-hand rule. This command is present in both piping input and the Static Output Processor, so it is the closest piping-specific precedent for Tuba's load and result views. [Forces](https://docs.hexagonppm.com/r/en-US/CAESAR-II-Users-Guide/Version-13/343631?contentId=ju6HY_TNNmmEghMV_P80dg), [right-hand rule](https://docs.hexagonppm.com/r/en-US/CAESAR-II-Users-Guide/Version-14/336570) | Five named arrow sizes are available. Force/moment arrows use a configurable two-color stripe pattern, and the Forces/Moments legend lets users inspect values at nodes and page through load vectors. [Forces](https://docs.hexagonppm.com/r/en-US/CAESAR-II-Users-Guide/Version-13/343631?contentId=ju6HY_TNNmmEghMV_P80dg), [Forces/Moments colors](https://docs.hexagonppm.com/r/en-US/CAESAR-II-Users-Guide/15/787186), [Legends toolbar](https://docs.hexagonppm.com/r/en-US/CAESAR-II-Users-Guide/15/479244) |
| Abaqus/CAE | Free-body force vectors use one arrowhead; moment vectors use **two arrowheads on the same signed end**. Resultant and component vectors can be shown, including components transformed to a chosen coordinate system. [Resultant forces and moments](https://docs.software.vt.edu/abaqusv2025/English/SIMACAECAERefMap/simacae-c-fbdintro.htm), [official figure](https://docs.software.vt.edu/abaqusv2025/English/SIMACAERefImages/fbd-arrows.png), [view-cut component resolution](https://docs.software.vt.edu/abaqusv2025/English/SIMACAECAERefMap/simacae-t-cuthlpfreebody.htm) | Length is magnitude-proportional by default, with an optional constant-length mode. Force and moment scales are independent; each can use model or screen size, and the largest vector supplies the reference length. Force and moment colors are also independent; defaults are red and blue. Labels and per-family thresholds are configurable. [General options](https://docs.software.vt.edu/abaqusv2025/English/SIMACAECAERefMap/simacae-t-fbdoptionsgeneral.htm), [scaling](https://docs.software.vt.edu/abaqusv2024/English/SIMACAECAERefMap/simacae-t-fbdoptionsscaling.htm), [colors](https://docs.software.vt.edu/abaqusv2025/English/SIMACAECAERefMap/simacae-t-fbdoptionscolors.htm), [FreeBodyOptions](https://docs.software.vt.edu/abaqusv2024/English/SIMACAEKERRefMap/simaker-c-freebodyoptionspyc.htm) |
| ANSYS | Mechanical defines moment direction by the right-hand rule and official verification figures depict applied moments with curved arrows. Mechanical APDL exposes applied moments, nodal moments, and reaction moments as display symbols oriented in the nodal coordinate system. The text documentation does not prescribe a distinct curved glyph for `RMOM`, so it is supporting evidence for sign/axis treatment rather than a reaction-glyph precedent. [Mechanical Moment](https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/wb_sim/ds_Moment.html), [APDL `/PBC`](https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/ans_cmd/Hlp_C_PBC.html) | APDL scales force arrows by magnitude, provides a separate vector scale control including uniform length, can print result values beside symbols, and can display local/nodal coordinate triads. It also lets users choose the scaling basis when applied and derived forces/moments differ greatly. [`/PBC`](https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/ans_cmd/Hlp_C_PBC.html), [geometry display controls](https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/ans_bas/Hlp_G_BAS11_3.html) |
| Bentley AutoPIPE | Bentley states that anchor moments are positive by the right-hand rule in global X/Y/Z, and that a positive rotation is counter-clockwise when looking along the positive axis. For pipe-force reports, the selected global/local coordinate system and the node's before/after cut face control the reported sign. The reviewed official material does **not** define a special 3D moment glyph shape, so AutoPIPE supports the sign convention but not a curved-versus-straight choice. [Anchor loads](https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0117940), [axis and rotation convention](https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0026797), [pipe force and moment signs](https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0116590) | AutoPIPE's official product material emphasizes color-coded results, point inspection, and filtered/sortable result grids, not moment-glyph scaling. [AutoPIPE input and results](https://www.bentley.com/en/products/autopipe/) |
| TUBA V2 | V2 is not a moment-glyph precedent. It constructs straight solid arrows only for authored **forces**, scaled from pipe section radius, and its ParaVis postprocessor creates ordinary Arrow glyphs for reaction-force vectors. No moment visualization path is present in the generator at the inspected commit. [force geometry](https://github.com/jgwagenfeld/TUBA_V2/blob/fe4dbe0ebcd91e059fb69644683dcb4546a618c0/tuba/write_Salome_file.py#L889-L924), [reaction-force glyph and legend](https://github.com/jgwagenfeld/TUBA_V2/blob/fe4dbe0ebcd91e059fb69644683dcb4546a618c0/tuba/write_ParaPost_file.py#L193-L230) | The reaction-force glyph uses ParaView vector scaling/orientation and a scalar bar titled `Forces` with magnitude in N. V2 provides no separate moment scale or legend. [ParaVis generator](https://github.com/jgwagenfeld/TUBA_V2/blob/fe4dbe0ebcd91e059fb69644683dcb4546a618c0/tuba/write_ParaPost_file.py#L193-L230) |

## Minimal display contract

For each nonzero moment vector `M` at point `P`:

1. axis direction is `normalize(M)`; negative components therefore reverse the
   axis arrow;
2. arc sense follows the right-hand rule about that signed axis;
3. glyph length is computed only against other moments in the active result
   family, never against force magnitudes;
4. the legend reports `Reaction moment`, `N*m`, the active scale mode, and the
   reference magnitude; and
5. selection exposes `Mx`, `My`, `Mz`, magnitude, coordinate system, load case,
   node, and Code_Aster result provenance.

Applied moments and reaction moments may share the geometry convention, but
must retain distinct layer names/colors and provenance so authored input cannot
be mistaken for a solver result.
