# E-2 — Representação lexical: o que ganha, e por que nada foi adotado

E-1 concluiu que o ganho disponível estava na **tokenização**, não no ranking. E-2 testou isso
mantendo o scorer intocado e variando apenas o tokenizer, de modo que qualquer delta é atribuível
à representação lexical e a mais nada.

O resultado é um `PASS_DEFER_ARCHITECTURE`: a hipótese se confirmou com folga — e a adoção esbarrou
numa restrição de arquitetura que a própria medição revelou.

## Método

Cada variante é um `Engine` real, mesmo corpus de 520 documentos, mesmas 170 consultas, mesmo
ground truth independente, **mesmo scorer**. Transformações medidas isoladamente (§7), nunca
empilhadas por padrão: `plural + aliases` é uma hipótese diferente de cada uma das partes.

## Matriz global

| variante | P@1 | MRR | nDCG@10 | Δ | p50 | termos |
|---|---|---|---|---|---|---|
| **A** baseline (E-1) | 0,524 | 0,537 | 0,537 | — | 8,6 ms | 19.913 |
| B1 folding de acentos | 0,524 | 0,537 | 0,537 | +0,000 | 20,6 ms | 19.913 |
| **B2 normalização de plural** | 0,576 | 0,591 | 0,588 | **+0,051** | 10,2 ms | **19.913** |
| B3 possessivos | 0,524 | 0,538 | 0,538 | +0,000 | 9,3 ms | 19.913 |
| B4 compostos com hífen | 0,524 | 0,534 | 0,536 | −0,001 | 18,7 ms | 21.307 |
| C1 aliases (explícitos) | 0,541 | 0,559 | 0,547 | +0,010 | 10,5 ms | 21.593 |
| C2 aliases (+ paráfrase) | 0,565 | 0,584 | 0,577 | +0,040 | 10,7 ms | 23.227 |
| D3 char 3-grams | 0,582 | 0,606 | 0,603 | +0,066 | 39,9 ms | 89.184 |
| D4 char 4-grams | 0,600 | 0,627 | 0,627 | +0,090 | 31,1 ms | 72.453 |
| **D5 char 5-grams** | 0,600 | 0,624 | **0,635** | **+0,098** | 24,3 ms | 57.121 |
| E compor tudo | 0,576 | 0,597 | 0,596 | +0,059 | **425,5 ms** | **634.194** |
| E2 plural + alias | 0,588 | 0,605 | 0,592 | +0,055 | 12,3 ms | 22.673 |

## Por categoria (nDCG@10)

| variante | exato | morfologia | sinônimo | paráfrase | cross-ling | temporal | conflito | crossref | advers. |
|---|---|---|---|---|---|---|---|---|---|
| A baseline | 1,000 | 0,056 | 0,025 | 0,237 | 0,073 | 1,000 | 1,000 | 1,000 | 1,000 |
| B2 plural | 1,000 | **0,520** | 0,043 | 0,238 | 0,066 | 1,000 | 1,000 | 1,000 | 1,000 |
| C2 aliases+para | 1,000 | 0,052 | **0,000** | **0,458** | 0,104 | 1,000 | 1,000 | 1,000 | 0,997 |
| D5 5-grams | 1,000 | **0,904** | 0,067 | **0,200** | 0,177 | 1,000 | 1,000 | 1,000 | 1,000 |

## Regression matrix — categorias críticas

**Nenhuma variante regrediu `exact`, `temporal`, `conflict` ou `crossref`.** Todas em ±0,000. O
scorer permaneceu intocado, e são os componentes temporal/exato/autoridade que sustentam essas
categorias — o que confirma, do outro lado, o diagnóstico do E-1 sobre por que substituir o scorer
por BM25 as derrubava.

Regressões **não-críticas**, que a média global esconderia:

- **C1/C2/E2 zeram `synonym`** (0,025 → 0,000). Aliases puxam muitos documentos do mesmo conceito e
  afundam o único que enuncia o termo.
- **D3 derruba `paraphrase`** (0,237 → 0,116) e **D5 também** (→ 0,200). N-grams compram morfologia
  vendendo paráfrase.
- **B2 arranha `crosslingual`** (0,073 → 0,066).

## Composição não soma — cancela

`E` (todos os vencedores juntos) dá **+0,059**, *pior* que D5 sozinho (+0,098), com **425 ms** de
latência (50×) e **634 mil termos** (32×). Empilhar transformações que individualmente ganham
produziu um resultado pior e caríssimo. Registrado porque é contraintuitivo e teria sido adotado
por plausibilidade.

## Por que nada entrou no core

`Engine.open(None)` (memória) usa o retriever de varredura, Python puro. Com SQLite, o índice FTS5
tokeniza **do lado do banco**, e o `tokenize=` é fixo no `CREATE`. Um tokenizer Python que
normaliza plurais mas declara `fts_tokenize="ascii"` faz o FTS guardar `audits` enquanto a consulta
pede `audit`:

```
tokenizer.tokens('Several audits') = ['several', 'audit']
fts_tokenize declarado             = ascii
consulta 'audits'  ->  indexed=0   scan=1     PARIDADE QUEBRADA
```

Isso viola `RETRIEVAL_SEMANTIC_PARITY` (ADR-021), um gate que o projeto já tem: a varredura é a
referência de correção e o índice é otimização; se discordam, um dos dois está mentindo sobre o
conteúdo do corpus.

O SQLite não oferece tokenizer que normalize plurais, então a transformação **não pode ser
empurrada para baixo**. A implementação correta é gravar texto já normalizado no conteúdo do FTS —
o que muda o que é indexado, exige rebuild completo e altera a verificação de deriva de conteúdo.
É migração, não patch.

`DEFERRED_PENDING_ARCHITECTURAL_REVIEW` (§10). O achado está travado em teste
(`test_a_tokenizer_sqlite_cannot_reproduce_breaks_parity`) para que ninguém readote por acidente.

## O que foi adotado

Só uma coisa, e ela veio da medição: **o receipt agora sela `lexical_variant`**. E-2 mediu o mesmo
scorer devolvendo rankings materialmente diferentes conforme o tokenizer (morfologia 0,056 → 0,904).
Um recibo que nomeava o scorer mas omitia a representação nomearia a função de ranking escondendo a
entrada dela — e não seria replicável.

## Recomendação

Quando a migração de índice for autorizada, **B2 (normalização de plural) é a candidata**, não D5:
+0,051 com **zero crescimento de índice**, +1,6 ms, e a única variante que não regride categoria
alguma. D5 ganha o dobro mas custa 2,87× índice, 2,8× latência e regride paráfrase — é
`QUALITY_WIN_WITH_COST` (§15), não um vencedor limpo.
