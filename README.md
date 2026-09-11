# Panorama Fiscal dos Municípios — publicação e atualização

Painel da Daddus Consultoria com CAPAG, CAUC, SADIPEM, CDP e PPPs (RREO Anexo 13) dos 5.570 municípios.
Este documento é o passo a passo para colocar o painel no ar e mantê-lo atualizado **sem precisar programar**.

## Como a coisa funciona (2 minutos)

```
Tesouro Nacional (CKAN / APIs)                 você (arquivos manuais)
        │                                                │
        ▼                                                ▼
GitHub Actions ──► etl/atualizar.py ──► docs/dados/base.json.gz  +  meta.json
   (toda segunda)                                        │
                                                         ▼
                              GitHub Pages ──► https://SEU-USUARIO.github.io/painel-fiscal/
                                                         │
                                       (opcional) Apps Script: login Google + cópia no Drive
```

- **docs/index.html** é o painel. Ele não carrega dados embutidos: busca `dados/geo.json.gz` (malha do IBGE, fixa)
  e `dados/base.json.gz` (a base, que muda).
- **etl/atualizar.py** reconstrói a base. Com `--baixar`, tenta buscar cada fonte no Tesouro; se uma fonte falha,
  ele usa o arquivo mais recente da pasta `entrada/` e, se também não houver, **mantém a versão anterior daquela camada**
  e registra um aviso em `meta.json`. Uma fonte quebrada nunca derruba o painel inteiro.
- O cabeçalho do painel mostra a data de cada camada. Se uma data não avançou, olhe `meta.json`.

Ritmo de cada fonte: CAPAG é anual (junho, com reposições); CAUC e CDP são mensais; SADIPEM é diário;
PPPs seguem o bimestre do RREO. O agendamento semanal cobre tudo isso.

> **Aviso honesto.** As rotinas de download foram escritas a partir da documentação oficial do Tesouro,
> mas não puderam ser executadas no ambiente em que o painel foi construído. Por isso a **primeira execução**
> deve ser acompanhada (Parte 4). A carga manual (Parte 5) foi testada de ponta a ponta com os arquivos reais
> e é o caminho garantido.

---

## Parte 1 — Conta e repositório no GitHub (10 min)

1. Crie uma conta em **github.com** (gratuita) com o e-mail da Daddus.
2. Canto superior direito, **+** → **New repository**.
   - Repository name: `painel-fiscal`
   - Visibilidade: **Public** (o GitHub Pages gratuito só publica repositórios públicos; os dados são abertos por natureza — o que fica público é o painel)
   - Marque **Add a README file**
   - **Create repository**

## Parte 2 — Subir os arquivos (10 min)

Descompacte o `painel-fiscal-repo.zip` no seu computador. Dentro vêm as pastas `etl/`, `docs/`, `appsscript/`, `entrada/` e `.github/`.

1. No repositório, **Add file → Upload files**.
2. Arraste as pastas **`etl`**, **`docs`**, **`appsscript`**, **`entrada`** e os arquivos **`README.md`** e **`.gitignore`** para a área de upload (arraste a pasta inteira; o Chrome aceita).
3. Em *Commit changes*, escreva "painel inicial" e clique **Commit changes**.
4. **Verifique** se apareceu a pasta `.github/workflows` com dois arquivos (`atualizar.yml` e `ppp-siconfi.yml`). Pastas que começam com ponto às vezes não sobem pelo arrastar. Se não apareceram:
   - **Add file → Create new file**; no nome digite exatamente `.github/workflows/atualizar.yml`
     (a barra cria as pastas); cole o conteúdo do arquivo de mesmo nome do zip; **Commit changes**.
   - Repita para `.github/workflows/ppp-siconfi.yml`.

Ponto de verificação: a raiz do repositório mostra `.github`, `appsscript`, `docs`, `entrada`, `etl`, `.gitignore`, `README.md`.

## Parte 3 — Ligar o GitHub Pages (2 min)

1. **Settings → Pages** (menu lateral).
2. Em *Build and deployment* → *Source*: **Deploy from a branch**.
3. *Branch*: **main**, pasta **/docs** → **Save**.
4. Aguarde 1–2 minutos e recarregue: aparece "Your site is live at `https://SEU-USUARIO.github.io/painel-fiscal/`".
5. Abra a URL. O painel deve carregar com as datas no cabeçalho (CAPAG 01/06/2026 · CAUC 25/08/2026 · …).

Se aparecer "O painel não conseguiu carregar os dados": confira se existe `docs/dados/base.json.gz` e `docs/dados/geo.json.gz` no repositório.

## Parte 4 — Ligar a atualização automática (5 min + acompanhar a 1ª execução)

1. **Settings → Actions → General**. Em *Workflow permissions* marque **Read and write permissions** → **Save**.
   (Sem isso o robô não consegue gravar a base nova.)
2. Aba **Actions** → à esquerda, **Atualizar painel** → botão **Run workflow** → **Run workflow**.
3. Clique na execução que apareceu e depois em **atualizar** para ver o log. Leva de 3 a 8 minutos.
4. Leia o log do passo *"Baixar do Tesouro e reconstruir a base"*. Cada fonte escreve uma linha:
   - `CAPAG: 5568 municípios | anos-base 2024, 2025 | divergências 0` → certo.
   - `CAUC: 5569 entes | 28 itens | Data da Pesquisa: …` → certo.
   - `SADIPEM: 26990 pedidos …` → certo. Se vier `salvo sadipem-api-….csv | colunas: [...]` e logo depois
     `AVISO: SADIPEM mantido da versão anterior: coluna não encontrada`, a API usa nomes de coluna diferentes
     dos previstos: me mande a lista de colunas que apareceu no log e eu ajusto o mapa `SAD_COLS` em `etl/extrair.py`.
     Enquanto isso o painel segue com o SADIPEM anterior.
   - `CDP 02: 26288 contratos …` → certo. Se vier `conjunto … não encontrado`, use a carga manual do CDP (Parte 5).
   - A última linha `Base gravada: … "avisos": []` é o resumo. **Avisos vazios = tudo atualizado.**
5. Volte ao painel (Ctrl+F5) e confira as datas do cabeçalho.

A partir daí roda sozinho **toda segunda-feira às 6h**. Você recebe e-mail do GitHub se uma execução falhar.

### PPPs pela API do Siconfi (mensal, separado)

A coleta de PPPs faz duas chamadas por município e é lenta (1 a 3 horas). Por isso é um workflow próprio,
**Coletar PPPs no Siconfi**, que roda no dia 5 de cada mês e pode ser disparado pelo **Run workflow** informando
exercício e bimestre. Ele é retomável: se parar no tempo limite, a próxima execução continua de onde parou
(`docs/dados/ppp_siconfi.json`). Enquanto o cache não estiver completo, o painel usa a planilha de PPPs mais recente.

---

## Parte 5 — Carga manual (o caminho garantido)

Use quando quiser atualizar uma base na hora, ou quando o download automático de alguma fonte falhar.

**Uma vez só:** instale o Python (python.org → Downloads → marque "Add Python to PATH"). Abra o *Prompt de Comando*
na pasta descompactada e rode:

```
pip install -r etl\requirements.txt
```

**A cada atualização:**

1. Baixe os arquivos do Tesouro e coloque em `entrada\` (veja `entrada\LEIA-ME.txt` para os nomes aceitos):
   - CAPAG: tesourotransparente.gov.br → dados abertos → *Capacidade de Pagamento de Municípios* → xlsx mais recente
   - CAUC: dados abertos → *CAUC* → "Relatório da situação dos municípios" (csv)
   - SADIPEM: sadipem.tesouro.gov.br → Consulta pública → exportar **a consulta geral** (é a que traz o Código IBGE)
   - CDP: dados abertos → *Cadastro da Dívida Pública* → os arquivos 01, 02, 05, 06, 10 e 13
   - PPPs: a planilha consolidada (RREO Anexo 13), com o nome começando por `ppp-`
2. Rode:
   ```
   python etl\atualizar.py
   ```
   Confira o log (mesmas linhas da Parte 4) e a linha final `"avisos": []`.
3. Publique: no GitHub, entre em `docs/dados/` → **Add file → Upload files** → arraste `docs\dados\base.json.gz`
   e `docs\dados\meta.json` → **Commit changes**. Em 1–2 minutos o painel no ar está atualizado.

Dica: coloque uma data no nome do arquivo (`sadipem-20261005.csv`): ela vira a data mostrada no painel.

---

## Parte 6 — (Opcional) Apps Script: login Google e cópia no Drive

Serve para abrir o painel a partir de uma URL do Google, exigindo login da conta da Daddus, e para manter
uma cópia semanal da base no Drive. Lembre: como o GitHub Pages é público, isso organiza o acesso, mas não
esconde o painel de quem tiver a URL do Pages.

1. **script.google.com** → **Novo projeto**. Apague o conteúdo e cole o arquivo `appsscript/Code.gs`.
2. Na primeira linha, troque `SEU-USUARIO` pelo seu usuário do GitHub (a URL do Pages, terminando em `/`).
3. **Implantar → Nova implantação → tipo: Aplicativo da Web**. *Executar como*: você. *Quem pode acessar*:
   "Qualquer pessoa na Daddus" (aparece se a conta for Google Workspace) ou "Qualquer pessoa com conta Google".
   **Implantar** e copie a URL — é essa que você distribui.
4. Cópia no Drive: no editor, ícone de relógio (**Acionadores**) → **Adicionar acionador** → função `espelharNoDrive`,
   *Baseado em tempo*, *Semanal*. Os arquivos aparecem na pasta "Painel Fiscal - base" do seu Drive.

## Parte 7 — Rotina de conferência (2 min por semana)

- Abra o painel: as cinco datas do cabeçalho avançaram como esperado?
- Abra `https://SEU-USUARIO.github.io/painel-fiscal/dados/meta.json`: `"avisos": []`?
- Aba **Actions** com marca verde na última execução?

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Pages mostra 404 | Pasta errada em Settings → Pages | Branch `main`, pasta `/docs` |
| Painel diz "não conseguiu carregar os dados" | `docs/dados/*.gz` não subiu | Suba `base.json.gz` e `geo.json.gz` em `docs/dados/` |
| Workflow falha em "Publicar" com *permission denied* | Permissão de escrita desligada | Parte 4, item 1 |
| Log traz `AVISO: … mantido da versão anterior` | Aquela fonte não baixou ou mudou de formato | Painel continua no ar; use a carga manual (Parte 5) e me avise o texto do aviso |
| Data de uma camada não avança há semanas | Tesouro não publicou nada novo, ou download quebrado | Compare com o site do Tesouro; se lá há arquivo novo, carga manual |
| Painel demora a abrir | Base de ~3 MB + malha de 0,5 MB | Normal na primeira abertura; depois fica em cache |
| Quer testar sem esperar segunda-feira | — | Actions → Atualizar painel → Run workflow |

## O que não fazer

- Não edite `docs/dados/base.json.gz` à mão; ele é gerado.
- Não suba a pasta `entrada/` com os arquivos brutos (o `.gitignore` já bloqueia; alguns passam de 25 MB).
- Não mude os nomes das colunas nos arquivos do Tesouro antes de colocá-los em `entrada/`.
