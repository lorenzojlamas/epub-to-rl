# Cuna + prensa para punzar cuadernillos

Piezas imprimibles en 3D para hacer los 4 agujeros de costura de forma
sistemática (adiós al clavo + martillo + ojo). Modeladas paramétricas con
[build123d](https://build123d.readthedocs.io) y visualizadas con
[ocp_vscode](https://github.com/bernhard-42/vscode-ocp-cad-viewer).

## Qué son (diseño en V, agujeros pasantes por las dos piezas)

- **Cuna**: valle en **V** que sostiene el cuadernillo abierto por el centro
  (pliegue abajo, como libro abierto). En un extremo, una **pared-tope** =
  *datum*: apoyás el borde del cuadernillo ahí y las 4 estaciones caen siempre en
  el mismo lugar. En el vértice hay 4 **agujeros-yunque** pasantes: el papel se
  corta limpio sobre el hueco (como una perforadora) y la punta del clavo sale.
- **Prensa**: una **cuña en V** que encaja en el valle apretando el cuadernillo,
  con una loza plana arriba (agarre + tope de profundidad). Lleva los mismos 4
  agujeros, alineados con los de la cuna. El clavo entra por arriba, la loza +
  cuña lo guían derecho (~24 mm de guiado), cruza el pliegue y sale por la cuna.

Todo es paramétrico: cambiás `FORMATO` y se recalculan el largo del lomo y las
4 estaciones (A y D a `MARGEN_EXTREMO` de cada borde, B y C repartidos parejo).

## Setup (una sola vez)

El venv del proyecto (`.venv`, Python 3.12) ya tiene `build123d` y `ocp_vscode`
(ver `requirements.txt`). Falta solo el visor dentro de VS Code:

1. Instalá la extensión **OCP CAD Viewer** (`bernhard-42.ocp-cad-viewer`).
2. En VS Code, elegí el intérprete de Python del proyecto: `.venv/bin/python`.
3. Abrí el visor: `Cmd+Shift+P` → **"OCP CAD Viewer: Open viewer"**
   (queda escuchando en el puerto 3939).

No hace falta correr `python -m ocp_vscode --backend`: eso es solo el backend de
mediciones. La geometría se ve igual sin él.

## Visualizar / iterar

Con el visor abierto, corré el archivo:

```bash
.venv/bin/python cuna/cuna.py
```

Aparecen la **cuna** (marrón) y la **prensa** (azul semitransparente) armadas en
posición de uso. Editá los parámetros arriba de `cuna.py`, volvé a correr, y el
visor se actualiza.

## Imprimir

`python cuna/cuna.py` deja dos STL en `cuna/stl/`: `cuna_<F>.stl` y
`prensa_<F>.stl`.

- **Sin soportes**, las dos. La cuna se apoya como está (valle hacia arriba,
  paredes a ~45°). La prensa **ya se exporta dada vuelta** (loza abajo, cuña
  hacia arriba como pirámide): imprimila tal cual viene.
- Material: PLA o PETG. Los agujeros ya llevan holgura (`HOLGURA_GUIA`), pero un
  clavo repetido lima el PLA: si vas a punzar mucho, PETG aguanta mejor, o dejá
  el agujero un pelín más grande.
- Si las paredes del valle salen feas, bajá `ANGULO_V` (valle más angosto =
  paredes más verticales = imprime mejor).

## Usar

1. Apoyá el cuadernillo **abierto por el centro** en la V, pliegue abajo, con un
   borde contra la **pared-tope**.
2. Encajá la **prensa** por arriba (topa contra la pared; la V la centra sola).
3. Clavá por cada uno de los 4 agujeros: el clavo cruza el pliegue y sale por el
   agujero-yunque de la cuna. Poné la cuna sobre una plancha de corte / corcho, o
   al borde de la mesa, para que la punta tenga por dónde salir.
4. Sacá la prensa, sacá el cuadernillo, cosé.
