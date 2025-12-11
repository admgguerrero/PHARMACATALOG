import streamlit as st
import pandas as pd
import re, json, time
from openai import AzureOpenAI
import os
# --------------------------
# CONFIG CLIENTE
# --------------------------

client = AzureOpenAI(
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    api_version="2024-08-01-preview",
    azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")

)

# --------------------------
# SESSION STATE
# --------------------------
for k in [
    "tokens_input", "tokens_output", "tokens_total",
    "tiempo_total", "df_sql_editado"
]:
    if k not in st.session_state:
        st.session_state[k] = None if k == "df_sql_editado" else 0

# --------------------------
# HELPERS
# --------------------------
def fmt(n):
    return f"{n:,}" if isinstance(n, int) else "0"

def limpiar_sql():
    st.session_state.sql_text = ""
    st.session_state.df_sql_editado = None

# --------------------------
# DATA
# --------------------------
LINEAS = [
    "ANTIBIOTICOS","ENFERMEDADES DE LA PIEL","OFTALMOLOGICOS","MATERNIDAD Y LACTANTES",
    "ANTIMICOTICOS","SISTEMA NERVIOSO","ESTOMACALES (GASTRO)","MULTIVITAMINICOS",
    "ANALGESICOS","CARDIOVASCULARES","CUIDADO DE LA PIEL","RESPIRATORIOS",
    "CURACION Y MEDICION","DIABETES","SOUVENIRS","ANTIHISTAMINICOS","HORMONALES",
    "HIGIENE","ESPECIALIDAD","ANTIINFLAMATORIOS","PESO Y METABOLISMO",
    "REHIDRATANTES","SEXUALIDAD","RELAJANTES","DEPORTISTAS"
]

ANTIINFLAMATORIOS = [
    "BENCIDAMINA","DEFLAZACORT","PIROXICAM","ACEMETACINA",
    "PREDNISONA","DEXAMETASONA","BETAMETASONA","MELOXICAM"
]

# --------------------------
# GPT
# --------------------------
def clasificar_producto(nombre):
    prompt = f"""
Clasifica el producto en una línea comercial:
{LINEAS}

Producto: {nombre}

Si el producto no coincide con ninguno directamente, analiza su función general y efecto terapéutico para determinar la línea más probable.
Si el producto contiene 'Simibaby' es MATERNIDAD Y LACTANTES
Si el producto contiene 'SIMIDIAB' es DIABETES
Si el producto contiene 'XGEAR' o 'PROT' es DEPORTISTAS siempre y cuando no sea un muñeco, pastillero ya que eso es Souvenir.
Si el producto contiene jeringa, lancetas, cubrebocas, tiras reactivas,etc es CURACION Y MEDICION
Si el producto es un medicamento que su función general es relacionado de piel que es untado o aplicado en la piel es de ENFERMEDADES DE LA PIEL, de lo contrario de ESPECIALIDAD.
Si el producto es con ingredientes herbolarios, natural que sea RELAJANTES.
Si el producto es Naproxeno, Ibuprofeno, Simiflex, SFX,ETORICOXIB, Diclofenaco, ketoprofeno, Antiinflamatorios en crema, gel, GLUC/CONDR o es para dolor de rodillas y articulaciones o de Fracción 4 es ANALGESICOS.
Si el producto tiene la molecula de {ANTIINFLAMATORIOS} o alguna compuesta o parecida va en ANTIINFLAMATORIOS de lo contrario en ANALGESICOS


Devuelve JSON:
{{"producto":"{nombre}","linea_comercial":"..."}}
"""

    resp = client.chat.completions.create(
        model="gpt-4o-im",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    usage = resp.usage
    st.session_state.tokens_input += usage.prompt_tokens
    st.session_state.tokens_output += usage.completion_tokens
    st.session_state.tokens_total += usage.total_tokens

    content = re.sub(r"```json|```", "", resp.choices[0].message.content)
    return json.loads(re.search(r"\{[\s\S]*\}", content).group())

# --------------------------
# UI
# --------------------------
st.set_page_config("Clasificador", "☀️", layout="wide")

st.markdown("""
<style>
.block {background:#ffffff; padding:20px; border-radius:14px; box-shadow:0 2px 8px rgba(0,0,0,.08);}
.metric {background:#E3F2FD;padding:15px;border-radius:12px;text-align:center;}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;color:#0D47A1'>☀️ Clasificador de Productos</h1>", unsafe_allow_html=True)

# --------------------------
# SIDEBAR
# --------------------------
with st.sidebar:
    st.subheader("📊 Métricas")
    st.write(f"📥 Entrada: {fmt(st.session_state.tokens_input)}")
    st.write(f"📤 Salida: {fmt(st.session_state.tokens_output)}")
    st.write(f"🔢 Total: {fmt(st.session_state.tokens_total)}")
    if st.session_state.tiempo_total:
        st.write(f"⏱️ Tiempo: {st.session_state.tiempo_total} s")
# --------------------------
# PRODUCTO INDIVIDUAL
# --------------------------
st.markdown("<div class='block'>", unsafe_allow_html=True)
st.subheader("Producto individual")

producto = st.text_input("Escribe un producto")

if st.button("Clasificar producto"):
    inicio = time.perf_counter()

    if producto:
        r = clasificar_producto(producto)
        st.success(f"🧾 {r['producto']} | 📌 {r['linea_comercial']}")
    else:
        st.warning("Ingresa un producto.")

    st.session_state.tiempo_total = round(time.perf_counter() - inicio, 2)

# --------------------------
# EXCEL EDITABLE
# --------------------------
st.markdown("<div class='block'>", unsafe_allow_html=True)
st.subheader("📥 Subir Excel")

archivo = st.file_uploader("Debe incluir columna PRODUCTO", type=["xlsx"])

if archivo:
    inicio = time.perf_counter()
    df = pd.read_excel(archivo)

    if "PRODUCTO" in df.columns:
        df["LINEA_CLASIFICADA"] = df["PRODUCTO"].apply(
            lambda x: clasificar_producto(x)["linea_comercial"]
        )

        df_editado = st.data_editor(df, num_rows="dynamic", use_container_width=True)

        st.download_button(
            "📥 Descargar Excel",
            data=to_excel(df_editado),
            file_name="productos_clasificados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.session_state.tiempo_total = round(time.perf_counter() - inicio, 2)
    else:
        st.error("El Excel debe tener columna PRODUCTO")

# --------------------------
# SQL
# --------------------------
st.markdown("<div class='block'>", unsafe_allow_html=True)
st.subheader("🧩 Clasificar desde SQL")

col1, col2 = st.columns([5, 1])

with col1:
    st.text_area("Pega productos", key="sql_text", height=150)

with col2:
    st.button("🗑️ Borrar", on_click=limpiar_sql)

if st.button("Clasificar SQL"):
    inicio = time.perf_counter()

    productos = [
        p.strip()
        for p in st.session_state.sql_text.replace("\n", ",").split(",")
        if p.strip()
    ]

    resultados = [clasificar_producto(p) for p in productos]
    st.session_state.df_sql_editado = pd.DataFrame(resultados)

    st.session_state.tiempo_total = round(time.perf_counter() - inicio, 2)

# --------------------------
# EDITOR + DESCARGA (PERSISTENTE)
# --------------------------
if st.session_state.df_sql_editado is not None:

    st.session_state.df_sql_editado = st.data_editor(
        st.session_state.df_sql_editado,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_sql"
    )

    st.download_button(
        "📥 Descargar CSV",
        st.session_state.df_sql_editado.to_csv(index=False).encode("utf-8"),
        "resultados_sql_editados.csv",
        "text/csv"
    )

    st.success(f"✅ Clasificados {len(st.session_state.df_sql_editado)} productos")
    st.info(f"⏱️ Tiempo total: {st.session_state.tiempo_total} segundos")



