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

    # -----------------------
    # CNPJ
    # -----------------------
    cnpj_match = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)

    if cnpj_match:
        cnpj = cnpj_match.group()

    # -----------------------
    # DATA
    # -----------------------
    datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)

    if datas:
        data = datas[0]

    # -----------------------
    # VALOR TOTAL DA NOTA
    # -----------------------
    valor_match = re.search(
        r"VALOR TOTAL DA NOTA\s*R?\$?\s*([\d\.\,]+)",
        texto,
        re.IGNORECASE
    )

    if valor_match:
        try:
            valor = float(
                valor_match.group(1)
                .replace(".", "")
                .replace(",", ".")
            )
        except:
            valor = 0

    # fallback
    if valor == 0:

        valores = re.findall(
            r"[\d]{1,3}(?:\.\d{3})*,\d{2}",
            texto
        )

        valores_float = []

        for v in valores:
            try:
                numero = float(
                    v.replace(".", "").replace(",", ".")
                )

                if numero < 100000:
                    valores_float.append(numero)

            except:
                pass

        if valores_float:
            valor = max(valores_float)

    # -----------------------
    # ICMS
    # -----------------------
    icms_match = re.search(
        r"VALOR DO ICMS\s*R?\$?\s*([\d\.,]+)",
        texto,
        re.IGNORECASE
    )

    if icms_match:
        try:
            icms = float(
                icms_match.group(1)
                .replace(".", "")
                .replace(",", ".")
            )
        except:
            pass

    # -----------------------
    # IPI
    # -----------------------
    ipi_match = re.search(
        r"VALOR DO IPI\s*R?\$?\s*([\d\.,]+)",
        texto,
        re.IGNORECASE
    )

    if ipi_match:
        try:
            ipi = float(
                ipi_match.group(1)
                .replace(".", "")
                .replace(",", ".")
            )
        except:
            pass

    # -----------------------
    # TRIBUTOS APROXIMADOS
    # -----------------------
    trib_match = re.search(
        r"Federal R\$(.*?)Estadual R\$(.*?)\(",
        texto
    )

    if trib_match:
        try:
            federal = float(
                trib_match.group(1)
                .replace(".", "")
                .replace(",", ".")
                .strip()
            )

            estadual = float(
                trib_match.group(2)
                .replace(".", "")
                .replace(",", ".")
                .strip()
            )

            tributos_aprox = federal + estadual

        except:
            pass

    # -----------------------
    # FORNECEDOR
    # -----------------------
    if cnpj:
        fornecedor_api = buscar_cnpj(cnpj)

        if fornecedor_api:
            fornecedor = fornecedor_api

    if fornecedor == "":
        linhas = texto.split("\n")

        for i, linha in enumerate(linhas):

            if "RECEBEMOS DE" in linha.upper():
                fornecedor = (
                    linha.upper()
                    .replace("RECEBEMOS DE", "")
                    .split("OS PRODUTOS")[0]
                    .strip()
                )
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

    # -----------------------------
    # HEADER
    # -----------------------------
    st.markdown("""
    <style>
    .main {
        background-color: #f5f7fb;
    }

    .titulo {
        font-size: 42px;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 5px;
    }

    .subtitulo {
        font-size: 18px;
        color: #6b7280;
        margin-bottom: 30px;
    }

    .card {
        background-color: white;
        padding: 30px;
        border-radius: 18px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }

    .kpi {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        padding: 20px;
        border-radius: 18px;
        color: white;
        text-align: center;
    }

    .kpi h1 {
        font-size: 32px;
        margin: 0;
    }

    .kpi p {
        margin: 0;
        font-size: 14px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="titulo">📊 Gestão Inteligente de Compras</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitulo">Upload automático de notas fiscais • OCR • Análise tributária • Dashboard executivo</div>', unsafe_allow_html=True)

    # -----------------------------
    # KPIs SUPERIORES
    # -----------------------------
    df_dashboard = carregar_dados()

    total_compras = 0
    total_notas = 0
    total_impostos = 0

    if not df_dashboard.empty:
        total_compras = df_dashboard['valor'].sum()
        total_notas = len(df_dashboard)
        total_impostos = df_dashboard['tributos_aprox'].sum()

            st.markdown('</div>', unsafe_allow_html=True)
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
        df['mes'] = df['data'].dt.strftime('%Y-%m')

        st.subheader("📈 Evolução de Compras (Mensal)")
        evolucao = df.groupby('mes')['valor'].sum()
        st.bar_chart(evolucao)

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
