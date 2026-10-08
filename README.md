# Fuel Price Intelligence RJ

Pipeline de dados e Machine Learning para monitoramento, análise e previsão dos preços de combustíveis no estado do Rio de Janeiro, usando dados públicos e reais da Agência Nacional do Petróleo, Gás Natural e Biocombustíveis (ANP).

> Status: em desenvolvimento — Etapa 1, fundação e coleta de dados.

## Problema de negócio

Gestores, consumidores e profissionais do setor de energia precisam acompanhar mudanças de preços, comparar municípios e antecipar movimentos de curto prazo. O projeto buscará responder:

**Qual deverá ser o preço médio da gasolina comum e do etanol nas próximas quatro semanas nos municípios analisados do Rio de Janeiro?**

## Objetivos

- Coletar dados brutos diretamente da fonte pública.
- Preservar os arquivos originais para rastreabilidade.
- Validar, limpar e padronizar dados inconsistentes.
- Explorar preços, cobertura, dispersão e comportamento temporal.
- Construir variáveis temporais sem vazamento de dados.
- Comparar baselines e modelos de Machine Learning.
- Avaliar os resultados com validação temporal e análise de erros.
- Publicar uma aplicação interativa para consulta das previsões.

## Arquitetura planejada

```text
ANP (CSV bruto)
    ↓
data/raw             dados originais e imutáveis
    ↓
data/interim         dados normalizados e validados
    ↓
data/processed       tabelas analíticas e features
    ↓
models               artefatos treinados
    ↓
app                   visualização e previsões
```

## Fluxo do projeto

1. Coleta e catalogação dos arquivos da ANP
2. Auditoria de qualidade
3. Limpeza e padronização
4. Análise exploratória
5. Consultas e transformações SQL com DuckDB
6. Engenharia de características
7. Baselines e modelos
8. Validação temporal
9. Análise e interpretação dos erros
10. Aplicação Streamlit e automação

## Tecnologias

- Python
- Pandas
- DuckDB
- scikit-learn
- Plotly
- Streamlit
- Pytest
- GitHub Actions

## Princípios

- Os dados brutos nunca serão alterados.
- Transformações importantes serão implementadas em módulos Python, não apenas em notebooks.
- O teste final sempre representará um período futuro.
- Modelos complexos somente serão adotados se superarem baselines simples.
- Resultados serão explicados também em linguagem de negócio.
- Limitações e incertezas serão documentadas.

## Estrutura

```text
├── app/                 aplicação Streamlit
├── configs/             parâmetros e fontes
├── data/
│   ├── raw/             arquivos originais
│   ├── interim/         dados validados
│   ├── processed/       tabelas analíticas
│   └── rejected/        registros rejeitados
├── models/              modelos e metadados
├── notebooks/           investigação e experimentos
├── reports/figures/     gráficos exportados
├── src/                 pipeline reutilizável
├── tests/               testes automatizados
├── requirements.txt
└── README.md
```

## Fonte dos dados

Série Histórica de Preços de Combustíveis da ANP:

https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/serie-historica-de-precos-de-combustiveis

## Próxima etapa

Implementar a coleta reproduzível, baixar os primeiros arquivos brutos e produzir um relatório inicial de auditoria.

## Autor

Alexandre Santos Rodrigues
