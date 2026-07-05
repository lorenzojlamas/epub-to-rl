#!/usr/bin/env python3
"""
encuadernar.py — de EPUB a libro cosido a mano, en un comando.
=================================================================
Flujo completo: EPUB -> pandoc -> Typst -> PDF A5 tipográfico ->
imposición en cuadernillos A4 listos para imprimir en dúplex manual.
La tapa se genera aparte, cuando ya cosiste y mediste el lomo real.

Comandos:
  python encuadernar.py init  libros/mi-libro/
      Crea la carpeta con un libro.yaml de ejemplo. Poné el .epub adentro.

  python encuadernar.py libro libros/mi-libro/
      Hace todo: interior A5 + cuadernillos. Opciones:
        --config RUTA     usar otro yaml (default: libro.yaml de la carpeta)
        --solo-interior   genera el PDF A5 y no impone cuadernillos
        --desde-pdf PDF   saltea pandoc/Typst y usa un PDF A5 ya hecho
                          (el flujo viejo de Calibre); solo impone
        --borrar-primera  con --desde-pdf: descarta la 1.ª página (portada)

  python encuadernar.py tapa  libros/mi-libro/ --lomo 11.5
      Genera la tapa (contratapa + lomo + frente) con el lomo MEDIDO en mm
      sobre los cuadernillos ya cosidos.

Salida: libros/mi-libro/salida/
  interior-a5.pdf            el libro terminado, para revisar en pantalla
  cuadernillos/*.pdf         un PDF por cuadernillo, con marcas
  tapa-lomo-11.5mm.pdf       la tapa

Requiere: pandoc y typst en el PATH; pypdf, reportlab y PyYAML (venv).
"""

import argparse
import copy
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color

RAIZ = Path(__file__).resolve().parent
PLANTILLAS = RAIZ / "plantilla"

GRIS = Color(0.5, 0.5, 0.5)
NEGRO = Color(0, 0, 0)


# ====================== config ======================

def fusionar(base, extra):
    """Merge profundo: extra pisa a base."""
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            fusionar(base[k], v)
        else:
            base[k] = v
    return base


def cargar_config(carpeta, ruta_config=None):
    defaults = yaml.safe_load((PLANTILLAS / "libro.yaml").read_text())
    ruta = Path(ruta_config) if ruta_config else carpeta / "libro.yaml"
    if not ruta.exists():
        sys.exit(f"No encuentro {ruta}. Creala con: python encuadernar.py init {carpeta}")
    cfg = fusionar(copy.deepcopy(defaults), yaml.safe_load(ruta.read_text()))
    # ancho de tapa por defecto = A5 menos el refilado del borde delantero
    if not cfg["tapa"].get("ancho_pagina_mm"):
        cfg["tapa"]["ancho_pagina_mm"] = 148 - cfg["imposicion"]["margen_corte_mm"]
    cfg["tapa"].setdefault("lomo_mm", 0)
    return cfg


def encontrar_epub(carpeta):
    epubs = sorted(carpeta.glob("*.epub"))
    if not epubs:
        sys.exit(f"No hay ningún .epub en {carpeta}")
    if len(epubs) > 1:
        print(f"AVISO: hay {len(epubs)} epubs; uso {epubs[0].name}")
    return epubs[0]


def correr(cmd, **kw):
    try:
        subprocess.run(cmd, check=True, **kw)
    except FileNotFoundError:
        sys.exit(
            f"No está instalado '{cmd[0]}' "
            f"(macOS: brew install {cmd[0]} · Manjaro/Arch: sudo pacman -S {cmd[0]})"
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"Falló {cmd[0]} (código {e.returncode})")


# ====================== EPUB -> Typst -> PDF A5 ======================

def listar_secciones(epub):
    """Nombres de los archivos de contenido del EPUB (para interior.omitir)."""
    with zipfile.ZipFile(epub) as z:
        return sorted(
            Path(n).name for n in z.namelist()
            if re.search(r"\.x?html?$", n, re.I)
        )


def inspeccionar_epub(epub):
    """(nombre, resumen) de cada archivo del EPUB, en orden de lectura."""
    NS_OPF = "{http://www.idpf.org/2007/opf}"
    import xml.etree.ElementTree as ET

    def resumen_html(html):
        html = re.sub(r"<head\b.*?</head>", " ", html, flags=re.S | re.I)
        titulo = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, re.S | re.I)
        cuerpo = re.sub(r"<[^>]+>", " ", html)
        cuerpo = re.sub(r"\s+", " ", cuerpo).strip()
        partes = []
        if titulo:
            t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", titulo.group(1))).strip()
            if t:
                partes.append(f"«{t}»")
        if cuerpo:
            partes.append(cuerpo[:70] + ("…" if len(cuerpo) > 70 else ""))
        if not partes:
            imgs = len(re.findall(r"<img\b|<image\b", html, re.I))
            partes.append(f"(solo {imgs} imagen/es)" if imgs else "(vacío)")
        return "  ".join(partes)

    with zipfile.ZipFile(epub) as z:
        try:
            contenedor = ET.fromstring(z.read("META-INF/container.xml"))
            ruta_opf = contenedor.find(
                ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
            ).get("full-path")
            opf = ET.fromstring(z.read(ruta_opf))
            base = str(Path(ruta_opf).parent)
            hrefs = {
                item.get("id"): item.get("href")
                for item in opf.iter(f"{NS_OPF}item")
            }
            orden = [
                hrefs[ref.get("idref")]
                for ref in opf.iter(f"{NS_OPF}itemref")
                if ref.get("idref") in hrefs
            ]
            rutas = [(h, str(Path(base) / h) if base != "." else h) for h in orden]
        except Exception:
            # EPUB raro: caer a listar los html alfabéticamente
            rutas = [(n, n) for n in z.namelist() if re.search(r"\.x?html?$", n, re.I)]
        salida = []
        for href, ruta in rutas:
            try:
                html = z.read(ruta).decode("utf-8", "ignore")
            except KeyError:
                continue
            salida.append((Path(href).name, resumen_html(html)))
        return salida


def convertir_epub(epub, build, cfg):
    """pandoc: EPUB -> cuerpo.typ + media/, con rutas relativas al build."""
    build.mkdir(parents=True, exist_ok=True)
    interior = cfg["interior"]
    print(f"  secciones del EPUB: {', '.join(listar_secciones(epub))}")
    if interior["omitir"]:
        print(f"  omitiendo: {', '.join(interior['omitir'])}")
    entorno = dict(
        os.environ,
        ENC_OMITIR=",".join(interior["omitir"]),
        ENC_NOTAS="1" if interior["notas_al_pie"] else "0",
        ENC_PORTADA="0" if not interior["saltar_portada_epub"] else "1",
    )
    correr([
        "pandoc", str(epub.resolve()),
        "-t", "typst", "-o", "cuerpo.typ",
        "--extract-media=media", "--wrap=none",
        f"--lua-filter={PLANTILLAS / 'filtro.lua'}",
    ], cwd=build, env=entorno)
    return (build / "cuerpo.typ").read_text()


def compilar_typst(build, entrada, salida_pdf):
    cmd = ["typst", "compile", "--root", str(build), str(build / entrada), str(salida_pdf)]
    fuentes = RAIZ / "fuentes"
    if fuentes.is_dir():
        cmd[2:2] = ["--font-path", str(fuentes)]
    correr(cmd)


def generar_interior(carpeta, cfg, salida):
    build = salida / "build"
    cuerpo = convertir_epub(encontrar_epub(carpeta), build, cfg)
    plantilla = (PLANTILLAS / "libro.typ").read_text()
    if "{{CUERPO}}" not in plantilla:
        sys.exit("plantilla/libro.typ perdió el marcador {{CUERPO}}")
    (build / "main.typ").write_text(plantilla.replace("{{CUERPO}}", cuerpo))
    (build / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    interior = salida / "interior-a5.pdf"
    compilar_typst(build, "main.typ", interior)
    paginas = len(PdfReader(str(interior)).pages)
    print(f"  interior: {interior}  ({paginas} páginas A5)")
    return interior


# ====================== imposición ======================

def preparar_bloque(pdf_interior, cfg, borrar_primera=False):
    """Bloque = guardas al inicio + interior + guardas al final."""
    imp = cfg["imposicion"]
    libro = PdfReader(str(pdf_interior))
    p0 = libro.pages[0]
    aw, ah = float(p0.mediabox.width), float(p0.mediabox.height)
    for lado, n in (("guardas_inicio", imp["guardas_inicio"]),
                    ("guardas_final", imp["guardas_final"])):
        if n % 2:
            print(f"AVISO: {lado}={n} es impar y rompe el recto/verso; conviene un número par.")
    w = PdfWriter()
    for _ in range(imp["guardas_inicio"]):
        w.add_blank_page(width=aw, height=ah)
    desde = 1 if borrar_primera else 0
    for pg in libro.pages[desde:]:
        w.add_page(pg)
    for _ in range(imp["guardas_final"]):
        w.add_blank_page(width=aw, height=ah)
    return w, aw, ah


def orden_cuadernillo(n):
    """Orden clásico de plegado: caras (izq, der) 1-based para n páginas."""
    caras = []
    lo, hi = 1, n
    cara_externa = True
    while lo < hi:
        caras.append((hi, lo) if cara_externa else (lo, hi))
        lo += 1
        hi -= 1
        cara_externa = not cara_externa
    return caras


def tamanos_cuadernillos(total, hojas_por_cuadernillo):
    """Cuadernillos llenos + un último más chico para no acumular blancas."""
    ppc = hojas_por_cuadernillo * 4
    tams = [ppc] * (total // ppc)
    resto = total % ppc
    if resto:
        tams.append(math.ceil(resto / 4) * 4)
    return tams


def imponer(writer_bloque, aw, ah, cfg):
    buf = io.BytesIO()
    writer_bloque.write(buf)
    buf.seek(0)
    paginas = PdfReader(buf).pages
    total = len(paginas)

    cuadernillos = []
    base = 0
    for tam in tamanos_cuadernillos(total, cfg["imposicion"]["hojas_por_cuadernillo"]):
        w = PdfWriter()
        for pi, pd in orden_cuadernillo(tam):
            hoja = PageObject.create_blank_page(width=aw * 2, height=ah)
            for idx, tx in ((pi, 0), (pd, aw)):
                gidx = base + idx - 1
                if gidx < total:
                    hoja.merge_transformed_page(paginas[gidx], Transformation().translate(tx=tx, ty=0))
            w.add_page(hoja)
        cuadernillos.append((w, aw * 2, ah, tam))
        base += tam
    return cuadernillos, total


def overlay_marcas(ancho, alto, con_plegado, imp):
    """Marcas: plegado central (solo cara externa) + corte en el borde delantero."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(ancho, alto))
    cx = ancho / 2
    if imp["mostrar_plegado"] and con_plegado:
        # linea punteada solo en la cara externa: por ahi se dobla
        c.setStrokeColor(GRIS)
        c.setLineWidth(0.6)
        c.setDash(3, 3)
        c.line(cx, 0, cx, alto)
        c.setDash()
    if imp["mostrar_corte"]:
        c.setStrokeColor(NEGRO)
        c.setLineWidth(0.5)
        xi = imp["margen_corte_mm"] * mm
        xd = ancho - imp["margen_corte_mm"] * mm
        L = imp["largo_marca_mm"] * mm
        for x in (xi, xd):
            c.line(x, alto, x, alto - L)
            c.line(x, 0, x, L)
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def aplicar_marcas(writer, ancho, alto, imp):
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    externa = overlay_marcas(ancho, alto, True, imp)
    interna = overlay_marcas(ancho, alto, False, imp)
    out = PdfWriter()
    for i, pg in enumerate(PdfReader(buf).pages):
        pg.merge_page(externa if i % 2 == 0 else interna)
        out.add_page(pg)
    return out


def generar_cuadernillos(pdf_interior, cfg, salida, borrar_primera=False):
    bloque, aw, ah = preparar_bloque(pdf_interior, cfg, borrar_primera)
    cuadernillos, total = imponer(bloque, aw, ah, cfg)
    carpeta_c = salida / "cuadernillos"
    if carpeta_c.exists():
        shutil.rmtree(carpeta_c)
    carpeta_c.mkdir(parents=True)
    imp = cfg["imposicion"]
    hojas_totales = 0
    for i, (w, W, H, tam) in enumerate(cuadernillos, start=1):
        con_marcas = aplicar_marcas(w, W, H, imp)
        ruta = carpeta_c / f"cuadernillo-{i:02d}.pdf"
        with open(ruta, "wb") as f:
            con_marcas.write(f)
        hojas = tam // 4
        hojas_totales += hojas
        print(f"  {ruta.name}: {hojas} hojas A4 ({tam} carillas)")
    print(f"\nBloque: {total} carillas A5 · {len(cuadernillos)} cuadernillos · {hojas_totales} hojas A4")
    print("Imprimir cada cuadernillo en dúplex manual (voltear por el borde corto).")
    print("Después de coser: medí el grosor del lomo y generá la tapa con")
    print(f"  python encuadernar.py tapa <carpeta> --lomo <mm>")


# ====================== tapa ======================

def generar_tapa(carpeta, cfg, salida, lomo_mm):
    t = cfg["tapa"]
    t["lomo_mm"] = lomo_mm
    hoja_w = 420 if t["hoja"] == "A3" else 297
    total_w = t["ancho_pagina_mm"] * 2 + lomo_mm
    if total_w > hoja_w:
        sys.exit(
            f"La tapa mide {total_w:.1f} mm de ancho y no entra en una {t['hoja']} "
            f"apaisada ({hoja_w} mm). Poné tapa.hoja: A3 en libro.yaml."
        )
    build = salida / "build-tapa"
    build.mkdir(parents=True, exist_ok=True)
    shutil.copy(PLANTILLAS / "tapa.typ", build / "tapa.typ")
    if t["imagen_fondo"]:
        origen = carpeta / t["imagen_fondo"]
        if not origen.exists():
            sys.exit(f"No encuentro la imagen de fondo: {origen}")
        shutil.copy(origen, build / origen.name)
        t = dict(t, imagen_fondo=origen.name)
    cfg_tapa = dict(cfg, tapa=t)
    (build / "config.json").write_text(json.dumps(cfg_tapa, ensure_ascii=False, indent=1))
    destino = salida / f"tapa-lomo-{lomo_mm:g}mm.pdf"
    compilar_typst(build, "tapa.typ", destino)
    print(f"  tapa: {destino}")
    print(f"  (tapa de {total_w:.1f} × {t['alto_pagina_mm']} mm en hoja {t['hoja']}; imprimir al 100%)")


# ====================== comandos ======================

def cmd_init(args):
    carpeta = Path(args.carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / "libro.yaml"
    if destino.exists():
        sys.exit(f"{destino} ya existe; no lo piso.")
    shutil.copy(PLANTILLAS / "libro.yaml", destino)
    print(f"Listo: {destino}")
    print("Editá el yaml, copiá el .epub a la carpeta y corré:")
    print(f"  python encuadernar.py libro {carpeta}")


def cmd_libro(args):
    carpeta = Path(args.carpeta)
    cfg = cargar_config(carpeta, args.config)
    salida = carpeta / "salida"
    salida.mkdir(parents=True, exist_ok=True)

    if args.desde_pdf:
        interior = Path(args.desde_pdf)
        if not interior.exists():
            sys.exit(f"No existe {interior}")
        print(f"Usando PDF ya armado: {interior} (sin pandoc/Typst)")
    else:
        print(f"«{cfg['titulo']}» — generando interior con Typst…")
        interior = generar_interior(carpeta, cfg, salida)

    if args.solo_interior:
        print("Listo (solo interior).")
        return
    print("Imponiendo cuadernillos…")
    generar_cuadernillos(interior, cfg, salida, borrar_primera=args.borrar_primera)


def cmd_secciones(args):
    carpeta = Path(args.carpeta)
    epub = encontrar_epub(carpeta)
    print(f"Secciones de {epub.name}, en orden de lectura:\n")
    for nombre, resumen in inspeccionar_epub(epub):
        print(f"  {nombre:<28} {resumen}")
    print(
        "\nPara descartar una sección entera, copiá su nombre en libro.yaml:\n"
        "  interior:\n"
        "    omitir: [Cubierta.xhtml, indice.xhtml]\n"
        "Candidatas típicas: la cubierta, la portada y el índice propios del\n"
        "EPUB (este pipeline genera los suyos), y la página legal."
    )


def cmd_tapa(args):
    carpeta = Path(args.carpeta)
    cfg = cargar_config(carpeta, args.config)
    salida = carpeta / "salida"
    salida.mkdir(parents=True, exist_ok=True)
    print(f"«{cfg['titulo']}» — tapa con lomo de {args.lomo:g} mm…")
    generar_tapa(carpeta, cfg, salida, args.lomo)


def main():
    p = argparse.ArgumentParser(
        prog="encuadernar.py",
        description="De EPUB a libro cosido a mano: interior A5, cuadernillos y tapa.",
    )
    sub = p.add_subparsers(dest="comando", required=True)

    p_init = sub.add_parser("init", help="crea la carpeta del libro con un libro.yaml de ejemplo")
    p_init.add_argument("carpeta")
    p_init.set_defaults(func=cmd_init)

    p_libro = sub.add_parser("libro", help="EPUB -> interior A5 + cuadernillos")
    p_libro.add_argument("carpeta")
    p_libro.add_argument("--config", help="yaml alternativo (default: libro.yaml de la carpeta)")
    p_libro.add_argument("--solo-interior", action="store_true", help="no imponer cuadernillos")
    p_libro.add_argument("--desde-pdf", metavar="PDF", help="usar un PDF A5 ya hecho (flujo Calibre)")
    p_libro.add_argument("--borrar-primera", action="store_true",
                         help="con --desde-pdf: descartar la 1.ª página")
    p_libro.set_defaults(func=cmd_libro)

    p_secc = sub.add_parser("secciones",
                            help="lista las secciones del EPUB para decidir qué omitir")
    p_secc.add_argument("carpeta")
    p_secc.set_defaults(func=cmd_secciones)

    p_tapa = sub.add_parser("tapa", help="genera la tapa con el lomo medido")
    p_tapa.add_argument("carpeta")
    p_tapa.add_argument("--lomo", type=float, required=True, metavar="MM",
                        help="grosor medido del lomo cosido, en mm")
    p_tapa.add_argument("--config", help="yaml alternativo")
    p_tapa.set_defaults(func=cmd_tapa)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
