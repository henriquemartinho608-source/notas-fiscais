import streamlit as st
import pdfplumber
import pandas as pd
import sqlite3
import re
import requests

st.set_page_config(page_title="Gestão de Compras", layout="wide")

conn = sqlite3.connect("notas.db", check_same_thread=False)
c = conn.cursor()

c.execute(
    """
    CREATE TABLE IF NOT EXISTS notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fornecedor TEXT,
        cnpj TEXT,
        data TEXT,
        valor REAL,
        icms REAL,
        ipi REAL,
        tributos_aprox REAL
    )
    """
)

def extrair_texto_pdf(file):
    texto = ""

    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                texto += page.extract_text() or ""
    except:
        pass

    # Se falhar ou vier vazio → usa OCR
    if len(texto.strip()) < 50:
        texto = extrair_texto_ocr(file)

    return texto
    
def extrair_texto_ocr(file):
    url = "https://api.ocr.space/parse/image"

    payload = {
        'apikey': 'K88717938688957',
        'language': 'por'
    }

    files = {
        'file': file.getvalue()
    }

    response = requests.post(url, files=files, data=payload)
    result = response.json()

    try:
        return result['ParsedResults'][0]['ParsedText']
    except:
        return ""
def extrair_dados(texto):
    fornecedor = ""
    cnpj = ""
    valor = 0
    data = ""
    icms = 0
    ipi = 0
    tributos_aprox = 0

    # CNPJ
    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    if cnpj_match:
        cnpj = cnpj_match.group()

    # DATA
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
    if datas:
        data = datas[0]

    # VALOR TOTAL
    valores = re.findall(r"[\d]{1,3}(?:\.\d{3})*,\d{2}", texto)
    if valores:
        valores_float = [float(v.replace('.', '').replace(',', '.')) for v in valores]
        valor = max(valores_float)

    # ICMS
    icms_match = re.search(r"ICMS.*?([\d\.,]+)", texto)
    if icms_match:
        try:
            icms = float(icms_match.group(1).replace('.', '').replace(',', '.'))
        except:
            pass

    # IPI
    ipi_match = re.search(r"IPI.*?([\d\.,]+)", texto)
    if ipi_match:
        try:
            ipi = float(ipi_match.group(1).replace('.', '').replace(',', '.'))
        except:
            pass

    # Tributos aproximados
    trib_match = re.search(r"R\$\s*([\d\.,]+)", texto)
    if trib_match:
        try:
            tributos_aprox = float(trib_match.group(1).replace('.', '').replace(',', '.'))
        except:
            pass

    # FORNECEDOR
    for linha in texto.split("\n"):
        if "RECEBEMOS DE" in linha:
            fornecedor = linha.replace("RECEBEMOS DE", "").split("OS PRODUTOS")[0].strip()

    return fornecedor, cnpj, data, valor, icms, ipi, tributos_aprox

def salvar_dados(dados):
    c.execute("""
    INSERT INTO notas 
    (fornecedor, cnpj, data, valor, icms, ipi, tributos_aprox)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, dados)
    conn.commit()

def carregar_dados():
    return pd.read_sql("SELECT * FROM notas", conn)

menu = st.sidebar.selectbox("Menu", ["Upload", "Base", "Dashboard"])

if menu == "Upload":
    st.title("📤 Upload de Notas")

    arquivos = st.file_uploader("Envie PDFs", type=["pdf"], accept_multiple_files=True)

if arquivos:
    for file in arquivos:
        texto = extrair_texto_pdf(file)
        fornecedor, cnpj, data, valor, icms, ipi, tributos_aprox = extrair_dados(texto)

        st.subheader(file.name)

        fornecedor = st.text_input("Fornecedor", fornecedor, key=file.name+"f")
        cnpj = st.text_input("CNPJ", cnpj, key=file.name+"c")
        data = st.text_input("Data", data, key=file.name+"d")
        valor = st.number_input("Valor", value=float(valor), key=file.name+"v")

        icms = st.number_input("ICMS", value=float(icms), key=file.name+"i")
        ipi = st.number_input("IPI", value=float(ipi), key=file.name+"ipi")
        tributos_aprox = st.number_input("Tributos Aproximados", value=float(tributos_aprox), key=file.name+"t")

        if st.button("Salvar", key=file.name):
            salvar_dados((fornecedor, cnpj, data, valor, icms, ipi, tributos_aprox))
            st.success("Salvo!")

elif menu == "Base":
    st.title("📄 Base de Dados")

    df = carregar_dados()

    if df.empty:
        st.warning("Sem dados ainda")
    else:
        for i, row in df.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns(6)

            col1.write(row['id'])
            col2.write(row['fornecedor'])
            col3.write(row['cnpj'])
            col4.write(row['data'])
            col5.write(f"R$ {row['valor']:.2f}")

            if col6.button("❌ Excluir", key=row['id']):
                c.execute("DELETE FROM notas WHERE id = ?", (row['id'],))
                conn.commit()
                st.success("Nota excluída!")
                st.rerun()
    st.title("📄 Base de Dados")
    df = carregar_dados()
    st.dataframe(df, use_container_width=True)

elif menu == "Dashboard":
    st.title("📊 Dashboard de Compras")

    df = carregar_dados()

    if df.empty:
        st.warning("Sem dados ainda.")
    else:
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df = df.dropna(subset=['data'])

        total = df['valor'].sum()

        st.subheader("🏆 Top Fornecedores")
        top_forn = df.groupby('fornecedor')['valor'].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top_forn)

        # 💰 IMPOSTOS
        st.subheader("💰 Impostos Totais")

        total_impostos = df['tributos_aprox'].sum()
        percentual = (total_impostos / total * 100) if total > 0 else 0

        col1, col2 = st.columns(2)
        col1.metric("Total em Tributos", f"R$ {total_impostos:,.2f}")
        col2.metric("Carga Tributária (%)", f"{percentual:.2f}%")

        st.metric("Total Geral", f"R$ {df['valor'].sum():,.2f}")
   
