> **⚠️ HISTORICAL — pre-implementation design note.** This document describes an
> earlier design and may not match the shipped code (e.g. it references a
> CalculiX/Aster solver-agnostic engine and file paths that do not exist). For
> current, authoritative behavior see `README.md`, `AGENTS.md`, the
> `notebooks/00`–`08` course, and `docs/architecture/`.

# Piping Systems: Desirable Features, AI Integration & Code Compliance Design

---

## 1. Desirable Features of Industrial Piping Systems

When human engineers or AI agents design piping layouts, they optimize for several critical, interacting physical and operational criteria. These criteria are the target metrics for our optimization loops:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Design Objective Function                    │
├────────────────────────────────┬────────────────────────────────┤
│       Structural Safety        │      Operational Cost          │
├────────────────────────────────┼────────────────────────────────┤
│ • Thermal Flexibility (Loops)  │ • Minimum Pipe Length          │
│ • Deadweight Support (Spacing)  │ • Minimum Pressure Drop (Fittings)│
│ • Vibration Mitigation         │ • Material/Welding Reduction   │
│ • Safe Nozzle Load limits      │ • Clash-Free Routing           │
└────────────────────────────────┴────────────────────────────────┘
```

### A. Thermal Flexibility & Expansion Loops
- **The Physics**: Pipes carry high-temperature fluids and undergo thermal expansion. If both ends are anchored, thermal expansion creates massive axial forces, causing pipe buckling or crushing connected equipment nozzles (e.g., pumps, turbines).
- **The Solution**: Inserting directional changes (offsets, Z-bends, or 3D expansion loops) that flex under bending rather than compressing axially.
- **AI Rule**: Maximize flexibility without exceeding pressure drop limits or encroaching on access zones.

### B. Deadweight Support & Optimal Spacing
- **The Physics**: Pipes must support their own weight, the weight of the fluid, insulation, and valves. Insufficient support causes excessive sag (deflection), creating bending stress peaks and liquid pooling pockets.
- **The Solution**: Space supports according to code limits (e.g., maximum span rules).
- **AI Rule**: Place vertical rests at standard span intervals, preferring locations near heavy valves or structures where support frames can be easily anchored.

### C. Flow Efficiency & Pressure Drop
- **The Physics**: Elbows, tees, and valves introduce local turbulence and pressure drops, increasing pump power requirements over the plant's lifetime.
- **The Solution**: Route lines as straight as possible, preferring large-radius bends (e.g., 3D/5D elbows) over tight 1.5D elbows, and minimizing total bend counts.

---

## 2. AI-Ready Architecture: Bridging the Gap

To make Tuba v4 fully ready for the AI age, we separate the system into a declarative data model, a physics engine, and a post-processing compliance checker:

```
                  ┌───────────────────────────────┐
                  │          AI Agent             │
                  │   Generates design intent     │
                  └──────────────┬────────────────┘
                                 │ Writes / Modifies
                                 ▼
                  ┌───────────────────────────────┐
                  │      Canonical JSON Model     │
                  │  Specifies topology/obstacles │
                  └──────────────┬────────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌──────────────────────────────┐                ┌──────────────────────────────┐
│      Routing Engine          │                │        Solver Engine         │
│  Computes collision-free     │                │   Runs FEA (CalculiX/Aster)  │
│  paths using A* / PBS        │                │   Computes raw Forces/Moments│
└──────────────────────────────┘                └──────────────┬───────────────┘
                                                               │
                                                               ▼
                                                ┌──────────────────────────────┐
                                                │      Compliance Engine       │
                                                │  Applies B31.3 / EN 13480    │
                                                │  Calculates Stress Ratios    │
                                                └──────────────┬───────────────┘
                                                               │ Returns
                                                               ▼
                                                ┌──────────────────────────────┐
                                                │      Structured Feedback     │
                                                │  "Node 14: Overstressed 125%"│
                                                └──────────────────────────────┘
```

### Key AI-Ready APIs

1. **Auto-routing API**:
   - Instead of routing individual coordinate segments, the AI calls:
     ```python
     router.route_pipe(from_nozzle="E1_N1", to_nozzle="E2_N2", avoid_obstacles=True)
     ```
2. **Support Recommendation API**:
   - The system analyzes stress results and suggests structural modifications as structured data:
     ```json
     [
       {
         "type": "RECOMMENDATION",
         "code": "SUSTAINED_OVERSTRESS",
         "node": "N14",
         "action": "ADD_SUPPORT",
         "support_type": "rest",
         "reason": "Mid-span deflection exceeds 2.5mm limit."
       }
     ]
     ```

---

## 3. Implementing Multi-Standard Code Compliance

A common architectural mistake is hardcoding code compliance directly into the finite element solver. **Code_Aster and CalculiX are solver-agnostic**—they only solve the structural equations ($K d = F$). Standard-specific equations are applied in the post-processing phase.

### A. The Separation of Concerns
1. **Solver Phase**: Calculates raw nodal displacements ($u, v, w, \theta_x, \theta_y, \theta_z$) and element local forces/moments (axial force $F_x$, shear forces $F_y, F_z$, torsional moment $M_x$, bending moments $M_y, M_z$).
2. **Compliance Phase**: Takes these raw forces/moments and applies the standard code equations.

### B. Standard Equations & Stress Combinations

#### 1. ASME B31.3 (Process Piping)
- **Sustained Stress ($S_L$)** (Weight + Pressure):
  $$S_L = \frac{P D_o}{4 t_h} + \frac{\sqrt{(I_i M_i)^2 + (I_o M_o)^2}}{Z} \le S_h$$
  Where $I_i, I_o$ are sustained stress indices (typically $0.75 \times \text{SIF} \ge 1.0$), and $Z$ is the corroded section modulus.
- **Displacement/Expansion Stress ($S_E$)** (Thermal):
  $$S_E = \frac{\sqrt{(i_i M_i)^2 + (i_o M_o)^2 + M_t^2}}{Z} \le S_A$$
  Where $i_i, i_o$ are the expansion Stress Intensification Factors (SIFs), $M_t$ is the torsional moment, and $S_A$ is the allowable displacement stress range:
  $$S_A = f (1.25 S_c + 0.25 S_h)$$
  ($S_c$: Allowable stress at ambient temperature; $S_h$: Allowable stress at design hot temperature; $f$: Stress range reduction factor for cycling).

#### 2. EN 13480 (Metallic Industrial Piping)
- **Sustained Stress ($S_{\sigma}$)**:
  $$S_{\sigma} = \frac{P D_c}{4 e_n} + \frac{\sqrt{(i_i M_i)^2 + (i_o M_o)^2}}{Z} \le f_h$$
  Where EN uses slightly different coefficients for SIFs ($i$-factors) and section moduli compared to ASME.
- **Thermal Range ($S_{eq}$)**:
  $$S_{eq} = \frac{\sqrt{(i_i M_i)^2 + (i_o M_o)^2 + M_t^2}}{Z} \le f_a$$

---

## 4. Architectural Implementation Plan for Standards

To implement these standards modularly, we define a structured database and standard rule engines in python.

### A. Materials Database (`tuba/compliance/database.db`)
An SQLite or JSON database mapping materials to temperature-dependent properties:

```sql
CREATE TABLE allowable_stresses (
    material_name TEXT,
    code TEXT,            -- 'ASME_B31.3', 'EN_13480'
    temp_c REAL,
    allowable_stress_pa REAL
);
```

### B. SIF & Flexibility Factor Library (`tuba/compliance/sif.py`)
Computes SIFs ($i$) and flexibility factors ($k$) for elbows and branch connections based on geometry parameters (e.g., thickness, bend radius, run pipe size).
- **ASME B31.3 Appendix D / ASME B31J**:
  - For an elbow: Flexibility characteristic $h = \frac{t \cdot R}{r_m^2}$
  - In-plane SIF: $i_i = \frac{0.90}{h^{2/3}}$
  - Out-of-plane SIF: $i_o = \frac{0.75}{h^{2/3}}$
  - Flexibility factor: $k = \frac{1.65}{h}$

### C. Compliance Calculator (`tuba/compliance/evaluator.py`)
Combines results and generates compliance reports:

```python
class CodeComplianceEvaluator:
    def __init__(self, code_name: str, material_db):
        self.code_name = code_name
        self.db = material_db

    def check(self, model: TubaModel, results: FEAResults) -> ComplianceReport:
        report = ComplianceReport()
        for element in model.elements:
            # 1. Fetch element forces and moments from results
            forces = results.get_forces(element.id)
            
            # 2. Compute SIFs for this element type
            sif_in, sif_out = compute_sifs(element, self.code_name)
            
            # 3. Apply stress combinations
            sustained_stress = self.calc_sustained(element, forces, sif_in, sif_out)
            expansion_stress = self.calc_expansion(element, forces, sif_in, sif_out)
            
            # 4. Compare with allowable stress from database
            sh = self.db.get_allowable(element.material, temp=model.design_temp)
            
            report.add_result(
                element.id,
                sustained_ratio=sustained_stress / sh,
                expansion_ratio=expansion_stress / self.calc_sa(element)
            )
        return report
```
