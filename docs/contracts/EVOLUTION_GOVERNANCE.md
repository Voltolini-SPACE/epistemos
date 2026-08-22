# Governança do ciclo de evolução

Regra permanente de manutenção, não exigência de uma missão específica. Aplica-se a toda evolução
futura do EPISTEMOS.

## O ciclo

```
INSPECIONAR → VALIDAR → IMPLEMENTAR (se autorizado) → TESTAR → AUDITAR
   → REGISTRAR NO GIT → SINCRONIZAR DOCUMENTAÇÃO/SITE → VALIDAR NOVAMENTE
```

Nenhuma etapa é opcional, e nenhuma pode ser presumida por outra. Em particular: **código correto
não implica documentação correta, e documentação correta não implica site correto.** Cada superfície
é verificada por si.

## O que toda alteração tem de deixar como evidência verificável

| | Evidência |
|---|---|
| o que mudou | diff, contido e sem alterações não relacionadas |
| por que mudou | mensagem de commit que descreve o problema, não só a solução |
| invariantes preservados | quais gates foram executados e o seu resultado real |
| testes/gates executados | saída real, não afirmação — contagem por JUnit XML, não por texto |
| qual commit contém | um commit pequeno e coerente por unidade de mudança |
| doc/site sincronizados | ou a declaração explícita de que não era necessário, e porquê |

## Regras que já custaram caro

Cada uma destas está aqui porque falhou em alguma missão desta linha, não por precaução abstrata.

- **Não anunciar no site o que não está publicado no código.** O site descreve o estado publicado,
  nunca o estado de uma branch. Trabalho em branch não empurrada não existe para o público.
- **Não declarar teste executado sem saída real.** Ferramentas de proxy já reportaram `EXIT=0` para
  comandos que falharam. Contagens vêm de JUnit XML; integridade vem de SHA-256.
- **Manchete tem de bater com a evidência que ela linka.** Um número publicado que aponta para um
  arquivo que mede outra coisa quebra a cadeia claim→evidência — exatamente o que o produto vende.
- **Resultado negativo é resultado.** Registrar a falsificação e seguir. Não transformar evidência
  negativa localizada em teorema arquitetural.
- **Benchmark pequeno lisonjeia.** Uma medição em corpus reduzido não transfere para escala e não
  deve fundamentar decisão irreversível.
- **Corrigir onde a afirmação vive, não só na conversa.** Um overclaim corrigido em prosa mas
  mantido no documento continua em vigor.

## Incremental, rastreável, reversível

Melhorias futuras são incrementais e reversíveis. Uma alteração que não pode ser revertida por um
commit isolado é grande demais e deve ser dividida antes de entrar.

Push é ação externa: exige autorização explícita, por publicação, e nunca é inferido de uma
autorização de implementação.
