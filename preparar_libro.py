#!/usr/bin/env python3
"""
encuadernar.py  -  reemplaza a BookbinderJS y mas, en un solo script local.
==========================================================================
Toma un PDF A5 (el que sale de Calibre) y produce los cuadernillos (signatures)
A4 listos para imprimir en duplex manual, con:
  - portada del EPUB eliminada (opcional)
  - hoja de colofon al principio o al final
  - hojas en blanco de cortesia
  - IMPOSICION en cuadernillos (lo que hacia BookbinderJS), 100% local
  - linea de plegado central + marcas de corte en el borde delantero

Uso:
    python3 encuadernar.py libro-A5.pdf

Salida: una carpeta 'salida_cuadernillos/' con signature0.pdf, signature1.pdf ...
        (ya marcados y listos para imprimir impares/pares)

Requiere: pypdf y reportlab  ->  pip3 install pypdf reportlab
"""

import sys, os, io, math
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from reportlab.lib.pagesizes import A5, A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color

# ====================== DATOS DEL COLOFON ======================
titulo        = "99 Bottles of OOP"
autores       = "Sandi Metz & Katrina Owen"
encuadernador = "Loren"
ciudad        = "Buenos Aires, Argentina"
fecha         = "junio de 2026"
prueba        = "Prueba N.\u00ba 01"
detalle       = "Encuadernaci\u00f3n cosida \u00b7 tapa blanda"
lema_top      = ["Hecho con amor.", "El conocimiento no es negocio."]
lema_bottom   = "Hack the world."

# ====================== OPCIONES ======================
BORRAR_PRIMERA_PAGINA = True   # borra la portada-imagen del EPUB
GUARDAS_INICIO        = 4      # carillas A5 en blanco al INICIO (guardas). 4 = 2 hojas
GUARDAS_FINAL         = 4      # carillas A5 en blanco al FINAL (guardas). 4 = 2 hojas
HOJAS_POR_CUADERNILLO = 4      # sheets per signature (4 = recomendado)
MARGEN_CORTE_MM       = 8
LARGO_MARCA_MM        = 6
MOSTRAR_PLEGADO       = True
MOSTRAR_CORTE         = True
CARPETA_SALIDA        = "salida_cuadernillos"
# Orden del bloque: [guardas inicio] -> [colofon] -> [libro] -> [guardas final]
# La 1a guarda del inicio se pega a la tapa; la ultima del final a la contratapa.
# El colofon queda en hoja libre (no se pega), por eso va DESPUES de las guardas.
# ======================================================

PT = 1.0
A5_W, A5_H = A5      # 419.5 x 595.3 pt aprox
A4_W, A4_H = A4
GRIS = Color(0.5, 0.5, 0.5)
NEGRO = Color(0, 0, 0)


# ---------- colofon ----------
def construir_colofon():
    buf = io.BytesIO()
    W, H = A5
    cx = W / 2
    c = canvas.Canvas(buf, pagesize=A5)
    def ctr(y, s, f, t, g=0):
        c.setFont(f, t); c.setFillGray(g); c.drawCentredString(cx, y, s)
    y = H - 70*mm
    ctr(y, "\u2b29", "Helvetica", 9, 0.5); y -= 16*mm
    for l in lema_top:
        ctr(y, l, "Times-Italic", 13); y -= 7*mm
    y -= 10*mm
    ctr(y, "\u2b29", "Helvetica", 9, 0.5); y -= 16*mm
    ctr(y, titulo, "Times-Bold", 12); y -= 6*mm
    ctr(y, autores, "Times-Roman", 10, 0.2); y -= 14*mm
    ctr(y, f"Impreso y encuadernado a mano por {encuadernador}", "Times-Roman", 9, 0.3); y -= 5*mm
    ctr(y, f"{ciudad} \u2014 {fecha}", "Times-Roman", 9, 0.3); y -= 5*mm
    ctr(y, prueba, "Times-Roman", 9, 0.3); y -= 5*mm
    ctr(y, detalle, "Times-Roman", 9, 0.3); y -= 16*mm
    ctr(y, "\u2b29", "Helvetica", 9, 0.5); y -= 16*mm
    ctr(y, lema_bottom, "Times-Italic", 13)
    c.save(); buf.seek(0)
    return PdfReader(buf).pages[0]


# ---------- preparar el bloque (portada/colofon/blancas) ----------
def preparar_bloque(ruta):
    libro = PdfReader(ruta)
    p0 = libro.pages[0]
    aw, ah = float(p0.mediabox.width), float(p0.mediabox.height)
    writer = PdfWriter()
    colofon = construir_colofon()

    # 1) Guardas del inicio (la 1a se pega a la tapa)
    for _ in range(GUARDAS_INICIO):
        writer.add_blank_page(width=aw, height=ah)
    # 2) Colofon (en hoja libre, despues de las guardas)
    writer.add_page(colofon)
    # 3) El libro (saltando la portada del EPUB si corresponde)
    inicio = 1 if BORRAR_PRIMERA_PAGINA else 0
    for pg in libro.pages[inicio:]:
        writer.add_page(pg)
    # 4) Guardas del final (la ultima se pega a la contratapa)
    for _ in range(GUARDAS_FINAL):
        writer.add_blank_page(width=aw, height=ah)

    return writer, aw, ah


# ---------- orden de imposicion de un cuadernillo ----------
def orden_cuadernillo(num_paginas_A5):
    """Devuelve la lista de indices de pagina (0-based) en el orden en que
    deben colocarse en las hojas A4, cara por cara.
    Para un cuadernillo de S hojas = 4S paginas A5.
    Cada hoja A4 tiene: CARA FRENTE = [pag_der_externa, pag_izq...] etc.
    Implementacion clasica de folding."""
    # num_paginas_A5 debe ser multiplo de 4
    n = num_paginas_A5
    # secuencia de un cuadernillo plegado: pares (ultima, primera), (segunda, penultima)...
    # generamos el orden de las CARAS A4 (cada cara = 2 paginas A5: izquierda, derecha)
    izq = n
    der = 1
    caras = []  # cada elemento: (pagina_izquierda, pagina_derecha) 1-based
    # Recorremos de afuera hacia adentro
    lo, hi = 1, n
    cara_par = True
    while lo < hi:
        if cara_par:
            # cara externa (frente de la hoja): hi a la izquierda, lo a la derecha
            caras.append((hi, lo))
        else:
            # cara interna (dorso): lo a la izquierda, hi a la derecha
            caras.append((lo, hi))
        lo += 1; hi -= 1
        cara_par = not cara_par
    return caras  # lista de (izq,der) 1-based


def imponer(writer_bloque, aw, ah):
    """Toma el bloque preparado y arma cuadernillos A4 apaisados.
    Devuelve lista de PdfWriter, uno por cuadernillo."""
    # Pasamos el bloque a un reader en memoria
    buf = io.BytesIO(); writer_bloque.write(buf); buf.seek(0)
    bloque = PdfReader(buf)
    paginas = bloque.pages
    total = len(paginas)

    pag_por_cuad = HOJAS_POR_CUADERNILLO * 4
    num_cuad = math.ceil(total / pag_por_cuad)
    total_relleno = num_cuad * pag_por_cuad

    # tamano A5 real (de la pagina del libro)
    pw, ph = aw, ah
    # A4 apaisado: ancho = 2*A5_ancho, alto = A5_alto
    A4L_W = pw * 2
    A4L_H = ph

    cuadernillos = []
    for ci in range(num_cuad):
        base = ci * pag_por_cuad
        # indices globales de las paginas de este cuadernillo (1-based dentro del cuadernillo)
        def get_pagina(idx_1based):
            gidx = base + (idx_1based - 1)
            if gidx < total:
                return paginas[gidx]
            return None  # blanco

        caras = orden_cuadernillo(pag_por_cuad)
        w = PdfWriter()
        for (pi, pd) in caras:
            # nueva hoja A4 apaisada en blanco
            hoja = PageObject.create_blank_page(width=A4L_W, height=A4L_H)
            pag_izq = get_pagina(pi)
            pag_der = get_pagina(pd)
            if pag_izq is not None:
                hoja.merge_transformed_page(pag_izq, Transformation().translate(tx=0, ty=0))
            if pag_der is not None:
                hoja.merge_transformed_page(pag_der, Transformation().translate(tx=pw, ty=0))
            w.add_page(hoja)
        cuadernillos.append((w, A4L_W, A4L_H))
    return cuadernillos


# ---------- marcas ----------
def overlay_marcas(ancho, alto, con_plegado):
    """Genera el overlay de marcas. La linea de plegado (punteada central) solo
    se dibuja si con_plegado=True, lo que usamos para que aparezca UNICAMENTE en
    la cara externa (frente) de cada hoja: asi sabes por cual cara doblar y no
    te equivocas. El corte va siempre."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(ancho, alto))
    cx = ancho / 2
    if MOSTRAR_PLEGADO and con_plegado:
        c.setStrokeColor(GRIS); c.setLineWidth(0.6); c.setDash(3,3)
        c.line(cx, 0, cx, alto); c.setDash()
        c.setFillColor(GRIS); c.setFont("Helvetica", 7)
        c.drawCentredString(cx, alto-10, "doblar por aqui (cara externa)")
    if MOSTRAR_CORTE:
        c.setStrokeColor(NEGRO); c.setLineWidth(0.5)
        xi = MARGEN_CORTE_MM*mm; xd = ancho - MARGEN_CORTE_MM*mm; L = LARGO_MARCA_MM*mm
        for x in (xi, xd):
            c.line(x, alto, x, alto-L)
            c.line(x, 0, x, L)
    c.save(); buf.seek(0)
    return PdfReader(buf).pages[0]


def aplicar_marcas(writer, ancho, alto):
    buf = io.BytesIO(); writer.write(buf); buf.seek(0)
    r = PdfReader(buf)
    out = PdfWriter()
    # caras pares (0,2,4..) = frente/externa -> con linea de plegado
    # caras impares (1,3,5..) = dorso/interna -> sin linea (queda limpia)
    marca_externa = overlay_marcas(ancho, alto, con_plegado=True)
    marca_interna = overlay_marcas(ancho, alto, con_plegado=False)
    for i, pg in enumerate(r.pages):
        pg.merge_page(marca_externa if i % 2 == 0 else marca_interna)
        out.add_page(pg)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    ruta = sys.argv[1]
    print(f"Bloque: preparando {ruta} ...")
    writer_bloque, aw, ah = preparar_bloque(ruta)
    print(f"  pagina A5: {aw:.0f} x {ah:.0f} pt")

    print("Imponiendo cuadernillos ...")
    cuadernillos = imponer(writer_bloque, aw, ah)
    print(f"  {len(cuadernillos)} cuadernillos de {HOJAS_POR_CUADERNILLO} hojas")

    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    for i, (w, W, H) in enumerate(cuadernillos):
        w2 = aplicar_marcas(w, W, H)
        sal = os.path.join(CARPETA_SALIDA, f"signature{i}.pdf")
        with open(sal, "wb") as f:
            w2.write(f)
        print(f"  -> {sal}")
    print(f"Listo. Cuadernillos en ./{CARPETA_SALIDA}/")


if __name__ == "__main__":
    main()