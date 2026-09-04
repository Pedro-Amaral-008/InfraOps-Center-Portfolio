/**
 * GraficoHistoricoConsumo.jsx
 * "Consumo total da rede — picos"
 *
 * Implementação baseada em Recharts. A linha azul e as bolinhas vermelhas
 * são desenhadas pela MESMA série de dados, na MESMA escala: cada pico vira
 * uma linha do dataset com o valor da curva interpolado naquele instante e a
 * bolinha é o `dot` customizado dessa linha. Não existe cálculo de pixel
 * separado — por construção a bolinha fica exatamente em cima da curva.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * Como usar (modo real, com a API do InfraOps Center):
 *
 *   <GraficoHistoricoConsumo token={token} apiUrl={apiUrl} />
 *
 * O componente monta sozinho as URLs de histórico/picos e manda o header
 * Authorization: Bearer <token>. Também dá pra usar controlado (historico/
 * picos como prop) ou com URLs manuais (urlHistorico/urlPicos) — ver props.
 * ─────────────────────────────────────────────────────────────────────────
 */

import React, { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";

/* ───────────────────────────── constantes ───────────────────────────── */

const CAPACIDADE_MBPS = 300;          // escala fixa do eixo Y (0–300)
const JANELA_LISTA_MS = 7 * 24 * 3600 * 1000; // lista de picos: sempre 7 dias
const MAX_PONTOS_CURVA = 1200;        // acima disso a curva é reduzida (mantendo o maior valor de cada trecho)

const PERIODOS = [
  { id: "30s", rotulo: "30s", ms: 30 * 1000 },
  { id: "1min", rotulo: "1min", ms: 60 * 1000 },
  { id: "5min", rotulo: "5min", ms: 5 * 60 * 1000 },
  { id: "10min", rotulo: "10min", ms: 10 * 60 * 1000 },
  { id: "1h", rotulo: "1h", ms: 3600 * 1000 },
  { id: "24h", rotulo: "24h", ms: 24 * 3600 * 1000 },
  { id: "7d", rotulo: "1 semana", ms: 7 * 24 * 3600 * 1000 },
];

const COR_LINHA = "#6d78ff";
const COR_PICO = "#ff3b47";

/* ───────────────────────────── utilidades ───────────────────────────── */

function paraMs(v) {
  if (v == null) return NaN;
  if (typeof v === "number") return v < 1e12 ? v * 1000 : v; // aceita segundos
  if (v instanceof Date) return v.getTime();
  const n = Date.parse(v);
  return Number.isNaN(n) ? NaN : n;
}

function numeroOuNulo(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function normalizarHistorico(lista) {
  return (Array.isArray(lista) ? lista : [])
    .map((p) => ({
      ts: paraMs(p.ts ?? p.timestamp ?? p.data ?? p.time),
      total: numeroOuNulo(p.total ?? p.total_mbps ?? p.consumo ?? p.mbps ?? p.valor),
    }))
    .filter((p) => Number.isFinite(p.ts) && p.total != null)
    .sort((a, b) => a.ts - b.ts);
}

function normalizarPicos(lista) {
  return (Array.isArray(lista) ? lista : [])
    .map((p, i) => {
      const ts = paraMs(p.ts ?? p.timestamp ?? p.data ?? p.inicio ?? p.time);
      return {
        id: String(p.id ?? p.uid ?? `${p.mac ?? p.dispositivo ?? "pico"}-${ts}-${i}`),
        dispositivo: p.dispositivo ?? p.hostname ?? p.nome ?? "Dispositivo",
        mac: p.mac ?? p.endereco ?? "",
        tipo: String(p.tipo ?? p.direcao ?? "upload").toLowerCase(),
        valor: numeroOuNulo(p.valor ?? p.pico_mbps ?? p.pico ?? p.mbps),
        duracaoSeg: numeroOuNulo(p.duracaoSeg ?? p.duracao_segundos ?? p.duracao ?? p.segundos),
        ts,
      };
    })
    .filter((p) => Number.isFinite(p.ts))
    .sort((a, b) => a.ts - b.ts);
}

/** Reduz séries longas mantendo o MAIOR valor de cada trecho (não some pico). */
function reduzir(serie, maximo) {
  if (serie.length <= maximo) return serie;
  const tamanho = Math.ceil(serie.length / maximo);
  const saida = [];
  for (let i = 0; i < serie.length; i += tamanho) {
    let melhor = serie[i];
    for (let j = i + 1; j < i + tamanho && j < serie.length; j++) {
      if (serie[j].total > melhor.total) melhor = serie[j];
    }
    saida.push(melhor);
  }
  const ultimo = serie[serie.length - 1];
  if (saida[saida.length - 1] !== ultimo) saida.push(ultimo);
  return saida;
}

/** Valor da curva no instante `ts`, interpolando entre os dois vizinhos. */
function interpolar(historico, ts) {
  if (!historico.length) return null;
  if (ts <= historico[0].ts) return historico[0].total;
  const ultimo = historico[historico.length - 1];
  if (ts >= ultimo.ts) return ultimo.total;

  let lo = 0;
  let hi = historico.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (historico[mid].ts <= ts) lo = mid;
    else hi = mid;
  }
  const a = historico[lo];
  const b = historico[hi];
  if (b.ts === a.ts) return a.total;
  const f = (ts - a.ts) / (b.ts - a.ts);
  return a.total + (b.total - a.total) * f;
}

function fmtMbps(v) {
  return `${Number(v).toFixed(1).replace(".", ",")} Mbps`;
}

function fmtDuracao(seg) {
  if (seg == null) return "";
  const m = Math.floor(seg / 60);
  const s = Math.round(seg % 60);
  return m > 0 ? `${m}min ${s}s` : `${s}s`;
}

function fmtDataHora(ts) {
  const d = new Date(ts);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}, ${hh}:${mi}`;
}

function fmtTickEixo(ts, periodoMs) {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  if (periodoMs <= 10 * 60 * 1000) {
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${hh}:${mi}:${ss}`;
  }
  if (periodoMs <= 24 * 3600 * 1000) return `${hh}:${mi}`;
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm} ${hh}:${mi}`;
}

/* ─────────────────────────── subcomponentes ─────────────────────────── */

/** Bolinha vermelha: só é desenhada nas linhas do dataset que são pico. */
function PontoPico({ cx, cy, payload, picoAtivo, aoEntrar, aoSair }) {
  if (!payload || !payload.picoId || cx == null || cy == null) return null;
  const ativo = picoAtivo === payload.picoId;
  return (
    <g
      className={`ghc-ponto${ativo ? " ghc-ponto--ativo" : ""}`}
      onMouseEnter={() => aoEntrar(payload.picoId)}
      onMouseLeave={aoSair}
      style={{ cursor: "pointer" }}
    >
      {ativo && <circle cx={cx} cy={cy} r={9} fill={COR_PICO} fillOpacity={0.25} />}
      <circle cx={cx} cy={cy} r={ativo ? 5 : 3.5} fill={COR_PICO} stroke="#10141c" strokeWidth={1.5} />
    </g>
  );
}

/** Tooltip: na linha mostra só o consumo total; na bolinha mostra também o dispositivo. */
function TooltipConsumo({ active, payload, picosPorId, picoAtivo, linhasPorPico }) {
  if (!active || !payload || !payload.length) return null;
  /* se o mouse está numa bolinha, usa a linha exata do pico (e não o vizinho mais próximo) */
  const ponto = (picoAtivo && linhasPorPico.get(picoAtivo)) || payload[0].payload;
  if (!ponto || ponto.total == null) return null;
  const pico = ponto.picoId ? picosPorId.get(ponto.picoId) : null;
  return (
    <div className="ghc-tooltip">
      {pico && (
        <>
          <strong className="ghc-tooltip__nome">{pico.dispositivo}</strong>
          <span className="ghc-tooltip__pico">
            Pico de {pico.tipo === "download" ? "download" : "upload"}:{" "}
            {pico.valor != null ? fmtMbps(pico.valor) : "—"}
            {pico.duracaoSeg != null ? ` · ${fmtDuracao(pico.duracaoSeg)} acima de 60 Mbps` : ""}
          </span>
        </>
      )}
      <span>consumo total: {fmtMbps(ponto.total)}</span>
      <small>{fmtDataHora(ponto.ts)}</small>
    </div>
  );
}

function CardPico({ pico, ativo, temPonto, aoEntrar, aoSair }) {
  return (
    <div
      className={`ghc-card${ativo ? " ghc-card--ativo" : ""}`}
      onMouseEnter={() => aoEntrar(pico.id)}
      onMouseLeave={aoSair}
      title={temPonto ? "" : "Fora da janela do gráfico — só aparece na lista"}
    >
      <div className="ghc-card__nome">{pico.dispositivo}</div>
      <div className="ghc-card__mac">{pico.mac}</div>
      <div className="ghc-card__pico">
        Pico de {pico.tipo === "download" ? "download" : "upload"}:{" "}
        <strong>{pico.valor != null ? fmtMbps(pico.valor) : "—"}</strong>
      </div>
      <div className="ghc-card__alerta">
        Acima de 60 Mbps{pico.duracaoSeg != null ? ` por ${fmtDuracao(pico.duracaoSeg)}` : ""}
      </div>
      <div className="ghc-card__data">{fmtDataHora(pico.ts)}</div>
    </div>
  );
}

/* ─────────────────────────── componente principal ───────────────────── */

export default function GraficoHistoricoConsumo({
  historico: historicoProp,
  picos: picosProp,
  urlHistorico,
  urlPicos,
  token,
  apiUrl,
  intervaloMs = 15000,
  periodoInicial = "24h",
}) {
  const [periodoId, setPeriodoId] = useState(periodoInicial);
  const [picoAtivo, setPicoAtivo] = useState(null);
  const [remoto, setRemoto] = useState({ historico: [], picos: [] });
  const [erro, setErro] = useState(null);

  /*
   * Fonte dos dados, em ordem de prioridade:
   *   1. historico/picos vindos por prop (uso "controlado")
   *   2. urlHistorico/urlPicos explícitas (fetch simples, sem auth)
   *   3. apiUrl + token: monta as URLs da API do InfraOps Center e manda
   *      o header Authorization — é o modo usado no dashboard real.
   * O histórico é re-buscado sempre que o período muda (o backend agrega
   * os baldes de acordo com `minutos`); os picos usam sempre a janela fixa
   * de 7 dias, igual à lista embaixo do gráfico.
   */
  const periodoAtual = PERIODOS.find((p) => p.id === periodoId) ?? PERIODOS[5];
  const minutosHistorico = periodoAtual.ms / 60000;
  const minutosPicos = JANELA_LISTA_MS / 60000;

  const urlHistoricoFinal =
    urlHistorico ?? (apiUrl ? `${apiUrl}/dashboard/unifi/consumo/historico?minutos=${minutosHistorico}` : null);
  const urlPicosFinal =
    urlPicos ?? (apiUrl ? `${apiUrl}/dashboard/unifi/consumo/picos?minutos=${minutosPicos}` : null);

  useEffect(() => {
    if (historicoProp || picosProp) return undefined; // uso controlado: não busca nada
    if (!urlHistoricoFinal && !urlPicosFinal) return undefined;
    let vivo = true;

    const headers = token ? { Authorization: `Bearer ${token}` } : undefined;

    async function buscar() {
      try {
        const [h, p] = await Promise.all([
          urlHistoricoFinal ? fetch(urlHistoricoFinal, { headers }).then((r) => r.json()) : [],
          urlPicosFinal ? fetch(urlPicosFinal, { headers }).then((r) => r.json()) : [],
        ]);
        if (!vivo) return;
        setRemoto({
          historico: Array.isArray(h) ? h : h?.itens ?? h?.data ?? [],
          picos: Array.isArray(p) ? p : p?.itens ?? p?.data ?? [],
        });
        setErro(null);
      } catch (e) {
        if (vivo) setErro(e?.message || "Falha ao carregar dados");
      }
    }

    buscar();
    const timer = setInterval(buscar, intervaloMs);
    return () => {
      vivo = false;
      clearInterval(timer);
    };
  }, [historicoProp, picosProp, urlHistoricoFinal, urlPicosFinal, token, intervaloMs]);

  const historico = useMemo(
    () => normalizarHistorico(historicoProp ?? remoto.historico),
    [historicoProp, remoto.historico]
  );
  const picos = useMemo(
    () => normalizarPicos(picosProp ?? remoto.picos),
    [picosProp, remoto.picos]
  );

  const periodo = PERIODOS.find((p) => p.id === periodoId) ?? PERIODOS[5];
  const picosPorId = useMemo(() => new Map(picos.map((p) => [p.id, p])), [picos]);

  /* "agora" = último ponto do histórico (se houver), senão o relógio */
  const agora = historico.length ? historico[historico.length - 1].ts : Date.now();
  const inicioJanela = agora - periodo.ms;
  const inicioLista = agora - JANELA_LISTA_MS;

  /* lista de picos: janela FIXA de 7 dias, independe da aba */
  const picosLista = useMemo(
    () => picos.filter((p) => p.ts >= inicioLista && p.ts <= agora).slice().reverse(),
    [picos, inicioLista, agora]
  );

  /* dataset do gráfico: histórico dentro da aba + uma linha por pico visível */
  const { dados, idsComPonto } = useMemo(() => {
    const visivel = reduzir(
      historico.filter((p) => p.ts >= inicioJanela && p.ts <= agora),
      MAX_PONTOS_CURVA
    );
    if (!visivel.length) return { dados: [], idsComPonto: new Set() };

    const primeiro = visivel[0].ts;
    const ultimo = visivel[visivel.length - 1].ts;
    const ids = new Set();

    const linhasPico = picos
      .filter((p) => p.ts >= primeiro && p.ts <= ultimo)
      .map((p) => {
        ids.add(p.id);
        return { ts: p.ts, total: interpolar(visivel, p.ts), picoId: p.id };
      });

    const tudo = [...visivel.map((p) => ({ ts: p.ts, total: p.total })), ...linhasPico].sort(
      (a, b) => a.ts - b.ts || (a.picoId ? 1 : -1)
    );
    return { dados: tudo, idsComPonto: ids };
  }, [historico, picos, inicioJanela, agora]);

  const linhasPorPico = useMemo(
    () => new Map(dados.filter((d) => d.picoId).map((d) => [d.picoId, d])),
    [dados]
  );
  const dominioX = [inicioJanela, agora];
  const entrar = (id) => setPicoAtivo(id);
  const sair = () => setPicoAtivo(null);

  return (
    <section className="ghc">
      <style>{CSS}</style>

      <header className="ghc__topo">
        <div>
          <h3 className="ghc__titulo">Consumo total da rede — picos</h3>
          <p className="ghc__sub">
            Linha azul: soma da rede toda (escala fixa 0–{CAPACIDADE_MBPS} Mbps, capacidade do link).
            Bolinha vermelha: exatamente em cima da linha, marcando quando um dispositivo específico
            teve um pico (valor real dele no card abaixo).
          </p>
        </div>
        <div className="ghc__periodos" role="tablist" aria-label="Período do gráfico">
          {PERIODOS.map((p) => (
            <button
              key={p.id}
              type="button"
              role="tab"
              aria-selected={p.id === periodoId}
              className={`ghc__periodo${p.id === periodoId ? " ghc__periodo--ativo" : ""}`}
              onClick={() => setPeriodoId(p.id)}
            >
              {p.rotulo}
            </button>
          ))}
        </div>
      </header>

      <div className="ghc__grafico">
        {erro && <div className="ghc__aviso">Não foi possível carregar: {erro}</div>}
        {!erro && !dados.length && <div className="ghc__aviso">sem dados neste trecho</div>}

        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={dados}
            margin={{ top: 10, right: 12, bottom: 0, left: 12 }}
            /* solta o destaque quando o mouse sai da bolinha (o dot é re-renderizado
               ao ficar ativo, então o mouseleave dele nem sempre dispara) */
            onMouseMove={(_, ev) => {
              if (picoAtivo && ev?.target && !ev.target.closest?.(".ghc-ponto")) setPicoAtivo(null);
            }}
            onMouseLeave={() => setPicoAtivo(null)}
          >
            <defs>
              <linearGradient id="ghcArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COR_LINHA} stopOpacity={0.45} />
                <stop offset="100%" stopColor={COR_LINHA} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="ts"
              type="number"
              scale="time"
              domain={dominioX}
              tickFormatter={(v) => fmtTickEixo(v, periodo.ms)}
              tick={{ fill: "#59627a", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              minTickGap={220}
              tickMargin={8}
            />
            <YAxis domain={[0, CAPACIDADE_MBPS]} hide />
            <Tooltip
              content={<TooltipConsumo picosPorId={picosPorId} picoAtivo={picoAtivo} linhasPorPico={linhasPorPico} />}
              cursor={{ stroke: "rgba(255,255,255,0.12)", strokeDasharray: "3 3" }}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="total"
              stroke={COR_LINHA}
              strokeWidth={2}
              fill="url(#ghcArea)"
              isAnimationActive={false}
              connectNulls
              /* a bolinha vermelha É o dot da própria curva → sempre em cima da linha */
              dot={<PontoPico picoAtivo={picoAtivo} aoEntrar={entrar} aoSair={sair} />}
              activeDot={{ r: 4, fill: COR_LINHA, stroke: "#10141c", strokeWidth: 1.5 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="ghc__lista-titulo">
        Picos recentes — últimos 7 dias ({picosLista.length})
      </div>

      {picosLista.length ? (
        <div className="ghc__lista">
          {picosLista.map((p) => (
            <CardPico
              key={p.id}
              pico={p}
              ativo={picoAtivo === p.id}
              temPonto={idsComPonto.has(p.id)}
              aoEntrar={entrar}
              aoSair={sair}
            />
          ))}
        </div>
      ) : (
        <div className="ghc__vazio">Nenhum pico registrado nos últimos 7 dias.</div>
      )}
    </section>
  );
}

/* ───────────────────────────────── CSS ──────────────────────────────── */

const CSS = `
.ghc{background:#151a24;border:1px solid #232a38;border-radius:10px;padding:14px 16px 16px;color:#e6e9f0;font-family:inherit}
.ghc__topo{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap}
.ghc__titulo{margin:0;font-size:13px;font-weight:700}
.ghc__sub{margin:3px 0 0;font-size:10.5px;line-height:1.4;color:#8a93a6;max-width:470px}
.ghc__periodos{display:flex;gap:5px;flex-wrap:wrap}
.ghc__periodo{background:#1e2533;border:1px solid #2a3243;color:#9aa3b8;font-size:10px;padding:3px 8px;border-radius:5px;cursor:pointer;transition:background .12s}
.ghc__periodo:hover{background:#252d3d}
.ghc__periodo:focus-visible{outline:2px solid #5b6cf6;outline-offset:1px}
.ghc__periodo--ativo{background:#3b5bff;border-color:#3b5bff;color:#fff}
.ghc__grafico{position:relative;height:290px;margin-top:10px;background:#10141c;border-radius:8px;padding-top:4px}
.ghc__aviso{position:absolute;left:14px;top:10px;font-size:10px;color:#3f4759;z-index:1}
.ghc-tooltip{background:#0f131b;border:1px solid #2a3243;border-radius:6px;padding:6px 10px;font-size:12px;color:#e6e9f0;display:flex;flex-direction:column;gap:2px}
.ghc-tooltip small{color:#8a93a6;font-size:10px}
.ghc-tooltip__nome{color:${COR_PICO};font-size:12px}
.ghc-tooltip__pico{color:#c9cfdc;font-size:11px;margin-bottom:2px}
.ghc-ponto{transition:opacity .12s}
.ghc__lista-titulo{margin:14px 0 8px;font-size:11.5px;font-weight:700}
.ghc__lista{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.ghc__vazio{font-size:12px;color:#6b7385}
.ghc-card{background:#1a2030;border:1px solid #232a38;border-radius:8px;padding:9px 11px;font-size:11px;line-height:1.35;cursor:default;transition:border-color .12s,background .12s}
.ghc-card--ativo{border-color:${COR_PICO};background:#221e2a}
.ghc-card__nome{color:${COR_PICO};font-weight:700;font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ghc-card__mac{color:#5f6880;font-size:9.5px;margin-bottom:6px}
.ghc-card__pico{color:#e6e9f0}
.ghc-card__pico strong{font-weight:700}
.ghc-card__alerta{color:${COR_PICO};margin-top:2px}
.ghc-card__data{color:#5f6880;font-size:9.5px;margin-top:4px}
@media (prefers-reduced-motion:reduce){.ghc *{transition:none!important}}
`;
