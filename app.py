import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="Extração de PDFs", layout="wide")
st.title("📑 Extração de informações estruturadas de PDFs")

# -------------------------------
# Funções auxiliares
# -------------------------------
def convert_brl_to_en(value_str):
    """Converte número em formato brasileiro para inglês (string -> float)."""
    clean = value_str.replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None

def extract_cronograma(text, lote, quadra):
    """Extrai cronograma de pagamento do texto."""
    cronograma = []

    # Isola trecho do cronograma
    match = re.search(r"Cronograma de Pagamento:(.*?)TOTAL", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return cronograma

    block = match.group(1)

    # Remove cabeçalhos fixos
    block = re.sub(r"Descrição.*?Correção", "", block, flags=re.DOTALL | re.IGNORECASE).strip()

    # Quebra em linhas
    lines = [l.strip() for l in block.splitlines() if l.strip()]

    # Agrupar em blocos de 7 (cada linha de tabela)
    for i in range(0, len(lines), 7):
        if i + 6 < len(lines):
            desc = lines[i]
            valor_total = convert_brl_to_en(lines[i+1])
            parcelas = lines[i+2]
            vencimento = lines[i+3]
            valor_inicial = convert_brl_to_en(lines[i+4])
            juros = lines[i+5]
            correcao = lines[i+6]

            cronograma.append({
                "Lote": lote,
                "Quadra": quadra,
                "Descrição": desc,
                "Valor Total da Série": f"{valor_total:,.2f}" if valor_total is not None else None,
                "Parcelas": parcelas,
                "Vencimento (1ª Parcela)": vencimento,
                "Valor Inicial (1ª Parcela)": f"{valor_inicial:,.2f}" if valor_inicial is not None else None,
                "Taxa Juros (% mensal)": juros,
                "Correção": correcao
            })

    return cronograma

# -------------------------------
# Upload múltiplo de arquivos PDF
# -------------------------------
uploaded_files = st.file_uploader(
    "Envie seus arquivos PDF",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    data_text = []       # tabela 1: texto bruto
    data_extracted = []  # tabela 2: valores principais
    data_cronograma = [] # tabela 3: cronograma

    for file in uploaded_files:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text_content = ""

        # Extrair no máximo 3 páginas
        for page_num in range(min(3, len(doc))):
            page = doc[page_num]
            text_content += page.get_text("text") + "\n"

        data_text.append({
            "Arquivo": file.name,
            "Texto (3 primeiras páginas)": text_content.strip()
        })

        # -------------------------------
        # Extração de informações principais
        # -------------------------------
        lote_match = re.search(r"Lote\s+(\d+)", text_content, re.IGNORECASE)
        quadra_match = re.search(r"Quadra[^\d]*(\d+)", text_content, re.IGNORECASE)

        lote = lote_match.group(1) if lote_match else None
        quadra = quadra_match.group(1) if quadra_match else None

        total_match = re.search(r"TOTAL\s+([\d\.,]+)", text_content, re.IGNORECASE)
        total_value = convert_brl_to_en(total_match.group(1)) if total_match else None

        comissao_match = re.search(
            r"COMISSÃO DE CORRETAGEM.*?R\$ ([\d\.,]+)",
            text_content,
            re.IGNORECASE | re.DOTALL
        )
        comissao_value = convert_brl_to_en(comissao_match.group(1)) if comissao_match else None

        soma = None
        if total_value is not None and comissao_value is not None:
            soma = total_value + comissao_value

        data_extracted.append({
            "Arquivo": file.name,
            "Lote": lote,
            "Quadra": quadra,
            "Total": f"{total_value:,.2f}" if total_value is not None else None,
            "Valor Comissão": f"{comissao_value:,.2f}" if comissao_value is not None else None,
            "Soma (Total + Comissão)": f"{soma:,.2f}" if soma is not None else None
        })

        # -------------------------------
        # Extração do cronograma
        # -------------------------------
        cronograma_rows = extract_cronograma(text_content, lote, quadra)
        data_cronograma.extend(cronograma_rows)

    # -------------------------------
    # Mostrar tabelas
    # -------------------------------
    df_text = pd.DataFrame(data_text)
    df_extracted = pd.DataFrame(data_extracted)
    df_cronograma = pd.DataFrame(data_cronograma)

    st.subheader("📄 Tabela 1: Conteúdo bruto (3 primeiras páginas)")
    st.dataframe(df_text, use_container_width=True)

    st.subheader("📊 Tabela 2: Valores principais extraídos")
    st.dataframe(df_extracted, use_container_width=True)

    st.subheader("📑 Tabela 3: Cronograma de Pagamento")
    st.dataframe(df_cronograma, use_container_width=True)

    # Botões para exportar
    csv_extracted = df_extracted.to_csv(index=False)
    st.download_button(
        label="📥 Baixar CSV (Valores principais)",
        data=csv_extracted,
        file_name="valores_principais.csv",
        mime="text/csv"
    )

    if not df_cronograma.empty:
        csv_cronograma = df_cronograma.to_csv(index=False)
        st.download_button(
            label="📥 Baixar CSV (Cronograma de Pagamento)",
            data=csv_cronograma,
            file_name="cronograma_pagamento.csv",
            mime="text/csv"
        )

else:
    st.info("Faça upload de um ou mais PDFs para iniciar a extração.")
