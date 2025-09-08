import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import re

st.set_page_config(page_title="Extração de PDFs", layout="wide")
st.title("📑 Extração de texto das 3 primeiras páginas de PDFs")

# Função para converter valores monetários BR -> EN
def convert_brl_to_en(value_str):
    """Converte número em formato brasileiro para inglês (string -> float)."""
    clean = value_str.replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None

# Upload múltiplo de arquivos PDF
uploaded_files = st.file_uploader(
    "Envie seus arquivos PDF",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    data_text = []  # tabela com o texto bruto
    data_extracted = []  # tabela estruturada com os valores

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
        # Extração de informações específicas
        # -------------------------------

        # Lote e Quadra
        lote_match = re.search(r"Lote\s+(\d+)", text_content, re.IGNORECASE)
        quadra_match = re.search(r"Quadra[^\d]*(\d+)", text_content, re.IGNORECASE)

        lote = lote_match.group(1) if lote_match else None
        quadra = quadra_match.group(1) if quadra_match else None

        # Total
        total_match = re.search(r"TOTAL\s+([\d\.,]+)", text_content, re.IGNORECASE)
        total_value = convert_brl_to_en(total_match.group(1)) if total_match else None

        # Comissão
        comissao_match = re.search(
            r"COMISSÃO DE CORRETAGEM.*?R\$ ([\d\.,]+)",
            text_content,
            re.IGNORECASE | re.DOTALL
        )
        comissao_value = convert_brl_to_en(comissao_match.group(1)) if comissao_match else None

        # Soma
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
    # Mostrar tabelas
    # -------------------------------
    df_text = pd.DataFrame(data_text)
    df_extracted = pd.DataFrame(data_extracted)

    st.subheader("📄 Tabela com o conteúdo bruto (3 primeiras páginas)")
    st.dataframe(df_text, use_container_width=True)

    st.subheader("📊 Tabela estruturada com valores extraídos")
    st.dataframe(df_extracted, use_container_width=True)

    # Botão para exportar
    csv = df_extracted.to_csv(index=False)
    st.download_button(
        label="📥 Baixar CSV (valores extraídos)",
        data=csv,
        file_name="valores_extraidos.csv",
        mime="text/csv"
    )

else:
    st.info("Faça upload de um ou mais PDFs para iniciar a extração.")
