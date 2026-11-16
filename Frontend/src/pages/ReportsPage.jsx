import { useCallback, useEffect, useState } from "react";
import { api, fieldRequest } from "../services/api";
import { useI18n } from "../i18n";
import "./ReportsPage.css";

const STORE_KEY = "cerradoshift_talhoes";
const API_BASE = (
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

function getFields() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}
function fmtNum(value, digits = 1, locale = "pt-BR", na = "Não disponível") {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString(locale, { maximumFractionDigits: digits }) : na;
}
function coordinates(field) {
  if (!field) return null;
  const req = fieldRequest(field);
  const lat = Number(req.lat), lon = Number(req.lon);
  if (req.lat != null && req.lon != null && Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180) return {lat, lon};
  const geom = req.geometry || field.geometry || field.geometria || field.geojson?.geometry;
  const ring = geom?.type === "Polygon" ? geom.coordinates?.[0] : geom?.type === "MultiPolygon" ? geom.coordinates?.[0]?.[0] : null;
  const valid = (ring || []).filter(p => Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1]));
  if (!valid.length) return null;
  return { lat: (Math.min(...valid.map(p => p[1])) + Math.max(...valid.map(p => p[1]))) / 2,
           lon: (Math.min(...valid.map(p => p[0])) + Math.max(...valid.map(p => p[0]))) / 2 };
}

export default function ReportsPage() {
  const { t, tn, locale } = useI18n();
  const n = (value, digits = 1) => fmtNum(value, digits, locale, t("Não disponível"));
  const [fields, setFields] = useState(getFields);
  const [selected, setSelected] = useState(() => String(getFields()[0]?.id ?? ""));
  const [context, setContext] = useState(null);
  const [soil, setSoil] = useState(null);
  const [loading, setLoading] = useState(false);
  const [soilLoading, setSoilLoading] = useState(false);
  const [error, setError] = useState("");
  const [soilError, setSoilError] = useState("");
  const field = fields.find(item => String(item.id) === selected);
  const position = coordinates(field);

  useEffect(() => { setContext(null); setSoil(null); setError(""); setSoilError(""); }, [selected]);

  const loadReport = useCallback(async () => {
    if (!field) return;
    setLoading(true); setError(""); setContext(null); setSoil(null); setSoilError("");
    try {
      const result = await api.fieldContext(fieldRequest(field));
      setContext(result);
    } catch (err) { setError(err.message || t("Não foi possível consultar o contexto ambiental.")); }
    finally { setLoading(false); }
  }, [field, t]);

  async function loadSoil() {
    if (!position) { setSoilError(t("Não foi possível identificar as coordenadas do talhão.")); return; }
    setSoilLoading(true); setSoilError("");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 21000);
    try {
      const response = await fetch(`${API_BASE}/v1/soil/diagnose`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...position, root_depth_cm: 30 }), signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
      setSoil(data);
    } catch (err) { setSoilError(err.name === "AbortError" ? t("Consulta de solo excedeu o tempo limite.") : err.message); }
    finally { clearTimeout(timeout); setSoilLoading(false); }
  }

  const climate = context?.climate || {};
  const indicators = context?.indicators || {};
  const summary = soil?.summary || {};
  const soilData = soil?.soil || context?.soil || {};
  const sources = context?.sources || [];
  const alerts = context?.alerts || [];

  return (
    <div className="cs-report-page">
      <div className="page-heading cs-report-no-print">
        <h1>{t("Relatórios")}</h1>
        <p>{t("Gere um documento técnico com indicadores reais, proveniência e limitações dos dados.")}</p>
      </div>
      <div className="panel cs-report-controls cs-report-no-print">
        <label htmlFor="report-field">{t("Talhão analisado")}</label>
        <select id="report-field" value={selected} onChange={e => setSelected(e.target.value)}>
          {fields.map(item => <option key={item.id} value={String(item.id)}>{tn(item.nome) || item.id}</option>)}
        </select>
        <button type="button" onClick={loadReport} disabled={!field || loading}>{loading ? t("Consultando fontes...") : t("Gerar relatório")}</button>
        <button type="button" className="cs-report-secondary" onClick={() => window.print()} disabled={!context}>{t("Imprimir / salvar PDF")}</button>
      </div>
      {!fields.length && <section className="panel">{t("Nenhum talhão cadastrado. Cadastre um no Mapa da Propriedade.")}</section>}
      {error && <section role="alert" className="panel cs-report-error">{error}</section>}
      {context && <article className="cs-report-sheet" aria-label={t("Relatório técnico do talhão")}>
        <header className="cs-report-cover">
          <div><span className="cs-report-kicker">{t("CERRADOSHIFT · RELATÓRIO TÉCNICO")}</span><h2>{t("Diagnóstico ambiental e agrícola")}</h2><p>{tn(field?.nome) || t("Talhão selecionado")}</p></div>
          <span className="cs-report-status">{t("Análise preliminar")}</span>
        </header>
        <div className="cs-report-meta">
          <p><strong>{t("Emitido em:")}</strong> {context.generated_at ? new Date(context.generated_at).toLocaleString(locale) : new Date().toLocaleString(locale)}</p>
          <p><strong>{t("Período climático:")}</strong> {t("{inicio} a {fim}", { inicio: context.window?.start || "—", fim: context.window?.end || "—" })}</p>
          <p><strong>{t("Local:")}</strong> {position ? `${n(position.lat, 5)}, ${n(position.lon, 5)}` : t("Localização não identificada")}</p>
          <p><strong>{t("Área:")}</strong> {n(context.location?.area_ha)} ha</p>
          {context.request_id && <p><strong>{t("ID da consulta:")}</strong> <code>{context.request_id}</code></p>}
        </div>
        <h3>{t("1. Indicadores climáticos")}</h3>
        <div className="cs-report-metrics">
          <div><span>{t("Precipitação")}</span><strong>{n(climate.precip_mm_total)} mm</strong></div>
          <div><span>{t("Temperatura média")}</span><strong>{n(climate.tmean_mean_c)} °C</strong></div>
          <div><span>{t("ET de referência (ET₀)")}</span><strong>{n(climate.et0_mm_total)} mm</strong></div>
          <div><span>{t("Maior período seco")}</span><strong>{n(climate.longest_dry_spell_days, 0)} {t("dias")}</strong></div>
        </div>
        <p className="cs-report-note">{t("ET₀ e evapotranspiração real não são equivalentes. Cada indicador depende da disponibilidade da sua fonte.")}</p>
        <h3>{t("2. Condição hídrica e riscos")}</h3>
        <p><strong>{t("Risco de seca (triagem):")}</strong> {indicators.drought_risk ? t(indicators.drought_risk) : t("Não calculado")}</p>
        <p><strong>{t("Déficit climático estimado:")}</strong> {n(indicators.water_deficit_mm)} mm</p>
        {indicators.drought_risk_basis?.length > 0 && <ul>{indicators.drought_risk_basis.map((item, i) => <li key={i}>{item}</li>)}</ul>}
        <h3>{t("3. Diagnóstico do solo")}</h3>
        <div className="cs-report-no-print cs-report-actions">
          <button type="button" onClick={loadSoil} disabled={soilLoading || !position}>{soilLoading ? t("Consultando solo...") : t("Incluir diagnóstico automático de solo")}</button>
          <span>{t("Quando a fonte não responder, o relatório indicará dados ausentes.")}</span>
        </div>
        {soilError && <p role="alert" className="cs-report-error">{soilError}</p>}
        <div className="cs-report-metrics">
          <div><span>{t("Textura")}</span><strong>{soilData.texture_class ? t(soilData.texture_class) : t("Não disponível")}</strong></div>
          <div><span>{t("Argila")}</span><strong>{n(soilData.clay_pct)}%</strong></div>
          <div><span>{t("pH em água")}</span><strong>{n(soilData.ph_h2o)}</strong></div>
          <div><span>{t("Água disponível no perfil")}</span><strong>{n(soilData.awc_mm_rootzone)} mm</strong></div>
        </div>
        <p className="cs-report-note"><strong>{t("Origem:")}</strong> {soilData.provider || t("Sem estimativa automática")}. {soil ? t("Estado: {estado}. Lacunas: {lacunas}.", { estado: soil.source_status?.status || soil.status, lacunas: summary.data_gaps ?? t("não informado") }) : t("Diagnóstico específico não consultado; exibidos apenas atributos do contexto ambiental.")}</p>
        {soil?.findings?.length > 0 && <div className="cs-report-findings">{soil.findings.map(f => <section key={f.code}><strong>{f.title}</strong><p>{f.detail}</p><small>{f.suggested_action}</small></section>)}</div>}
        <h3>{t("4. Alertas ambientais")}</h3>
        {alerts.length ? <div className="cs-report-findings">{alerts.map((a, i) => <section key={a.code || i}><strong>{a.title}</strong><p>{a.detail}</p><small>{a.action}</small></section>)}</div> : <p>{t("Nenhum alerta gerado com os dados disponíveis. Isso não comprova ausência de risco.")}</p>}
        <h3>{t("5. Fontes e integridade")}</h3>
        {sources.length ? <table className="cs-report-table"><thead><tr><th>{t("Fonte")}</th><th>{t("Estado")}</th><th>{t("Cache")}</th></tr></thead><tbody>{sources.map((s, i) => <tr key={i}><td>{s.name}</td><td>{s.status}</td><td>{s.cached ? t("Sim") : t("Não")}</td></tr>)}</tbody></table> : <p>{t("Nenhuma fonte documentada na resposta.")}</p>}
        {[...(context.warnings || []), ...(soil?.warnings || [])].length > 0 && <><h3>{t("6. Ressalvas dos dados")}</h3><ul>{[...(context.warnings || []), ...(soil?.warnings || [])].map((w, i) => <li key={i}>{w}</li>)}</ul></>}
        <footer className="cs-report-footer">{t("CerradoShift — Documento automatizado para apoio à análise. Não substitui laudo laboratorial, validação de campo ou recomendação de engenheiro agrônomo. Simulações de rotação não estão incluídas sem resultados vinculados ao talhão.")}</footer>
      </article>}
    </div>
  );
}
