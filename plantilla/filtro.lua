-- =====================================================================
-- plantilla/filtro.lua — curaduría del EPUB antes de tipografiar
--
--  · Notas tipo endnote (bloques al final del capítulo, con links de
--    ida y vuelta) -> notas al pie REALES (#footnote de Typst).
--    Soporta los dos dialectos vistos hasta ahora: Divs `..._footnote-N`
--    (Sigil/popup) y párrafos `[N] texto` con ancla `_ftnN`/`_ednN`
--    (los EPUB que vienen de Word, p. ej. los del Vaticano).
--  · Divs de capítulo desarmados: los saltos de página por capítulo
--    de la plantilla no funcionan adentro de contenedores.
--  · Links internos -> texto plano (en papel no hay hipervínculos);
--    los que apuntan a un archivo omitido (botones de navegación tipo
--    «Volver al índice») se van enteros.
--  · Títulos partidos en dos headings consecutivos del mismo nivel
--    («CAPÍTULO PRIMERO» + su título temático) se fusionan en uno.
--  · Secciones que quedaron sin contenido (p. ej. el capítulo «Notas»
--    después de cosechar las notas) pierden también su título.
--  · Archivos del EPUB listados en ENC_OMITIR (separados por coma,
--    p. ej. "Cubierta.xhtml,indice.xhtml") se descartan enteros.
--
-- Config por variables de entorno (las setea encuadernar.py):
--   ENC_OMITIR   lista de archivos a descartar
--   ENC_NOTAS    "0" desactiva la conversión de notas
--   ENC_PORTADA  "0" conserva la imagen de tapa del EPUB
-- =====================================================================

local notas = {}
local convertir_notas = (os.getenv("ENC_NOTAS") or "1") ~= "0"

local omitir = {}
for nombre in (os.getenv("ENC_OMITIR") or ""):gmatch("[^,]+") do
  omitir[nombre:match("^%s*(.-)%s*$")] = true
end

local function omitido(id)
  if not id or id == "" then return false end
  if omitir[id] then return true end
  local base = id:match("([^/]+)$")
  return base ~= nil and omitir[base] == true
end

local function es_nota(id)
  return id and id:match("footnote%-%d+$") ~= nil
end

-- ¿Este párrafo es una nota estilo Word? Empieza con el backlink numerado:
-- un Link con id ..._ftnN (o _ednN) que apunta de vuelta a la referencia.
local function ancla_nota_word(b)
  if b.t ~= "Para" and b.t ~= "Plain" then return nil end
  local x = b.content[1]
  if x and x.t == "Link"
     and (x.identifier:match("_ftn%d+$") or x.identifier:match("_edn%d+$"))
     and (x.target:match("_ftnref%d+$") or x.target:match("_ednref%d+$")) then
    return x.identifier
  end
  return nil
end

-- Saca del contenido de la nota el backlink numerado que la encabeza
-- ("1." como link de vuelta al texto): Typst numera solo.
local function limpiar_nota(bloques)
  local primero = bloques[1]
  if primero and (primero.t == "Para" or primero.t == "Plain") then
    local inl = primero.content
    if inl[1] and (inl[1].t == "Link" or inl[1].t == "Superscript") then
      inl:remove(1)
      while inl[1] and ((inl[1].t == "Str" and inl[1].text:match("^[%d%.%):]+$"))
                        or inl[1].t == "Space") do
        inl:remove(1)
      end
    elseif inl[1] and inl[1].t == "Str" and inl[1].text:match("^%d+[%.%)]?$") then
      inl:remove(1)
      while inl[1] and inl[1].t == "Space" do inl:remove(1) end
    end
  end
  return bloques
end

-- El lector de EPUB de pandoc marca el comienzo de cada archivo del libro
-- con un párrafo que solo contiene un Span vacío cuyo id es el nombre del
-- archivo. Devuelve ese nombre, o nil si el bloque no es un marcador.
local function marcador_de_archivo(b)
  if (b.t == "Para" or b.t == "Plain") and #b.content == 1 then
    local x = b.content[1]
    if x.t == "Span" and x.identifier ~= "" and #x.content == 0 then
      return x.identifier
    end
  end
  return nil
end

function Pandoc(doc)
  -- 0a) descartar archivos completos del EPUB: desde su marcador hasta el
  --     siguiente. Los marcadores en sí se van siempre (labels colgantes).
  local filtrados = pandoc.Blocks({})
  local saltando = false
  for _, b in ipairs(doc.blocks) do
    local id = marcador_de_archivo(b)
    if id then
      saltando = omitido(id)
    elseif not saltando then
      filtrados:insert(b)
    end
  end
  local tmp = pandoc.Pandoc(filtrados, doc.meta)

  -- 0b) por si este EPUB vino con capítulos envueltos en divs con id
  tmp = tmp:walk({
    Div = function(el)
      if omitido(el.identifier) then return {} end
    end,
  })

  if convertir_notas then
    -- 1) recolectar los bloques-nota y sacarlos del documento
    tmp = tmp:walk({
      Div = function(el)
        if es_nota(el.identifier) then
          notas["#" .. el.identifier] = limpiar_nota(el.content)
          return {}
        end
      end,
    })
    -- 1b) ídem para las notas estilo Word (párrafos "[N] texto")
    tmp = tmp:walk({
      Para = function(el)
        local id = ancla_nota_word(el)
        if id then
          notas["#" .. id] = limpiar_nota(pandoc.Blocks({ el }))
          return {}
        end
      end,
    })
    -- 2) reemplazar cada referencia por una nota al pie de verdad
    tmp = tmp:walk({
      Link = function(el)
        local contenido = notas[el.target]
        if contenido then return pandoc.Note(contenido) end
      end,
    })
  end

  -- 3) links internos restantes -> texto plano; los que apuntan a un
  --    archivo omitido son navegación («Volver al índice») y se van
  --    enteros, junto con el párrafo si queda vacío
  tmp = tmp:walk({
    Link = function(el)
      if el.target:sub(1, 1) == "#" then
        if omitido(el.target:sub(2)) then return {} end
        return el.content
      end
    end,
    Para = function(el)
      if #el.content == 0 then return {} end
    end,
    Plain = function(el)
      if #el.content == 0 then return {} end
    end,
  })

  -- 4) desarmar todos los divs (deja los capítulos al tope del documento)
  tmp = tmp:walk({
    Div = function(el) return el.content end,
  })

  -- 4b) fusionar títulos partidos: dos headings consecutivos del mismo
  --     nivel se vuelven uno solo con salto de línea (si no, el segundo
  --     abriría OTRA página de capítulo)
  local fusionados = pandoc.Blocks({})
  for _, b in ipairs(tmp.blocks) do
    local ult = fusionados[#fusionados]
    if b.t == "Header" and ult and ult.t == "Header" and ult.level == b.level then
      ult.content:insert(pandoc.LineBreak())
      ult.content:extend(b.content)
    else
      fusionados:insert(b)
    end
  end
  tmp = pandoc.Pandoc(fusionados, tmp.meta)

  -- 4c) títulos colgados al final del documento sin contenido debajo
  --     (p. ej. el capítulo «Notas» después de cosechar las notas): fuera.
  --     Solo al final: un heading vacío a mitad de libro puede ser un
  --     título de presentación deliberado (frontispicios y similares).
  while #tmp.blocks > 0 and tmp.blocks[#tmp.blocks].t == "Header" do
    tmp.blocks:remove(#tmp.blocks)
  end

  -- 5) descartar la(s) imagen(es) de tapa del EPUB: todo bloque que sea
  --    solo una imagen y aparezca ANTES del primer título es la cubierta
  --    (suele venir repetida en más de un archivo)
  if (os.getenv("ENC_PORTADA") or "1") ~= "0" then
    local function es_solo_imagen(b)
      if b.t == "Figure" then return true end
      if b.t ~= "Para" and b.t ~= "Plain" then return false end
      for _, x in ipairs(b.content) do
        if x.t ~= "Image" and x.t ~= "Space" and x.t ~= "SoftBreak" then
          return false
        end
      end
      return #b.content > 0
    end
    local depurados = pandoc.Blocks({})
    local hubo_titulo = false
    for _, b in ipairs(tmp.blocks) do
      if b.t == "Header" then hubo_titulo = true end
      if hubo_titulo or not es_solo_imagen(b) then
        depurados:insert(b)
      end
    end
    tmp = pandoc.Pandoc(depurados, tmp.meta)
  end

  return tmp
end
