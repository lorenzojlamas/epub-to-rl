// Hoja de prueba para calibrar el DÚPLEX MANUAL de una impresora simplex.
// 2 hojas físicas = 4 caras. Sirve para descubrir, sin arriesgar el pliego 1:
//   1) de qué lado sale la cara impresa (cara arriba / cara abajo),
//   2) cómo reinsertar la pila para que el DORSO caiga derecho,
//   3) que el intercalado sea correcto (el 2 detrás del 1, el 4 detrás del 3).
// Negro puro, apta impresora monocromo.  Compilar:  typst compile prueba-impresora-duplex.typ

#set page(width: 210mm, height: 297mm, margin: 0pt)
#set text(font: "Helvetica", lang: "es")

// --- Flecha grande apuntando ARRIBA, negra, dibujada (sin depender de glifos) ---
#let flecha = box(width: 40mm, height: 50mm, place(polygon(
  fill: black,
  (20mm, 0mm), (0mm, 23mm), (12mm, 23mm),
  (12mm, 50mm), (28mm, 50mm), (28mm, 23mm), (40mm, 23mm),
)))

// --- Cruces de registro en las 4 esquinas (misma posición en todas las caras:
//     miradas a contraluz tienen que coincidir si el registro es bueno) ---
#let cruz = text(size: 18pt, weight: "bold")[+]
#let cruces = {
  place(top + left,     dx: 6mm,  dy: 5mm,  cruz)
  place(top + right,    dx: -8mm, dy: 5mm,  cruz)
  place(bottom + left,  dx: 6mm,  dy: -12mm, cruz)
  place(bottom + right, dx: -8mm, dy: -12mm, cruz)
}

// --- Una cara ---
#let cara(hoja, tipo, numero, nota, verdict: none) = {
  // barra superior negra = CABEZA (borde de arriba del libro)
  place(top, rect(width: 210mm, height: 15mm, fill: black))
  place(top + center, dy: 3.5mm,
    text(fill: white, weight: "bold", size: 17pt)[CABEZA  ·  BORDE SUPERIOR])
  // barra inferior fina = PIE
  place(bottom, rect(width: 210mm, height: 9mm, fill: luma(220)))
  place(bottom + center, dy: -6.5mm,
    text(weight: "bold", size: 12pt)[PIE  ·  borde inferior])
  // estrella de referencia, siempre arriba-izquierda
  place(top + left, dx: 10mm, dy: 20mm,
    text(size: 20pt, weight: "bold")[★ esquina de referencia])
  cruces
  // bloque central, en posiciones fijas para que nada se pise
  place(top + center, dy: 33mm,  text(size: 34pt, weight: "bold")[HOJA #hoja])
  place(top + center, dy: 48mm,  flecha)
  place(top + center, dy: 101mm, text(size: 20pt, weight: "bold")[A R R I B A])
  place(top + center, dy: 117mm, text(size: 44pt, weight: "bold")[#tipo])
  place(top + center, dy: 139mm, text(size: 120pt, weight: "bold")[#numero])
  place(top + center, dy: 200mm,
    box(width: 155mm, align(center, text(size: 15pt)[#nota])))
  if verdict != none {
    place(bottom + center, dy: -14mm, verdict)
  }
}

#let panel = box(width: 178mm, inset: 7pt, stroke: 1pt + black, radius: 3pt)[
  #set text(size: 10.5pt)
  #set par(leading: 4pt)
  *CÓMO LEER EL RESULTADO* (después de imprimir las 2 hojas en dúplex manual) \
  #v(2pt)
  ✔ *Cara:* el dorso (2, 4) se imprimió sobre la cara en blanco, no encima del frente. \
  ✔ *Intercalado:* la HOJA 1 tiene *1 de un lado y 2 del otro* (no 1 y 4). Ídem HOJA 2 = 3 y 4. \
  ✔ *Volteo:* con el frente hacia vos y la flecha ARRIBA, al dar vuelta la hoja el dorso también
  queda con la flecha ARRIBA. Si sale de cabeza → reinsertá rotando la pila 180°. \
  #v(1pt)
  Cuando las tres den ✔, *anotá el gesto físico exacto* con el que reinsertaste la pila:
  ese es el volteo para tus libros (A5 = borde corto · A6 = borde largo).
]

// ---- HOJA 1 ----
#cara(1, "FRENTE", "1", "primera carilla que sale de la impresora",
  verdict: panel)
#pagebreak()

// ---- HOJA 1 dorso ----
#cara(1, "DORSO", "2", "va DETRÁS de la pág 1 · si la leés derecha, el volteo está bien")
#pagebreak()

// ---- HOJA 2 ----
#cara(2, "FRENTE", "3", "segunda carilla que sale de la impresora")
#pagebreak()

// ---- HOJA 2 dorso ----
#cara(2, "DORSO", "4", "va DETRÁS de la pág 3 · si la leés derecha, el volteo está bien")
