# Como a página é atualizada

1. Ler o HTML atual do app (Artifact `read` de https://claude.ai/artifact/XrAcRECLFZfEPg61Z1chZS) → modelo.
2. Exportar o banco do app (ArtifactData `list`, `limit` 1000, `out_dir` = pasta dump) das coleções `t`, `p`, `wk`, `log` e `cfg`.
3. `python3 tools/build_public.py --template MODELO.html --dump DUMP --out index.html`
4. Se `dados.json` não mudou (`git status --porcelain dados.json` vazio), descartar e não publicar.
5. Senão, `git add index.html dados.json`, commit e push na branch `main`.
