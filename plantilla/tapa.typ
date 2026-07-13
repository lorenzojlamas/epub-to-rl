// =====================================================================
// plantilla/tapa.typ — tapa completa: contratapa + lomo + frente
//
// Se imprime APARTE, al final: cosés los cuadernillos, medís el grosor
// real del lomo y corrés
//     python encuadernar.py tapa <carpeta> --lomo <mm>
// encuadernar.py deja config.json (con tapa.lomo_mm ya cargado) junto
// a este archivo y lo compila.
// =====================================================================

#let cfg = json("config.json")
#let T = cfg.tapa

#let lomo = T.lomo_mm * 1mm
#let pw = T.ancho_pagina_mm * 1mm      // ancho de página TERMINADA (post refilado)
#let ph = T.alto_pagina_mm * 1mm
// escala tipográfica: la tapa está dibujada para A5; en A6 acompaña
#let esc = calc.max(T.alto_pagina_mm / 210, 0.72)

#let hoja = if T.hoja == "A3" { (w: 420mm, h: 297mm) } else { (w: 297mm, h: 210mm) }
#let total-w = pw * 2 + lomo
#let ox = (hoja.w - total-w) / 2       // origen de la tapa dentro de la hoja
#let oy = (hoja.h - ph) / 2

#set page(width: hoja.w, height: hoja.h, margin: 0mm)
#set text(font: cfg.interior.fuente, fill: rgb(T.color_texto))
#set par(justify: false)

// ---------- fondo ----------
// color_fondo vacío = tapa blanca (recomendado en impresoras monocromo:
// un fondo de color sale como tramado gris y no llega a los bordes)
#if T.color_fondo != "" {
  place(dx: ox, dy: oy, block(width: total-w, height: ph, fill: rgb(T.color_fondo)))
}
#if T.imagen_fondo != "" {
  place(dx: ox, dy: oy, block(width: total-w, height: ph, clip: true,
    image(T.imagen_fondo, width: 100%, height: 100%, fit: "cover")))
}

// ---------- contratapa (izquierda) ----------
#if T.mostrar_lema_contratapa and cfg.colofon.lema_bottom != "" {
  place(dx: ox, dy: oy, block(width: pw, height: ph, inset: 16mm * esc,
    align(center + horizon,
      text(size: 11pt * esc, style: "italic", cfg.colofon.lema_bottom))))
}

// ---------- lomo ----------
#let texto-lomo = if T.lomo_texto == "auto" {
  cfg.titulo + "  ·  " + cfg.autores
} else { T.lomo_texto }
// se lee de arriba hacia abajo con el libro parado; tamaño según grosor
// la altura de línea rotada ocupa el ancho del lomo: ~1.5 pt por mm de lomo
#if texto-lomo != "" and T.lomo_mm >= 5 {
  place(dx: ox + pw, dy: oy, block(width: lomo, height: ph,
    align(center + horizon,
      rotate(90deg, reflow: true,
        text(size: calc.min(T.lomo_mm * 1.5, 11) * 1pt,
          smallcaps(texto-lomo))))))
}
// versión al pie del lomo (donde las editoriales ponen el logo)
#if cfg.version != "" and T.lomo_mm >= 5 {
  place(dx: ox + pw, dy: oy + ph - 26mm, block(width: lomo, height: 22mm,
    align(center + bottom,
      rotate(90deg, reflow: true,
        text(size: calc.min(T.lomo_mm * 1.1, 8) * 1pt,
          cfg.version)))))
}

// ---------- frente (derecha) ----------
#place(dx: ox + pw + lomo, dy: oy, block(width: pw, height: ph, inset: 15mm * esc)[
  #align(center)[
    #v(26mm * esc)
    #text(size: 22pt * esc, weight: "bold", cfg.titulo)
    #if cfg.subtitulo != "" [
      #v(2.5mm * esc)
      #text(size: 12pt * esc, style: "italic", cfg.subtitulo)
    ]
    #v(10mm * esc)
    #text(size: 13pt * esc, cfg.autores)
  ]
  #align(center + bottom, text(size: 9pt * esc)[
    #smallcaps[encuadernado a mano]
  ])
])

// ---------- marcas de plegado ----------
// Los pliegues van en los dos bordes del lomo.
#let pliegues = (ox + pw, ox + pw + lomo)
#if oy > 6mm {
  // hay aire en la hoja: marcas afuera de la tapa (no quedan impresas en ella)
  for x in pliegues {
    place(dx: x, dy: oy - 5mm, line(angle: 90deg, length: 4mm, stroke: 0.4pt))
    place(dx: x, dy: oy + ph + 1mm, line(angle: 90deg, length: 4mm, stroke: 0.4pt))
  }
  // marcas de corte en las 4 esquinas de la tapa
  for esquina in ((ox, oy), (ox + total-w, oy), (ox, oy + ph), (ox + total-w, oy + ph)) {
    let (cx, cy) = esquina
    place(dx: cx - 5mm, dy: cy, line(angle: 0deg, length: 4mm, stroke: 0.4pt))
    place(dx: cx + 1mm, dy: cy, line(angle: 0deg, length: 4mm, stroke: 0.4pt))
    place(dx: cx, dy: cy - 5mm, line(angle: 90deg, length: 4mm, stroke: 0.4pt))
    place(dx: cx, dy: cy + 1mm, line(angle: 90deg, length: 4mm, stroke: 0.4pt))
  }
  // etiqueta con el dato del lomo, fuera del área de la tapa
  place(dx: ox, dy: oy - 10mm,
    text(size: 7pt, fill: luma(35%))[tapa · lomo #T.lomo_mm mm · imprimir al 100% (sin escalar)])
} else {
  // La tapa ocupa toda la hoja: marcas punteadas muy sutiles que
  // desaparecen solas — las de plegado quedan escondidas en la doblez
  // y las de corte se van con el refile de los costados.
  let sutil = (paint: luma(60%), thickness: 0.3pt, dash: "loosely-dotted")
  for x in pliegues {
    place(dx: x, dy: oy, line(angle: 90deg, length: ph, stroke: sutil))
  }
  for x in (ox, ox + total-w) {
    place(dx: x, dy: oy, line(angle: 90deg, length: ph, stroke: sutil))
  }
}
