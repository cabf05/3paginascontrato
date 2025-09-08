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
    """Extrai cronograma de pagamento do texto em blocos de 7 linhas."""
    cronograma = []

    match = re.search(r"Cronograma de Pagamento:(.*?TOTAL\s+[\d\.,]+)", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return cronograma

    block = match.group(1)

    # Remove cabeçalho fixo
    block = re.sub(
        r"Descrição\s*Valor Total da Série.*?Correção",
        "",
        block,
        flags=re.DOTALL | re.IGNORECASE
    ).strip()

    lines = [l.strip() for l in block.splitlines() if l.strip()]

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
                "Valor Total da Série": valor_total,
                "Parcelas": parcelas,
                "Vencimento (1ª Parcela)": vencimento,
                "Valor Inicial (1ª Parcela)": valor_inicial,
                "Taxa Juros (% mensal)": juros,
                "Correção": correcao
            })

    return cronograma

def extract_valores_lotes(pdf_file):
    """Extrai tabela de valores de lotes do PDF enviado separadamente."""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n"

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    data = []
    for line in lines:
        parts = re.split(r"\s+", line)

        # Espera algo como: Lote Quadra Valor
        if len(parts) >= 3 and parts[0].isdigit():
            lote = parts[0]
            quadra = parts[1]  # pode ser número ou texto (ex: "C1")
            try:
                valor = float(parts[2].replace(",", "").replace(" ", ""))
                data.append({
                    "Lote": str(lote),
                    "Quadra": str(quadra),
                    "VALOR TABELA": valor
                })
            except ValueError:
                continue

    return pd.DataFrame(data)

# -------------------------------
# Upload de arquivos
# -------------------------------
uploaded_files = st.file_uploader(
    "Envie seus contratos em PDF",
    type=["pdf"],
    accept_multiple_files=True
)

uploaded_tabela = st.file_uploader(
    "Envie o PDF com a tabela de valores dos lotes",
    type=["pdf"],
    accept_multiple_files=False
)

if uploaded_files:
    data_text = []       
    data_extracted = []  
    data_cronograma = [] 

    for file in uploaded_files:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text_content = ""

        for page_num in range(min(3, len(doc))):
            page = doc[page_num]
            text_content += page.get_text("text") + "\n"

        data_text.append({
            "Arquivo": file.name,
            "Texto (3 primeiras páginas)": text_content.strip()
        })

        lote_match = re.search(r"Lote\s+(\d+)", text_content, re.IGNORECASE)
        quadra_match = re.search(r"Quadra[^\dA-Za-z]*(\w+)", text_content, re.IGNORECASE)

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

        cronograma_rows = extract_cronograma(text_content, lote, quadra)
        data_cronograma.extend(cronograma_rows)

    df_text = pd.DataFrame(data_text)
    df_extracted = pd.DataFrame(data_extracted)
    df_cronograma = pd.DataFrame(data_cronograma)

    # -------------------------------
    # Mostrar tabelas 1 a 3
    # -------------------------------
    st.subheader("📄 Tabela 1: Conteúdo bruto (3 primeiras páginas)")
    st.dataframe(df_text, use_container_width=True)

    st.subheader("📊 Tabela 2: Valores principais extraídos")
    st.dataframe(df_extracted, use_container_width=True)

    st.subheader("📑 Tabela 3: Cronograma de Pagamento")
    st.dataframe(df_cronograma, use_container_width=True)

    # -------------------------------
    # Tabela 5 (se tabela de valores enviada)
    # -------------------------------
    if uploaded_tabela and not df_cronograma.empty:
        df_tabela = extract_valores_lotes(uploaded_tabela)

        # Padronizar colunas para merge
        df_cronograma["Lote"] = df_cronograma["Lote"].astype(str).str.strip()
        df_cronograma["Quadra"] = df_cronograma["Quadra"].astype(str).str.strip()
        df_tabela["Lote"] = df_tabela["Lote"].astype(str).str.strip()
        df_tabela["Quadra"] = df_tabela["Quadra"].astype(str).str.strip()

        # Merge
        df5 = df_cronograma.merge(df_tabela, on=["Lote", "Quadra"], how="left")

        # Diferença e percentual
        df5["Diferença (VALOR TABELA - Valor Total da Série)"] = df5.apply(
            lambda row: row["VALOR TABELA"] - row["Valor Total da Série"]
            if pd.notnull(row.get("VALOR TABELA")) and pd.notnull(row.get("Valor Total da Série"))
            else None,
            axis=1
        )

        df5["% Diferença"] = df5.apply(
            lambda row: (row["Diferença (VALOR TABELA - Valor Total da Série)"] / row["VALOR TABELA"] * 100)
            if pd.notnull(row.get("VALOR TABELA")) and pd.notnull(row.get("Diferença (VALOR TABELA - Valor Total da Série)"))
            else None,
            axis=1
        )

        st.subheader("📊 Tabela 5: Cronograma + Valor Tabela")
        st.dataframe(df5, use_container_width=True)

        csv_df5 = df5.to_csv(index=False)
        st.download_button(
            label="📥 Baixar CSV (Tabela 5)",
            data=csv_df5,
            file_name="tabela_5.csv",
            mime="text/csv"
        )

    # -------------------------------
    # Exportações
    # -------------------------------
    csv_text = df_text.to_csv(index=False)
    st.download_button(
        label="📥 Baixar CSV (Texto bruto)",
        data=csv_text,
        file_name="texto_bruto.csv",
        mime="text/csv"
    )

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
    st.info("Faça upload de contratos em PDF para iniciar a extração.")
