import streamlit as st
import pdfplumber
import pandas as pd
import sqlite3
import re
import requests
def buscar_cnpj(cnpj):
    try:
        cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
        url = f"https://www.receitaws.com.br/v1/cnpj/{cnpj_limpo}"

        response = requests.get(url)
        data = response.json()

        if data.get('status') == 'OK':
            return data.get('nome', "")
        else:
            return ""
    except:
        return ""

st.set_page_config(page_title="Gestão de Compras", layout="wide")

conn = sqlite3.connect("notas.db", check_same_thread=False)
c = conn.cursor()

c.execute(
    """
    CREATE TABLE IF NOT EXISTS notas2 (
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

def processar_nota(texto, cnpj, data, valor, icms, ipi, tributos_aprox):

    fornecedor = ""

    if cnpj:
        fornecedor_api = buscar_cnpj(cnpj)
        if fornecedor_api:
            fornecedor = fornecedor_api

    if fornecedor == "":
        linhas = texto.split("\n")

        for i, linha in enumerate(linhas):
            if "RECEBEMOS DE" in linha.upper():
                fornecedor = linha.upper().replace("RECEBEMOS DE", "").split("OS PRODUTOS")[0].strip()
                break

            if "CNPJ" in linha.upper():
                if i > 0:
                    fornecedor = linhas[i - 1].strip()
                    break

    if fornecedor == "":
        fornecedor = "Não identificado"

    return fornecedor, cnpj, data, valor, icms, ipi, tributos_aprox

def salvar_dados(dados):
    c.execute("""
    INSERT INTO notas2 
    (fornecedor, cnpj, data, valor, icms, ipi, tributos_aprox)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, dados)
    conn.commit()

def carregar_dados():
    return pd.read_sql("SELECT * FROM notas2", conn)

menu = st.sidebar.selectbox("Menu", ["Upload", "Base", "Dashboard"])

if menu == "Upload":
    st.title("📤 Upload de Notas")

    arquivos = st.file_uploader(
        "Envie PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

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
                c.execute("DELETE FROM notas2 WHERE id = ?", (row['id'],))
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

        st.divider()

               # -----------------------
        # 💰 IMPOSTOS
        # -----------------------
        st.subheader("💰 Análise de Impostos")

        total_impostos = df['tributos_aprox'].sum()
        total_geral = df['valor'].sum()

        percentual = (total_impostos / total_geral * 100) if total_geral > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total em Compras", f"R$ {total_geral:,.2f}")
        col2.metric("Total em Tributos", f"R$ {total_impostos:,.2f}")
        col3.metric("Carga Tributária (%)", f"{percentual:.2f}%")

        # -----------------------
        # 🚨 FORA DO PADRÃO
        # -----------------------
        st.subheader("🚨 Fornecedores com Carga Tributária Fora do Padrão")

        df_forn = df.groupby('fornecedor').agg({
            'valor': 'sum',
            'tributos_aprox': 'sum'
        }).reset_index()

        df_forn['carga_%'] = (df_forn['tributos_aprox'] / df_forn['valor']) * 100

        media_geral = df_forn['carga_%'].mean()
        limite = media_geral * 1.2

        fora_padrao = df_forn[df_forn['carga_%'] > limite].sort_values(by='carga_%', ascending=False)

        st.write(f"Média geral: {media_geral:.2f}%")

        if fora_padrao.empty:
            st.success("Nenhum fornecedor fora do padrão 👌")
        else:
            st.warning("Fornecedores com carga acima do normal:")
            st.dataframe(fora_padrao, use_container_width=True)

        # -----------------------
        # 💡 ECONOMIA POTENCIAL
        # -----------------------
        st.subheader("💡 Potencial de Economia")

        melhor_carga = df_forn['carga_%'].min()

        df_forn['economia_potencial'] = (
            (df_forn['carga_%'] - melhor_carga) / 100
        ) * df_forn['valor']

        economia_total = df_forn['economia_potencial'].sum()

        st.metric("💰 Economia Potencial Total", f"R$ {economia_total:,.2f}")
        st.write(f"Melhor carga encontrada: {melhor_carga:.2f}%")

        st.subheader("📊 Onde economizar mais")
        top_economia = df_forn.sort_values(by='economia_potencial', ascending=False)
        st.dataframe(top_economia, use_container_width=True)

        # -----------------------
        # 📊 IMPOSTOS POR FORNECEDOR
        # -----------------------
        st.subheader("📊 Impostos por Fornecedor")
        impostos_forn = df.groupby('fornecedor')['tributos_aprox'].sum().sort_values(ascending=False).head(10)
        st.bar_chart(impostos_forn)
