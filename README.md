# Libros encuadernados a mano

De un EPUB a un libro cosido a mano, en un comando. Reemplaza la conversión
de Calibre (y a BookbinderJS) con un pipeline propio:

```
EPUB ──pandoc──▶ Typst ──▶ interior A5 tipográfico ──▶ cuadernillos A4 para imprimir
                                                        (y la tapa aparte, con el lomo medido)
```

Qué gana sobre Calibre:

- **Notas al pie de verdad**: las notas del EPUB (que Calibre deja como
  bloques a mitad de página o al final del capítulo) se convierten en
  `#footnote` de Typst, al pie de la página que las referencia. 
- **Márgenes espejados** con medianil más ancho del lado del cosido.
- **Preliminares de libro real**: portadilla, portada, dedicatoria
  personalizada por regalo, colofón con versión.
- **Índice propio** con números de página (opcional).
- **Capítulos que abren en página impar**, encabezados corridos, silabeo.
- **Tapa** (contratapa + lomo + frente) generada con el grosor real del
  lomo, medido después de coser.

## Setup (una sola vez)

Corre en cualquier sistema con pandoc, typst y Python 3: no hay nada
específico de macOS (las tipografías vienen embebidas en Typst, así que
el PDF sale idéntico en cualquier máquina).

**macOS:**

```bash
brew install pandoc typst
```

**Manjaro / Arch (sirve para instalación fresca, desde cero):**

```bash
# 1. Sistema al día PRIMERO (en Arch/Manjaro instalar paquetes sobre un
#    sistema desactualizado rompe cosas: nunca instalar sin -Syu antes)
sudo pacman -Syu

# 2. Todo lo necesario (git incluido; --needed saltea lo que ya esté)
sudo pacman -S --needed git python pandoc-cli typst
# si pandoc-cli no existe en tu rama de Manjaro: sudo pacman -S pandoc

# 3. Verificar que quedaron en el PATH
pandoc --version && typst --version
```

En Arch el paquete `python` ya trae `venv` y `ensurepip`: no hace falta
instalar `python-pip` aparte, el venv se bootstrapea su propio pip.

**Después, en ambos sistemas:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Smoke test** (el repo trae un libro de prueba sintético en
`libros/ejemplo/`, con notas al pie, imagen ancha y código):

```bash
python encuadernar.py libro libros/ejemplo/
# tiene que terminar con "Bloque: ... cuadernillos ..." y dejar
# libros/ejemplo/salida/interior-a5.pdf listo para abrir y mirar
```

Para llevar el proyecto a otra máquina: copiá la carpeta entera (o cloná
el repo). Ojo: los `.epub` reales y todo `libros/*/salida/` están en el
`.gitignore`, así que si viajás vía git tenés que copiar los EPUBs aparte
(el de `libros/ejemplo/` sí viaja: es sintético, generado por nosotros).

## Flujo de trabajo

```bash
source .venv/bin/activate

# 1. Crear la carpeta del libro (deja un libro.yaml de ejemplo para editar)
python encuadernar.py init libros/mi-libro/

# 2. Copiar el .epub adentro, editar libro.yaml (título, dedicatoria, colofón…)

# 2b. Ver qué trae el EPUB adentro y decidir qué descartar (su cubierta,
#     su índice, la página legal…): cada sección con título y resumen
python encuadernar.py secciones libros/mi-libro/
#     → los nombres que no quieras van a interior.omitir del libro.yaml

# 3. Generar interior + cuadernillos
python encuadernar.py libro libros/mi-libro/

# 4. Imprimir libros/mi-libro/salida/cuadernillos/*.pdf en dúplex manual
#    (voltear por el borde corto), plegar, coser.

# 5. Medir el grosor del lomo cosido y generar la tapa
python encuadernar.py tapa libros/mi-libro/ --lomo 11.5
```

La salida queda en `libros/mi-libro/salida/`:

| Archivo | Qué es |
|---|---|
| `interior-a5.pdf` | el libro terminado, para revisar en pantalla |
| `cuadernillos/cuadernillo-NN.pdf` | un PDF por cuadernillo, con marcas de plegado y corte |
| `tapa-lomo-XX mm.pdf` | tapa completa, imprimir al 100 % sin escalar |
| `build/` | intermedios (main.typ, config.json) para depurar |

## Config por libro (`libro.yaml`)

Todos los valores y su documentación están en `plantilla/libro.yaml`
(lo que no pongas en tu yaml usa esos defaults). Los más importantes:

- `titulo`, `autores`, `version`, `dedicatoria` — la personalización del regalo.
  La versión sale en el colofón y al pie del lomo.
- `colofon:` — encuadernador, ciudad, fecha, lemas.
- `interior.omitir:` — archivos del EPUB a descartar enteros (su cubierta,
  su portada, su índice…). `encuadernar.py secciones <carpeta>` te muestra
  cada archivo con su título y un resumen para decidir.
- `interior.indice: true` — índice propio con números de página.
- `imposicion.hojas_por_cuadernillo` — 4 hojas A4 = 16 carillas por cuadernillo.
- `tapa.hoja: A4 | A3` — en A4 entra justo (con el refilado por defecto);
  en A3 quedan además marcas de corte afuera de la tapa.

## Opciones útiles

```bash
python encuadernar.py libro libros/mi-libro/ --solo-interior   # solo el PDF A5
python encuadernar.py libro libros/mi-libro/ --desde-pdf x.pdf # flujo viejo (PDF de Calibre)
```

## Cómo funciona

- `encuadernar.py` — CLI. Convierte con pandoc, arma `build/main.typ`
  (plantilla + cuerpo), compila con Typst e impone los cuadernillos con
  pypdf (guardas en blanco, orden de plegado, marcas).
- `plantilla/libro.typ` — la cara tipográfica del interior. Editable.
- `plantilla/tapa.typ` — layout de la tapa con lomo paramétrico.
- `plantilla/filtro.lua` — curaduría del EPUB en pandoc: notas-endnote →
  notas al pie reales, links internos → texto plano, omisión de archivos,
  descarte de la imagen de cubierta.
- `plantilla/libro.yaml` — defaults documentados de toda la config.
- Tipografías propias: crear `fuentes/` en la raíz y poner los .ttf/.otf;
  se pasa solo a Typst (`interior.fuente` elige la familia).

`preparar_libro.py` es el script anterior (imposición sobre PDF de
Calibre); quedó superado por `encuadernar.py --desde-pdf`.
