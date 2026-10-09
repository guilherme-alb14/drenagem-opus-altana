#!/usr/bin/env python3
"""Gera a página pública (somente leitura) do painel da drenagem Opus Altana.

Uso:
  python3 tools/build_public.py --template APP.html --dump DUMP_DIR --out index.html [--stamp "09/10/2026 14:00"]

APP.html  = HTML atual do app no Claude (traz o código, o mapa e a linha de base).
DUMP_DIR  = pasta com os documentos do banco do app, um JSON por documento:
            DUMP_DIR/t/*.json, p/*.json, wk/*.json, log/*.json, cfg/rp.json
A página gerada não tem nenhuma função de edição: fora do Claude o app abre só para leitura.
"""
import argparse, glob, json, os, re, sys, datetime

SVC_T = {"esc", "mon", "re1", "re2"}
SVC_P = {"pv1", "pv2"}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_dir(d):
    out = []
    for f in sorted(glob.glob(os.path.join(d, "*.json"))):
        with open(f, encoding="utf-8") as fh:
            try:
                out.append((os.path.splitext(os.path.basename(f))[0], json.load(fh)))
            except json.JSONDecodeError:
                print("ignorado (JSON inválido):", f, file=sys.stderr)
    return out


def clean_rec(r):
    """Mantém só campos conhecidos de um serviço: s (0-2), i/c (datas), src."""
    if not isinstance(r, dict):
        return None
    s = r.get("s")
    if s not in (1, 2):
        return None
    o = {"s": s}
    for k in ("i", "c"):
        v = r.get(k)
        if isinstance(v, str) and DATE.match(v):
            o[k] = v
    if isinstance(r.get("src"), str) and len(r["src"]) < 12:
        o["src"] = r["src"]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stamp", default=None)
    a = ap.parse_args()

    html = open(a.template, encoding="utf-8").read()
    m = re.search(r'(<script type="application/json" id="state">)(.*?)(</script>)', html, re.S)
    if not m:
        sys.exit("modelo sem o bloco de estado (id=state)")
    st = json.loads(m.group(2))

    t, p, wk, log = {}, {}, {}, []
    for _, d in load_dir(os.path.join(a.dump, "t")):
        if isinstance(d, dict) and isinstance(d.get("id"), str):
            r = {k: clean_rec(v) for k, v in d.items() if k in SVC_T}
            r = {k: v for k, v in r.items() if v}
            if r:
                t[d["id"]] = r
    for _, d in load_dir(os.path.join(a.dump, "p")):
        if isinstance(d, dict) and isinstance(d.get("id"), str):
            r = {k: clean_rec(v) for k, v in d.items() if k in SVC_P}
            r = {k: v for k, v in r.items() if v}
            if r:
                p[d["id"]] = r
    for k, d in load_dir(os.path.join(a.dump, "wk")):
        if DATE.match(k) and isinstance(d, dict):
            it = [x for x in d.get("it", []) if isinstance(x, list) and len(x) == 3 and all(isinstance(y, str) for y in x)]
            w = {"it": it, "ca": {kk: vv for kk, vv in (d.get("ca") or {}).items() if isinstance(vv, str)}}
            if isinstance(d.get("ob"), str) and d["ob"]:
                w["ob"] = d["ob"][:2000]
            for f in ("ch", "dt"):
                if isinstance(d.get(f), (int, float)):
                    w[f] = d[f]
            wk[k] = w
    for _, d in load_dir(os.path.join(a.dump, "log")):
        if isinstance(d, dict) and isinstance(d.get("d"), str):
            e = {"d": d["d"], "n": d.get("n", 0) if isinstance(d.get("n"), (int, float)) else 0}
            if isinstance(d.get("txt"), str):
                e["txt"] = d["txt"][:400]
            if isinstance(d.get("lanc"), str):
                e["lanc"] = d["lanc"]
            log.append(e)  # o id de quem lançou não vai para a página pública
    log.sort(key=lambda e: e["d"])
    rpf = os.path.join(a.dump, "cfg", "rp.json")
    if os.path.exists(rpf):
        rp = json.load(open(rpf, encoding="utf-8"))
        st["rp"] = {"d": rp.get("d", "") if isinstance(rp.get("d"), str) else "",
                    "o": {k: v for k, v in (rp.get("o") or {}).items() if isinstance(v, str)}}
    if not t:
        sys.exit("nenhum trecho lido do banco; a página não foi gerada")
    st["t"], st["p"], st["wk"], st["log"] = t, p, wk, log[-150:]

    stamp = a.stamp or (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime("%d/%m/%Y %H:%M")
    js = json.dumps(st, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = html[:m.start(2)] + js + html[m.end(2):]

    extra = (
        '<meta name="robots" content="noindex,nofollow">'
        '<style>.pubtag{margin-top:6px;display:inline-flex;gap:8px;align-items:center;font:600 11.5px/1.2 var(--f-body);'
        'color:var(--ink-2);background:var(--surface-2);border:1px solid var(--line);border-radius:999px;padding:4px 10px}'
        '.pubtag b{color:var(--ok)}</style>'
    )
    tag = ('<script>(function(){function put(){var b=document.querySelector(".brand");if(!b){return setTimeout(put,200)}'
           'if(document.querySelector(".pubtag"))return;var d=document.createElement("div");d.className="pubtag";'
           'd.textContent="Página pública · somente leitura · dados de ' + stamp + '";b.appendChild(d)}put()})();</script>')
    html = html.replace("<title>", extra + "<title>", 1)
    k = html.rfind("</body>")
    html = html[:k] + tag + html[k:] if k >= 0 else html + tag
    open(a.out, "w", encoding="utf-8").write(html)
    # dados.json: só os dados do banco, para saber se houve mudança desde a última publicação
    core = {"t": t, "p": p, "wk": wk, "rp": st.get("rp"), "log": log[-150:]}
    open(os.path.join(os.path.dirname(os.path.abspath(a.out)), "dados.json"), "w", encoding="utf-8").write(
        json.dumps(core, ensure_ascii=False, sort_keys=True, indent=0))
    print("ok:", a.out, "| trechos", len(t), "| PVs", len(p), "| semanas", len(wk), "| lançamentos", len(log), "|", stamp)


if __name__ == "__main__":
    main()
