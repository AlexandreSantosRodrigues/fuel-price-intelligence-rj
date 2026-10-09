from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.app.data import (
    build_current_snapshot,
    build_latest_competitiveness,
    build_model_comparison,
    build_municipality_ranking,
    build_recent_history,
    load_dashboard_data,
)

PROJECT_ROOT = Path(__file__).resolve().parent

WEEKLY_PATH = (
    PROJECT_ROOT
    / "reports"
    / "eda"
    / "weekly_price_summary.csv"
)

COMPETITIVENESS_PATH = (
    PROJECT_ROOT
    / "reports"
    / "eda"
    / "ethanol_competitiveness.csv"
)

MUNICIPALITY_PATH = (
    PROJECT_ROOT
    / "reports"
    / "eda"
    / "municipality_price_index.csv"
)

METRICS_PATH = (
    PROJECT_ROOT
    / "reports"
    / "modeling"
    / "model_metrics.csv"
)

PRODUCT_COLORS = {
    "ETANOL": "#16A34A",
    "GASOLINA": "#2563EB",
}

PRODUCT_LABELS = {
    "ETANOL": "Etanol",
    "GASOLINA": "Gasolina",
}


st.set_page_config(
    page_title="Fuel Price Intelligence RJ",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
        .block-container {
            max-width: 1440px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        [data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }

        [data-testid="stMetricLabel"] {
            color: #4B5563;
        }

        .app-subtitle {
            color: #4B5563;
            font-size: 1.05rem;
            margin-bottom: 1.5rem;
        }

        .forecast-box {
            background-color: #F8FAFC;
            border: 1px solid #CBD5E1;
            border-left: 5px solid #2563EB;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            margin: 0.5rem 0 1.5rem 0;
        }

        .method-box {
            background-color: #FFFBEB;
            border: 1px solid #FDE68A;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            margin: 0.5rem 0 1.5rem 0;
        }

        .limitation-box {
            background-color: #FEF2F2;
            border: 1px solid #FECACA;
            border-radius: 10px;
            padding: 1rem 1.2rem;
            margin-top: 1rem;
        }

        .small-note {
            color: #6B7280;
            font-size: 0.88rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def get_dashboard_data() -> dict[str, pd.DataFrame]:
    """Load the versioned reports used by the application."""
    return load_dashboard_data(
        weekly_path=WEEKLY_PATH,
        competitiveness_path=COMPETITIVENESS_PATH,
        municipality_path=MUNICIPALITY_PATH,
        metrics_path=METRICS_PATH,
    )


def format_brl(value: float) -> str:
    """Format a numeric value as Brazilian reais."""
    formatted = f"{value:,.2f}"

    return (
        "R$ "
        + formatted.replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def format_date(value: pd.Timestamp) -> str:
    """Format a timestamp using the Brazilian date pattern."""
    return value.strftime("%d/%m/%Y")


def render_header() -> None:
    """Render the application title and business context."""
    st.title("⛽ Fuel Price Intelligence RJ")

    st.markdown(
        """
        <div class="app-subtitle">
            Monitoramento, comparação e previsão semanal dos preços
            de gasolina comum e etanol no estado do Rio de Janeiro.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Dados públicos da ANP • Pipeline reproduzível • "
        "Validação temporal sem divisão aleatória"
    )


def render_snapshot(
    snapshot: pd.DataFrame,
) -> None:
    """Render current price and next-week forecast cards."""
    st.subheader("Visão atual e previsão")

    latest_date = snapshot["week_start"].max()
    forecast_date = snapshot["forecast_week"].max()

    st.caption(
        f"Última semana observada: {format_date(latest_date)} | "
        f"Semana prevista: {format_date(forecast_date)}"
    )

    columns = st.columns(4)

    for index, product in enumerate(
        ("GASOLINA", "ETANOL")
    ):
        row = snapshot.loc[
            snapshot["product"].eq(product)
        ].iloc[0]

        product_label = PRODUCT_LABELS[product]

        columns[index * 2].metric(
            label=f"{product_label} — preço atual",
            value=format_brl(row["median_price"]),
            help=(
                "Mediana estadual dos preços observados "
                "na última semana disponível."
            ),
        )

        columns[index * 2 + 1].metric(
            label=f"{product_label} — próxima semana",
            value=format_brl(
                row["forecast_next_week"]
            ),
            delta="Sem alteração projetada",
            delta_color="off",
            help=(
                "Previsão do baseline de persistência: "
                "o último preço conhecido."
            ),
        )

    st.markdown(
        """
        <div class="forecast-box">
            <strong>Como interpretar:</strong> a previsão para a próxima
            semana repete a última mediana observada. Essa abordagem
            simples superou Ridge, Random Forest e
            HistGradientBoosting no backtesting temporal.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_recent_history(
    weekly_data: pd.DataFrame,
) -> None:
    """Render the recent weekly price history."""
    st.subheader("Histórico recente")

    selected_weeks = st.select_slider(
        "Período exibido",
        options=[12, 26, 52, 104],
        value=52,
        format_func=lambda value: f"{value} semanas",
    )

    recent = build_recent_history(
        weekly_data,
        weeks=selected_weeks,
    )

    recent = recent.copy()
    recent["product_label"] = recent[
        "product"
    ].map(PRODUCT_LABELS)

    figure = px.line(
        recent,
        x="week_start",
        y="median_price",
        color="product_label",
        markers=True,
        color_discrete_map={
            "Etanol": PRODUCT_COLORS["ETANOL"],
            "Gasolina": PRODUCT_COLORS["GASOLINA"],
        },
        labels={
            "week_start": "Semana",
            "median_price": "Preço mediano (R$/litro)",
            "product_label": "Combustível",
        },
    )

    figure.update_traces(
        line={"width": 3},
        marker={"size": 5},
    )

    figure.update_layout(
        height=460,
        hovermode="x unified",
        legend_title_text="",
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
    )

    figure.update_yaxes(
        tickprefix="R$ ",
        tickformat=".2f",
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )

    st.caption(
        "Os valores representam a mediana estadual semanal, "
        "reduzindo a influência de preços extremos."
    )


def render_competitiveness(
    competitiveness_data: pd.DataFrame,
) -> None:
    """Render the latest ethanol competitiveness indicators."""
    st.subheader("Etanol ou gasolina?")

    summary = build_latest_competitiveness(
        competitiveness_data
    )

    metric_columns = st.columns(3)

    metric_columns[0].metric(
        "Relação mediana etanol/gasolina",
        f"{summary['median_ratio']:.1%}",
        help=(
            "Relação entre as medianas municipais dos "
            "dois combustíveis na semana mais recente."
        ),
    )

    metric_columns[1].metric(
        "Municípios com etanol competitivo",
        (
            f"{summary['competitive_count']} "
            f"de {summary['comparisons']}"
        ),
    )

    metric_columns[2].metric(
        "Taxa de competitividade",
        f"{summary['competitive_rate']:.1%}",
    )

    if summary["median_ratio"] <= 0.70:
        message = (
            "Pela regra geral de 70%, o etanol apresentou "
            "vantagem econômica na mediana da última semana."
        )
        message_type = "success"
    else:
        message = (
            "Pela regra geral de 70%, a gasolina apresentou "
            "vantagem econômica na mediana da última semana."
        )
        message_type = "warning"

    getattr(st, message_type)(message)

    st.caption(
        "A regra de 70% é uma aproximação. O resultado real "
        "depende da eficiência específica de cada veículo."
    )


def render_municipality_analysis(
    municipality_data: pd.DataFrame,
) -> None:
    """Render the time-adjusted municipality price index."""
    st.subheader("Comparação ajustada entre municípios")

    selected_product_label = st.radio(
        "Combustível",
        options=["Gasolina", "Etanol"],
        horizontal=True,
        key="municipality_product",
    )

    selected_product = (
        "GASOLINA"
        if selected_product_label == "Gasolina"
        else "ETANOL"
    )

    ranking = build_municipality_ranking(
        municipality_data,
        product=selected_product,
    )

    chart_data = ranking.copy()

    chart_data["position"] = chart_data[
        "median_relative_price_pct"
    ].apply(
        lambda value: (
            "Abaixo da referência"
            if value < 0
            else "Acima da referência"
        )
    )

    figure = px.bar(
        chart_data,
        x="median_relative_price_pct",
        y="municipality",
        orientation="h",
        color="position",
        color_discrete_map={
            "Abaixo da referência": "#16A34A",
            "Acima da referência": "#DC2626",
        },
        labels={
            "median_relative_price_pct": (
                "Diferença mediana para a referência estadual (%)"
            ),
            "municipality": "Município",
            "position": "Posição",
        },
        hover_data={
            "observations": True,
            "weeks": True,
            "stations": True,
            "median_price": ":.2f",
        },
    )

    figure.add_vline(
        x=0,
        line_dash="dash",
        line_color="#475569",
    )

    figure.update_layout(
        height=max(500, len(chart_data) * 25),
        legend_title_text="",
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )

    cheapest = ranking.iloc[0]
    most_expensive = ranking.iloc[-1]

    insight_columns = st.columns(2)

    insight_columns[0].success(
        f"Menor índice relativo: "
        f"{cheapest['municipality']} "
        f"({cheapest['median_relative_price_pct']:.2f}%)"
    )

    insight_columns[1].error(
        f"Maior índice relativo: "
        f"{most_expensive['municipality']} "
        f"(+{most_expensive['median_relative_price_pct']:.2f}%)"
    )

    st.caption(
        "O índice compara cada município com a referência estadual "
        "nas mesmas semanas. Ele reduz o viés provocado por períodos "
        "de cobertura diferentes."
    )


def render_model_comparison(
    metrics: pd.DataFrame,
) -> None:
    """Render backtesting results and model interpretation."""
    st.subheader("Por que um modelo simples venceu?")

    comparison = build_model_comparison(metrics)

    selected_product_label = st.radio(
        "Resultados do produto",
        options=["Gasolina", "Etanol"],
        horizontal=True,
        key="model_product",
    )

    selected_product = (
        "GASOLINA"
        if selected_product_label == "Gasolina"
        else "ETANOL"
    )

    filtered = comparison.loc[
        comparison["product"].eq(selected_product)
    ].copy()

    figure = px.bar(
        filtered.sort_values("mae", ascending=False),
        x="mae",
        y="model_label",
        orientation="h",
        color="rank",
        color_continuous_scale="Blues_r",
        labels={
            "mae": "MAE (R$/litro)",
            "model_label": "Modelo",
            "rank": "Posição",
        },
        text="mae",
    )

    figure.update_traces(
        texttemplate="R$ %{text:.4f}",
        textposition="outside",
    )

    figure.update_layout(
        height=390,
        coloraxis_showscale=False,
        margin={"l": 20, "r": 40, "t": 30, "b": 20},
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )

    display_table = filtered[
        [
            "rank",
            "model_label",
            "mae",
            "rmse",
            "wape_pct",
            "bias",
            "folds",
        ]
    ].rename(
        columns={
            "rank": "Posição",
            "model_label": "Modelo",
            "mae": "MAE",
            "rmse": "RMSE",
            "wape_pct": "WAPE (%)",
            "bias": "Viés",
            "folds": "Janelas",
        }
    )

    st.dataframe(
        display_table.style.format(
            {
                "MAE": "R$ {:.4f}",
                "RMSE": "R$ {:.4f}",
                "WAPE (%)": "{:.2f}%",
                "Viés": "R$ {:.4f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    winner = filtered.loc[
        filtered["rank"].eq(1)
    ].iloc[0]

    st.markdown(
        f"""
        <div class="method-box">
            <strong>Modelo selecionado:</strong>
            {winner["model_label"]}<br>
            <strong>MAE:</strong> {format_brl(winner["mae"])} por litro<br><br>
            Os preços semanais apresentam forte persistência.
            Os modelos mais complexos aumentaram o erro e não
            justificaram sua complexidade operacional.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_methodology() -> None:
    """Render methodology, limitations, and portfolio context."""
    st.subheader("Metodologia e limitações")

    with st.expander(
        "Como a validação foi realizada",
        expanded=False,
    ):
        st.markdown(
            """
            - Treino inicial com 52 semanas.
            - Teste com as quatro semanas seguintes.
            - Avanço de quatro semanas entre as janelas.
            - Janela de treinamento crescente.
            - 19 janelas avaliadas por produto.
            - 76 previsões por modelo e produto.
            - Nenhuma divisão aleatória dos dados.
            - Todas as características utilizam apenas informações
              disponíveis antes da semana prevista.
            """
        )

    st.markdown(
        """
        <div class="limitation-box">
            <strong>Principal limitação operacional:</strong>
            o modelo de persistência não antecipa mudanças abruptas.
            Quando ocorre um choque de preço, sua reação acontece com
            uma semana de atraso. A previsão deve apoiar decisões,
            não ser tratada como garantia do preço futuro.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <br>
        <span class="small-note">
            Outras limitações: histórico inferior a três anos,
            ausência de petróleo, câmbio, inflação e impostos como
            variáveis externas, cobertura variável da pesquisa da ANP
            e previsão da mediana estadual em vez de postos individuais.
        </span>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    """Render project information in the sidebar."""
    with st.sidebar:
        st.header("Sobre o projeto")

        st.write(
            "Projeto de ciência de dados de ponta a ponta "
            "construído com dados públicos da ANP."
        )

        st.markdown(
            """
            **Fluxo implementado**

            1. Coleta rastreável
            2. Auditoria dos dados brutos
            3. Limpeza e validação
            4. Análise exploratória
            5. Engenharia de características
            6. Backtesting temporal
            7. Aplicação prática
            """
        )

        st.divider()

        st.markdown(
            "[Repositório no GitHub]"
            "(https://github.com/"
            "AlexandreSantosRodrigues/"
            "fuel-price-intelligence-rj)"
        )

        st.caption(
            "Os dados exibidos são artefatos versionados "
            "e reproduzíveis do pipeline."
        )


def main() -> None:
    """Run the Streamlit dashboard."""
    render_sidebar()
    render_header()

    try:
        data = get_dashboard_data()
    except (FileNotFoundError, ValueError) as error:
        st.error(
            "Não foi possível carregar os relatórios "
            "necessários para o painel."
        )
        st.exception(error)
        st.stop()

    snapshot = build_current_snapshot(data["weekly"])

    render_snapshot(snapshot)

    st.divider()

    render_recent_history(data["weekly"])

    st.divider()

    render_competitiveness(
        data["competitiveness"]
    )

    st.divider()

    render_municipality_analysis(
        data["municipality"]
    )

    st.divider()

    render_model_comparison(data["metrics"])

    st.divider()

    render_methodology()


if __name__ == "__main__":
    main()