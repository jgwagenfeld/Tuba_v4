"""Code_Aster comm emission for a linear buckling eigenvalue analysis.

A buckling study is the load case's own linear static solve plus one extra
eigenproblem, so this appends to an existing comm rather than replacing it. The
chain solves ``K phi = -lambda * Kg phi`` with the geometric stiffness ``Kg``
taken from the prestress the static run already produced.

Four things about this are not obvious and each cost a failed run:

* **The block must precede ``FIN()``.** ``FIN`` closes the jeveux memory manager;
  a command after it dies with ``code_aster memory manager is not started``.
* **``CREA_CHAMP`` needs ``NUME_ORDRE=1``** to select the prestress instance.
  Without it: ``Exactly one argument of ('NUME_ORDRE', 'INST', 'FREQ', ...) is
  required``.
* **The a-posteriori modal check must usually be switched off.** Code_Aster's
  default tolerance is 1e-6, which a real frame frequently cannot meet even
  though the factors are converged to 1e-12, and the run then raises
  ``ALGELINE5_15`` *after* computing usable factors. Hence
  ``stop_on_error=False`` by default in :class:`~tuba.model.BucklingOptions`.
* **``CHAR_CRIT`` is a result parameter, not a field.** ``CREA_TABLE`` only
  extracts fields, so the factors are read off the result object with
  ``getParameters()`` from the interpreter embedded in the comm, the same
  mechanism the contact writer uses for its JSON.

The keyword is ``STABILITE``/``MODE_FLAMB``; the solver has no command named for
buckling in English, and searching for one gives a false negative.
"""

from __future__ import annotations

from tuba.model import BucklingOptions
from tuba.solver.aster_loads import LineWriter

#: Fortran unit the mode-shape table is written to.
BUCKLING_MODES_UNIT = 43
#: Fortran unit the critical-factor JSON is written to.
BUCKLING_FACTORS_UNIT = 44


def write_buckling_analysis(
    w: LineWriter,
    options: BucklingOptions,
    *,
    boundary_conditions: list[str],
) -> None:
    """Append the buckling eigenproblem to a comm that already holds a linear static solve.

    No name mapping is needed here: the chain works on the model, the material and
    the section, not on individual members, so it never references a solver-safe
    element label.
    """
    if not boundary_conditions:
        # RIGI_MECA needs the DDL_IMPO definitions; without any there is no
        # supported degree of freedom and the assembled matrix is meaningless.
        raise ValueError(
            "Buckling analysis requires a supported model: the elastic stiffness matrix is "
            "assembled with the boundary conditions, and this model declares none."
        )
    charges = ", ".join(boundary_conditions)

    w("# ----- Linear buckling eigenvalue analysis on this load case's prestress -----")
    w("PREC = CREA_CHAMP(")
    w("    RESULTAT=RESU,")
    w("    NOM_CHAM='SIEF_ELGA',")
    w("    NUME_ORDRE=1,")
    w("    OPERATION='EXTR',")
    w("    TYPE_CHAM='ELGA_SIEF_R',")
    w(");")
    w()
    w("# Elastic stiffness.")
    w("MELR = CALC_MATR_ELEM(")
    w("    MODELE=MODELE,")
    w("    CARA_ELEM=CARA,")
    w("    CHAM_MATER=CHMAT,")
    w("    OPTION='RIGI_MECA',")
    w(f"    CHARGE=({charges},),")
    w(");")
    w()
    w("# Geometric stiffness: the only thing that makes a structure able to buckle.")
    w("MERG = CALC_MATR_ELEM(")
    w("    MODELE=MODELE,")
    w("    CARA_ELEM=CARA,")
    w("    OPTION='RIGI_GEOM',")
    w("    SIEF_ELGA=PREC,")
    w(");")
    w()
    w("NUM_DDL = NUME_DDL(MATR_RIGI=MELR);")
    w("K_MECA = ASSE_MATRICE(MATR_ELEM=MELR, NUME_DDL=NUM_DDL);")
    w("K_GEOM = ASSE_MATRICE(MATR_ELEM=MERG, NUME_DDL=NUM_DDL);")
    w()
    w("MD_FLANB = CALC_MODES(")
    w("    MATR_RIGI=K_MECA,")
    w("    TYPE_RESU='MODE_FLAMB',")
    w("    MATR_RIGI_GEOM=K_GEOM,")
    w(f"    CALC_CHAR_CRIT=_F(NMAX_CHAR_CRIT={int(options.n_modes)}),")
    # Note the quotes belong to the emitted Code_Aster, not to this interpolation:
    # f"...={'OUI' if flag else 'NON'}" would emit a bare NON and NameError.
    w(f"    VERI_MODE=_F(STOP_ERREUR=\"{'OUI' if options.stop_on_error else 'NON'}\"),")
    w("    SOLVEUR_MODAL=_F(")
    w(f"        MODE_RIGIDE='{options.rigid_modes}',")
    w(f"        METHODE='{options.method}',")
    w(f"        COEF_DIM_ESPACE={int(options.modal_subspace)},")
    w("    ),")
    w(");")
    w()

    if options.mode_shapes:
        w("# Mode shapes, in the same column layout as a static DEPL table so the")
        w("# standard displacement reader can consume them.")
        w("TAB_FLANB = CREA_TABLE(")
        w("    RESU=_F(")
        w("        RESULTAT=MD_FLANB,")
        w("        NOM_CHAM='DEPL',")
        w("        TOUT='OUI',")
        w("        TOUT_CMP='OUI',")
        w("    ),")
        w(");")
        w()
        w("IMPR_TABLE(")
        w("    TABLE=TAB_FLANB,")
        w(f"    UNITE={BUCKLING_MODES_UNIT},")
        w("    FORMAT='TABLEAU',")
        w("    FORMAT_R='1PE24.16',")
        w("    SEPARATEUR=',',")
        w(");")
        w()

    w("# Critical load factors. Code_Aster reports CHAR_CRIT negative; the sign is a")
    w("# convention of the eigenproblem, so the magnitude is the load factor and the")
    w("# raw value is kept beside it for traceability.")
    w("import json")
    w("_flamb_params = MD_FLANB.getParameters()")
    w("_flamb_raw = _flamb_params.get('CHAR_CRIT', []) or []")
    w("buckling_rows = [")
    w("    {")
    w("        'mode': int(_mode),")
    w("        'critical_factor': abs(float(_value)),")
    w("        'raw_eigenvalue': float(_value),")
    w("    }")
    w("    for _mode, _value in enumerate(_flamb_raw, start=1)")
    w("]")
    # The unit is interpolated here, not left as a brace: this string is Python
    # that Code_Aster's own interpreter runs, where the writer's names do not exist.
    w(f"with open('fort.{BUCKLING_FACTORS_UNIT}', 'w') as _stream:")
    w("    json.dump({'modes': buckling_rows}, _stream, allow_nan=False)")
    w()