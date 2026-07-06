# Pasta preparada para GitHub

Esta pasta foi gerada a partir do projeto Escola de Profetas para subir em um repositorio GitHub.

## Incluido

- Codigo Flask (`app.py`)
- Templates Jinja (`templates/`)
- CSS, JS e imagens publicas (`static/`)
- Midia de teste da aula 1 (`protected_media/videos/ciclo_leao_01_filiacao.mp4`)
- PDF de teste da aula 1 (`protected_media/pdfs/ciclo_leao_01_filiacao.pdf`)
- Documentacao (`README.md` e `CONTINUIDADE_CODEX.md`)
- Arquivos de deploy (`Procfile`, `runtime.txt`, `requirements.txt`)

## Nao incluido por seguranca

- `mentoria.db`
- Outros videos privados de `protected_media/videos/`
- Outros PDFs privados de `protected_media/pdfs/`
- `__pycache__/`

O app recria o banco automaticamente ao rodar `python app.py` ou `gunicorn app:app`.

## Render

O pacote ja inclui:

```text
Procfile: web: gunicorn app:app
runtime.txt: python-3.12.7
```

Para teste sem login na Area do Aluno, mantenha:

```text
PUBLIC_TEST_ACCESS=1
```

## Subir no GitHub

```bash
git init
git add .
git commit -m "Versao inicial Escola de Profetas"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/escola-de-profetas.git
git push -u origin main
```
