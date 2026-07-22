"""
cuna.py — Cuna (valle en V) + prensa (cuña en V) para punzar cuadernillos.

Idea (diseño en V, agujeros pasantes que van por las dos piezas):
  - La CUNA es un valle en V. El cuadernillo se apoya ABIERTO por el centro
    (pliegue abajo, como libro abierto) dentro del valle.
  - La PRENSA es una cuña (V invertida) que encaja en el valle por arriba y
    aprieta el cuadernillo contra las caras del valle. Arriba tiene una loza
    plana que hace de agarre y de tope de profundidad (apoya en el borde).
  - Un TOPE en un extremo de la cuna = datum: apoyás el borde del cuadernillo
    ahí y las 4 estaciones caen siempre en el mismo lugar.
  - Cada estación es UN agujero vertical que atraviesa prensa + pliegue + cuna
    (pasante por las dos). Metés el clavo por arriba: la prensa lo guía derecho,
    el clavo corta el pliegue y sale por el agujero de la cuna (como perforadora:
    el papel corta limpio sobre el hueco).

Imprime sin soportes:
  - Cuna: apoyada como está (valle hacia arriba, paredes ~45deg auto-soportadas).
  - Prensa: se exporta DADA VUELTA (loza abajo, cuña hacia arriba = pirámide).

Salida: dos STL distintos en cuna/stl/ (cuna_<F>.stl y prensa_<F>.stl).
Paramétrico: cambiá FORMATO (o ALTO_LOMO) y se recalcula todo. 4 agujeros
para todos los tamaños (A y D a MARGEN_EXTREMO de cada borde, B y C parejos).

Visualizar:   abrí OCP CAD Viewer y corré este archivo.
Exportar STL: python cuna/cuna.py
"""

from math import radians, tan
from pathlib import Path

from build123d import *

# ----------------------------------------------------------------------------
# PARÁMETROS  (tocá acá y volvé a correr)
# ----------------------------------------------------------------------------

# --- Cuadernillo ---
FORMATO = "A6"                       # "A6" | "A5" | "A7" | "A4" | "libre"
ALTO_LOMO = {                        # alto de la página = largo del lomo (mm)
    "A7": 105, "A6": 148, "A5": 210, "A4": 297,
}.get(FORMATO, 148.0)                # si FORMATO="libre", editá este número
ESPESOR_CUADERNILLO = 1.5            # grosor del pliegue plegado (para la holgura)

# --- Estaciones de costura (4 agujeros para todos los tamaños) ---
N_AGUJEROS     = 4
MARGEN_EXTREMO = 15.0                # A y D a esta distancia de cada borde

# --- Clavo / punzón ---
DIAM_CLAVO   = 1.1                   # diámetro del clavo/punzón (el tuyo: 1.1 x 19 mm)
LARGO_CLAVO  = 19.0                  # largo del clavo (solo informativo, para el chequeo)
HOLGURA_GUIA = 0.9                   # holgura generosa: entra siempre e imprime redondo
                                     # (la posición la fija el tope, no el diámetro)
DIAM_GUIA    = DIAM_CLAVO + HOLGURA_GUIA   # -> 2.0 mm

# --- Cuna (valle en V) ---
# La V es BAJA a propósito: solo tiene que asentar el pliegue, no abrir el
# cuadernillo entero. Valle bajo = punto de entrada cerca del pliegue = clavo
# corto, y mucho menos material.
ANGULO_V   = 90.0                    # ángulo incluido del valle (más chico = paredes
                                     # más verticales = imprime mejor, valle más angosto)
PROF_V     = 7.0                     # profundidad del valle (baja: alcanza para el pliegue)
PARED_LADO = 4.0                     # material a cada lado del valle
PISO_ESP   = 5.0                     # piso debajo del vértice (largo del agujero-yunque)
PARED_TOPE = 5.0                     # espesor de la pared-tope (datum)
ALTO_TOPE  = 10.0                    # cuánto sobresale el tope por encima del borde
RUNOUT     = 10.0                    # material extra más allá de la última estación

# --- Prensa (cuña en V) ---
HOLGURA_PRENSA = 0.4                 # juego entre cuña y valle (además del papel)
CAP_ESP  = 3.0                       # espesor de la loza de arriba (agarre + guía)
FLANGE   = 2.0                       # cuánto apoya la loza sobre el borde del valle

# ----------------------------------------------------------------------------
# DERIVADOS
# ----------------------------------------------------------------------------

_A = radians(ANGULO_V / 2.0)
_T = tan(_A)
HALF_W  = PROF_V * _T                 # medio ancho del valle arriba
WY      = 2 * HALF_W + 2 * PARED_LADO # ancho total de la cuna
APEX_Z  = PISO_ESP                    # z del vértice del valle
HZ      = APEX_Z + PROF_V             # z del borde del valle
LX      = PARED_TOPE + ALTO_LOMO + RUNOUT
GAP     = ESPESOR_CUADERNILLO + HOLGURA_PRENSA   # separación vertical en el pliegue
APEX_W  = APEX_Z + GAP                # z del vértice de la cuña (prensa)


def estaciones(largo, n, margen):
    """Posiciones de los agujeros medidas desde el tope (datum)."""
    a, d = margen, largo - margen
    if n <= 1:
        return [largo / 2.0]
    paso = (d - a) / (n - 1)
    return [a + i * paso for i in range(n)]


ESTACIONES = estaciones(ALTO_LOMO, N_AGUJEROS, MARGEN_EXTREMO)   # desde el tope
X0 = PARED_TOPE                                                  # cara datum en X
X1 = PARED_TOPE + ESTACIONES[-1] + MARGEN_EXTREMO                # fin útil de la prensa


# ----------------------------------------------------------------------------
# CUNA (valle en V)
# ----------------------------------------------------------------------------

def build_cuna() -> Part:
    with BuildPart() as cuna:
        # cuerpo macizo
        Box(LX, WY, HZ, align=(Align.MIN, Align.CENTER, Align.MIN))

        # tope (pared datum) que sobresale por encima del borde
        with Locations((PARED_TOPE / 2, 0, HZ)):
            Box(PARED_TOPE, WY, ALTO_TOPE, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # valle en V: prisma triangular restado desde el tope hasta el final
        with BuildSketch(Plane.YZ.offset(X0)):
            with BuildLine():
                Polyline((-HALF_W, HZ), (0, APEX_Z), (HALF_W, HZ), close=True)
            make_face()
        extrude(amount=LX - X0, mode=Mode.SUBTRACT)

        # agujeros-yunque: pasantes verticales, del vértice al piso
        with Locations(*[(PARED_TOPE + p, 0, 0) for p in ESTACIONES]):
            Cylinder(DIAM_GUIA / 2, APEX_Z + 1.0,
                     align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

    assert cuna.part is not None
    return cuna.part


# ----------------------------------------------------------------------------
# PRENSA (cuña en V)  — construida en posición de uso (vértice hacia abajo)
# ----------------------------------------------------------------------------

def build_prensa() -> Part:
    largo = X1 - X0
    half_w_rim = (HZ - APEX_W) * _T          # medio ancho de la cuña al ras del borde
    cap_w = 2 * HALF_W + 2 * FLANGE          # loza: apoya sobre el borde del valle

    with BuildPart() as prensa:
        # cuña (prisma triangular, vértice abajo)
        with BuildSketch(Plane.YZ.offset(X0)):
            with BuildLine():
                Polyline((-half_w_rim, HZ), (0, APEX_W), (half_w_rim, HZ), close=True)
            make_face()
        extrude(amount=largo)

        # loza de agarre arriba
        with Locations(((X0 + X1) / 2, 0, HZ)):
            Box(largo, cap_w, CAP_ESP, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # agujeros guía: pasantes verticales por loza + cuña
        with Locations(*[(PARED_TOPE + p, 0, APEX_W - 1.0) for p in ESTACIONES]):
            Cylinder(DIAM_GUIA / 2, (HZ + CAP_ESP) - APEX_W + 2.0,
                     align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

    assert prensa.part is not None
    return prensa.part


def prensa_para_imprimir(p):
    """Da vuelta la prensa (loza abajo, cuña arriba) y la apoya en z=0."""
    girada = p.rotate(Axis.X, 180)
    return girada.translate((0, 0, -girada.bounding_box().min.Z))


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

cuna_p = build_cuna()
prensa_p = build_prensa()


def _resumen():
    print(f"Formato {FORMATO}  |  lomo {ALTO_LOMO:.0f} mm  |  {N_AGUJEROS} agujeros")
    print("Estaciones desde el tope (mm): "
          + ", ".join(f"{p:.1f}" for p in ESTACIONES))
    print(f"Cuna:   {LX:.0f} x {WY:.0f} x {HZ + ALTO_TOPE:.0f} mm "
          f"(valle {ANGULO_V:.0f}deg, prof {PROF_V:.0f})")
    print(f"Prensa: {X1 - X0:.0f} mm de largo, loza {CAP_ESP:.0f} mm")
    stack = HZ + CAP_ESP                        # de la boca del agujero al piso
    hasta_pliegue = stack - APEX_Z              # boca -> pliegue
    agarre = LARGO_CLAVO - hasta_pliegue        # cuánto asoma con la punta en el pliegue
    print(f"Clavo {DIAM_CLAVO}x{LARGO_CLAVO:.0f} mm -> agujero {DIAM_GUIA:.1f} mm | "
          f"guiado ~{stack - APEX_W:.0f} mm arriba + {APEX_Z:.0f} mm yunque")
    print(f"  boca->pliegue {hasta_pliegue:.0f} mm | con la punta en el pliegue asoman "
          f"{agarre:.0f} mm p/ agarrar | punta cruza el piso por {LARGO_CLAVO - stack:.0f} mm")


if __name__ == "__main__":
    _resumen()
    out = Path(__file__).parent / "stl"
    out.mkdir(exist_ok=True)
    export_stl(cuna_p, str(out / f"cuna_{FORMATO}.stl"))
    export_stl(prensa_para_imprimir(prensa_p), str(out / f"prensa_{FORMATO}.stl"))
    print(f"STL exportados en {out}/")

    # Vista armada (posición de uso): cuna + prensa encajada.
    try:
        from ocp_vscode import show
        show(cuna_p, prensa_p,
             names=["cuna", "prensa"],
             colors=["#b0752a", "#2a6fb0"],
             alphas=[1.0, 0.55])
    except Exception as e:
        print(f"(visor no disponible: {e})")
