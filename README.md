# 🏦 Convertidor Bancario — Colegio Médico del Sur del Chubut

Aplicación web para convertir archivos de liquidación de haberes a los formatos requeridos por distintos bancos: **BBVA**, **Credicoop** y **MACRO**.

---

## Estructura del proyecto

```
convertidor-bancario/
├── app.py                      # Aplicación principal Streamlit
├── convertidores/
│   ├── __init__.py
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
