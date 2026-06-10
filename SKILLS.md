# Vigia - Monitor de Vagas da Farmacia

## Objetivo

Monitorar apenas o ultimo Diario Oficial do Municipio de Vila Velha em busca de publicacoes relacionadas a `AGENTE DE FARMACIA`, `CONCURSO` e `PROCESSO SELETIVO`.

## Fonte oficial

- URL: `https://diariooficial.vilavelha.es.gov.br/`
- A consulta e publica e nao exige login.
- O monitor baixa diretamente o PDF da ultima edicao exibida na pagina inicial.

## Regras de deteccao

- Filtros de texto no PDF:
  - `agente de farmacia`
  - `concurso`
  - `processo seletivo`
- O log registra se cada termo apareceu no ultimo diario.

## Estado local

- `ultimo_status.txt` guarda a assinatura JSON do ultimo conjunto de matches.
- `registro` registra a atividade com timestamp.
- O primeiro ciclo apos trocar a logica grava uma base limpa sem disparar alerta falso.

## Fluxo operacional

1. Abre a pagina inicial do diario oficial.
2. Identifica a ultima edicao exibida.
3. Baixa o PDF dessa edicao.
4. Extrai o texto e procura as palavras-chave.
5. Se houver novidade em relacao a base local, envia Telegram e alerta visual no Windows.

## Observacoes

- A autenticacao antiga foi removida.
- Nao ha dependencias de login ou portal privado.
- O foco do monitor e somente a publicacao oficial mais recente da prefeitura.
