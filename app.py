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
        'file': file
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
            icms = st.number_input("ICMS", value=float(icms), key=file.name+"i")
ipi = st.number_input("IPI", value=float(ipi), key=file.name+"ipi")
tributos_aprox = st.number_input("Tributos Aproximados", value=float(tributos_aprox), key=file.name+"t")

            st.subheader(file.name)

            fornecedor = st.text_input("Fornecedor", fornecedor, key=file.name+"f")
            cnpj = st.text_input("CNPJ", cnpj, key=file.name+"c")
            data = st.text_input("Data", data, key=file.name+"d")
            valor = st.number_input("Valor", value=float(valor), key=file.name+"v")

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
        # -----------------------
        # TRATAMENTO
        # -----------------------
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df = df.dropna(subset=['data'])

        # -----------------------
        # FILTROS
        # -----------------------
        st.sidebar.subheader("Filtros")

        data_inicio = st.sidebar.date_input("Data início", df['data'].min())
        data_fim = st.sidebar.date_input("Data fim", df['data'].max())

        fornecedores = st.sidebar.multiselect(
            "Fornecedor",
            df['fornecedor'].unique(),
            default=df['fornecedor'].unique()
        )

        df = df[
            (df['data'] >= pd.to_datetime(data_inicio)) &
            (df['data'] <= pd.to_datetime(data_fim)) &
            (df['fornecedor'].isin(fornecedores))
        ]

        # -----------------------
        # KPIs
        # -----------------------
        total = df['valor'].sum()
        qtd_notas = len(df)
        ticket_medio = total / qtd_notas if qtd_notas > 0 else 0

        col1, col2, col3 = st.columns(3)

        col1.metric("💰 Total Comprado", f"R$ {total:,.2f}")
        col2.metric("📄 Nº de Notas", qtd_notas)
        col3.metric("📊 Ticket Médio", f"R$ {ticket_medio:,.2f}")

        st.divider()

        # -----------------------
        # EVOLUÇÃO MENSAL
        # -----------------------
        df['mes'] = df['data'].dt.to_period('M')

        st.subheader("📈 Evolução de Compras (Mensal)")
        st.bar_chart(df.groupby('mes')['valor'].sum())

        # -----------------------
        # TOP FORNECEDORES
        # -----------------------
        st.subheader("🏆 Top Fornecedores")

        top_forn = df.groupby('fornecedor')['valor'].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top_forn)

        # -----------------------
        # PARTICIPAÇÃO (%)
        # -----------------------
        st.subheader("📊 Participação por Fornecedor (%)")

        participacao = (df.groupby('fornecedor')['valor'].sum() / total * 100).sort_values(ascending=False)

        st.dataframe(
            participacao.reset_index().rename(columns={"valor": "%"}),
            use_container_width=True
        )

        # -----------------------
        # CONCENTRAÇÃO
        # -----------------------
        st.subheader("⚠️ Concentração de Compras")

        top3 = top_forn.head(3).sum()
        concentracao = (top3 / total) * 100 if total > 0 else 0

        st.metric("Top 3 fornecedores (%)", f"{concentracao:.2f}%")
    st.title("📊 Dashboard")

    df = carregar_dados()

    if not df.empty:
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df['mes'] = df['data'].dt.to_period('M')

        st.subheader("Gastos por Mês")
        st.bar_chart(df.groupby('mes')['valor'].sum())

        st.subheader("Top Fornecedores")
        st.bar_chart(df.groupby('fornecedor')['valor'].sum().sort_values(ascending=False).head(10))
        st.subheader("Top Fornecedores")
st.bar_chart(df.groupby('fornecedor')['valor'].sum().sort_values(ascending=False).head(10))

# 👇 COLE AQUI 👇
st.subheader("💰 Impostos Totais")

total_impostos = df['tributos_aprox'].sum()
total_geral = df['valor'].sum()

percentual = (total_impostos / total_geral * 100) if total_geral > 0 else 0

col1, col2 = st.columns(2)

col1.metric("Total em Tributos", f"R$ {total_impostos:,.2f}")
col2.metric("Carga Tributária (%)", f"{percentual:.2f}%")

        st.metric("Total Geral", f"R$ {df['valor'].sum():,.2f}")
    else:
        st.warning("Sem dados ainda")
