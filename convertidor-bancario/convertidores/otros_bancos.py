"""
otros_bancos.py — Parser y normalizador del archivo "OTROS BANCOS"
═══════════════════════════════════════════════════════════════════

Este módulo es la ÚNICA fuente de verdad para leer el archivo de origen
`OTROS_BANCOS.txt`. Los convertidores BBVA y Credicoop lo usan en lugar
de cortar la línea por posiciones fijas.

MODELO ESTANDARIZADO (209 caracteres por registro + CRLF)
──────────────────────────────────────────────────────────
  ┌─────┬────────────────────┬───────┬──────────────────────────────┐
  │ Pos │ Campo              │ Largo │ Observaciones                │
  ├─────┼────────────────────┼───────┼──────────────────────────────┤
  │ 000 │ CBU                │   22  │ numérico, con dígitos verif. │
  │ 022 │ Importe            │   10  │ numérico, 2 decimales impl.  │
  │ 032 │ Nombre/Razón social│  100  │ alfanumérico, izq. + espacios│
  │ 132 │ Concepto           │    3  │ "HON"                        │
  │ 135 │ Descripción conc.  │   12  │ "Honorarios "                │
  │ 147 │ Relleno            │   50  │ espacios                     │
  │ 197 │ Tipo documento     │    1  │ "1" = CUIT/CUIL              │
  │ 198 │ CUIT/CUIL          │   11  │ numérico, con díg. verif.    │
  └─────┴────────────────────┴───────┴──────────────────────────────┘
                                 209

LAS DOS ANOMALÍAS QUE ROMPÍAN EL PROCESO
─────────────────────────────────────────
1) LÍNEAS CORRIDAS POR IMPORTE (línea de 210 caracteres)
   Cuando el importe supera $99.999.999,99 el sistema de origen escribe
   11 dígitos en un campo de 10 y **empuja todo el resto un lugar a la
   derecha**. Leer por posiciones fijas devuelve:
       - importe truncado (se pierde el último dígito → paga 10× menos)
       - nombre con un dígito pegado adelante
       - CUIT corrido (queda un CUIT inexistente)
   Ejemplo real (22-07-2026): CEPAT CR. , CHUBUT S.R.L.
       leído  → $10.407.468,42  CUIT 13071776200  (inválido)
       real   → $104.074.684,23 CUIT 30717762009  (válido)
   El importe se conserva íntegro: el campo se amplía lo necesario y el monto
   completo llega al archivo del banco destino.

2) LÍNEAS CORRIDAS POR CODIFICACIÓN (el caso BUTILER)
   El archivo de origen viene en **UTF-8**, pero los convertidores lo
   leían con **latin-1**. Cualquier nombre con tilde o ñ ocupa 2 bytes
   en UTF-8; al leerlo como latin-1 se convierte en 2 caracteres y la
   línea pasa a medir 210. Todo lo que está a la derecha del nombre se
   corre un lugar.
   Ejemplo real: BUTILER, JOSÈ RICARDO
       leído  → nombre "BUTILER, JOSÃ\x88 RICARDO"  CUIT 12020785823 (inválido)
       real   → nombre "BUTILER, JOSE RICARDO"      CUIT 20207858235 (válido)
   Por eso el banco rechazaba el registro: le llegaba un CUIT que no
   existe y un nombre con caracteres basura. **Ese era el "no entendemos
   por qué".**

ESTRATEGIA DE LECTURA
──────────────────────
En lugar de cortar por posiciones fijas, se ancla el registro por sus
extremos, que son invariantes:
    · el CBU son SIEMPRE los primeros 22 dígitos
    · el tipo de documento + CUIT son SIEMPRE los últimos 12 dígitos
    · el importe es la corrida de dígitos que sigue al CBU (10 u 11)
    · el resto es nombre(100) + concepto(3) + descripción(12) + relleno
Así el registro se lee bien mida 209, 210 o 211 caracteres.
"""

import re
import unicodedata
from collections import Counter

# ══════════════════════════════════════════════════════════════
# CONSTANTES DEL MODELO
# ══════════════════════════════════════════════════════════════
LARGO_ESTANDAR   = 209
LARGO_CBU        = 22
LARGO_IMPORTE    = 10
LARGO_NOMBRE     = 100
LARGO_CONCEPTO   = 3
LARGO_DESC_CONC  = 12
LARGO_RELLENO    = 50
LARGO_TIPO_DOC   = 1
LARGO_CUIT       = 11

# Valor máximo que entra en el campo de 10 dígitos del archivo de origen.
# Por encima de esto el campo se amplía: NUNCA se trunca ni se divide el pago.
IMPORTE_CAMPO_10 = 10 ** LARGO_IMPORTE - 1        # 9.999.999.999 → $99.999.999,99

# Bancos que tienen su propio convertidor y NO deben ir por el circuito genérico
COD_BBVA         = "017"
COD_MACRO        = "285"


# ══════════════════════════════════════════════════════════════
# UTILIDADES DE VALIDACIÓN
# ══════════════════════════════════════════════════════════════
def cbu_valido(cbu: str) -> bool:
    """Valida los dos dígitos verificadores del CBU (bloque de 8 + bloque de 14)."""
    if len(cbu) != 22 or not cbu.isdigit():
        return False
    b1, b2 = cbu[:8], cbu[8:]
    p1 = [7, 1, 3, 9, 7, 1, 3]
    s1 = sum(int(d) * p for d, p in zip(b1[:7], p1))
    if (10 - s1 % 10) % 10 != int(b1[7]):
        return False
    p2 = [3, 9, 7, 1, 3, 9, 7, 1, 3, 9, 7, 1, 3]
    s2 = sum(int(d) * p for d, p in zip(b2[:13], p2))
    return (10 - s2 % 10) % 10 == int(b2[13])


def cuit_valido(cuit: str) -> bool:
    """Valida el dígito verificador del CUIT/CUIL (módulo 11)."""
    if len(cuit) != 11 or not cuit.isdigit():
        return False
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    s = sum(int(d) * p for d, p in zip(cuit[:10], pesos))
    resto = 11 - s % 11
    dv = 0 if resto == 11 else (9 if resto == 10 else resto)
    return dv == int(cuit[10])


# ══════════════════════════════════════════════════════════════
# UTILIDADES DE TEXTO / CODIFICACIÓN
# ══════════════════════════════════════════════════════════════
def decodificar(raw: bytes):
    """
    Decodifica el archivo de origen probando UTF-8 primero (que es lo que
    realmente emite el sistema) y cayendo a latin-1 / cp1252 si hace falta.

    Devuelve (texto, nombre_encoding).
    """
    if raw.startswith(b"\xef\xbb\xbf"):                 # BOM UTF-8
        return raw[3:].decode("utf-8", errors="replace"), "utf-8-sig"
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1 (con reemplazos)"


_MOJIBAKE = re.compile(r"[ÃÂ][\x80-\xbf\u0080-\u00bf]")


def reparar_mojibake(texto: str) -> str:
    """
    Repara texto UTF-8 que fue leído como latin-1 ("JOSÃ\\x88" → "JOSÈ").
    Si no detecta el patrón, devuelve el texto intacto.
    """
    if not _MOJIBAKE.search(texto):
        return texto
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def a_ascii(texto: str) -> str:
    """
    Translitera a ASCII estricto: 'JOSÈ' → 'JOSE', 'MUÑOZ' → 'MUNOZ'.

    Esto es lo que elimina de raíz el problema BUTILER: un registro que sólo
    contiene ASCII mide 209 BYTES en cualquier codificación, así que ninguna
    etapa posterior lo puede correr.
    """
    desc = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in desc if not unicodedata.combining(c))
    return sin_tildes.encode("ascii", "replace").decode("ascii")


def limpiar_nombre(nombre: str, forzar_ascii: bool = True) -> str:
    """
    Normaliza el nombre / razón social:
      · repara mojibake
      · quita caracteres de control
      · colapsa espacios múltiples
      · corrige el espacio antes de la coma ("CEDIG SC , X" → "CEDIG SC, X")
      · pasa a mayúsculas
      · opcionalmente translitera a ASCII
    """
    n = reparar_mojibake(nombre)
    n = "".join(c if c >= " " else " " for c in n)
    n = re.sub(r"\s+", " ", n).strip()
    n = re.sub(r"\s+,", ",", n)
    n = re.sub(r",(?!\s)", ", ", n)
    n = n.upper()
    if forzar_ascii:
        n = a_ascii(n)
    return n


def formatear_importe(centavos: int) -> str:
    """1040746842 → '$10.407.468,42' (para mostrar en pantalla)."""
    s = f"{centavos / 100:,.2f}"
    return "$" + s.replace(",", "@").replace(".", ",").replace("@", ".")


# ══════════════════════════════════════════════════════════════
# PARSEO DE UN REGISTRO
# ══════════════════════════════════════════════════════════════
_RE_TAIL = re.compile(r"(\d)(\d{11})\s*$")
_RE_LEAD_DIGITS = re.compile(r"^\d+")


def parsear_linea(linea: str, nro: int = 0) -> dict:
    """
    Parsea un registro anclando por los extremos (ver docstring del módulo).

    Devuelve un dict con los campos y una lista `avisos` con todo lo que se
    detectó y/o corrigió. Si el registro es irrecuperable, `ok` es False.
    """
    reg = {
        "nro": nro,
        "linea_original": linea,
        "largo_original": len(linea),
        "ok": False,
        "avisos": [],
        "cbu": "", "importe": 0, "nombre": "", "nombre_original": "",
        "concepto": "", "desc_concepto": "", "tipo_doc": "", "cuit": "",
        "banco": "", "corrido": False, "campo_ampliado": False,
    }

    ln = linea.rstrip("\r\n")
    if not ln.strip():
        reg["avisos"].append("Línea vacía: se descarta.")
        return reg

    # ── 1. CBU: los primeros 22 dígitos ───────────────────────
    cbu = ln[:LARGO_CBU]
    if len(cbu) < LARGO_CBU or not cbu.isdigit():
        reg["avisos"].append("No se pudo leer el CBU (los primeros 22 caracteres no son numéricos).")
        return reg
    reg["cbu"] = cbu
    reg["banco"] = cbu[:3]
    if not cbu_valido(cbu):
        reg["avisos"].append(f"CBU {cbu} con dígito verificador inválido.")

    # ── 2. Cola: tipo de documento + CUIT (últimos 12 dígitos) ─
    m_tail = _RE_TAIL.search(ln)
    if not m_tail:
        reg["avisos"].append("No se encontró el bloque final tipo-documento + CUIT.")
        return reg
    reg["tipo_doc"] = m_tail.group(1)
    reg["cuit"] = m_tail.group(2)
    if not cuit_valido(reg["cuit"]):
        reg["avisos"].append(f"CUIT/CUIL {reg['cuit']} con dígito verificador inválido.")

    # ── 3. Importe: dígitos que siguen al CBU (ancho variable) ─
    medio = ln[LARGO_CBU:m_tail.start()]
    m_imp = _RE_LEAD_DIGITS.match(medio)
    if not m_imp:
        reg["avisos"].append("No se encontró el importe después del CBU.")
        return reg
    imp_raw = m_imp.group(0)
    reg["importe"] = int(imp_raw)

    if len(imp_raw) > LARGO_IMPORTE:
        reg["campo_ampliado"] = True
        reg["corrido"] = True
        reg["avisos"].append(
            f"Importe de {len(imp_raw)} dígitos en un campo de {LARGO_IMPORTE}: "
            f"la línea venía corrida {len(imp_raw) - LARGO_IMPORTE} lugar(es). "
            f"Se conserva el importe íntegro {formatear_importe(reg['importe'])} "
            f"(leer por posición fija daba {formatear_importe(int(imp_raw[:LARGO_IMPORTE]))})."
        )
    elif len(imp_raw) < LARGO_IMPORTE:
        reg["avisos"].append(f"Importe con sólo {len(imp_raw)} dígitos: se completa con ceros a la izquierda.")

    if reg["importe"] == 0:
        reg["avisos"].append("Importe en cero.")

    # ── 4. Nombre + concepto + descripción ────────────────────
    resto = medio[len(imp_raw):]
    nombre_raw = resto[:LARGO_NOMBRE]
    bloque_conc = resto[LARGO_NOMBRE:]

    concepto = bloque_conc[:LARGO_CONCEPTO]
    if not re.fullmatch(r"[A-Za-z]{3}", concepto):
        # Realineación de emergencia: buscamos el código de concepto real
        m_c = re.search(r"[A-Z]{3}(?=[A-Za-z])", resto[LARGO_NOMBRE - 5:])
        if m_c:
            corte = LARGO_NOMBRE - 5 + m_c.start()
            nombre_raw = resto[:corte]
            bloque_conc = resto[corte:]
            concepto = bloque_conc[:LARGO_CONCEPTO]
            reg["corrido"] = True
            reg["avisos"].append("Bloque de concepto desalineado: se realineó por búsqueda del código.")
        else:
            reg["avisos"].append("No se pudo ubicar el código de concepto; se usa el valor por posición.")

    reg["concepto"] = concepto.strip().upper()
    reg["desc_concepto"] = bloque_conc[LARGO_CONCEPTO:LARGO_CONCEPTO + LARGO_DESC_CONC].strip()

    reg["nombre_original"] = nombre_raw.rstrip()
    nombre_limpio = limpiar_nombre(nombre_raw)
    reg["nombre"] = nombre_limpio

    if any(ord(c) > 127 for c in nombre_raw):
        reg["corrido"] = True
        reg["avisos"].append(
            f"El nombre traía caracteres no-ASCII ('{nombre_raw.strip()}'): "
            f"con lectura latin-1 el registro se corría 1 lugar y salía con CUIT equivocado. "
            f"Normalizado a '{nombre_limpio}'."
        )
    if not nombre_limpio:
        reg["avisos"].append("Nombre/razón social vacío.")
    if len(nombre_limpio) > LARGO_NOMBRE:
        reg["avisos"].append(f"Nombre de {len(nombre_limpio)} caracteres: se trunca a {LARGO_NOMBRE}.")

    if len(ln) != LARGO_ESTANDAR:
        reg["avisos"].append(f"La línea medía {len(ln)} caracteres en vez de {LARGO_ESTANDAR}.")

    reg["ok"] = True
    return reg


# ══════════════════════════════════════════════════════════════
# ARMADO DEL REGISTRO NORMALIZADO
# ══════════════════════════════════════════════════════════════
def construir_linea(reg: dict, importe: int = None) -> str:
    """
    Arma el registro normalizado a partir de un dict parseado.

    Mide 209 caracteres. La ÚNICA excepción es el campo de importe, que se
    amplía lo necesario para que el monto viaje íntegro (igual que hace el
    sistema de origen). Un pago nunca se trunca ni se divide.
    """
    imp = reg["importe"] if importe is None else importe
    ancho = max(LARGO_IMPORTE, len(str(imp)))          # sólo crece si el monto lo exige
    linea = (
        reg["cbu"].zfill(LARGO_CBU)[:LARGO_CBU]
        + str(imp).zfill(ancho)
        + reg["nombre"].ljust(LARGO_NOMBRE)[:LARGO_NOMBRE]
        + (reg["concepto"] or "HON").ljust(LARGO_CONCEPTO)[:LARGO_CONCEPTO]
        + (reg["desc_concepto"] or "Honorarios").ljust(LARGO_DESC_CONC)[:LARGO_DESC_CONC]
        + " " * LARGO_RELLENO
        + (reg["tipo_doc"] or "1")[:LARGO_TIPO_DOC]
        + reg["cuit"].zfill(LARGO_CUIT)[:LARGO_CUIT]
    )
    return linea


# ══════════════════════════════════════════════════════════════
# API PRINCIPAL
# ══════════════════════════════════════════════════════════════
def parsear(raw: bytes) -> dict:
    """
    Lee el archivo completo y devuelve el análisis, sin generar salida.

    Retorna dict con:
        registros            list de dicts (sólo los ok=True)
        descartados          list de dicts (ok=False)
        encoding             encoding detectado
        total_lineas         int
        importe_total        int (en centavos)
        anomalias            list de dicts {nro, nombre, cbu, avisos}
        por_banco            Counter {cod_banco: cantidad}
        cbus_duplicados      list de (cbu, cantidad)
    """
    texto, encoding = decodificar(raw)
    registros, descartados = [], []

    for i, linea in enumerate(texto.splitlines(), 1):
        if not linea.strip():
            continue
        reg = parsear_linea(linea, i)
        (registros if reg["ok"] else descartados).append(reg)

    conteo = Counter(r["cbu"] for r in registros)
    duplicados = [(c, n) for c, n in conteo.items() if n > 1]

    anomalias = [
        {"nro": r["nro"], "nombre": r["nombre"], "cbu": r["cbu"],
         "importe": r["importe"], "avisos": r["avisos"]}
        for r in registros + descartados if r["avisos"]
    ]

    return {
        "registros":       registros,
        "descartados":     descartados,
        "encoding":        encoding,
        "total_lineas":    len(registros) + len(descartados),
        "importe_total":   sum(r["importe"] for r in registros),
        "anomalias":       anomalias,
        "por_banco":       Counter(r["banco"] for r in registros),
        "cbus_duplicados": duplicados,
    }


def normalizar(raw: bytes) -> dict:
    """
    Lee el archivo de origen y devuelve la versión normalizada al modelo estándar.

    El importe SIEMPRE viaja íntegro. Si supera los 10 dígitos del campo, el
    campo se amplía y ese registro queda en 210 caracteres — exactamente lo que
    hace el sistema de origen. No se trunca, no se divide y no se excluye ningún
    pago: el destino final (Credicoop admite hasta $999.999.999.999,99, BBVA
    hasta 25 dígitos) tiene capacidad de sobra.

    Retorna el dict de `parsear()` más:
        contenido        str normalizado (líneas separadas por CRLF)
        contenido_bytes  bytes listos para descargar
        normalizados     int
        ampliados        list de registros cuyo campo de importe se amplió
        nombre_archivo   str sugerido
    """
    res = parsear(raw)

    salida = [construir_linea(reg) for reg in res["registros"]]
    contenido = "\r\n".join(salida) + ("\r\n" if salida else "")

    res.update({
        "contenido":       contenido,
        "contenido_bytes": contenido.encode("ascii", "replace"),
        "normalizados":    len(salida),
        "ampliados":       [r for r in res["registros"] if r["campo_ampliado"]],
        "nombre_archivo":  "OTROS_BANCOS_normalizado.txt",
    })
    return res


def registros_para(raw: bytes, incluir=None, excluir=None) -> tuple:
    """
    Atajo para los convertidores: devuelve (registros_filtrados, analisis).

    incluir / excluir son listas de códigos de banco (los 3 primeros dígitos
    del CBU). `incluir` tiene prioridad si se pasan los dos.
    """
    res = parsear(raw)
    regs = res["registros"]
    if incluir:
        regs = [r for r in regs if r["banco"] in incluir]
    elif excluir:
        regs = [r for r in regs if r["banco"] not in excluir]
    return regs, res
