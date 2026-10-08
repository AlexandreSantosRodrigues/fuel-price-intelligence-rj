"""Initial Streamlit entry point."""

import streamlit as st

st.set_page_config(
    page_title="Fuel Price Intelligence RJ",
    page_icon="⛽",
    layout="wide",
)

st.title("⛽ Fuel Price Intelligence RJ")
st.caption("Monitoramento e previsão de preços de combustíveis com dados da ANP.")

st.info(
    "Projeto em construção. A primeira entrega será o painel de qualidade "
    "e cobertura dos dados brutos."
)

st.subheader("Problema de negócio")
st.write(
    "Prever o preço médio da gasolina e do etanol para as próximas quatro "
    "semanas nos municípios analisados do Rio de Janeiro."
)
