"""
╔══════════════════════════════════════════════════════════════════════╗
║  Convertidor Bancario - Colegio Médico del Sur del Chubut          ║
║  Aplicación unificada para conversión de archivos bancarios        ║
║                                                                    ║
║  Formatos soportados:                                              ║
║    • Otros Bancos (normalización del archivo de origen al modelo)  ║
║    • BBVA      (Otros Bancos → formato BBVA 250 chars/línea)       ║
║    • Credicoop (Otros Bancos → formato Credicoop 13 campos + ZIP)  ║
║    • MACRO     (PS.txt → formato MACRO con maestro)                ║
╚══════════════════════════════════════════════════════════════════════╝

Uso:
    streamlit run app.py
"""

import streamlit as st
from datetime import datetime, date

try:
    from convertidores import bbva, credicoop, macro, otros_bancos
except ImportError:                      # ejecución con módulos planos
    import bbva, credicoop, macro, otros_bancos

from auth import login_required
login_required()


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
    ["Otros Bancos (normalizar)", "BBVA", "Credicoop", "MACRO"],
    index=None,
    placeholder="Elegí una opción...",
)

if banco is None:
    st.info("👆 Seleccioná una opción para comenzar.")
    st.stop()


# ══════════════════════════════════════════════════════════════
# HELPER: panel de diagnóstico del archivo de origen
# ══════════════════════════════════════════════════════════════
def mostrar_anomalias(anomalias, encoding=None, titulo="Diagnóstico del archivo de origen"):
    """Panel reutilizable que muestra las líneas corridas / dudosas."""
    if encoding:
        st.caption(f"Codificación detectada en el archivo de origen: **{encoding}**")
    if not anomalias:
        st.success("✅ Sin anomalías: todos los registros respetan el modelo estándar.")
        return
    st.warning(f"⚠️ {len(anomalias)} registro(s) requirieron normalización o tienen datos dudosos.")
    with st.expander(f"🔎 {titulo} ({len(anomalias)})", expanded=True):
        for a in anomalias:
            st.markdown(f"**Línea {a['nro']} — {a['nombre'] or '(sin nombre)'}**  ·  CBU `{a['cbu']}`")
            for aviso in a["avisos"]:
                st.markdown(f"- {aviso}")
            st.divider()


# ══════════════════════════════════════════════════════════════
# OTROS BANCOS — NORMALIZACIÓN AL MODELO ESTÁNDAR
# ══════════════════════════════════════════════════════════════
if banco == "Otros Bancos (normalizar)":
    st.header("Normalización del archivo Otros Bancos")
    st.markdown(
        "Lee el archivo de origen **OTROS BANCOS**, detecta las **líneas corridas** "
        "y las reacomoda al **modelo estandarizado de 209 caracteres**. "
        "Usalo para revisar el archivo antes de convertirlo, o para generar una "
        "versión limpia que puedan consumir otros sistemas."
    )

    with st.expander("📐 Modelo estandarizado (209 caracteres)"):
        st.markdown(
            "| Pos | Campo | Largo |\n"
            "|---|---|---|\n"
            "| 000 | CBU | 22 |\n"
            "| 022 | Importe (2 decimales implícitos) | 10 |\n"
            "| 032 | Nombre / Razón social | 100 |\n"
            "| 132 | Concepto | 3 |\n"
            "| 135 | Descripción del concepto | 12 |\n"
            "| 147 | Relleno (espacios) | 50 |\n"
            "| 197 | Tipo de documento | 1 |\n"
            "| 198 | CUIT / CUIL | 11 |"
        )
        st.caption(
            "El parser no corta por posición fija: ancla el registro por el CBU "
            "(primeros 22 dígitos) y por el CUIT (últimos 12), de modo que lee bien "
            "aunque la línea mida 210 o 211 caracteres."
        )

    input_file = st.file_uploader(
        "📄 Archivo de origen (OTROS BANCOS)",
        type=["txt"],
        key="ob_input",
        help="Archivo TXT de 209 caracteres por línea generado por el sistema de liquidación",
    )

    with st.expander("💰 Tratamiento de los importes"):
        st.markdown(
            "El importe **siempre viaja íntegro**. Nunca se trunca, no se divide "
            "el pago en cuotas y no se excluye ningún registro.\n\n"
            "El campo de importe del archivo de origen tiene 10 dígitos "
            "(hasta `$99.999.999,99`). Si un pago lo supera — por ejemplo "
            "`$120.000.000,00` — el campo se amplía y ese registro queda en 210 "
            "caracteres, exactamente lo que hace el sistema de liquidación. "
            "El destino tiene capacidad de sobra:"
        )
        st.markdown(
            "| Destino | Campo de monto | Tope |\n"
            "|---|---|---|\n"
            "| Credicoop | 12 enteros + `,` + 2 decimales | `$999.999.999.999,99` |\n"
            "| BBVA | 25 dígitos | prácticamente sin límite |"
        )

    if input_file:
        if st.button("🚀 Normalizar", type="primary", use_container_width=True):
            with st.spinner("Analizando y normalizando..."):
                res = otros_bancos.normalizar(input_file.getvalue())
            st.session_state["ob_res"] = res

    if st.session_state.get("ob_res"):
        res = st.session_state["ob_res"]

        st.success("✅ Normalización completada")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Líneas leídas", res["total_lineas"])
        c2.metric("Normalizadas", res["normalizados"])
        c3.metric("Corregidas", len(res["anomalias"]))
        c4.metric("Importe total", otros_bancos.formatear_importe(res["importe_total"]))

        if res["ampliados"]:
            detalle = " · ".join(
                f"{r['nombre']} {otros_bancos.formatear_importe(r['importe'])}"
                for r in res["ampliados"]
            )
            st.info(
                f"ℹ️ {len(res['ampliados'])} registro(s) con importe mayor a "
                f"$99.999.999,99: se amplió el campo y el monto viaja completo → {detalle}"
            )
        if res["descartados"]:
            st.error(f"❌ {len(res['descartados'])} línea(s) ilegible(s) no se pudieron interpretar.")

        mostrar_anomalias(res["anomalias"], res["encoding"])

        if res["cbus_duplicados"]:
            with st.expander(f"👥 CBUs repetidos ({len(res['cbus_duplicados'])})"):
                st.caption("No es necesariamente un error: puede haber varios pagos al mismo beneficiario.")
                for cbu, n in res["cbus_duplicados"]:
                    st.text(f"{cbu}  →  {n} registros")

        with st.expander("🏦 Distribución por banco"):
            for cod, n in res["por_banco"].most_common():
                etiqueta = ""
                if cod == otros_bancos.COD_BBVA:
                    etiqueta = "  ← va por el convertidor BBVA"
                elif cod == otros_bancos.COD_MACRO:
                    etiqueta = "  ← va por el convertidor MACRO"
                st.text(f"{cod}: {n} registro(s){etiqueta}")

        st.download_button(
            label="📥 Descargar OTROS_BANCOS_normalizado.txt",
            data=res["contenido_bytes"],
            file_name=res["nombre_archivo"],
            mime="text/plain",
            use_container_width=True,
        )
    elif not input_file:
        st.warning("Cargá el archivo de origen para continuar.")


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

        st.divider()
        excluir_jur = st.checkbox(
            "Separar personas jurídicas (el BBVA las rechaza)",
            value=True,
            key="bbva_exc_jur",
            help="Las saca del archivo principal, renumera las secuencias, recalcula "
                 "el pie y te las exporta aparte.",
        )
        col_jur = st.text_input(
            "Columna del maestro que marca persona jurídica (opcional)",
            value="",
            key="bbva_col_jur",
            help="Dejalo vacío para usar el prefijo del CUIT (30/33/34 = jurídica), "
                 "que es regla de AFIP. Si tu maestro tiene una columna propia, "
                 "escribí acá su nombre exacto y esa manda.",
        )
        st.caption(
            "Criterio por defecto: prefijo del CUIT — **20/23/24/25/26/27** = persona física · "
            "**30/33/34** = persona jurídica."
        )

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
                    "excluir_juridicas": excluir_jur,
                    "columna_juridica": col_jur.strip() or None,
                }
                resultado = bbva.convertir(
                    input_bytes=input_file.getvalue(),
                    maestro_bytes=maestro_file.getvalue(),
                    fecha_proceso=fecha_str,
                    config=config,
                )

            juridicas = resultado.get("juridicas", [])

            if resultado.get("error"):
                st.error(f"❌ {resultado['error']}")
            else:
                st.success("✅ Conversión completada")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Beneficiarios", resultado["beneficiarios"],
                          delta=f"-{len(juridicas)} jurídicas" if juridicas else None,
                          delta_color="off")
                c2.metric("Líneas", resultado["total_lineas"])
                c3.metric("Importe total", f"${resultado['importe_total']:,.2f}")
                c4.metric("Maestro", f"{resultado['maestro_registros']} reg.")

                mostrar_anomalias(
                    resultado.get("anomalias", []),
                    resultado.get("encoding"),
                    "Registros BBVA normalizados desde el origen",
                )

                if resultado["no_maestro"]:
                    st.warning(
                        f"⚠️ {len(resultado['no_maestro'])} CBU(s) no encontrados en el maestro "
                        f"(se usó el nombre del archivo de input)."
                    )
                    with st.expander("Ver CBUs faltantes"):
                        for cbu, nombre in resultado["no_maestro"]:
                            st.text(f"CBU: {cbu}  →  {nombre}")

                st.download_button(
                    label="📥 Descargar BBVA_generado.txt (sin jurídicas)",
                    data=resultado["contenido"].encode("latin-1"),
                    file_name=resultado["nombre_archivo"],
                    mime="text/plain",
                    use_container_width=True,
                )

            # ── Personas jurídicas separadas ──────────────────────
            if juridicas:
                st.divider()
                st.subheader("🏢 Personas jurídicas separadas")
                st.info(
                    f"Se apartaron **{len(juridicas)}** registro(s) por "
                    f"**${resultado['importe_juridicas']:,.2f}**, sobre "
                    f"{resultado['leidos_017']} leídos del banco 017. "
                    f"El archivo principal ya está renumerado y con el pie recalculado."
                )

                for r in juridicas:
                    st.markdown(
                        f"**{r['nombre']}** · CUIT `{r['cuit']}` · CBU `{r['cbu']}` · "
                        f"{otros_bancos.formatear_importe(r['importe'])}"
                    )
                    st.caption(f"Motivo: {r['motivo_exclusion']}")

                d1, d2 = st.columns(2)
                with d1:
                    st.download_button(
                        label="📥 Líneas separadas (formato origen)",
                        data=resultado["contenido_juridicas"].encode("ascii", "replace"),
                        file_name=resultado["nombre_arch_juridicas"],
                        mime="text/plain",
                        use_container_width=True,
                        help="Registros de 209 caracteres, listos para reprocesar "
                             "por otro circuito sin tocar el archivo original.",
                    )
                with d2:
                    st.download_button(
                        label="📊 Detalle para revisar (CSV)",
                        data=resultado["csv_juridicas"],
                        file_name=resultado["nombre_csv_juridicas"],
                        mime="text/csv",
                        use_container_width=True,
                        help="Abrir en Excel: CUIT, razón social, CBU, importe y motivo.",
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

            mostrar_anomalias(
                resultado.get("anomalias", []),
                resultado.get("encoding"),
                "Registros normalizados desde el origen",
            )
            if resultado.get("ilegibles"):
                st.error(f"❌ {resultado['ilegibles']} línea(s) del origen no se pudieron interpretar.")
            if resultado.get("ampliados"):
                st.info(
                    f"ℹ️ {resultado['ampliados']} registro(s) traían un importe mayor a "
                    f"$99.999.999,99. El campo de monto de Credicoop los admite completos."
                )
            for f in resultado.get("fuera_de_rango", []):
                st.error(f"❌ {f['nombre']} (CBU {f['cbu']}): {f['detalle']}")

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
st.caption("Convertidor Bancario v1.2 — Colegio Médico del Sur del Chubut")
