# Escola de Profetas

Protótipo Flask/SQLite de uma escola de formação profética com cadastro de usuários, produtos adicionais, área do aluno, canal de dúvidas, painel privado da Escola, mapa ministerial e Ciclos de Formação.

## Como rodar

```bash
python app.py
```

Abra:

```text
http://127.0.0.1:5000
```

O banco SQLite é criado automaticamente no primeiro start com seed inicial.

## Deploy no Render

O app foi ajustado para inicializar o SQLite automaticamente também quando roda com:

```bash
gunicorn app:app
```

Não é necessário executar comando manual para criar tabelas. Na importação do `app.py`, o sistema chama `init_db()`, cria as tabelas ausentes e aplica os seeds iniciais quando o banco está vazio.

## Continuidade em outro notebook

Para continuar este mesmo projeto em outro notebook com Codex, zipar a pasta inteira do projeto incluindo:

- `app.py`
- `requirements.txt`
- `README.md`
- `CONTINUIDADE_CODEX.md`
- `mentoria.db`
- `templates/`
- `static/`
- `protected_media/`

O arquivo `CONTINUIDADE_CODEX.md` guarda o contexto atual do produto, fluxos, rotas, assets, banco, mídia protegida e observações para o próximo Codex.

## Usuários demo

- Ana Demo: aluna demo
- Beatriz Demo: aluna demo com progresso iniciado
- Admin Escola: role admin
- Admin novo: `admin@escoladeprofetas.local` / `admin123`

Use o seletor "Trocar" no topo quando estiver logado para alternar entre usuários demo.

## Rotas criadas

- `/` tela inicial da Escola de Profetas
- `/login` login da Área do Aluno
- `/cadastro` cadastro de novo aluno, com prevenção de e-mail duplicado
- `/logout` encerra sessão
- `/cursos` página de vendas dos cursos/produtos da Escola
- `/adquirir/escola-de-profetas` início do fluxo de aquisição da Escola de Profetas
- `/checkout/escola-de-profetas` pré-checkout protegido por login
- `/checkout/escola-de-profetas/simular-pagamento` simula pagamento aprovado e libera acesso
- `/webhook/payment` webhook de protótipo protegido por `X-Webhook-Token`
- `/comprar/<slug>` checkout com cadastro do aluno para aquisição do curso
- `/pagamento/<order_id>` etapa de pagamento simulada e liberação automática de acesso
- `/free`, `/crescer`, `/upgrade` e `/premium` são rotas legadas redirecionadas para Cursos/Ciclos
- `/aluno` Área do Aluno protegida por login e compra ativa
- `/minha-jornada` alias legado da Área do Aluno
- `/diagnostico` diagnóstico espiritual inicial
- `/duvidas` canal de dúvidas
- `/duvidas-da-semana` respostas anônimas
- `/oracao` e `/diario` são rotas legadas redirecionadas para a Área do Aluno
- `/admin` painel privado da Escola, protegido por `role = admin`
- `/admin/alunos` lista usuários e permite liberar/bloquear acesso manualmente
- `/admin/compras` lista compras e permite marcar como paga para teste
- `/api/ping` presença online
- `/mapa-ministerial` questionário baseado em Efésios 4:11 com radar em Canvas
- `/estacoes` visão geral dos Ciclos de Formação
- `/ciclos` atalho para a visão geral dos Ciclos de Formação
- `/ciclo/<slug>` detalhe do ciclo e submódulos internos
- `/curso/<cycle_slug>/<content_slug>` conteúdo interno com vídeo, PDF, reflexão e conclusão
- `/curso/<cycle_slug>/<content_slug>/comentario` salva a reflexão do aluno
- `/curso/<cycle_slug>/<content_slug>/concluir` marca o conteúdo como concluído
- `/estacao/<slug>` detalhe da estação, aulas e progresso
- `/aula/<lesson_id>` aula com player demonstrativo e exercício
- `/api/lesson/<lesson_id>/listened` marca áudio como ouvido
- `/api/lesson/<lesson_id>/complete` conclui exercício e libera próxima aula
- `/api/journey/progress` progresso JSON da formação por estações
- `/admin/estacoes` painel privado da Escola para acompanhar progresso por estação
- `/admin/comentarios` painel privado da Escola para acompanhar reflexões dos alunos nos cursos

## Implementado

- Schema SQLite com usuários, cursos, compras, matrículas, produtos legados, pedidos, vínculos usuário-produto, conteúdos, progresso, dúvidas e estações.
- Seed com usuários demo, admin, conteúdos estruturados e 7 estações com 21 aulas.
- Seed de produtos com Escola de Profetas como produto principal e extras: Como ministrar com os anjos, Implantação de Ministérios Proféticos, Como montar uma sala profética e Como montar uma sala de oração por cura.
- Página de Cursos com visual de vendas premium e CTA "Adquirir curso".
- Fluxo de login/cadastro, aquisição, checkout, pagamento simulado e liberação automática por matrícula ativa.
- Liberação progressiva por semana e por estação.
- Diagnóstico espiritual inicial.
- Minha Formação com progresso e conteúdos bloqueados/liberados.
- Ciclos de Formação com submódulos internos, estados e desbloqueio por exercício.
- Área interna da Escola de Profetas com 4 ciclos principais: Leão, Águia, Homem e Boi.
- Cada ciclo possui 4 conteúdos com espaço para vídeo, PDF, comentário/reflexão do aluno, status e conclusão.
- Vídeos e PDFs dos cursos são servidos por rota protegida `/media/...`, exigindo login e matrícula ativa.
- Canal de dúvidas e Dúvidas da Semana.
- Painel privado da Escola em `/admin` e `/admin/estacoes`.
- Ping global de presença a cada 60 segundos.
- Mapa de Correlação Ministerial com 25 perguntas e radar em Canvas puro.
- Identidade visual premium escura/dourada da Escola de Profetas, preparada para os assets oficiais em `static/img/`.
- Layout responsivo para desktop/web e celular, com navegação superior em telas largas e barra inferior fixa em telas mobile.
- Avisos de segurança espiritual, privacidade e limites de aconselhamento.

## Assets oficiais da marca

O layout usa estes caminhos oficiais quando os arquivos estiverem em `static/img/`:

- `logo_escola_profetas_horizontal.png` no header.
- `logo_escola_profetas.png` no footer e áreas institucionais.
- `hero_leao_aguia.png` no hero principal da home.
- `bg_dark_gold.png` como textura escura/dourada global.
- `jornada_estacoes_base.png` como apoio visual da tela de estações.

Se algum asset oficial não estiver presente, o CSS mantém um fallback escuro/dourado sem depender de internet.

## Conteúdos internos dos ciclos

Os vídeos e PDFs privados devem ser adicionados localmente nestas pastas, sem depender de internet:

- `protected_media/videos/`
- `protected_media/pdfs/`

Exemplos já referenciados no código:

- `protected_media/videos/ciclo_leao_01_filiacao.mp4`
- `protected_media/pdfs/ciclo_leao_01_filiacao.pdf`
- `protected_media/videos/ciclo_aguia_01_presenca.mp4`
- `protected_media/pdfs/ciclo_aguia_01_presenca.pdf`

## Fluxo de compra

1. Visitante clica em "Adquirir curso" na página `/cursos`.
2. Se não estiver logado, vai para `/cadastro?next=/adquirir/escola-de-profetas`.
3. Após cadastro ou login, vai para `/checkout/escola-de-profetas`.
4. No protótipo, clique em "Simular pagamento aprovado".
5. O sistema marca a compra como `paid`, cria uma matrícula `active` e redireciona para `/aluno`.
6. A Área do Aluno mostra somente cursos com matrícula ativa.

O webhook futuro fica em `/webhook/payment` e hoje exige o header:

```text
X-Webhook-Token: webhook-prototipo-local
```
