import streamlit as st
import pdfplumber
import pandas as pd
import sqlite3
import re

st.set_page_config(page_title="Gestão de Compras", layout="wide")

conn = sqlite3.connect("notas.db", check_same_thread=False)
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS notas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fornecedor TEXT,
    cnpj TEXT,
    data TEXT,
    valor REAL
)
''')

conn.commit()

def extrair_texto_pdf(file):
    texto = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto += page.extract_text() or ""
    return texto

def extrair_dados(texto):
    fornecedor = ""
    cnpj = ""
    valor = 0
    data = ""

    # -----------------------
    # CNPJ
    # -----------------------
    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    if cnpj_match:
        cnpj = cnpj_match.group()

    # -----------------------
    # DATA (pega a primeira válida)
    # -----------------------
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
    if datas:
        data = datas[0]

    # -----------------------
    # FORNECEDOR (seu padrão)
    # -----------------------
    for linha in texto.split("\n"):
        if "RECEBEMOS DE" in linha:
            fornecedor = linha.replace("RECEBEMOS DE", "").split("OS PRODUTOS")[0].strip()

    # -----------------------
    # VALOR TOTAL (melhorado)
    # -----------------------
    valores = re.findall(r"R\$\s*([\d\.\,]+)", texto)

    if valores:
        # pega o maior valor (geralmente é o total da nota)
        valores_float = [float(v.replace('.', '').replace(',', '.')) for v in valores]
        valor = max(valores_float)

    return fornecedor, cnpj, data, valor
    fornecedor = ""
    cnpj = ""
    valor = 0
    data = ""

    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    if cnpj_match:
        cnpj = cnpj_match.group()

    data_match = re.search(r"\d{2}/\d{2}/\d{4}", texto)
    if data_match:
        data = data_match.group()

    valor_match = re.search(r"R\$\\s*([\\d\\.]+,\\d{2})", texto)
    if valor_match:
        valor = float(valor_match.group(1).replace('.', '').replace(',', '.'))

    for linha in texto.split("\n"):
        if "RECEBEMOS DE" in linha:
            fornecedor = linha.replace("RECEBEMOS DE", "").split("OS PRODUTOS")[0].strip()

    return fornecedor, cnpj, data, valor

def salvar_dados(dados):
    c.execute("INSERT INTO notas (fornecedor, cnpj, data, valor) VALUES (?, ?, ?, ?)", dados)
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
            fornecedor, cnpj, data, valor = extrair_dados(texto)

            st.subheader(file.name)

            fornecedor = st.text_input("Fornecedor", fornecedor, key=file.name+"f")
            cnpj = st.text_input("CNPJ", cnpj, key=file.name+"c")
            data = st.text_input("Data", data, key=file.name+"d")
            valor = st.number_input("Valor", value=float(valor), key=file.name+"v")

            if st.button("Salvar", key=file.name):
                salvar_dados((fornecedor, cnpj, data, valor))
                st.success("Salvo!")

elif menu == "Base":
    st.title("📄 Base de Dados")
    df = carregar_dados()
    st.dataframe(df, use_container_width=True)

elif menu == "Dashboard":
    st.title("📊 Dashboard")

    df = carregar_dados()

    if not df.empty:
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df['mes'] = df['data'].dt.to_period('M')

        st.subheader("Gastos por Mês")
        st.bar_chart(df.groupby('mes')['valor'].sum())

        st.subheader("Top Fornecedores")
        st.bar_chart(df.groupby('fornecedor')['valor'].sum().sort_values(ascending=False).head(10))

        st.metric("Total Geral", f"R$ {df['valor'].sum():,.2f}")
    else:
        st.warning("Sem dados ainda")
