# Continuidade no Codex - Escola de Profetas

Este arquivo guarda o contexto principal do projeto para continuar em outro notebook depois de zipar a pasta.

## Projeto

- Nome visual principal: **Escola de Profetas**.
- Stack: Python, Flask, SQLite, HTML/Jinja2, CSS puro e JavaScript puro.
- Execucao local: `python app.py`.
- URL local: `http://127.0.0.1:5000`.
- Dependencia principal: `Flask==3.1.3` em `requirements.txt`.
- Banco local atual: `mentoria.db`.

## Identidade visual atual

- Estetica: premium, escura, dourada, nobre, ministerial e reverente.
- Cores principais: preto nobre, azul profundo, dourado envelhecido, champanhe e marfim.
- Marca principal visivel: **Escola de Profetas**.
- Assets principais em `static/img/`:
  - `logo_escola_profetas_horizontal.png`
  - `logo_escola_profetas.png`
  - `hero_leao_aguia.png`
  - `bg_dark_gold.png`
  - `ciclos_formacao.png`
  - imagens dos cursos: `curso_escola_profetas.png`, `curso_anjos.png`, `curso_ministerios_profeticos.png`, `curso_sala_profetica.png`, `curso_sala_oracao_cura.png`

## Fluxo principal do aluno

1. Visitante entra pela home `/`.
2. Clica em Cursos ou "Quero Fazer Parte" e acessa `/cursos`.
3. Escolhe um curso.
4. Se ainda nao estiver logado, passa por cadastro/login.
5. Segue para checkout/pagamento simulado.
6. Apos confirmacao, o acesso aparece na Area do Aluno `/aluno`.
7. A Area do Aluno exibe somente cursos com compra/matricula confirmada.
8. No curso **Escola de Profetas**, o botao "Acessar curso" leva primeiro para `/ciclos`, nao direto para a primeira aula.
9. Dentro de `/ciclos`, o aluno escolhe um ciclo, como `/ciclo/leao`.
10. Dentro do ciclo, acessa as aulas em `/curso/<cycle_slug>/<content_slug>`.

## Produtos/cursos cadastrados

- Escola de Profetas
- Como ministrar com os anjos
- Implantacao de Ministerios Profeticos
- Como montar uma sala profetica
- Como montar uma sala de oracao por cura

## Area interna da Escola de Profetas

Os ciclos principais sao:

- Leao: governo e identidade
- Aguia: visao e discernimento
- Homem: carater e maturidade
- Boi: servico e constancia

Cada ciclo tem conteudos internos com:

- pagina da aula;
- video protegido, se existir;
- PDF/material de apoio protegido, se existir;
- reflexao do aluno;
- botao de concluir;
- progresso do ciclo.

O painel de progresso da aula foi ajustado para:

- usar o texto "Progresso do ciclo" em badge dourado;
- mostrar o nome do ciclo centralizado;
- mostrar porcentagem centralizada dentro da barra de progresso;
- evitar o antigo circulo desalinhado.

## Midia protegida

Arquivos privados ficam em:

- `protected_media/videos/`
- `protected_media/pdfs/`

Arquivos de teste atuais:

- `protected_media/videos/ciclo_leao_01_filiacao.mp4`
- `protected_media/pdfs/ciclo_leao_01_filiacao.pdf`

A rota `/media/<kind>/<filename>` exige login e acesso ativo ao produto Escola de Profetas.

## Rotas importantes

- `/` home
- `/cursos` pagina de cursos/vendas
- `/login` login
- `/cadastro` cadastro
- `/logout` sair
- `/aluno` Area do Aluno
- `/minha-jornada` alias legado da Area do Aluno
- `/comprar/<slug>` compra de curso
- `/pagamento/<order_id>` pagamento simulado
- `/adquirir/escola-de-profetas` aquisicao da Escola de Profetas
- `/checkout/escola-de-profetas` checkout da Escola de Profetas
- `/checkout/escola-de-profetas/simular-pagamento` liberacao simulada
- `/curso/escola-de-profetas` redireciona para `/ciclos` quando o aluno tem acesso
- `/ciclos` e `/estacoes` visao dos ciclos
- `/ciclo/<slug>` detalhe do ciclo
- `/curso/<cycle_slug>/<content_slug>` aula interna
- `/curso/<cycle_slug>/<content_slug>/comentario` salva reflexao
- `/curso/<cycle_slug>/<content_slug>/concluir` conclui conteudo
- `/duvidas` canal de duvidas
- `/mapa-ministerial` mapa ministerial
- `/admin` painel admin
- `/admin/alunos` gestao de alunos/acesso
- `/admin/compras` gestao de compras
- `/admin/comentarios` reflexoes dos alunos
- `/api/ping` presenca online

## Estado de login e acesso

O projeto usa sessao Flask. Se a tela parecer "logada demais" ou estiver indo direto para Area do Aluno, teste:

1. Acessar `/logout`.
2. Acessar `/aluno`.
3. O app deve redirecionar para login se nao houver sessao.

Usuarios demo/locais podem estar dentro de `mentoria.db`. O usuario Marcus ja apareceu no banco local com acesso ativo a Escola de Profetas.

## Banco de dados

O banco `mentoria.db` esta na raiz do projeto. Para levar o estado atual para outro notebook, ele precisa ir junto no zip.

Tabelas relevantes:

- `users`
- `products`
- `purchases`
- `enrollments`
- `user_products`
- `course_progress`
- `course_comments`
- tabelas de jornada/estacoes/progresso
- tabelas de duvidas, diario, oracao e admin

## Arquivos principais

- `app.py`: rotas, schema SQLite, seeds, regras de acesso, compra e progresso.
- `templates/base.html`: layout base, header/nav e footer.
- `templates/index.html`: home premium.
- `templates/cursos.html`: pagina de cursos.
- `templates/journey.html`: Area do Aluno.
- `templates/stations.html`: tela visual dos ciclos.
- `templates/cycle_detail.html`: detalhe de um ciclo.
- `templates/course_content.html`: aula interna com video/PDF/reflexao/progresso.
- `static/css/styles.css`: identidade visual e responsividade.
- `static/js/app.js`: interacoes, ping e animacoes.
- `README.md`: documentacao geral.

## Como transferir para outro notebook

Zipar a pasta inteira:

`C:\Users\Marcus\Documents\Codex\2026-06-29\analise-o-app-que-estou-desenvolvendo`

Garantir que o zip inclua:

- `app.py`
- `requirements.txt`
- `README.md`
- `CONTINUIDADE_CODEX.md`
- `mentoria.db`
- `templates/`
- `static/`
- `protected_media/`

Em outro notebook:

```bash
pip install -r requirements.txt
python app.py
```

Abrir:

```text
http://127.0.0.1:5000
```

## Observacoes para o proximo Codex

- Nao refazer do zero.
- Preservar a identidade **Escola de Profetas**.
- Nao voltar para "Mentoria Profetica" como marca principal.
- Nao usar verde no layout.
- Preservar a logica: Area do Aluno mostra somente cursos com acesso confirmado.
- Preservar fluxo: Escola de Profetas -> Ciclos -> Ciclo especifico -> Aulas.
- Manter videos/PDFs protegidos por login e matricula ativa.
- Se ajustar visual, mexer preferencialmente em `static/css/styles.css` e templates especificos.
