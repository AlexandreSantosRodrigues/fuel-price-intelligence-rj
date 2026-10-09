# Engenharia de características para previsão semanal

## Problema preditivo

O objetivo é prever a mediana estadual do preço de cada combustível na próxima semana.

Cada linha da tabela de modelagem representa:

- um produto;
- uma semana-alvo;
- o preço mediano observado nessa semana;
- características construídas exclusivamente com informações disponíveis antes da semana-alvo.

Essa estrutura permite simular uma previsão real: ao prever uma semana, o modelo não pode conhecer nenhum preço coletado durante ou depois dela.

## Unidade de análise

| Campo | Definição |
|---|---|
| Produto | Gasolina comum ou etanol |
| Frequência | Semanal |
| Abrangência | Estado do Rio de Janeiro |
| Variável-alvo | Mediana estadual do preço de venda |
| Horizonte | Uma semana à frente |

## Resultado do processamento

| Indicador | Resultado |
|---|---:|
| Registros individuais de origem | 83.441 |
| Linhas semanais observadas | 282 |
| Linhas após regularização do calendário | 288 |
| Semanas ausentes adicionadas ao calendário | 6 |
| Alvos excluídos por baixa cobertura | 2 |
| Linhas disponíveis para modelagem | 256 |
| Linhas de etanol | 128 |
| Linhas de gasolina | 128 |
| Quantidade de características | 21 |
| Início da tabela de modelagem | 25/03/2024 |
| Final da tabela de modelagem | 28/09/2026 |

## Tratamento das lacunas

Foram identificadas três semanas ausentes para cada produto:

- 06/04/2026;
- 13/04/2026;
- 20/04/2026.

Também foi identificada baixa cobertura na semana de 27/04/2026:

- 9 observações de etanol;
- 10 observações de gasolina.

A cobertura típica semanal é muito superior:

- mediana de 283 observações para etanol;
- mediana de 319 observações para gasolina.

Por isso, a semana de 27/04/2026 foi excluída como variável-alvo.

As semanas ausentes e de baixa cobertura são preenchidas somente na série histórica utilizada para construir as defasagens. O preenchimento é causal: utiliza exclusivamente o último preço confiável conhecido.

Valores futuros não são usados para interpolar o passado.

## Características criadas

### Defasagens de preço

- `lag_1`
- `lag_2`
- `lag_4`
- `lag_8`
- `lag_12`

Representam o preço observado uma, duas, quatro, oito e doze semanas antes da semana-alvo.

### Médias móveis

- `rolling_mean_4`
- `rolling_mean_8`
- `rolling_mean_12`

Representam o nível recente dos preços em diferentes janelas temporais.

### Volatilidade histórica

- `rolling_std_4`
- `rolling_std_8`
- `rolling_std_12`

Medem a variação recente dos preços.

### Variações recentes

- `price_change_1`
- `price_change_4`

Representam mudanças de curto e médio prazo em relação ao último preço conhecido.

### Cobertura da pesquisa anterior

- `observation_count_lag_1`
- `station_count_lag_1`

Registram a quantidade de observações e postos disponíveis na semana anterior.

### Calendário

- `year`
- `month`
- `week_of_year`
- `week_sin`
- `week_cos`
- `trend`

As transformações seno e cosseno representam a natureza cíclica das semanas do ano. A variável de tendência representa a passagem do tempo.

## Controles contra vazamento de dados

1. Todas as defasagens utilizam somente semanas anteriores.
2. As médias e os desvios móveis são calculados após deslocar a série em uma semana.
3. A variável-alvo da semana atual nunca participa das próprias características.
4. Semanas ausentes não são criadas como alvos artificiais.
5. Semanas com cobertura inferior a 50% da cobertura típica não são usadas como alvos.
6. A validação dos modelos deverá respeitar a ordem temporal.
7. Divisões aleatórias entre treino e teste são proibidas.

## Decisões de modelagem

O conjunto possui somente 128 exemplos por produto. Portanto:

- modelos excessivamente complexos apresentam alto risco de sobreajuste;
- modelos simples serão usados como referência;
- todos os modelos deverão superar o baseline do último preço conhecido;
- o desempenho será estimado com backtesting temporal;
- os resultados serão apresentados separadamente por produto.

## Artefatos

- Tabela de modelagem: `data/processed/weekly_forecast_features.parquet`
- Relatório estruturado: [`feature_report.json`](feature_report.json)
- Implementação: `src/features/forecast.py`
- Execução: `scripts/build_forecast_features.py`
- Testes: `tests/test_forecast_features.py`

## Reprodução

```bash
.venv/bin/python -m scripts.build_forecast_features