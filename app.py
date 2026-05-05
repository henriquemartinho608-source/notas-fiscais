import streamlit as st
import pdfplumber
import pandas as pd
import sqlite3
import re
import requests

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
    import requests

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

        st.metric("Total Geral", f"R$ {df['valor'].sum():,.2f}")
    else:
        st.warning("Sem dados ainda")
