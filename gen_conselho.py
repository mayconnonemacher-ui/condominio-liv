# Gera a página pública (somente leitura) para o conselho a partir do banco do painel interno + aba Demandas da planilha.
import json, glob, html, datetime, os
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("LIV_DBDUMP", "/home/claude/dbdump")

# Fonte de dados: (a) fornecedores.json compacto ao lado do script (gerado pelo painel interno e entregue via Google Drive)
# ou (b) a pasta dbdump/fornecedores/*.json exportada diretamente do banco do painel (read_db).
_compact = os.path.join(HERE, "fornecedores.json")
if os.path.exists(_compact):
    rows = json.load(open(_compact, encoding="utf-8"))
else:
    rows = [json.load(open(f, encoding="utf-8")) | {"id": f.split("/")[-1][:-5]} for f in glob.glob(os.path.join(DB, "fornecedores", "*.json"))]
for _r in rows:
    _r.setdefault("status", "A contatar"); _r.setdefault("endereco", ""); _r.setdefault("dataVisita", ""); _r.setdefault("valorMensal", None); _r.setdefault("valorAvulso", None)
dem = json.load(open(os.path.join(HERE, "demandas.json"), encoding="utf-8"))  # aba Demandas da planilha, exportada

CATS = ["Administração/contabilidade", "Portaria / Zeladoria / Limpeza", "Portaria remota", "Controle de pragas / Caixa d'água",
        "Análise de água (poço)", "Piscineiro", "Jardinagem", "Extintores / incêndio", "Elevadores", "Seguro", "Gás (GLP)", "Manutenção predial", "Outros"]
MAP = {1: "Portaria / Zeladoria / Limpeza", 2: "Portaria / Zeladoria / Limpeza", 3: "Análise de água (poço)", 4: "Controle de pragas / Caixa d'água",
       5: "Controle de pragas / Caixa d'água", 6: "Piscineiro", 7: "Portaria remota", 8: "Administração/contabilidade", 9: "Jardinagem",
       10: "Elevadores", 11: "Extintores / incêndio", 12: "Manutenção predial", 13: "Seguro", 14: "Outros"}
STATUS = ["A contatar", "Contatado", "Visita agendada", "Visita realizada", "Orçamento recebido", "Contratado", "Descartado"]
PUB = {"A contatar": "Contato pendente", "Contatado": "Em contato", "Visita agendada": "Visita agendada", "Visita realizada": "Visita realizada",
       "Orçamento recebido": "Proposta recebida", "Contratado": "Contratado", "Descartado": "Descartado"}
e = html.escape
def brl(v): return "—" if v in (None, "", 0) else "R$ " + f"{float(v):,.0f}".replace(",", ".")
def brd(iso): return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "—"
sidx = lambda s: max(0, STATUS.index(s) if s in STATUS else 0)
today = datetime.date.today()
upd = today.strftime("%d/%m/%Y")

active = [r for r in rows if r.get("status") != "Descartado"]
contatados = [r for r in active if sidx(r["status"]) >= 1]
propostas = [r for r in active if sidx(r["status"]) >= 4]
contratados = [r for r in rows if r.get("status") == "Contratado"]
best = {}
for r in active:
    v = r.get("valorMensal")
    if v and (r["categoria"] not in best or v < best[r["categoria"]]["v"]): best[r["categoria"]] = {"v": v, "e": r["empresa"]}
estimado = sum(b["v"] for b in best.values())
tot_contr = sum(r.get("valorMensal") or 0 for r in contratados)
visitas = sorted([r for r in active if r.get("dataVisita") and r["dataVisita"] >= today.isoformat()], key=lambda r: r["dataVisita"])

def kpi(l, v, s, hi=False):
    return f'<div class="kpi{" hi" if hi else ""}"><div class="lbl">{l}</div><div class="val">{v}</div><div class="sub">{s}</div></div>'

kpis = kpi("Serviços em cotação", len([c for c in CATS if any(r["categoria"] == c for r in rows)]), f"{len(dem)} demandas mapeadas") + \
       kpi("Fornecedores contatados", f"{len(contatados)}<small>/{len(active)}</small>", "meta: 3 propostas por serviço") + \
       kpi("Propostas recebidas", len(propostas), f"em {len(best)} serviços") + \
       kpi("Custo mensal estimado", brl(estimado) if estimado else "—", "menor proposta por serviço" if estimado else "aguardando propostas", True) + \
       kpi("Contratado até agora", brl(tot_contr) if tot_contr else str(len(contratados)), f"{len(contratados)} contrato(s) firmado(s)")

# resumo de custos
cost_rows = ""
for c in CATS:
    rs = [r for r in active if r["categoria"] == c]
    if not rs: continue
    vals = [r["valorMensal"] for r in rs if r.get("valorMensal")]
    ctr = [r for r in rs if r["status"] == "Contratado"]
    got = len([r for r in rs if sidx(r["status"]) >= 4])
    prog = "".join(f'<i class="{"on" if i < got else ""}"></i>' for i in range(3))
    cost_rows += f'<tr><td>{e(c)}</td><td><span class="prog">{prog}</span> {got}/3</td><td class="n">{brl(min(vals)) if vals else "—"}</td><td class="n c-md">{brl(sum(vals)/len(vals)) if vals else "—"}</td><td class="n c-md">{brl(max(vals)) if vals else "—"}</td><td class="c-md">{e(ctr[0]["empresa"]) + " · " + brl(ctr[0].get("valorMensal")) if ctr else "<span class=muted>em cotação</span>"}</td></tr>'
cost_rows += f'<tr class="tot"><td>Total mensal estimado</td><td></td><td class="n">{brl(estimado) if estimado else "—"}</td><td class="c-md"></td><td class="c-md"></td><td class="c-md">{brl(estimado*12) + " / ano" if estimado else ""}</td></tr>'

# seções por serviço
secs = ""
for c in CATS:
    rs = sorted([r for r in rows if r["categoria"] == c], key=lambda r: (-sidx(r["status"]) if r["status"] != "Descartado" else 9, r["empresa"]))
    ds = [d for d in dem if MAP.get(d[0]) == c]
    if not rs and not ds: continue
    dhtml = "".join(f'<div class="dem"><div class="dt">{e(d[1])}</div><div class="dd">{e(d[2])}</div><div class="dm"><span><b>Periodicidade</b> {e(d[3])}</span><span><b>Prioridade</b> {e(d[6])}</span></div><div class="dl"><b>Base legal / normativa</b> {e(d[4])}</div></div>' for d in ds)
    trs = "".join(f'<tr class="{"done" if r["status"]=="Contratado" else "out" if r["status"]=="Descartado" else ""}"><td>{e(r["empresa"])}<small>{e((r.get("endereco") or "").split("(")[0].strip())}</small></td><td><span class="pill st{sidx(r["status"])}">{PUB[r["status"]]}</span></td><td>{brd(r.get("dataVisita"))}</td><td class="n">{brl(r.get("valorMensal"))}</td><td class="n c-md">{brl(r.get("valorAvulso"))}</td></tr>' for r in rs) or '<tr><td colspan="5" class="muted">Nenhum fornecedor mapeado ainda.</td></tr>'
    got = len([r for r in rs if r["status"] != "Descartado" and sidx(r["status"]) >= 4])
    secs += f'''<section class="svc" id="{e(c)}"><div class="svc-h"><h2>{e(c)}</h2><span class="tag">{got}/3 propostas · {len([r for r in rs if r["status"]!="Descartado"])} fornecedores</span></div>
    <div class="svc-body"><div class="dems">{dhtml or '<div class="muted">Sem demanda detalhada — serviço complementar.</div>'}</div>
    <div class="tw"><table><thead><tr><th>Fornecedor</th><th>Situação</th><th>Visita</th><th class="n">Mensal</th><th class="n c-md">Avulso / implantação</th></tr></thead><tbody>{trs}</tbody></table></div></div></section>'''

vis = "".join(f'<li><span class="d">{brd(r["dataVisita"])}</span><span class="w">{e(r["empresa"])}</span><small>{e(r["categoria"])}</small></li>' for r in visitas[:12]) or '<li class="muted">Nenhuma visita técnica agendada no momento.</li>'

page = f'''<title>Cotações LIV — Conselho</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#F2F5F3;--surface:#FFF;--surface-2:#E9EEEB;--line:#D5DDD9;--line-strong:#B9C5BF;--ink:#16221F;--ink-2:#4B5B56;--ink-3:#7C8B86;--accent:#0F6E63;--accent-ink:#FFF;--accent-soft:#D7EBE7;--good:#2E7D32;--good-soft:#DFF0E0;--warn:#A8701A;--warn-soft:#F6E8CC;--muted-soft:#ECEFEE;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0F1614;--surface:#172020;--surface-2:#1F2A29;--line:#2C3937;--line-strong:#3C4B48;--ink:#E7EDEA;--ink-2:#AEBCB7;--ink-3:#7F8E89;--accent:#4FB8A9;--accent-ink:#0B1513;--accent-soft:#1B3B37;--good:#7BC67E;--good-soft:#1C3220;--warn:#E0B25B;--warn-soft:#3A2E14;--muted-soft:#232D2B;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#0F1614;--surface:#172020;--surface-2:#1F2A29;--line:#2C3937;--line-strong:#3C4B48;--ink:#E7EDEA;--ink-2:#AEBCB7;--ink-3:#7F8E89;--accent:#4FB8A9;--accent-ink:#0B1513;--accent-soft:#1B3B37;--good:#7BC67E;--good-soft:#1C3220;--warn:#E0B25B;--warn-soft:#3A2E14;--muted-soft:#232D2B;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "IBM Plex Sans",system-ui,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:24px 24px 56px}}
header{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:20px}}
.eyebrow{{font:500 11px/1 "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-bottom:6px}}
h1{{font:700 26px/1.15 "Sora",sans-serif;margin:0;letter-spacing:-.01em}} h2{{font:600 16px/1.2 "Sora",sans-serif;margin:0}}
.upd{{font:500 12px "IBM Plex Mono",monospace;color:var(--ink-2);padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:var(--surface)}}
.intro{{color:var(--ink-2);max-width:70ch;margin:0 0 20px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:22px}}
.kpi{{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}.kpi .lbl{{font-size:12px;color:var(--ink-2)}}.kpi .val{{font:600 26px/1.1 "Sora",sans-serif;margin-top:4px;font-variant-numeric:tabular-nums}}.kpi .val small{{font-size:14px;color:var(--ink-3)}}.kpi .sub{{font:400 11px "IBM Plex Mono",monospace;color:var(--ink-3);margin-top:4px}}
.kpi.hi{{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}}.kpi.hi .lbl,.kpi.hi .sub{{color:color-mix(in srgb,var(--accent-ink) 78%,transparent)}}
.panel{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:18px}}
.two{{display:grid;grid-template-columns:1.5fr 1fr;gap:16px}}@media(max-width:820px){{.two{{grid-template-columns:1fr}}}}
.tw{{overflow-x:auto}}table{{border-collapse:collapse;width:100%}}th{{text-align:left;font:500 11px "IBM Plex Mono",monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-2);padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}}td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}tr:last-child td{{border-bottom:0}}
td small{{display:block;color:var(--ink-3);font-size:12px}}.n{{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;white-space:nowrap}}th.n{{text-align:right}}
tr.tot td{{font-weight:600;background:var(--surface-2)}}tr.done td{{background:color-mix(in srgb,var(--good-soft) 55%,transparent)}}tr.out td{{opacity:.5}}
.muted{{color:var(--ink-3)}}
.prog i{{display:inline-block;width:14px;height:6px;border-radius:2px;background:var(--surface-2);margin-right:2px;vertical-align:middle}}.prog i.on{{background:var(--accent)}}
.pill{{display:inline-block;padding:2px 8px;border-radius:999px;font:500 11px "IBM Plex Mono",monospace;white-space:nowrap}}.st0{{background:var(--muted-soft);color:var(--ink-2)}}.st1{{background:var(--warn-soft);color:var(--warn)}}.st2,.st3,.st4{{background:var(--accent-soft);color:var(--accent)}}.st5{{background:var(--good-soft);color:var(--good)}}.st6{{background:var(--muted-soft);color:var(--ink-3)}}
ul.vis{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}}ul.vis li{{display:flex;align-items:center;gap:10px;flex-wrap:nowrap;padding:8px 10px;border:1px solid var(--line);border-radius:8px;overflow:hidden}}ul.vis .w{{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}ul.vis .d{{flex:none;font:500 12px "IBM Plex Mono",monospace;color:var(--accent)}}ul.vis small{{margin-left:auto;flex:none;color:var(--ink-3);font-size:11px;white-space:nowrap;max-width:45%;overflow:hidden;text-overflow:ellipsis}}
.toc{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 18px}}.toc a{{font-size:12px;color:var(--accent);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 10px;background:var(--surface)}}.toc a:hover{{border-color:var(--accent)}}
.svc{{background:var(--surface);border:1px solid var(--line);border-radius:12px;margin-bottom:14px;overflow:hidden}}.svc-h{{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid var(--line);background:var(--surface-2)}}
.tag{{font:500 11px "IBM Plex Mono",monospace;color:var(--ink-2)}}.svc-body{{display:grid;grid-template-columns:1fr 1.25fr;gap:0}}@media(max-width:820px){{.svc-body{{grid-template-columns:1fr}}}}
.dems{{padding:14px 16px;border-right:1px solid var(--line);display:flex;flex-direction:column;gap:14px}}@media(max-width:820px){{.dems{{border-right:0;border-bottom:1px solid var(--line)}}}}
.dem .dt{{font-weight:600}}.dem .dd{{color:var(--ink-2);font-size:13px;margin:2px 0 6px}}.dem .dm{{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--ink-2)}}.dem b{{font-weight:500;color:var(--ink-3);font-family:"IBM Plex Mono",monospace;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;margin-right:4px}}.dem .dl{{font-size:12px;color:var(--ink-2);margin-top:6px}}
.svc-body .tw{{padding:6px 8px}}
.panel,.two>*,.svc-body>*,.svc{{min-width:0}}
@media(max-width:600px){{.wrap{{padding:16px 12px 40px}}h1{{font-size:22px}}.kpis{{grid-template-columns:1fr 1fr;gap:8px}}.kpi{{padding:10px 12px}}.kpi .val{{font-size:22px}}.c-md{{display:none}}td,th{{padding:8px 6px;font-size:13px}}.dems,.svc-h{{padding:12px}}.svc-body .tw{{padding:4px 2px}}.intro{{font-size:13px}}ul.vis small{{max-width:40%}}.two{{gap:12px}}
.svc thead{{display:none}}.svc tbody tr{{display:grid;grid-template-columns:1fr auto;gap:4px 10px;align-items:center;padding:10px 8px;border-bottom:1px solid var(--line)}}.svc tbody tr:last-child{{border-bottom:0}}.svc td{{display:block;border:0;padding:0;font-size:13px}}.svc td.c-md{{display:none}}.prog{{display:none}}ul.vis li.muted{{display:block}}th{{white-space:normal}}td{{font-size:12.5px}}.svc td:first-child{{grid-column:1/-1;font-weight:500}}.svc td:nth-child(3){{grid-column:1;color:var(--ink-2)}}.svc td:nth-child(3):not(:empty)::before{{content:"Visita: ";color:var(--ink-3)}}.svc td:nth-child(4){{grid-column:2;grid-row:2;text-align:right}}.svc td:nth-child(4)::before{{content:"Mensal ";font-family:"IBM Plex Sans",sans-serif;color:var(--ink-3)}}.svc td:nth-child(2){{grid-column:1;grid-row:2}}.svc tr.done td:first-child::after{{content:" · contratado";color:var(--good);font-weight:400;font-size:12px}}}}
footer{{font-size:12px;color:var(--ink-3);margin-top:24px;max-width:75ch}}
</style>
<div class="wrap">
<header><div><div class="eyebrow">Condomínio Residencial LIV · Cascavel-PR · Conselho</div><h1>Cotações LIV — Conselho</h1></div><div class="upd">atualizado em {upd}</div></header>
<p class="intro">Acompanhamento das cotações para contratação dos serviços de conservação e manutenção do condomínio. Para cada serviço estão o escopo pretendido, a base legal, os fornecedores consultados e as propostas recebidas. A regra adotada é obter no mínimo três propostas por serviço antes de levar a decisão à assembleia.</p>
<div class="kpis">{kpis}</div>
<div class="two">
<div class="panel"><h2 style="margin-bottom:10px">Resumo de custos por serviço</h2><div class="tw"><table><thead><tr><th>Serviço</th><th>Propostas</th><th class="n">Menor</th><th class="n c-md">Média</th><th class="n c-md">Maior</th><th class="c-md">Contratado</th></tr></thead><tbody>{cost_rows}</tbody></table></div><p class="muted" style="font-size:12px;margin:10px 0 0">Valores mensais em reais, conforme propostas recebidas. Serviços anuais (seguro, extintores, limpeza de reservatório) são lançados pelo valor mensal equivalente.</p></div>
<div class="panel"><h2 style="margin-bottom:10px">Próximas visitas técnicas</h2><ul class="vis">{vis}</ul></div>
</div>
<div class="toc">{"".join(f'<a href="#{e(c)}">{e(c)}</a>' for c in CATS if any(r["categoria"]==c for r in rows) or any(MAP.get(d[0])==c for d in dem))}</div>
{secs}
<footer>Página de leitura para o conselho, gerada a partir do painel interno de cotações do síndico. Contatos, anotações internas e avaliações dos fornecedores não são exibidos aqui. Referências legais citadas são indicativas e devem ser confirmadas junto à Vigilância Sanitária, CREA e Corpo de Bombeiros antes da contratação.</footer>
</div>'''
open(os.path.join(HERE, "cotacoes-liv-conselho.html"), "w", encoding="utf-8").write(page)
# versão completa (documento HTML) para hospedagem no GitHub Pages
full = "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"robots\" content=\"noindex\">" + page.replace("<title>", "<title>", 1) + "</head><body></body></html>"
# move o conteúdo visual para o body: tudo após </style> pertence ao body
head_part, body_part = page.split("</style>", 1)
full = "<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"robots\" content=\"noindex\">" + head_part + "</style></head><body>" + body_part + "</body></html>"
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(full)
print("ok", len(page))
