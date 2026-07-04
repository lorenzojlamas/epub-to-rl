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

```bash
brew install pandoc typst
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Flujo de trabajo

```bash
source .venv/bin/activate

# 1. Crear la carpeta del libro (deja un libro.yaml de ejemplo para editar)
python encuadernar.py init libros/mi-libro/

# 2. Copiar el .epub adentro, editar libro.yaml (título, dedicatoria, colofón…)

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
  su portada, su índice…). La corrida lista los nombres disponibles.
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
