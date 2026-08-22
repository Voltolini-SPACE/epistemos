# E-4 — Quanto a semântica acrescenta? Medido: nada adotável.

`DECISION = NO_ADOPTABLE_IMPROVEMENT`

E-3 provou a representação lexical e não foi tocada. E-4 é uma camada acima: reescreve a
**consulta**, nunca o índice, e alimenta o retriever lexical existente. A pergunta era estreita —
sem destruir o ganho do E-3, quanto valor adicional a semântica traz para cross-lingual e sinônimo?

A resposta é **nenhum que passe no portão**, e o diagnóstico é mais útil que o resultado.

## L0 reproduz o estado declarado

| | esperado | obtido |
|---|---|---|
| global nDCG@10 | 0,585 | **0,585** |
| morfologia | 0,520 | **0,520** |
| cross-lingual | 0,057 | **0,057** |
| sinônimo | 0,026 | 0,029 |

## Ablação

| condição | nDCG@10 | Δ | cross-lingual | sinônimo | críticas pioradas |
|---|---|---|---|---|---|
| **L0** lexical | 0,586 | — | 0,057 | 0,030 | — |
| **L1** expansão minerada | 0,554 | **−0,032** | +0,038 | **−0,013** | temporal, crossref, adversarial |
| **L2** distribucional | 0,569 | **−0,017** | **+0,067** | **−0,013** | temporal, conflict, adversarial |
| **L3** ambos | 0,552 | **−0,033** | +0,032 | −0,013 | exact, temporal, conflict, adversarial |
| **XC** teto escrito à mão *(experimental)* | 0,594 | +0,008 | **+0,000** | **+0,146** | exact, crossref, adversarial |

**Nenhuma condição é elegível.** Toda expansão alarga a consulta, e alargar custa precisão
exatamente onde o sistema era perfeito.

## O diagnóstico está nos recibos

```
L1 minerado : 'retention period' -> +[again, came, mentioned, budget, change, declared]
L2 distrib. : 'card authorisation' -> +[payments, api]
XC teto     : 'retention period' -> +[janela, retencao, retencion, ventana, window]
```

Três mecanismos, três coisas diferentes:

- **O corpus não sabe sinonímia.** A mineração por PMI encontrou co-ocorrência — e no nosso corpus
  isso significa os documentos de rascunho, que repetem vocabulário sem afirmar nada. 263 entradas,
  majoritariamente ruído. Por isso sinônimo **piorou**.
- **Distribucional acha entidade, não tradução.** `card authorisation` → `payments api`. Isso puxa
  os documentos em português do mesmo serviço, o que explica o melhor ganho cross-lingual (+0,067)
  sem nunca resolver o problema de idioma.
- **Só vocabulário curado resolve sinônimo** (+0,146) — e não faz **nada** por cross-lingual
  (+0,000), porque as consultas cross-lingual usam propósitos de serviço, não os conceitos que o
  teto cobre. Limitação declarada da minha medição de teto: ela mede o teto de **sinônimo**, não o
  de cross-lingual.

**Os dois problemas exigem mecanismos diferentes.** Tratá-los como um só — que era o risco que a
missão nomeou — teria produzido uma solução que não serve a nenhum.

## Sobre a métrica de falso positivo semântico

`FSP` = fração do top-10 fora do conjunto esperado. **Seu valor absoluto é artefato**: conflito tem
exatamente 2 documentos esperados, então com k=10 o melhor resultado possível já é 0,800. Só o
delta entre condições significa algo. Ele subiu em todas: L1 +0,036, L2 +0,046, L3 +0,098 — a
expansão está mesmo trazendo documento errado junto.

## Determinismo

L0, L1, L2 e XC: determinísticos em 3 execuções. **L3 acusou `NON_DETERMINISTIC` uma vez e não
reproduziu** em 3 execuções completas seguintes nem em teste isolado, onde nDCG, MRR e recibos
saíram idênticos. Registro a observação sem explicá-la: pode ser instabilidade da própria
verificação. L3 já é inelegível por outros motivos, então isso não muda a decisão — mas uma
verificação de determinismo intermitente é pior que inútil, e quem retomar isto deve desconfiar
dela antes de desconfiar do L3.

## Dependências

```
NEW_RUNTIME_DEPENDENCIES = 0      NEW_BUILD_DEPENDENCIES = 0
MODEL_SIZE = n/a                  MODEL_SOURCE = nenhum
DISK_COST = 0                     MEMORY_COST = ~265 vetores de termo, em memória, transitórios
```

Nada foi baixado nem instalado. Conforme §12, um candidato que exigisse modelo externo pararia no
diagnóstico — e o diagnóstico diz que o problema de sinônimo é de **vocabulário**, não de modelo:
um léxico bilíngue curado resolveria a maior parte, se houvesse um com origem, licença e cobertura
declaráveis.

## Recomendação

Não perseguir embeddings com base neste resultado. O que E-4 mostra é que **a expansão de consulta
é o mecanismo errado**, porque paga precisão em todas as categorias para comprar recall em duas.
Se cross-lingual e sinônimo forem prioridade, o caminho é *recuperação em duas fases* — os
candidatos semânticos entram numa lista separada, com a lista lexical permanecendo autoritativa e
o resultado semântico rotulado como tal — e não uma consulta alargada que contamina o ranking
único. Isso é uma missão de arquitetura, não de tuning.
