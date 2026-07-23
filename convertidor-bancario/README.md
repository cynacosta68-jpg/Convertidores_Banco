# 🏦 Convertidor Bancario — Colegio Médico del Sur del Chubut

Aplicación web para convertir archivos de liquidación de haberes a los formatos requeridos por distintos bancos: **BBVA**, **Credicoop** y **MACRO**, más una sección de **normalización del archivo de origen "Otros Bancos"**.

---

## Estructura del proyecto

```
convertidor-bancario/
├── app.py                      # Aplicación principal Streamlit
├── convertidores/
│   ├── __init__.py
│   ├── otros_bancos.py         # ★ Parser/normalizador del archivo de origen
│   ├── bbva.py                 # Módulo conversor BBVA
│   ├── credicoop.py            # Módulo conversor Credicoop
│   └── macro.py                # Módulo conversor MACRO
├── requirements.txt
└── README.md
```

---

## Instalación

### Requisitos previos

- Python 3.9 o superior

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/convertidor-bancario.git
cd convertidor-bancario

# 2. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## Uso

```bash
streamlit run app.py
```

Se abre automáticamente en el navegador en `http://localhost:8501`.

1. Seleccionar el banco destino en el menú desplegable.
2. Cargar los archivos requeridos (archivo de entrada + maestro Excel).
3. Ajustar configuración avanzada si es necesario.
4. Presionar **Convertir**.
5. Descargar el archivo generado.

---

## Modelo estandarizado "Otros Bancos" (209 caracteres)

Todos los convertidores que consumen el archivo de origen lo leen a través de
`otros_bancos.py`, que es la única fuente de verdad del layout:

| Pos | Campo | Largo | Observaciones |
|---|---|---|---|
| 000 | CBU | 22 | numérico, con dígitos verificadores |
| 022 | Importe | 10 | numérico, 2 decimales implícitos |
| 032 | Nombre / Razón social | 100 | alfanumérico, alineado a la izquierda |
| 132 | Concepto | 3 | `HON` |
| 135 | Descripción del concepto | 12 | `Honorarios ` |
| 147 | Relleno | 50 | espacios |
| 197 | Tipo de documento | 1 | `1` = CUIT/CUIL |
| 198 | CUIT / CUIL | 11 | numérico, con dígito verificador |

**Total: 209 caracteres + CRLF.**

### Por qué había líneas corridas

**1. Importe fuera de rango.** Cuando el importe supera `$99.999.999,99` no entra
en el campo de 10 dígitos: el sistema de origen escribe 11 y **empuja todo lo que
sigue un lugar a la derecha**. Leído por posición fija, el importe queda truncado
(se transfiere 10 veces menos) y el CUIT sale corrido e inválido.

**2. Codificación (el caso BUTILER).** El archivo de origen viene en **UTF-8**,
pero los convertidores lo leían con **latin-1**. Un nombre con tilde o `ñ` ocupa
2 bytes en UTF-8; leído como latin-1 se transforma en 2 caracteres y la línea pasa
a medir 210. Resultado: el registro salía con el nombre en caracteres basura y con
un CUIT corrido que no existe, **y por eso el banco lo rechazaba sin explicación**.

### Los importes viajan siempre íntegros

**Ningún pago se trunca, se divide ni se excluye.** El campo de importe del archivo
de origen tiene 10 dígitos (hasta `$99.999.999,99`). Si un pago lo supera —por
ejemplo `$120.000.000,00`— el campo se amplía y ese registro queda en 210
caracteres, que es exactamente lo que hace el sistema de liquidación. El destino
final tiene capacidad de sobra:

| Destino | Campo de monto | Tope |
|---|---|---|
| Credicoop | 12 enteros + `,` + 2 decimales = 15 chars | `$999.999.999.999,99` |
| BBVA | 25 dígitos | prácticamente sin límite |

Ejemplos de cómo queda el campo de monto de Credicoop:

```
$223.099,69      ->  000000223099,69
$120.000.000,00  ->  000120000000,00
$104.074.684,23  ->  000104074684,23
```

Si algún importe llegara a superar la capacidad del campo del banco, el proceso
lo informa como error en pantalla en vez de emitir un registro que sería
rechazado.

### Cómo se resuelve

`otros_bancos.py` **no corta por posición fija**. Ancla el registro por sus extremos
invariantes — el CBU son siempre los primeros 22 dígitos y el tipo de documento +
CUIT son siempre los últimos 12 — y deduce el ancho real del campo importe. Así el
registro se lee bien mida 209, 210 o 211 caracteres. Además:

- detecta la codificación real del archivo (UTF-8 / cp1252 / latin-1) y repara mojibake;
- valida los dígitos verificadores de CBU y CUIT;
- translitera los nombres a ASCII estricto (`JOSÈ` → `JOSE`), de modo que el registro
  normalizado mide 209 **bytes** en cualquier codificación y ninguna etapa posterior
  lo puede volver a correr;
- informa cada corrección en pantalla en vez de aplicarla en silencio.

### Sección "Otros Bancos (normalizar)"

| Campo | Detalle |
|---|---|
| **Entrada** | `OTROS_BANCOS.txt` — archivo de origen tal cual lo emite el sistema |
| **Salida** | `OTROS_BANCOS_normalizado.txt` — mismo contenido ajustado al modelo, en ASCII |

La sección informa en pantalla cada corrección aplicada: líneas corridas, nombres
con caracteres no-ASCII, campos de importe ampliados, CBU/CUIT con dígito
verificador inválido y CBUs repetidos.

---

## Descripción de cada convertidor

### BBVA

| Campo | Detalle |
|---|---|
| **Entrada** | `Otros_Bancos__imput_.txt` — archivo de texto con filas que comienzan con `017` (formato estándar interbancario, 209 chars/fila) |
| **Maestro** | `Maestro_datos_BBVA.xlsx` — Excel con columnas: `CBU`, `NombreApellido`, `NroCuenta`, `TipoCobro` |
| **Salida** | `BBVA_generado.txt` — formato BBVA de 250 caracteres por línea con registros 211 (cabecera), 221-224 (detalle × N) y 291 (pie) |

**Lógica:**
- Filtra las filas que comienzan con `017` del archivo de entrada.
- Cruza cada CBU con el maestro para obtener el nombre formateado como `APELLIDO, Nombre`.
- Genera 4 registros por beneficiario (datos bancarios, nombre, provincia, referencia).
- Si un CBU no está en el maestro, usa el nombre del archivo de entrada como fallback.

### Credicoop

| Campo | Detalle |
|---|---|
| **Entrada** | `Otros_Bancos__imput_.txt` — mismo archivo de entrada (se descartan filas `285` y `017`) |
| **Maestro** | `Maestro_de_datos_Credicoop.xlsx` — Excel hoja `Hoja1` con CBU (col B), NroCuenta (col D), Email (col G) |
| **Salida** | `Credicoop_consolidado.zip` — ZIP con archivos TXT divididos en bloques de 200 registros |

**Lógica:**
- Descarta las filas que comienzan con `285` o `017`.
- Genera una línea por beneficiario con 13 campos separados por `;` (CBU, monto, nombre, CUIT, tipo cuenta, cuenta destino, etc.).
- El monto se formatea como `000000032052,74` (12 dígitos enteros + coma + 2 decimales).
- Divide la salida en archivos de 200 registros y los empaqueta en un ZIP.

### MACRO

| Campo | Detalle |
|---|---|
| **Entrada** | `PS.txt` — archivo TAB-separado con columnas: código, CUIT, vacío, CBU, 0, importe, 0 |
| **Maestro** | `Maestro_datos_MACRO.xlsx` — Excel con columnas: `CBU`, `NombreApellido`, `NroCuenta` |
| **Salida** | `salida_MACRO.txt` — archivo TAB-separado con: código, CUIT, nombre, nro cuenta, CBU, importe, fecha |

**Lógica:**
- Lee el archivo PS.txt y busca cada CBU en el maestro.
- Completa nombre y número de cuenta desde el maestro.
- El importe se formatea con 2 decimales y punto.
- La fecha se agrega en formato `DDMMAA`.
- Los CBU no encontrados en el maestro se omiten y se reportan como advertencia.

---

## Configuración avanzada

Cada convertidor tiene un panel de configuración avanzada accesible desde la interfaz donde se pueden ajustar:

- **BBVA:** fecha de proceso, nro. de servicio, concepto, cuenta débito, razón social, provincia, referencia, tipo de cuenta.
- **Credicoop:** observaciones, cantidad de registros por archivo, tipo cuenta destino, tipo de persona.
- **MACRO:** fecha de pago.

---

## Archivos maestro requeridos

Los archivos maestro son planillas Excel (`.xlsx`) que contienen los datos de los beneficiarios. Cada banco requiere su propio maestro con estructura específica:

| Banco | Archivo | Columnas necesarias |
|---|---|---|
| BBVA | `Maestro_datos_BBVA.xlsx` | CBU, NombreApellido, NroCuenta, TipoCobro |
| Credicoop | `Maestro_de_datos_Credicoop.xlsx` | CBU (col B), NroCuenta (col D), Email (col G) |
| MACRO | `Maestro_datos_MACRO.xlsx` | CBU, NombreApellido, NroCuenta |

---

## Licencia

Uso interno — Colegio Médico del Sur del Chubut.
