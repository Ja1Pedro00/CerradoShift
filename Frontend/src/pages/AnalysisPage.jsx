import { useState } from "react";
import { Activity, AlertTriangle, CheckCircle2 } from "lucide-react";
import { api, fieldRequest } from "../services/api";
import { useI18n } from "../i18n";
import "./AnalysisPage.css";

const STORAGE_ROTACOES = "cerradoshift_rotacoes";
const STORAGE_TALHOES = "cerradoshift_talhoes";
function lerDados(key) { try { const value = JSON.parse(localStorage.getItem(key)); return Array.isArray(value) ? value : []; } catch { return []; } }
const cropIds = { "soja": "soybean", "milho": "maize", "algodão": "cotton", "feijão": "bean", "braquiária": "urochloa_ruziziensis", "milheto": "millet", "sorgo": "sorghum", "trigo": "wheat" };
const normalizar = (crop) => cropIds[String(crop).toLowerCase()] || String(crop).toLowerCase();

export default function AnalysisPage() {
  const { t, tn } = useI18n();
  const [rotacoes] = useState(() => lerDados(STORAGE_ROTACOES));
  const [talhoes] = useState(() => lerDados(STORAGE_TALHOES));
  const [primeira, setPrimeira] = useState("");
  const [segunda, setSegunda] = useState("");
  const [resultados, setResultados] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [environment, setEnvironment] = useState(null);
  const [environmentLoading, setEnvironmentLoading] = useState(false);
  const [environmentError, setEnvironmentError] = useState("");
  const nomeTalhao = (id) => tn(talhoes.find(item => item.id === id)?.nome) || id || t("Sem identificação");
  const estrategiaA = rotacoes.find(r => r.id === primeira);
  const estrategiaB = rotacoes.find(r => r.id === segunda);

  async function consultarAmbiente() {
    setEnvironmentLoading(true); setEnvironmentError(""); setEnvironment(null);
    try {
      const strategies = [estrategiaA, estrategiaB];
      const unique = [...new Map(strategies.map(strategy => {
        const field = talhoes.find(item => item.id === strategy.talhao);
        if (!field) throw new Error(t("O talhão associado à estratégia {id} não foi encontrado.", { id: strategy.id }));
        return [field.id, field];
      })).values()];
      const results = await Promise.all(unique.map(async field => [field.id, await api.fieldContext(fieldRequest(field))]));
      setEnvironment(Object.fromEntries(results));
    } catch (err) { setEnvironmentError(err.message); }
    finally { setEnvironmentLoading(false); }
  }

  async function avaliar() {
    setLoading(true); setError(""); setResultados(null);
    try {
      const [a, b] = await Promise.all([estrategiaA, estrategiaB].map(estrategia => api.assessRotation({ crop_sequence: estrategia.ciclos.map(normalizar) })));
      setResultados({ a, b });
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  function StrategyCard({ strategy, title, assessment }) {
    return <div className="analysis-card"><h2>{title}</h2><p><strong>{t("Talhão:")}</strong> {nomeTalhao(strategy.talhao)}</p><div className="analysis-crops">{strategy.ciclos.map((crop, i) => <div className="analysis-cycle" key={`${crop}-${i}`}><span>{t("Ciclo {n}", { n: i + 1 })}</span><strong>{t(crop)}</strong></div>)}</div>
      {assessment && <div className="analysis-status"><strong><CheckCircle2 size={16}/> {t("Avaliação da sequência concluída")}</strong><p>{assessment.overall_note}</p><small>{t("Base de dados:")} {assessment.data_completeness}</small></div>}
    </div>;
  }

  return <div className="analysis-page">
    <div className="page-heading"><h1>{t("Análises e Cenários")}</h1><p>{t("Compare sequências cadastradas e avalie as relações hospedeiro–praga com o motor científico.")}</p></div>
    <section className="analysis-card"><h2>{t("Selecionar estratégias")}</h2>
      {rotacoes.length < 2 ? <p>{t("Cadastre pelo menos duas estratégias na página Rotação de Culturas.")}</p> : <div className="analysis-selectors">
        <div><label htmlFor="estrategiaA">{t("Estratégia A")}</label><select id="estrategiaA" value={primeira} onChange={e => { setPrimeira(e.target.value); setResultados(null); }}><option value="">{t("Selecione")}</option>{rotacoes.map(r => <option key={r.id} value={r.id}>{nomeTalhao(r.talhao)} — {r.ciclos.map(c => t(c)).join(" / ")}</option>)}</select></div>
        <div><label htmlFor="estrategiaB">{t("Estratégia B")}</label><select id="estrategiaB" value={segunda} onChange={e => { setSegunda(e.target.value); setResultados(null); }}><option value="">{t("Selecione")}</option>{rotacoes.filter(r => r.id !== primeira).map(r => <option key={r.id} value={r.id}>{nomeTalhao(r.talhao)} — {r.ciclos.map(c => t(c)).join(" / ")}</option>)}</select></div>
      </div>}
      <button className="rotation-save" disabled={!estrategiaA || !estrategiaB || loading} onClick={avaliar}>{loading ? t("Avaliando…") : t("Avaliar as duas estratégias")}</button>
    </section>
    {error && <section className="analysis-card"><p><AlertTriangle size={18}/> {error}</p></section>}
    {estrategiaA && estrategiaB && <div className="analysis-grid"><StrategyCard strategy={estrategiaA} title={t("Estratégia A")} assessment={resultados?.a}/><StrategyCard strategy={estrategiaB} title={t("Estratégia B")} assessment={resultados?.b}/></div>}
    {resultados && <section className="analysis-card"><h2><Activity size={18}/> {t("Relações identificadas")}</h2><p>{t("Os resultados abaixo descrevem relações presentes no catálogo de referência. Não são previsão de infestação nem garantia de controle.")}</p>
      {[ ["Estratégia A", resultados.a], ["Estratégia B", resultados.b] ].map(([label, result]) => <div key={label}><h3>{t(label)}</h3>{result.transitions.map((transition, i) => <div className="analysis-status" key={`${label}-${i}`}><strong>{t(transition.from)} → {t(transition.to)}</strong>{transition.pests.map((pest, j) => <p key={`${pest.pest_id}-${j}`}><b>{pest.scientific_name || pest.pest_id}:</b> {t(pest.interpretation)}</p>)}</div>)}</div>)}
    </section>}
  </div>;
}
