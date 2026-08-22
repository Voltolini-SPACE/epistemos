# E-3 — A representação indexada, e a migração que a torna adotável

E-2 mediu um ganho real na normalização de plural e **não pôde adotá-lo**: o `tokenize=` do FTS5 é
fixo no `CREATE`, então uma transformação que o SQLite não sabe expressar fazia o índice e a
varredura responderem a mesma pergunta de forma diferente.

E-3 move a transformação **para cima** em vez de para baixo: o texto normalizado é o que se
persiste, o SQLite tokeniza conteúdo já normalizado, e uma consulta normalizada da mesma forma
casa com ele.

## O contrato novo

`Tokenizer.normalize_text(text) -> str` — a representação **persistida** no índice. O padrão é
identidade, então todo tokenizer anterior ao E-3 grava exatamente os mesmos bytes de antes: zero
migração, zero mudança de comportamento.

`PLURAL` (`tokenizer="plural"`) é a candidata B2 promovida a produção. Não é um stemmer — remove
um marcador de plural final e nada mais, com uma lista explícita de exceções (`status`, `analysis`,
`access`, `process`, `always`…) que um revisor consegue ler e refutar.

## Gate executado: MIGRATE → REBUILD → VERIFY → PARITY → BENCHMARK → DECIDE

### PARITY — com controle

Corpus completo do E-1, 448 documentos, 170 consultas, `limit=1000` para medir **recall** e não
ranking (os dois retrievers usam componentes lexicais diferentes por design, então ordem idêntica
nunca foi o contrato):

| tokenizer | consultas divergentes | documentos só na varredura |
|---|---|---|
| `ascii` (referência entregue) | **0 / 170** | 0 |
| `plural` (E-3, normalizado) | **0 / 170** | 0 |
| E-2 sem `normalize_text` (**controle**) | **15 / 170** | **575** |

O controle é o que torna isso convincente: a mesma transformação quebra sem a correção e sustenta
com ela.

### REBUILD

Reconstruir do ledger três vezes produz o índice byte a byte idêntico, e os resultados de consulta
antes e depois do rebuild são iguais. Sem isso, `verify()` estaria medindo ruído e uma migração
nunca poderia ser declarada completa.

### VERIFY — quatro camadas explícitas

`verify_detail()` não devolve só um booleano. Um booleano diz que o índice está consistente; não
diz consistente **com o quê** — e desde o E-3 o conteúdo indexado é uma representação, não o texto
do objeto. O relatório expõe `original` · `normalized` · `indexed` · `tokens`, e quando falha nomeia
os primeiros divergentes em vez de mandar o leitor comparar dois bancos à mão.

### MIGRATE — base existente, sem índice meio-antigo

Uma base escrita em `ascii` e reaberta em `plural` é reconstruída por inteiro: `DROP TABLE` +
`DELETE FROM fts_map` + rebuild. Um índice parcialmente migrado responderia algumas consultas na
representação antiga e outras na nova — pior que índice nenhum. Provado por teste: **toda** linha
indexada satisfaz `content == normalize_text(content)` após a migração, e o nome do tokenizer fica
gravado em `meta` para que a próxima abertura não reconstrua de novo.

### ROLLBACK — fail-closed

Se o rebuild produzir algo que não verifica, o índice fica `DEGRADED` e o nome do novo tokenizer
**não é gravado**. A engine cai para a varredura — correta, apenas mais lenta — e a próxima
abertura tenta migrar de novo em vez de acreditar que já migrou.

### BENCHMARK — só depois da paridade verde

Caminho indexado (SQLite/FTS), 448 documentos, 170 consultas:

| | ascii | plural | Δ |
|---|---|---|---|
| P@1 | 0,524 | 0,576 | **+0,053** |
| MRR | 0,538 | 0,590 | **+0,053** |
| nDCG@10 | 0,536 | 0,585 | **+0,049** |
| p50 | 1,48 ms | 1,55 ms | +0,07 ms |
| p95 | 5,66 ms | 5,53 ms | −0,13 ms |
| banco | 1,39 MB | 1,40 MB | +0,7 % |
| linhas indexadas | 448 | 448 | 0 |

Por categoria: **morfologia 0,056 → 0,520** (+0,465). `exact`, `temporal`, `conflict`, `crossref` e
`adversarial` permanecem em **1,000** — zero regressão crítica. Regressões não-críticas, declaradas:
cross-lingual −0,016 e paráfrase −0,004.

O ganho no caminho indexado (+0,049) confirma o que o E-2 mediu no caminho de varredura (+0,051).

## Decisão

`plural` é **opt-in**, não o padrão. Trocar o padrão reescreveria o índice de toda base existente
na próxima abertura, e essa é uma decisão de operação, não de engenharia. O caminho está provado e
a migração é segura; ligar é `Engine.open(path, tokenizer="plural")`.

**D5 (char 5-grams) permanece `QUALITY_WIN_WITH_COST`**, registrada e não adotada: ganha o dobro
(+0,098) mas custa 2,87× índice, 2,8× latência e regride paráfrase.
