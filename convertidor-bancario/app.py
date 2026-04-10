"""
╔══════════════════════════════════════════════════════════════════════╗
║  Convertidor Bancario - Colegio Médico del Sur del Chubut          ║
║  Aplicación unificada para conversión de archivos bancarios        ║
║                                                                    ║
║  Formatos soportados:                                              ║
║    • BBVA      (Otros Bancos → formato BBVA 250 chars/línea)       ║
║    • Credicoop (Otros Bancos → formato Credicoop 13 campos + ZIP)  ║
║    • MACRO     (PS.txt → formato MACRO con maestro)                ║
╚══════════════════════════════════════════════════════════════════════╝

Uso:
    streamlit run app.py
"""

import streamlit as st
from datetime import datetime, date

from convertidores import bbva, credicoop, macro


# ══════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PÁGINA
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Convertidor Bancario",
    page_icon="🏦",
    layout="centered",
)

# ── Estilos personalizados ──
st.markdown("""
<style>
    .stApp { max-width: 900px; margin: 0 auto; }
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        padding: 10px 15px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# ENCABEZADO
# ══════════════════════════════════════════════════════════════
st.title("🏦 Convertidor Bancario")
st.caption("Colegio Médico del Sur del Chubut")
st.divider()

# ══════════════════════════════════════════════════════════════
# SELECTOR DE CONVERTIDOR
# ══════════════════════════════════════════════════════════════
banco = st.selectbox(
    "Seleccionar formato de conversión:",
    ["BBVA", "Credicoop", "MACRO"],
    index=None,
    placeholder="Elegí un banco...",
)

if banco is None:
    st.info("👆 Seleccioná un banco para comenzar.")
    st.stop()


# ══════════════════════════════════════════════════════════════
# BBVA
# ══════════════════════════════════════════════════════════════
if banco == "BBVA":
    st.header("Conversión a formato BBVA")
    st.markdown(
        "Convierte el archivo **Otros Bancos (input)** al formato BBVA "
        "de 250 caracteres por línea, cruzando datos con el **Maestro BBVA**."
    )

    col1, col2 = st.columns(2)
    with col1:
        input_file = st.file_uploader(
            "📄 Archivo de entrada (Otros Bancos)",
            type=["txt"],
            key="bbva_input",
            help="Archivo TXT con filas que comienzan con '017'",
        )
    with col2:
        maestro_file = st.file_uploader(
            "📊 Maestro de datos BBVA",
            type=["xlsx"],
            key="bbva_maestro",
            help="Excel con columnas: CBU, NombreApellido, NroCuenta, TipoCobro",
        )

    # Opciones avanzadas
    with st.expander("⚙️ Configuración avanzada"):
        col_a, col_b = st.columns(2)
        with col_a:
            fecha_input = st.date_input("Fecha de proceso", value=date.today(), key="bbva_fecha")
            servicio = st.text_input("Nro. de servicio", value="001261")
            concepto = st.text_input("Concepto", value="HONORARIOS", max_chars=10)
            provincia = st.text_input("Provincia", value="CHUBUT")
        with col_b:
            cta_debito = st.text_input("Cuenta débito", value="0097740103302327", max_chars=16)
            empresa = st.text_input("Razón social", value="COLEGIO MEDICO DEL SUR DEL CHUBUT", max_chars=36)
            referencia = st.text_input("Referencia", value="LIQUIDACION")
            tipo_cuenta = st.selectbox("Tipo cuenta", ["1 - Caja de Ahorro", "0 - Cuenta Corriente"], key="bbva_tc")

    if input_file and maestro_file:
        if st.button("🚀 Convertir a BBVA", type="primary", use_container_width=True):
            with st.spinner("Procesando..."):
                fecha_str = fecha_input.strftime("%Y%m%d")
                config = {
                    "servicio": servicio,
                    "cta_debito": cta_debito,
                    "concepto": concepto,
                    "empresa": empresa,
                    "provincia": provincia,
                    "referencia": referencia,
                    "tipo_cuenta": tipo_cuenta[0],
                }
                resultado = bbva.convertir(
                    input_bytes=input_file.getvalue(),
                    maestro_bytes=maestro_file.getvalue(),
                    fecha_proceso=fecha_str,
                    config=config,
                )

            if resultado.get("error"):
                st.error(f"❌ {resultado['error']}")
            else:
                st.success("✅ Conversión completada")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Beneficiarios", resultado["beneficiarios"])
                c2.metric("Líneas", resultado["total_lineas"])
                c3.metric("Importe total", f"${resultado['importe_total']:,.2f}")
                c4.metric("Maestro", f"{resultado['maestro_registros']} reg.")

                if resultado["no_maestro"]:
                    st.warning(
                        f"⚠️ {len(resultado['no_maestro'])} CBU(s) no encontrados en el maestro "
                        f"(se usó el nombre del archivo de input)."
                    )
                    with st.expander("Ver CBUs faltantes"):
                        for cbu, nombre in resultado["no_maestro"]:
                            st.text(f"CBU: {cbu}  →  {nombre}")

                st.download_button(
                    label="📥 Descargar BBVA_generado.txt",
                    data=resultado["contenido"].encode("latin-1"),
                    file_name=resultado["nombre_archivo"],
                    mime="text/plain",
                    use_container_width=True,
                )
    else:
        st.warning("Cargá ambos archivos para continuar.")


# ══════════════════════════════════════════════════════════════
# CREDICOOP
# ══════════════════════════════════════════════════════════════
elif banco == "Credicoop":
    st.header("Conversión a formato Credicoop")
    st.markdown(
        "Convierte el archivo **Otros Bancos (input)** al formato Credicoop "
        "(13 campos separados por `;`), cruzando datos con el **Maestro Credicoop**. "
        "Genera archivos divididos en bloques de 200 registros + ZIP."
    )

    col1, col2 = st.columns(2)
    with col1:
        input_file = st.file_uploader(
            "📄 Archivo de entrada (Otros Bancos)",
            type=["txt"],
            key="credicoop_input",
            help="Archivo TXT (se descartan filas 285/017)",
        )
    with col2:
        maestro_file = st.file_uploader(
            "📊 Maestro de datos Credicoop",
            type=["xlsx"],
            key="credicoop_maestro",
            help="Excel con hoja 'Hoja1': CBU (col B), NroCuenta (col D), Email (col G)",
        )

    with st.expander("⚙️ Configuración avanzada"):
        col_a, col_b = st.columns(2)
        with col_a:
            observaciones = st.text_input("Observaciones", value="COLEGIO MEDICO", max_chars=60, key="credi_obs")
            chunk_size = st.number_input("Registros por archivo", value=200, min_value=1, max_value=1000, key="credi_chunk")
        with col_b:
            tipo_cta = st.text_input("Tipo cuenta destino", value="CAP", max_chars=3, key="credi_tc")
            tipo_pers = st.selectbox("Tipo persona", ["J - Jurídica", "F - Física"], key="credi_tp")

    if input_file and maestro_file:
        if st.button("🚀 Convertir a Credicoop", type="primary", use_container_width=True):
            with st.spinner("Procesando..."):
                config = {
                    "observaciones": observaciones,
                    "chunk_size": chunk_size,
                    "tipo_cuenta": tipo_cta,
                    "tipo_persona": tipo_pers[0],
                }
                resultado = credicoop.convertir(
                    input_bytes=input_file.getvalue(),
                    maestro_bytes=maestro_file.getvalue(),
                    config=config,
                )

            if resultado["errores"]:
                for err in resultado["errores"][:5]:
                    st.error(f"❌ {err}")
            else:
                st.success("✅ Conversión completada")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Convertidas", resultado["convertidas"])
            c2.metric("Descartadas", f"{resultado['descartadas']} (285/017)")
            c3.metric("Archivos", len(resultado["archivos"]))
            c4.metric("Maestro", f"{resultado['maestro_registros']} reg.")

            if resultado["sin_datos"]:
                st.warning(
                    f"⚠️ {len(resultado['sin_datos'])} CBU(s) sin datos en maestro "
                    f"(email y cuenta quedarán vacíos)."
                )
                with st.expander("Ver CBUs faltantes"):
                    for cbu in resultado["sin_datos"][:20]:
                        st.text(f"CBU: {cbu}")

            if resultado["zip_bytes"]:
                st.download_button(
                    label="📥 Descargar Credicoop_consolidado.zip",
                    data=resultado["zip_bytes"],
                    file_name=resultado["nombre_zip"],
                    mime="application/zip",
                    use_container_width=True,
                )

                with st.expander("📂 Descargar archivos individuales"):
                    for arch in resultado["archivos"]:
                        st.download_button(
                            label=f"📄 {arch['nombre']}",
                            data=arch["contenido_bytes"],
                            file_name=arch["nombre"],
                            mime="text/plain",
                            key=f"dl_{arch['nombre']}",
                        )
    else:
        st.warning("Cargá ambos archivos para continuar.")


# ══════════════════════════════════════════════════════════════
# MACRO
# ══════════════════════════════════════════════════════════════
elif banco == "MACRO":
    st.header("Conversión a formato MACRO")
    st.markdown(
        "Convierte el archivo **PS.txt** al formato Banco MACRO, "
        "cruzando con el **Maestro MACRO** para completar nombres y cuentas."
    )

    col1, col2 = st.columns(2)
    with col1:
        input_file = st.file_uploader(
            "📄 Archivo PS.txt",
            type=["txt"],
            key="macro_input",
            help="Archivo TAB-separado con columnas: 0000000, CUIT, vacío, CBU, 0, importe, 0",
        )
    with col2:
        maestro_file = st.file_uploader(
            "📊 Maestro de datos MACRO",
            type=["xlsx"],
            key="macro_maestro",
            help="Excel con columnas: CBU, NombreApellido, NroCuenta",
        )

    with st.expander("⚙️ Configuración avanzada"):
        fecha_macro = st.date_input("Fecha de pago", value=date.today(), key="macro_fecha")

    if input_file and maestro_file:
        if st.button("🚀 Convertir a MACRO", type="primary", use_container_width=True):
            with st.spinner("Procesando..."):
                fecha_str = fecha_macro.strftime("%d%m%y")
                resultado = macro.convertir(
                    input_bytes=input_file.getvalue(),
                    maestro_bytes=maestro_file.getvalue(),
                    fecha_ddmmaa=fecha_str,
                )

            if resultado["registros"] == 0:
                st.error("❌ No se generaron registros. Verificá el archivo de entrada y el maestro.")
            else:
                st.success("✅ Conversión completada")
                c1, c2, c3 = st.columns(3)
                c1.metric("Registros", resultado["registros"])
                c2.metric("Fecha", resultado["fecha"])
                c3.metric("Maestro", f"{resultado['maestro_registros']} reg.")

            if resultado["no_encontrados"]:
                st.warning(
                    f"⚠️ {len(resultado['no_encontrados'])} CBU(s) no encontrados en el maestro "
                    f"(se omitieron del archivo de salida)."
                )
                with st.expander("Ver CBUs faltantes"):
                    for item in resultado["no_encontrados"][:20]:
                        st.text(f"Línea {item['linea']}  CUIT {item['cuit']}  CBU {item['cbu']}")

            if resultado["lineas_invalidas"] > 0:
                st.info(f"ℹ️ {resultado['lineas_invalidas']} línea(s) con formato inválido fueron omitidas.")

            if resultado["contenido"]:
                st.download_button(
                    label="📥 Descargar salida_MACRO.txt",
                    data=resultado["contenido"].encode("utf-8"),
                    file_name=resultado["nombre_archivo"],
                    mime="text/plain",
                    use_container_width=True,
                )
    else:
        st.warning("Cargá ambos archivos para continuar.")


# ══════════════════════════════════════════════════════════════
# PIE DE PÁGINA
# ══════════════════════════════════════════════════════════════
st.divider()
st.caption("Convertidor Bancario v1.0 — Colegio Médico del Sur del Chubut")
