#!/usr/bin/env python3
# =====================================================================
# biblia.py — arma un EPUB de UN libro de la Biblia bajando sus
# capítulos desde bible.com (YouVersion) y produce un .epub que
# encuadernar.py sabe imprimir.
#
# Pensado para traducciones de DOMINIO PÚBLICO. Por defecto usa la
# Reina-Valera 1909 (versionId 1718, abreviatura RVR09), que la propia
# fuente marca como dominio público. El script LEE ese aviso de
# copyright en cada capítulo y se planta si no dice dominio público,
# salvo que pases --forzar. La idea es que la herramienta misma no sirva
# para reproducir traducciones con derechos.
#
# Uso:
#   python biblia.py --lista                 # códigos de los 66 libros
#   python biblia.py GEN                      # Génesis entero -> libros/genesis/
#   python biblia.py GEN --capitulos 1-11     # solo esos capítulos
#   python biblia.py SAL --salida libros/salmos --pausa 1.5
#
# Después:
#   python encuadernar.py libro libros/genesis/
#
# Solo usa la stdlib (urllib, html.parser, zipfile): nada que instalar,
# todo auditable.
# =====================================================================

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# --- Canon protestante: (código USFM, nombre en español, nº de capítulos)
# El nombre real que se imprime lo toma de la propia fuente; este de acá
# es el fallback y lo que muestra --lista.
LIBROS = [
    ("GEN", "Génesis", 50),        ("EXO", "Éxodo", 40),
    ("LEV", "Levítico", 27),       ("NUM", "Números", 36),
    ("DEU", "Deuteronomio", 34),   ("JOS", "Josué", 24),
    ("JDG", "Jueces", 21),         ("RUT", "Rut", 4),
    ("1SA", "1 Samuel", 31),       ("2SA", "2 Samuel", 24),
    ("1KI", "1 Reyes", 22),        ("2KI", "2 Reyes", 25),
    ("1CH", "1 Crónicas", 29),     ("2CH", "2 Crónicas", 36),
    ("EZR", "Esdras", 10),         ("NEH", "Nehemías", 13),
    ("EST", "Ester", 10),          ("JOB", "Job", 42),
    ("PSA", "Salmos", 150),        ("PRO", "Proverbios", 31),
    ("ECC", "Eclesiastés", 12),    ("SNG", "Cantares", 8),
    ("ISA", "Isaías", 66),         ("JER", "Jeremías", 52),
    ("LAM", "Lamentaciones", 5),   ("EZK", "Ezequiel", 48),
    ("DAN", "Daniel", 12),         ("HOS", "Oseas", 14),
    ("JOL", "Joel", 3),            ("AMO", "Amós", 9),
    ("OBA", "Abdías", 1),          ("JON", "Jonás", 4),
    ("MIC", "Miqueas", 7),         ("NAM", "Nahúm", 3),
    ("HAB", "Habacuc", 3),         ("ZEP", "Sofonías", 3),
    ("HAG", "Hageo", 2),           ("ZEC", "Zacarías", 14),
    ("MAL", "Malaquías", 4),       ("MAT", "Mateo", 28),
    ("MRK", "Marcos", 16),         ("LUK", "Lucas", 24),
    ("JHN", "Juan", 21),           ("ACT", "Hechos", 28),
    ("ROM", "Romanos", 16),        ("1CO", "1 Corintios", 16),
    ("2CO", "2 Corintios", 13),    ("GAL", "Gálatas", 6),
    ("EPH", "Efesios", 6),         ("PHP", "Filipenses", 4),
    ("COL", "Colosenses", 4),      ("1TH", "1 Tesalonicenses", 5),
    ("2TH", "2 Tesalonicenses", 3),("1TI", "1 Timoteo", 6),
    ("2TI", "2 Timoteo", 4),       ("TIT", "Tito", 3),
    ("PHM", "Filemón", 1),         ("HEB", "Hebreos", 13),
    ("JAS", "Santiago", 5),        ("1PE", "1 Pedro", 5),
    ("2PE", "2 Pedro", 3),         ("1JN", "1 Juan", 5),
    ("2JN", "2 Juan", 1),          ("3JN", "3 Juan", 1),
    ("JUD", "Judas", 1),           ("REV", "Apocalipsis", 22),
]
CAPS = {u: (nombre, n) for u, nombre, n in LIBROS}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


# =====================================================================
# Descarga (con caché en disco: no le pega dos veces al mismo capítulo)
# =====================================================================
def bajar_html(url, cache_path, pausa):
    """Devuelve el HTML del capítulo. Si está cacheado, lee del disco."""
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8"), True

    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    })
    ult_error = None
    for intento in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", "replace")
            # La página anti-bot ("Client Challenge") no trae __NEXT_DATA__.
            if "__NEXT_DATA__" in html:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(html, encoding="utf-8")
                if pausa:
                    time.sleep(pausa)
                return html, False
            ult_error = "la respuesta no trae contenido (¿challenge anti-bot?)"
        except Exception as e:  # noqa: BLE001
            ult_error = str(e)
        time.sleep(1.5 * intento)
    raise RuntimeError(f"No pude bajar {url}: {ult_error}")


def extraer_next_data(html):
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.S)
    if not m:
        raise RuntimeError("no encontré __NEXT_DATA__ en el HTML")
    return json.loads(m.group(1))


# =====================================================================
# Parser del HTML USX de YouVersion -> XHTML limpio
# =====================================================================
class _Nodo:
    __slots__ = ("tag", "clases", "hijos")

    def __init__(self, tag, clases):
        self.tag = tag
        self.clases = clases
        self.hijos = []


class _Arbol(__import__("html.parser", fromlist=["HTMLParser"]).HTMLParser):
    """Arma un árbol liviano del HTML del capítulo."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = _Nodo("root", [])
        self.pila = [self.raiz]

    def handle_starttag(self, tag, attrs):
        clases = dict(attrs).get("class", "").split()
        n = _Nodo(tag, clases)
        self.pila[-1].hijos.append(n)
        self.pila.append(n)

    def handle_startendtag(self, tag, attrs):
        clases = dict(attrs).get("class", "").split()
        self.pila[-1].hijos.append(_Nodo(tag, clases))

    def handle_endtag(self, tag):
        for i in range(len(self.pila) - 1, 0, -1):
            if self.pila[i].tag == tag:
                del self.pila[i:]
                return

    def handle_data(self, data):
        self.pila[-1].hijos.append(data)


def _clase0(n):
    return n.clases[0] if n.clases else ""


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _norm(s):
    return re.sub(r"\s+", " ", s)


def _texto_plano(n):
    out = []
    def rec(x):
        if isinstance(x, str):
            out.append(x)
        else:
            for h in x.hijos:
                rec(h)
    rec(n)
    return _norm("".join(out))


def _buscar(n, pred):
    if isinstance(n, str):
        return None
    if pred(n):
        return n
    for h in n.hijos:
        r = _buscar(h, pred)
        if r is not None:
            return r
    return None


def _inline(n, notas, incluir_notas):
    """Renderiza contenido en línea de un versículo (texto, nº, itálicas, notas)."""
    if isinstance(n, str):
        return _esc(_norm(n))
    c = _clase0(n)
    if c == "note":
        if not incluir_notas:
            return ""
        idx = len(notas) + 1
        txt = _texto_plano(n).strip().lstrip("#").strip()
        notas.append(txt)
        # id con sufijo "_footnote-N": el dialecto que filtro.lua reconoce
        # y convierte en #footnote real de Typst.
        return (f'<a id="nota_ref-{idx}" href="#nota_footnote-{idx}">'
                f'<sup>{idx}</sup></a>')
    inner = "".join(_inline(h, notas, incluir_notas) for h in n.hijos)
    if c == "label":            # número de versículo
        return f'<sup class="vn">{inner}</sup> '
    if c == "add":              # palabra añadida por el traductor -> itálica
        return f"<em>{inner}</em>"
    return inner                # content, verse, ref, xta, body... transparentes


def _sin_enum(txt):
    """Quita el enumerador que la fuente antepone a los títulos de sección
    ("1 El primer pecado." -> "El primer pecado."). Ese número reinicia en
    cada capítulo y NO es parte del título: dejarlo hace que la sección
    parezca un capítulo/subcapítulo numerado (el 100% de los títulos de la
    RVR1909 en esta fuente vienen así)."""
    return re.sub(r"^\d+\s+", "", txt)


# clases de bloque que son títulos y a qué heading van. Todo lo que NO es
# capítulo va a h3/h4: así el h2 queda reservado para el capítulo (y el índice,
# que lista h2, muestra solo los capítulos).
TITULOS = {"s": "h3", "s1": "h3", "s2": "h4",
           "ms": "h3", "ms1": "h3", "mr": "h4",
           "mt": "h3", "mt1": "h3"}


def _continua_titulo(prev, cur):
    """¿'cur' es continuación del fragmento de título 'prev'? La fuente parte
    un mismo título en varios <div class='s'> numerados. Es continuación si el
    anterior no cierra oración (. ! ? : ;) o si el fragmento arranca en
    minúscula. Ej.: 'José se da á conocer' + 'á sus hermanos.' -> uno solo;
    'El primer pecado.' + 'La primera promesa.' -> dos títulos distintos."""
    return (not prev.rstrip().endswith((".", "!", "?", ":", ";"))
            or cur[:1].islower())


def render_capitulo(chapter_node, numero, titulo_cap, notas, incluir_notas):
    """Convierte el <div class='chapter'> en XHTML: título + párrafos.
    Reensambla los títulos de sección que la fuente parte en fragmentos.
    'titulo_cap' es el título de capítulo curado (o None): va como subtítulo
    bajo el número."""
    if titulo_cap:
        # El título va DENTRO del <h2> (número + salto + título): así entra al
        # índice del PDF. La plantilla convierte el salto de línea en " · " en
        # el índice y lo respeta como segunda línea en el cuerpo.
        out = [f"<h2>{numero}<br/>{_esc(titulo_cap)}</h2>"]
    else:
        out = [f"<h2>{numero}</h2>"]
    poesia = []
    titulo_buf = []
    titulo_tag = "h3"

    def flush_poesia():
        if poesia:
            out.append('<p class="poesia">' + "<br/>".join(poesia) + "</p>")
            poesia.clear()

    def flush_titulo():
        if titulo_buf:
            out.append(f"<{titulo_tag}>{_esc(' '.join(titulo_buf))}</{titulo_tag}>")
            titulo_buf.clear()

    for hijo in chapter_node.hijos:
        if isinstance(hijo, str):
            continue
        c = _clase0(hijo)
        if c == "label":                       # nº de capítulo: ya lo pusimos
            continue
        if c in TITULOS:
            flush_poesia()
            txt = _sin_enum(_texto_plano(hijo).strip())
            if not txt:
                continue
            if titulo_buf and _continua_titulo(titulo_buf[-1], txt):
                titulo_buf.append(txt)         # continuación del mismo título
            else:
                flush_titulo()                 # empieza un título nuevo
                titulo_tag = TITULOS[c]
                titulo_buf.append(txt)
            continue
        # cualquier otro bloque cierra el título que se venía acumulando
        flush_titulo()
        if c == "d":                           # título descriptivo (encabezado de salmo)
            flush_poesia()
            txt = _texto_plano(hijo).strip()
            if txt:
                out.append(f'<p class="desc"><em>{_esc(txt)}</em></p>')
            continue
        if c.startswith("q"):                  # poesía: acumular líneas
            linea = "".join(_inline(h, notas, incluir_notas)
                            for h in hijo.hijos).strip()
            poesia.append(linea)
            continue
        # párrafo normal (p, m, mi, pi, li, nb, ...)
        flush_poesia()
        inner = "".join(_inline(h, notas, incluir_notas)
                        for h in hijo.hijos).strip()
        if inner:
            out.append(f"<p>{inner}</p>")
    flush_titulo()
    flush_poesia()
    return "\n".join(out)


# =====================================================================
# Empaquetado del EPUB (stdlib zipfile, EPUB3 mínimo y válido)
# =====================================================================
def escribir_epub(destino, titulo_display, nombre_libro, idioma, autor,
                  derechos, capitulos, uid):
    """Empaqueta el EPUB con UN archivo XHTML por capítulo y un índice
    (nav + ncx) que lista cada capítulo, para que el lector pueda navegar
    (antes iba todo en un solo archivo con una única entrada de índice).

    capitulos: lista de (numero:int, titulo:str|None, cuerpo_html:str).
    """
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    td = _esc(titulo_display)
    nl = _esc(nombre_libro)

    def archivo(num):
        return f"chap-{num:03d}.xhtml"

    def etiqueta(num, titulo):
        # rótulo del índice: "Génesis 17 · El pacto y la circuncisión"
        return _esc(f"{nombre_libro} {num}" + (f" · {titulo}" if titulo else ""))

    # --- un XHTML por capítulo (el primero lleva además el <h1> del libro)
    paginas = {}
    for i, (num, titulo, cuerpo) in enumerate(capitulos):
        h1 = f"<h1>{td}</h1>\n" if i == 0 else ""
        paginas[archivo(num)] = (
            f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" '
            f'xml:lang="{idioma}" lang="{idioma}">\n'
            f'<head><meta charset="utf-8"/>'
            f'<title>{etiqueta(num, titulo)}</title></head>\n'
            f'<body>\n{h1}{cuerpo}\n</body>\n</html>\n')

    # --- manifest, spine, índice: una entrada por capítulo, en orden
    items, spine, navlis, navpoints = [], [], [], []
    for orden, (num, titulo, _) in enumerate(capitulos, 1):
        af = archivo(num)
        et = etiqueta(num, titulo)
        items.append(f'    <item id="c{num}" href="{af}" '
                     f'media-type="application/xhtml+xml"/>')
        spine.append(f'    <itemref idref="c{num}"/>')
        navlis.append(f'        <li><a href="{af}">{et}</a></li>')
        navpoints.append(
            f'  <navPoint id="np{num}" playOrder="{orden}">'
            f'<navLabel><text>{et}</text></navLabel>'
            f'<content src="{af}"/></navPoint>')
    primer = archivo(capitulos[0][0])

    opf = (f'<?xml version="1.0" encoding="utf-8"?>\n'
           f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
           f'unique-identifier="bookid">\n'
           f'  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
           f'    <dc:identifier id="bookid">urn:uuid:{uid}</dc:identifier>\n'
           f'    <dc:title>{td}</dc:title>\n'
           f'    <dc:language>{idioma}</dc:language>\n'
           f'    <dc:creator>{_esc(autor)}</dc:creator>\n'
           f'    <dc:rights>{_esc(derechos)}</dc:rights>\n'
           f'    <meta property="dcterms:modified">{ahora}</meta>\n'
           f'  </metadata>\n'
           f'  <manifest>\n'
           f'    <item id="nav" href="nav.xhtml" '
           f'media-type="application/xhtml+xml" properties="nav"/>\n'
           f'    <item id="ncx" href="toc.ncx" '
           f'media-type="application/x-dtbncx+xml"/>\n'
           + "\n".join(items) + "\n"
           f'  </manifest>\n'
           f'  <spine toc="ncx">\n'
           + "\n".join(spine) + "\n"
           f'  </spine>\n'
           f'</package>\n')

    nav = (f'<?xml version="1.0" encoding="utf-8"?>\n'
           f'<html xmlns="http://www.w3.org/1999/xhtml" '
           f'xmlns:epub="http://www.idpf.org/2007/ops" lang="{idioma}">\n'
           f'<head><meta charset="utf-8"/><title>{td}</title></head>\n'
           f'<body>\n<nav epub:type="toc" id="toc">\n'
           f'    <ol>\n'
           f'      <li><a href="{primer}">{td}</a>\n'
           f'      <ol>\n'
           + "\n".join(navlis) + "\n"
           f'      </ol></li>\n'
           f'    </ol>\n'
           f'</nav>\n</body>\n</html>\n')

    ncx = (f'<?xml version="1.0" encoding="utf-8"?>\n'
           f'<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
           f'<head><meta name="dtb:uid" content="urn:uuid:{uid}"/></head>\n'
           f'<docTitle><text>{td}</text></docTitle>\n'
           f'<navMap>\n'
           + "\n".join(navpoints) + "\n"
           f'</navMap>\n</ncx>\n')

    container = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<container version="1.0" '
                 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                 '  <rootfiles>\n'
                 '    <rootfile full-path="OEBPS/content.opf" '
                 'media-type="application/oebps-package+xml"/>\n'
                 '  </rootfiles>\n</container>\n')

    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as z:
        # mimetype: primero y sin comprimir (lo exige la spec del EPUB)
        z.writestr("mimetype", "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        base = [
            ("META-INF/container.xml", container),
            ("OEBPS/content.opf", opf),
            ("OEBPS/nav.xhtml", nav),
            ("OEBPS/toc.ncx", ncx),
        ]
        for nombre, data in base:
            z.writestr(nombre, data, compress_type=zipfile.ZIP_DEFLATED)
        for nombre, data in paginas.items():
            z.writestr(f"OEBPS/{nombre}", data,
                       compress_type=zipfile.ZIP_DEFLATED)


# =====================================================================
# Utilidades varias
# =====================================================================
def slug(nombre):
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "libro"


def parse_capitulos(spec, total):
    """'1-11' / '3' / '1,3,5-7' -> lista ordenada. None -> todos."""
    if not spec:
        return list(range(1, total + 1))
    caps = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if "-" in tok:
            a, b = tok.split("-", 1)
            caps.update(range(int(a), int(b) + 1))
        elif tok:
            caps.add(int(tok))
    return sorted(c for c in caps if 1 <= c <= total)


def es_dominio_publico(txt):
    t = (txt or "").lower()
    return "dominio p" in t or "public domain" in t or "dominio publico" in t


def cargar_titulos(codigo):
    """Títulos de capítulo curados (editables) desde titulos/<CODE>.yaml,
    junto a este script. Devuelve {int: str}; vacío si no hay archivo."""
    ruta = Path(__file__).resolve().parent / "titulos" / f"{codigo}.yaml"
    if not ruta.exists():
        return {}
    try:
        import yaml
    except ImportError:
        print("  (aviso: PyYAML no está instalado; ignoro los títulos curados)")
        return {}
    data = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return {int(k): str(v).strip() for k, v in data.items() if str(v).strip()}


def escribir_libro_yaml(carpeta, titulo, subtitulo, autores, version):
    """Deja un libro.yaml mínimo para que encuadernar.py funcione directo.

    La versión queda visible en TODAS las superficies del libro terminado:
    subtítulo de la portada, byline/lomo (autores) y colofón (version)."""
    yaml_path = carpeta / "libro.yaml"
    if yaml_path.exists():
        return  # no piso ediciones del usuario
    yaml_path.write_text(
        f'titulo: "{titulo}"\n'
        f'subtitulo: "{subtitulo}"\n'
        f'autores: "{autores}"\n'
        f'idioma: es\n'
        f'version: "{version}"\n'
        f'\n'
        f'interior:\n'
        f'  indice: true          # índice con los capítulos y su página\n'
        f'  indice_nivel: 2        # los capítulos son h2 (el libro es el h1)\n',
        encoding="utf-8")


# =====================================================================
# Orquestación
# =====================================================================
def armar(args):
    codigo = args.libro.upper()
    if codigo not in CAPS:
        sys.exit(f"Código de libro desconocido: {codigo}. Mirá: python biblia.py --lista")
    nombre_tabla, total_caps = CAPS[codigo]
    caps = parse_capitulos(args.capitulos, total_caps)
    if not caps:
        sys.exit("El rango de capítulos quedó vacío.")

    # Carpeta por defecto prefijada con la versión: así conviven en libros/
    # varias versiones del mismo libro sin pisarse (RVR09-genesis, etc.).
    salida = (Path(args.salida) if args.salida
              else Path("libros") / f"{args.abrev}-{slug(nombre_tabla)}")
    cache = salida / ".cache"

    def url_de(ch):
        return f"https://www.bible.com/es/bible/{args.version}/{codigo}.{ch}.{args.abrev}"

    # --- primer capítulo: nombre real, aviso de copyright y guardarraíl
    html, cacheado = bajar_html(url_de(caps[0]), cache / f"{codigo}.{caps[0]}.html",
                                args.pausa)
    data = extraer_next_data(html)
    pp = data["props"]["pageProps"]
    info = pp["chapterInfo"]
    ver = pp.get("versionData", {})

    derechos = ((info.get("copyright") or {}).get("text")
                or (ver.get("copyright_short") or {}).get("text") or "").strip()
    if not es_dominio_publico(derechos) and not args.forzar:
        sys.exit(
            "\n⛔  La fuente NO declara dominio público para esta versión:\n"
            f"    «{derechos or '(sin aviso de copyright)'}»\n\n"
            "    Esta herramienta es para traducciones de dominio público.\n"
            "    Si estás seguro de que podés reproducirla, repetí con --forzar.\n")

    # nombre del libro tal como lo da la fuente (Génesis, no GEN)
    human = ((info.get("reference") or {}).get("human") or "").strip()
    nombre = re.sub(r"\s*\d+\s*$", "", human) or nombre_tabla
    version_titulo = ver.get("local_title") or args.abrev

    print(f"Libro:     {nombre}  ({codigo})")
    print(f"Versión:   {version_titulo}  (id {args.version})")
    print(f"Derechos:  {derechos}")
    print(f"Capítulos: {len(caps)}  ({caps[0]}–{caps[-1]})")
    print(f"Salida:    {salida}\n")

    incluir_notas = args.notas == "pie"
    titulos = {} if args.sin_titulos else cargar_titulos(codigo)
    if titulos:
        print(f"Títulos:   tabla curada titulos/{codigo}.yaml ({len(titulos)} capítulos)\n")
    notas = []              # acumulador global (ids únicos en todo el EPUB)
    capitulos = []          # (numero, titulo, cuerpo_html) — un archivo por capítulo
    for ch in caps:
        if ch == caps[0]:
            h = html
        else:
            h, cacheado = bajar_html(url_de(ch), cache / f"{codigo}.{ch}.html",
                                     args.pausa)
        cont = extraer_next_data(h)["props"]["pageProps"]["chapterInfo"]["content"]
        arbol = _Arbol()
        arbol.feed(cont)
        chapter = _buscar(arbol.raiz, lambda x: "chapter" in x.clases)
        if chapter is None:
            print(f"  ⚠  capítulo {ch}: no encontré el bloque de texto, lo salto")
            continue
        antes = len(notas)
        cuerpo_cap = render_capitulo(chapter, ch, titulos.get(ch), notas, incluir_notas)
        # Las notas de ESTE capítulo van al pie de SU archivo (así el link
        # resuelve dentro del mismo documento), con id global para que
        # pandoc no las colapse al concatenar el EPUB.
        nuevas = notas[antes:]
        if incluir_notas and nuevas:
            partes = ["<hr/>"]
            for j, txt in enumerate(nuevas):
                idx = antes + j + 1
                partes.append(f'<div id="nota_footnote-{idx}"><p>'
                              f'<a href="#nota_ref-{idx}">{idx}.</a> '
                              f'{_esc(txt)}</p></div>')
            cuerpo_cap += "\n" + "\n".join(partes)
        capitulos.append((ch, titulos.get(ch), cuerpo_cap))
        marca = "·" if cacheado else "▼"
        print(f"  {marca} {nombre} {ch}")

    if not capitulos:
        sys.exit("No se pudo armar ningún capítulo.")

    # La versión va incrustada en el nombre del archivo, en el título del
    # EPUB (lo que se ve en la biblioteca de un lector) y en el <h1> del
    # cuerpo (y de ahí al encabezado corrido de cada página): se comparan
    # versiones, no puede quedar ninguna duda de cuál es cuál.
    titulo_epub = f"{nombre} · {args.abrev}"
    uid = f"biblia-{args.version}-{codigo}-{caps[0]}-{caps[-1]}"
    epub = salida / f"{args.abrev}-{slug(nombre)}.epub"
    escribir_epub(epub, titulo_epub, nombre, "es", version_titulo, derechos,
                  capitulos, uid)
    escribir_libro_yaml(salida, nombre, version_titulo, args.abrev, args.abrev)

    print(f"\n✔  {epub}")
    print(f"   Ahora: python encuadernar.py libro {salida}/")


def main():
    p = argparse.ArgumentParser(
        description="Arma un EPUB de un libro de la Biblia desde bible.com "
                    "(traducciones de dominio público).")
    p.add_argument("libro", nargs="?", help="código USFM del libro (GEN, EXO, SAL...)")
    p.add_argument("--capitulos", help="rango: '1-11', '3', '1,3,5-7' (default: todos)")
    p.add_argument("--salida", help="carpeta destino (default: libros/<libro>)")
    p.add_argument("--version", default="1718", help="versionId de bible.com (default 1718 = RVR09)")
    p.add_argument("--abrev", default="RVR09", help="abreviatura de la versión (default RVR09)")
    p.add_argument("--notas", choices=["omitir", "pie"], default="omitir",
                   help="referencias cruzadas: omitir (default) o convertir en notas al pie")
    p.add_argument("--pausa", type=float, default=1.5,
                   help="segundos entre descargas (cortesía con el sitio; default 1.0)")
    p.add_argument("--forzar", action="store_true",
                   help="seguir aunque la fuente no declare dominio público")
    p.add_argument("--sin-titulos", action="store_true",
                   help="no usar la tabla curada de títulos de capítulo (titulos/<CODE>.yaml)")
    p.add_argument("--lista", action="store_true", help="lista los códigos de libro y sale")
    args = p.parse_args()

    if args.lista:
        for u, nombre, n in LIBROS:
            print(f"  {u:4}  {nombre:18} {n:>3} cap.")
        return
    if not args.libro:
        p.error("falta el código del libro (o usá --lista)")
    armar(args)


if __name__ == "__main__":
    main()
