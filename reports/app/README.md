# Aplicação Fuel Price Intelligence RJ

## Objetivo

A aplicação transforma os resultados do pipeline de dados e do backtesting em uma ferramenta acessível para acompanhamento dos preços de gasolina comum e etanol no estado do Rio de Janeiro.

O painel foi construído com Streamlit e utiliza somente artefatos analíticos versionados no repositório. Dessa forma, o deploy não depende dos arquivos brutos ou processados, que são maiores e permanecem fora do controle de versão.

## Funcionalidades

- consulta da última mediana semanal estadual;
- previsão do preço da próxima semana;
- histórico interativo de 12, 26, 52 ou 104 semanas;
- comparação da competitividade entre etanol e gasolina;
- índice municipal ajustado pelo contexto temporal;
- comparação dos modelos avaliados;
- apresentação das métricas do backtesting;
- explicação da metodologia e das limitações.

## Previsão apresentada

O modelo implantado é o baseline de persistência:

> Previsão da próxima semana = último preço semanal conhecido.

A simplicidade do modelo foi uma escolha orientada pelas evidências. Durante o backtesting temporal, ele apresentou o menor MAE para gasolina e etanol, superando:

- Regressão Ridge;
- Random Forest;
- HistGradientBoosting.

Implantar um modelo mais complexo elevaria o custo de manutenção sem produzir ganho preditivo.

## Métricas do modelo selecionado

| Produto | MAE | RMSE | WAPE | Janelas vencidas |
|---|---:|---:|---:|---:|
| Etanol | R$ 0,0318 | R$ 0,0506 | 0,68% | 14 de 19 |
| Gasolina | R$ 0,0301 | R$ 0,0645 | 0,48% | 17 de 19 |

Os resultados foram obtidos com janela de treino crescente:

- treino inicial: 52 semanas;
- teste por janela: 4 semanas;
- avanço: 4 semanas;
- janelas por produto: 19;
- divisão aleatória: não.

## Fontes utilizadas pela aplicação

| Arquivo | Uso |
|---|---|
| `reports/eda/weekly_price_summary.csv` | Histórico e preço atual |
| `reports/eda/ethanol_competitiveness.csv` | Comparação etanol/gasolina |
| `reports/eda/municipality_price_index.csv` | Índice municipal ajustado |
| `reports/modeling/model_metrics.csv` | Comparação dos modelos |

## Arquitetura

```text
Relatórios versionados
        |
        v
src/app/data.py
Leitura, validação e transformação
        |
        v
app.py
Interface Streamlit e visualizações
        |
        v
Usuário final
```

A lógica de preparação dos dados está separada da interface. Isso facilita testes, manutenção e reutilização.

## Execução local ou no Codespaces

```bash
.venv/bin/python -m streamlit run app.py
```

O aplicativo será disponibilizado na porta `8501`.

## Testes

A camada de dados possui testes para:

- leitura dos relatórios;
- validação dos esquemas;
- conversão das datas;
- seleção da semana mais recente;
- geração da previsão de persistência;
- classificação dos modelos por MAE;
- ordenação do índice municipal.

Execute:

```bash
.venv/bin/python -m pytest -q -W error
```

## Limitações

- O modelo prevê a mediana estadual, não preços de postos individuais.
- A previsão de persistência reage aos choques com uma semana de atraso.
- O histórico disponível possui menos de três anos.
- Variáveis externas como petróleo, câmbio, inflação e impostos ainda não foram incorporadas.
- A cobertura dos municípios e postos varia ao longo do tempo.
- A regra de 70% para o etanol é uma aproximação e depende do veículo.

## Uso responsável

As previsões são estimativas baseadas no histórico disponível. Elas apoiam análise e monitoramento, mas não garantem preços futuros nem substituem decisões individuais de abastecimento.