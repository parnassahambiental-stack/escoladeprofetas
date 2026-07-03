# Pasta preparada para GitHub

Esta pasta foi gerada a partir do projeto Escola de Profetas para subir em um repositorio GitHub.

## Incluido

- Codigo Flask (`app.py`)
- Templates Jinja (`templates/`)
- CSS, JS e imagens publicas (`static/`)
- Documentacao (`README.md` e `CONTINUIDADE_CODEX.md`)
- Pastas vazias para midia protegida com `.gitkeep`

## Nao incluido por seguranca

- `mentoria.db`
- Videos privados de `protected_media/videos/`
- PDFs privados de `protected_media/pdfs/`
- `__pycache__/`

O app recria o banco automaticamente ao rodar `python app.py`.

## Subir no GitHub

```bash
git init
git add .
git commit -m "Versao inicial Escola de Profetas"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/escola-de-profetas.git
git push -u origin main
```
