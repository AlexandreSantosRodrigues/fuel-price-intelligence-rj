# Comparação de modelos para previsão semanal

## Objetivo

Esta etapa compara diferentes abordagens para prever a mediana estadual do preço de gasolina comum e etanol com horizonte de uma semana.

O objetivo não é escolher o modelo mais complexo, mas identificar a abordagem que apresenta menor erro em dados futuros simulados por backtesting.

## Estratégia de validação

Foi utilizado backtesting com janela de treino crescente:

| Configuração | Valor |
|---|---:|
| Treino inicial | 52 semanas |
| Horizonte de teste por janela | 4 semanas |
| Avanço entre janelas | 4 semanas |
| Janelas por produto | 19 |
| Previsões por modelo e produto | 76 |
| Divisão aleatória | Não |

Em cada rodada:

1. o modelo é treinado somente com semanas passadas;
2. as quatro semanas seguintes são usadas como teste;
3. a janela de treino é ampliada;
4. o processo é repetido até o fim da série.

Essa estratégia representa melhor o uso real do modelo e evita vazamento temporal.

## Modelos comparados

### Baseline: último preço conhecido

Utiliza o preço da semana anterior como previsão da próxima semana.

Esse modelo representa a hipótese de persistência:

> o preço da próxima semana será igual ao último preço confiável observado.

### Ridge

Regressão linear regularizada com padronização das características.

Foi escolhida como modelo linear capaz de combinar tendência, sazonalidade, defasagens e médias móveis, reduzindo parcialmente problemas de multicolinearidade.

### Random Forest

Modelo de árvores com limitação de profundidade e quantidade mínima de observações por folha.

Foi incluído para avaliar relações não lineares e interações entre as características.

### HistGradientBoosting

Modelo de boosting baseado em árvores, com regularização e configuração conservadora para reduzir sobreajuste.

## Métricas

- **MAE:** erro absoluto médio em reais por litro.
- **RMSE:** penaliza com maior intensidade os erros grandes.
- **WAPE:** erro absoluto total dividido pelo preço total observado.
- **Viés:** média da previsão menos o valor real. Valores negativos indicam tendência de subestimação.

## Resultados do etanol

| Modelo | MAE | RMSE | WAPE | Viés | Diferença para o baseline |
|---|---:|---:|---:|---:|---:|
| Último preço | R$ 0,0318 | R$ 0,0506 | 0,6753% | -R$ 0,0020 | Referência |
| Ridge | R$ 0,0518 | R$ 0,0728 | 1,0983% | R$ 0,0099 | 62,63% pior |
| HistGradientBoosting | R$ 0,0704 | R$ 0,0915 | 1,4942% | -R$ 0,0246 | 121,25% pior |
| Random Forest | R$ 0,0786 | R$ 0,1009 | 1,6673% | -R$ 0,0258 | 146,88% pior |

### Vitórias por janela no etanol

| Modelo | Janelas vencidas |
|---|---:|
| Último preço | 14 |
| Ridge | 2 |
| HistGradientBoosting | 2 |
| Random Forest | 1 |

## Resultados da gasolina

| Modelo | MAE | RMSE | WAPE | Viés | Diferença para o baseline |
|---|---:|---:|---:|---:|---:|
| Último preço | R$ 0,0301 | R$ 0,0645 | 0,4806% | -R$ 0,0053 | Referência |
| Ridge | R$ 0,0494 | R$ 0,0812 | 0,7874% | R$ 0,0048 | 63,85% pior |
| Random Forest | R$ 0,0612 | R$ 0,1262 | 0,9756% | -R$ 0,0237 | 103,01% pior |
| HistGradientBoosting | R$ 0,0690 | R$ 0,1286 | 1,1009% | -R$ 0,0326 | 129,09% pior |

### Vitórias por janela na gasolina

| Modelo | Janelas vencidas |
|---|---:|
| Último preço | 17 |
| Random Forest | 2 |
| Ridge | 0 |
| HistGradientBoosting | 0 |

## Modelo selecionado

O baseline do último preço foi selecionado para os dois combustíveis.

| Produto | Modelo selecionado | MAE | WAPE |
|---|---|---:|---:|
| Etanol | Último preço | R$ 0,0318 | 0,6753% |
| Gasolina | Último preço | R$ 0,0301 | 0,4806% |

A escolha do baseline não representa ausência de modelagem. Ela é resultado de uma comparação temporal entre abordagens de diferentes complexidades.

Implantar um modelo mais complexo, mesmo após ele apresentar desempenho inferior, aumentaria o custo operacional sem produzir ganho preditivo.

## Por que o baseline venceu?

Os preços semanais apresentam alta persistência. Na maior parte das semanas, a mediana muda pouco em relação à semana anterior.

As características históricas carregam informações semelhantes ao último preço. Como o conjunto possui apenas 128 exemplos por produto, modelos mais flexíveis também possuem maior risco de aprender ruído.

Os modelos de árvore possuem outra limitação importante: eles não extrapolam tendências com facilidade. Quando o nível dos preços aumenta para uma faixa ainda não observada durante o treino, esses modelos tendem a produzir previsões abaixo dos valores reais.

Isso aparece nos vieses negativos:

- Random Forest no etanol: -R$ 0,0258;
- HistGradientBoosting no etanol: -R$ 0,0246;
- Random Forest na gasolina: -R$ 0,0237;
- HistGradientBoosting na gasolina: -R$ 0,0326.

## Análise dos maiores erros

### Etanol

| Semana | Real | Previsto | Erro absoluto |
|---|---:|---:|---:|
| 04/05/2026 | R$ 4,99 | R$ 5,14 | R$ 0,15 |
| 04/08/2025 | R$ 4,39 | R$ 4,49 | R$ 0,10 |
| 08/12/2025 | R$ 4,69 | R$ 4,59 | R$ 0,10 |
| 23/03/2026 | R$ 5,19 | R$ 5,09 | R$ 0,10 |
| 18/05/2026 | R$ 4,89 | R$ 4,99 | R$ 0,10 |

### Gasolina

| Semana | Real | Previsto | Erro absoluto |
|---|---:|---:|---:|
| 23/03/2026 | R$ 6,79 | R$ 6,49 | R$ 0,30 |
| 16/03/2026 | R$ 6,49 | R$ 6,29 | R$ 0,20 |
| 13/07/2026 | R$ 6,59 | R$ 6,79 | R$ 0,20 |
| 05/01/2026 | R$ 6,19 | R$ 6,03 | R$ 0,16 |
| 09/06/2025 | R$ 6,09 | R$ 6,19 | R$ 0,10 |

Os maiores erros ocorrem quando há mudanças abruptas entre semanas. Como o baseline assume persistência, ele reage com uma semana de atraso a choques de preço.

## Limitações

- A série possui somente 128 exemplos de modelagem por produto.
- O histórico cobre menos de três anos.
- Variáveis externas, como petróleo, câmbio, inflação e impostos, ainda não foram incorporadas.
- O baseline não antecipa choques e mudanças estruturais.
- O desempenho histórico não garante o mesmo erro no futuro.
- As métricas representam a mediana estadual e não previsões por posto ou município.

## Monitoramento recomendado

Após a implantação:

1. registrar cada previsão e o valor posteriormente observado;
2. recalcular MAE, RMSE, WAPE e viés;
3. comparar continuamente com o baseline;
4. detectar aumento persistente de erro;
5. retreinar ou revisar as características quando necessário;
6. promover um modelo challenger somente se ele superar o baseline de forma consistente.

## Artefatos

- [`model_metrics.csv`](model_metrics.csv)
- [`backtest_predictions.csv`](backtest_predictions.csv)
- [`model_report.json`](model_report.json)
- Implementação: `src/modeling/backtesting.py`
- Execução: `scripts/train_models.py`
- Testes: `tests/test_backtesting.py`

## Reprodução

```bash
.venv/bin/python -m scripts.train_models