import { useState } from "react";
import { Calculator, Droplets, Sprout, AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "../services/api";
import { useI18n } from "../i18n";
import "./CalculatorPage.css";

const initial = { et0_mm_day: "5", kcb: "0.95", ks: "1", kr: "1", kcmax: "1.2", few: "0.3", eta_actual_mm: "4", eta_max_mm: "5", ky: "1" };
const number = (v) => Number(v);
const fmt = (v, digits = 2, locale = "pt-BR") => Number.isFinite(Number(v)) ? Number(v).toLocaleString(locale, { maximumFractionDigits: digits }) : "—";

export default function CalculatorPage() {
  const { t, locale } = useI18n();
  const [values, setValues] = useState(initial);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const update = (key, value) => setValues(current => ({ ...current, [key]: value }));

  async function calculate(event) {
    event.preventDefault();
    setLoading(true); setError(""); setResult(null);
    try {
      const [dualKc, yieldResponse] = await Promise.all([
        api.assessDualKc({ et0_mm_day: number(values.et0_mm_day), kcb: number(values.kcb), ks: number(values.ks), kr: number(values.kr), kcmax: number(values.kcmax), few: number(values.few) }),
        api.assessYieldWaterResponse({ eta_actual_mm: number(values.eta_actual_mm), eta_max_mm: number(values.eta_max_mm), ky: number(values.ky) }),
      ]);
      setResult({ dualKc, yieldResponse });
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }

  const fields = [
    ["et0_mm_day", "ET₀ diária", "mm/dia", "5"],
    ["kcb", "Coeficiente basal (Kcb)", "adimensional", "0,95"],
    ["ks", "Fator de estresse hídrico (Ks)", "0 a 1", "1"],
    ["kr", "Fator de redução (Kr)", "0 a 1", "1"],
    ["kcmax", "Kc máximo (Kcmax)", "adimensional", "1,2"],
    ["few", "Fração de solo molhado/exposto (few)", "0 a 1", "0,3"],
    ["eta_actual_mm", "ET real da cultura", "mm", "4"],
    ["eta_max_mm", "ET máxima sem estresse", "mm", "5"],
    ["ky", "Fator de resposta do rendimento (Ky)", "adimensional", "1"],
  ];

  return <div className="calculator-page">
    <div className="page-heading"><h1>{t("Calculadora Agrícola")}</h1><p>{t("Execute os modelos científicos do CerradoShift pela API integrada.")}</p></div>
    <form className="calc-card" onSubmit={calculate}>
      <div className="calc-title"><Calculator /><h2>{t("Parâmetros dos modelos")}</h2></div>
      <p className="calc-description">{t("Informe os parâmetros medidos ou validados para calcular evapotranspiração pelo método dual Kc e resposta relativa da produtividade à água.")}</p>
      <div className="calculator-grid">
        {fields.map(([key, label, unit, placeholder]) => <label className="calc-field" key={key}><span>{t(label)}</span><div className="calc-input-wrap"><input type="number" step="any" min="0" max={key === "ks" || key === "kr" || key === "few" ? 1 : undefined} required value={values[key]} placeholder={t(placeholder)} onChange={e => update(key, e.target.value)} /><span>{t(unit)}</span></div></label>)}
      </div>
      <button className="rotation-save" type="submit" disabled={loading}>{loading ? t("Calculando…") : t("Calcular com o motor científico")}</button>
    </form>
    {error && <section className="calc-card"><p><AlertCircle size={18} /> {error}</p></section>}
    {result && <div className="calculator-grid results-grid">
      <section className="calc-card"><div className="calc-title"><Droplets /><h2>{t("Evapotranspiração dual Kc")}</h2></div><p><strong>{t("ETc calculada:")}</strong> {fmt(result.dualKc.etc_actual_mm_day, 2, locale)} {t("mm/dia")}</p><pre>{JSON.stringify(result.dualKc, null, 2)}</pre></section>
      <section className="calc-card"><div className="calc-title"><Sprout /><h2>{t("Resposta da cultura à água")}</h2></div><p><strong>{t("Redução relativa estimada:")}</strong> {fmt(result.yieldResponse.estimated_relative_yield_loss_percent, 2, locale)}%</p><pre>{JSON.stringify(result.yieldResponse, null, 2)}</pre></section>
    </div>}
    <p className="calc-description"><CheckCircle2 size={16} /> {t("Os resultados dependem da qualidade dos parâmetros de entrada e não substituem calibração local nem avaliação de profissional agrônomo.")}</p>
  </div>;
}
