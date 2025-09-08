import streamlit as st
import pandas as pd
import fitz  # PyMuPDF

st.set_page_config(page_title="Extração de PDFs", layout="wide")
st.title("📑 Extração de texto das 3 primeiras páginas de PDFs")

# Upload múltiplo de arquivos PDF
uploaded_files = st.file_uploader(
    "Envie seus arquivos PDF",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    data = []

    for file in uploaded_files:
        # Abrir PDF diretamente do upload
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text_content = ""

        # Extrair no máximo 3 páginas
        for page_num in range(min(3, len(doc))):
            page = doc[page_num]
            text_content += page.get_text("text") + "\n"

        data.append({
            "Arquivo": file.name,
            "Texto (3 primeiras páginas)": text_content.strip()
        })

    # Criar DataFrame
    df = pd.DataFrame(data)

    st.subheader("Tabela com o conteúdo extraído")
    st.dataframe(df, use_container_width=True)

    # Botão para exportar em CSV
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Baixar CSV",
        data=csv,
        file_name="conteudo_pdfs.csv",
        mime="text/csv"
    )
else:
    st.info("Faça upload de um ou mais PDFs para iniciar a extração.")
