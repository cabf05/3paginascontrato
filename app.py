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
    if value_str is None:
        return None
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

# -------------------------------
# Upload de arquivos
# -------------------------------
uploaded_files = st.file_uploader(
    "Envie seus contratos em PDF",
    type=["pdf"],
    accept_multiple_files=True
)

uploaded_csv = st.file_uploader(
    "Envie o CSV com os valores de tabela (colunas: Lote, Quadra, VALOR LOTE)",
    type=["csv"],
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

        # Guardar tanto valores numéricos quanto formatados
        data_extracted.append({
            "Arquivo": file.name,
            "Lote": lote,
            "Quadra": quadra,
            "Total_num": total_value,
            "Comissao_num": comissao_value,
            "Soma_num": soma,
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
    st.dataframe(df_extracted[["Arquivo","Lote","Quadra","Total","Valor Comissão","Soma (Total + Comissão)"]], use_container_width=True)

    st.subheader("📑 Tabela 3: Cronograma de Pagamento")
    st.dataframe(df_cronograma, use_container_width=True)

    # -------------------------------
    # Tabela 5 (se CSV enviado)
    # -------------------------------
    if uploaded_csv and not df_extracted.empty:
        df_tabela = pd.read_csv(uploaded_csv, dtype=str)

        # Garantir que os nomes das colunas sejam padronizados
        df_tabela.rename(columns=lambda x: x.strip().upper(), inplace=True)

        if not {"LOTE", "QUADRA", "VALOR LOTE"}.issubset(df_tabela.columns):
            st.error("O CSV deve conter as colunas: Lote, Quadra, VALOR LOTE")
        else:
            # Ajustar tipos
            df_tabela["VALOR LOTE"] = df_tabela["VALOR LOTE"].apply(convert_brl_to_en)

            df5 = df_extracted.merge(
                df_tabela.rename(columns={"LOTE": "Lote", "QUADRA": "Quadra", "VALOR LOTE": "VALOR LOTE"}),
                on=["Lote", "Quadra"],
                how="left"
            )

            df5["Diferença (VALOR LOTE - Soma)"] = df5.apply(
                lambda row: row["VALOR LOTE"] - row["Soma_num"] if pd.notnull(row["VALOR LOTE"]) and pd.notnull(row["Soma_num"]) else None,
                axis=1
            )

            df5["% Diferença"] = df5.apply(
                lambda row: (row["Diferença (VALOR LOTE - Soma)"] / row["VALOR LOTE"] * 100) if pd.notnull(row["VALOR LOTE"]) and pd.notnull(row["Diferença (VALOR LOTE - Soma)"]) else None,
                axis=1
            )

            st.subheader("📊 Tabela 5: Tabela 2 + Valor Lote")
            st.dataframe(df5[["Arquivo","Lote","Quadra","Total","Valor Comissão","Soma (Total + Comissão)","VALOR LOTE","Diferença (VALOR LOTE - Soma)","% Diferença"]], use_container_width=True)

            csv_df5 = df5.to_csv(index=False)
            st.download_button(
                label="📥 Baixar CSV (Tabela 5)",
                data=csv_df5,
                file_name="tabela_5.csv",
                mime="text/csv"
            )

else:
    st.info("Faça upload de contratos em PDF para iniciar a extração.")
