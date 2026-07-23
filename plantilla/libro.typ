// =====================================================================
// plantilla/libro.typ — interior del libro (A5, para coser a mano)
//
// encuadernar.py arma build/main.typ reemplazando el marcador CUERPO
// (entre llaves dobles, al final de este archivo) por la salida de
// pandoc, y deja config.json (el libro.yaml ya fusionado) al lado.
// Editá esta plantilla libremente: es la cara tipográfica del libro.
// =====================================================================

#let cfg = json("config.json")
#let I = cfg.interior
#let nivel-cap = I.nivel_capitulo
// Nivel de encabezado que lista el índice. Por defecto, el del capítulo;
// una Biblia (libro = h1, capítulos = h2) lo pone en 2 para listar capítulos.
#let indice-nivel = I.at("indice_nivel", default: nivel-cap)

// Tamaño de página según el formato del libro (A5 o A6, lo fija
// encuadernar.py en config.json). `esc` escala los blancos verticales
// y los cuerpos de título, que están dibujados pensando en A5.
#let pag-ancho = I.pagina_ancho_mm * 1mm
#let pag-alto = I.pagina_alto_mm * 1mm
#let esc = I.pagina_alto_mm / 210

// El refile del borde delantero se come imposicion.margen_corte_mm:
// se compensa acá, así margen_exterior_mm es el margen que queda en el
// libro TERMINADO (ya refilado), igual que el interior.
#let m-interior = I.margen_interior_mm * 1mm
#let m-exterior = (I.margen_exterior_mm + cfg.imposicion.margen_corte_mm) * 1mm
#let ancho-texto = pag-ancho - m-interior - m-exterior

// tipografía de servicio (encabezado corrido, folios, notas al pie):
// proporcional al cuerpo del texto
#let t-servicio = I.tamano * 0.81pt
// escala para los cuerpos de display (títulos, portada, colofón): baja
// menos que la página para que en A6 no queden ilegibles
#let esc-t = calc.max(esc, 0.78)

// ---------- shims para la salida de pandoc ----------
#let horizontalrule = align(center, block(above: 1.4em, below: 1.4em,
  text(size: 9pt * esc-t, fill: luma(45%))[· · ·]))

// ---------- página ----------
#let en-cuerpo = state("en-cuerpo", false)

#set page(
  width: pag-ancho,
  height: pag-alto,
  binding: left,
  margin: (
    inside:  m-interior,
    outside: m-exterior,
    top:     I.margen_superior_mm * 1mm,
    bottom:  I.margen_inferior_mm * 1mm,
  ),
  // Encabezado corrido: solo en el cuerpo, nunca en la apertura de capítulo.
  // Verso (par):  folio … título del libro   /   Recto (impar): capítulo … folio
  header: context {
    if not en-cuerpo.get() { return }
    let pag = here().page()
    let caps-aca = query(heading.where(level: nivel-cap))
      .filter(h => h.location().page() == pag)
    if caps-aca.len() > 0 { return }
    let antes = query(selector(heading.where(level: nivel-cap)).before(here()))
    if antes.len() == 0 { return }
    let n = counter(page).get().first()
    set text(size: t-servicio, fill: luma(25%))
    if calc.even(n) [
      #n #h(1fr) #emph(cfg.titulo)
    ] else [
      // el capítulo, si entra en una línea; si el título es larguísimo
      // o viene partido con salto de línea, mejor el del libro
      #let cap = emph(antes.last().body)
      #let medida = measure(text(size: t-servicio, cap))
      #if medida.width > 0.75 * ancho-texto or medida.height > t-servicio * 1.45 {
        cap = emph(cfg.titulo)
      }
      #cap #h(1fr) #n
    ]
  },
  // Folio centrado abajo solo en la apertura de capítulo
  footer: context {
    if not en-cuerpo.get() { return }
    let pag = here().page()
    let caps-aca = query(heading.where(level: nivel-cap))
      .filter(h => h.location().page() == pag)
    if caps-aca.len() == 0 { return }
    align(center, text(size: t-servicio, fill: luma(25%))[#counter(page).get().first()])
  },
)

// ---------- texto ----------
#set text(font: I.fuente, size: I.tamano * 1pt, lang: cfg.idioma)
#set par(
  justify: true,
  leading: 0.68em,
  spacing: 0.68em,
  first-line-indent: (amount: 1.2em, all: false),
)

// notas al pie: la razón de ser de todo esto — al PIE, como corresponde
#set footnote.entry(indent: 0em, gap: 0.55em)
#show footnote.entry: set text(size: t-servicio)
#show footnote.entry: set par(leading: 0.5em, first-line-indent: 0em)

// código
#show raw: set text(font: "DejaVu Sans Mono", size: 0.82em)
#show raw.where(block: true): it => block(
  width: 100%, inset: 6pt, fill: luma(96%), radius: 2pt, breakable: true, it)

// imágenes del EPUB: nunca más anchas que la caja de texto
#show image: it => layout(caja => {
  let medida = measure(it)
  if medida.width <= caja.width { it } else {
    image(it.source, width: caja.width, alt: it.alt)
  }
})

// títulos
#set heading(numbering: none)
#show heading: set text(hyphenate: false)
#show heading.where(level: nivel-cap): it => {
  pagebreak(to: "odd", weak: true)
  v(24mm * esc)
  set par(justify: false, first-line-indent: 0em)
  set text(size: 17pt * esc-t, weight: "bold")
  it.body
  v(9mm * esc)
}
#show heading.where(level: nivel-cap + 1): set text(size: 12.5pt * esc-t)
#show heading.where(level: nivel-cap + 1): set block(above: 1.6em, below: 0.9em)

// Frontispicio: un heading más profundo que el nivel de capítulo que
// aparece ANTES del primer capítulo es un título de presentación (p. ej.
// el encabezamiento formal de una encíclica) — página propia, centrado.
#show heading: it => {
  if it.level <= nivel-cap { it } else {
    context {
      let caps-antes = query(selector(heading.where(level: nivel-cap)).before(here()))
      if caps-antes.len() > 0 { it } else {
        v(52mm * esc)
        set par(justify: false, first-line-indent: 0em)
        set text(hyphenate: false)
        align(center, block(width: 88%,
          text(size: 12.5pt * esc-t, weight: "regular", tracking: 0.5pt, smallcaps(it.body))))
      }
    }
  }
}

// ---------- piezas de los preliminares ----------
#let separador = text(size: 9pt * esc-t, fill: luma(45%))[· · ·]

#let pagina-portadilla = {
  set par(justify: false, first-line-indent: 0em)
  v(58mm * esc)
  align(center, text(size: 13pt * esc-t, tracking: 1.8pt, smallcaps(cfg.titulo)))
  pagebreak()
}

#let pagina-portada = {
  set par(justify: false, first-line-indent: 0em)
  v(46mm * esc)
  align(center)[
    #text(size: 21pt * esc-t, weight: "bold", cfg.titulo)
    #if cfg.subtitulo != "" [
      #v(2mm * esc)
      #text(size: 12pt * esc-t, style: "italic", cfg.subtitulo)
    ]
    #v(9mm * esc)
    #text(size: 12pt * esc-t, cfg.autores)
  ]
  v(1fr)
  align(center, text(size: t-servicio, fill: luma(25%))[
    Impreso y encuadernado a mano \
    #cfg.colofon.ciudad
  ])
  v(4mm * esc)
  pagebreak()
}

#let pagina-colofon = {
  set par(justify: false, first-line-indent: 0em)
  let C = cfg.colofon
  v(52mm * esc)
  align(center)[
    #separador
    #v(9mm * esc)
    #for lema in C.lema_top [
      #text(size: 12.5pt * esc-t, style: "italic", lema) \
    ]
    #v(7mm * esc)
    #separador
    #v(9mm * esc)
    #text(size: 11.5pt * esc-t, weight: "bold", cfg.titulo) \
    #v(1mm * esc)
    #text(size: 10pt * esc-t, fill: luma(20%), cfg.autores)
    #v(8mm * esc)
    #text(size: 9pt * esc-t, fill: luma(30%))[
      Impreso y encuadernado a mano por #C.encuadernador \
      #C.ciudad — #C.fecha \
      #cfg.version \
      #C.detalle
    ]
    #v(9mm * esc)
    #separador
    #v(9mm * esc)
    #text(size: 12.5pt * esc-t, style: "italic", C.lema_bottom)
  ]
}

#let pagina-dedicatoria = {
  set par(justify: false, first-line-indent: 0em)
  v(64mm * esc)
  align(center, block(width: 80%,
    for (i, linea) in cfg.dedicatoria.split("\n").enumerate() {
      if i > 0 { linebreak() }
      text(size: 11.5pt * esc-t, style: "italic", linea)
    }
  ))
}

// ---------- armado de los preliminares ----------
// p1 portadilla · p2 blanca · p3 portada · p4 colofón (si "inicio")
// p5 dedicatoria · cuerpo arranca en el impar siguiente
#if I.portadilla { pagina-portadilla }          // p1, deja en p2
#if I.portada {
  if I.portadilla { pagebreak() }               // p2 en blanco → p3
  pagina-portada                                 // p3, deja en p4
}
#if cfg.colofon.posicion == "inicio" {
  pagina-colofon
  pagebreak()
}
#if cfg.dedicatoria.trim() != "" {
  pagebreak(to: "odd", weak: true)              // dedicatoria siempre en recto
  pagina-dedicatoria
  pagebreak()
}
#if I.indice {
  pagebreak(to: "odd", weak: true)
  {
    set par(justify: false, first-line-indent: 0em)
    v(14mm * esc)
    text(size: 15pt * esc-t, weight: "bold")[Índice]
    v(7mm * esc)
    set text(size: 0.95em)
    // títulos partidos que el filtro fusionó con salto de línea:
    // en el índice van en una sola línea, separados por un punto medio
    show linebreak: h(0.5em) + [·] + h(0.5em)
    outline(title: none, target: heading.where(level: indice-nivel))
  }
  pagebreak()
}

// ---------- cuerpo ----------
// Arrancar el cuerpo en un recto FÍSICO y ahí sí reiniciar el folio en 1,
// para que la paridad lógica (folio) coincida con la física (recto/verso)
// y los márgenes espejados queden del lado correcto del cosido.
#pagebreak(to: "odd", weak: true)
#counter(page).update(1)
#en-cuerpo.update(true)

{{CUERPO}}

// ---------- colofón al final (opcional) ----------
#if cfg.colofon.posicion == "final" {
  en-cuerpo.update(false)
  pagebreak(to: "even", weak: true)
  pagina-colofon
}
