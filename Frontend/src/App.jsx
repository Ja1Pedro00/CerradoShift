import ReportsPage from "./pages/ReportsPage";
import SoilDiagnostic from "./components/SoilDiagnostic";
import CalculatorPage from "./pages/CalculatorPage";
import MapPreview from "./components/MapPreview";
import AnalysisPage from "./pages/AnalysisPage";
import RotationPage from "./pages/RotationPage";
import FarmMap from './components/FarmMap';
import SettingsPage from "./pages/SettingsPage";
import { useEffect, useState } from "react";
import { api, fieldRequest } from "./services/api";
import { useI18n, LanguageSwitch } from "./i18n";
import { NavLink, Routes, Route, useLocation } from "react-router";
import {
  LayoutDashboard, Map, Sprout, ChartNoAxesCombined,
  FileText, Settings, Menu, X, Satellite, Leaf,
  Layers3, Calculator
} from "lucide-react";

const menu = [
  { name: "Dashboard", path: "/", icon: LayoutDashboard },
  {name: "Calculadora Agrícola", path: "/calculadora", icon: Calculator},
  { name: "Mapa da Propriedade", path: "/mapa", icon: Map },
  { name: "Rotação de Culturas", path: "/rotacao", icon: Sprout },
  { name: "Análises e Cenários", path: "/analises", icon: ChartNoAxesCombined },
  { name: "Relatórios", path: "/relatorios", icon: FileText },
  { name: "Diagnóstico do Solo", path: "/solo", icon: Layers3 },
  { name: "Configurações", path: "/configuracoes", icon: Settings },
];


const STORAGE_TALHOES = "cerradoshift_talhoes";

function carregarTalhoes() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_TALHOES));
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function formatarNumero(value, digits = 1, locale = "pt-BR") {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value.toLocaleString(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function Dashboard() {
  const { t, tn, locale } = useI18n();
  const [talhoes] = useState(carregarTalhoes);
  const [talhaoId, setTalhaoId] = useState(() => carregarTalhoes()[0]?.id || "");
  const [dados, setDados] = useState(null);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState("");

  const talhaoSelecionado = talhoes.find((item) => item.id === talhaoId) || null;

  useEffect(() => {
    let ativo = true;
    async function carregarIndicadores() {
      setDados(null);
      setErro("");
      if (!talhaoSelecionado) return;
      try {
        setLoading(true);
        const resposta = await api.fieldContext(fieldRequest(talhaoSelecionado));
        if (ativo) setDados(resposta);
      } catch (error) {
        if (ativo) setErro(error.message || t("Não foi possível carregar os indicadores da API."));
      } finally {
        if (ativo) setLoading(false);
      }
    }
    carregarIndicadores();
    return () => { ativo = false; };
  }, [talhaoId]);

  const clima = dados?.climate || {};
  const solo = dados?.soil || {};
  const umidadeRaiz = clima?.soil_moisture_rootzone?.mean;
  const umidadeMeteo = clima?.soil_moisture_volumetric?.rootzone_7_28cm_latest_m3m3;
  const umidade = typeof umidadeRaiz === "number" ? umidadeRaiz * 100
    : typeof umidadeMeteo === "number" ? umidadeMeteo * 100 : null;
  const metricas = [
    { label: "Temperatura média", value: formatarNumero(clima.tmean_mean_c, 1, locale), unit: "°C", icon: "thermometer" },
    { label: "Precipitação acumulada", value: formatarNumero(clima.precip_mm_total, 0, locale), unit: "mm", icon: "cloud-rain" },
    { label: "Umidade do solo", value: formatarNumero(umidade, 1, locale), unit: "%", icon: "droplets" },
    { label: "Radiação solar média", value: formatarNumero(clima.solar_mj_m2_mean, 1, locale), unit: "MJ/m²/dia", icon: "sun" },
  ];

  return (
    <>
      <div className="page-heading">
        <h1>{t("Visão geral")}</h1>
        <p>{t("Monitore sua propriedade e planeje safras mais resilientes.")}</p>
      </div>

      {talhoes.length > 0 && (
        <div className="dashboard-field-select">
          <label htmlFor="dashboard-talhao">{t("Talhão analisado")}</label>
          <select id="dashboard-talhao" value={talhaoId} onChange={(event) => setTalhaoId(event.target.value)}>
            {talhoes.map((item) => <option key={item.id} value={item.id}>{tn(item.nome)}</option>)}
          </select>
        </div>
      )}

      {loading && <section className="panel dashboard-data-pending" aria-live="polite">{t("Consultando clima, solo e fontes ambientais da API…")}</section>}
      {erro && <section className="panel dashboard-data-pending dashboard-data-error" role="alert"><strong>{t("Não foi possível atualizar os indicadores.")}</strong><p>{erro}</p><button type="button" onClick={() => setTalhaoId((value) => `${value}`)}>{t("Tentar novamente")}</button></section>}
      {!talhaoSelecionado && <section className="panel dashboard-data-pending"><strong>{t("Nenhum talhão cadastrado")}</strong><p>{t("Cadastre e delimite um talhão no Mapa da Propriedade para consultar os indicadores reais.")}</p></section>}

      {talhaoSelecionado && !loading && !erro && dados && (
        <section className="dashboard-metrics" aria-live="polite">
          {metricas.map((item) => (
            <article className="panel dashboard-metric" key={item.label}>
              <span className="dashboard-metric-icon" aria-hidden="true">{item.icon === "thermometer" ? "♨" : item.icon === "cloud-rain" ? "☂" : item.icon === "droplets" ? "◉" : "☀"}</span>
              <span className="dashboard-metric-label">{t(item.label)}</span>
              <strong>{item.value === null ? t("Sem dado disponível") : `${item.value} ${t(item.unit)}`}</strong>
              <small>{item.value === null ? t("A fonte não retornou este indicador para o talhão.") : t("Fonte: {fonte}", { fonte: item.label.includes("Temperatura") || item.label.includes("Precipitação") || item.label.includes("Radiação") ? "NASA POWER" : "NASA POWER / Open-Meteo" })}</small>
            </article>
          ))}
          <p className="dashboard-data-period">{t("Dados retornados pela API para {nome}. Período: {inicio} a {fim}.", { nome: tn(talhaoSelecionado.nome), inicio: dados.window?.start || "—", fim: dados.window?.end || "—" })}</p>
        </section>
      )}

      <div className="dashboard-grid">
        <section className="panel">
          <MapPreview />
        </section>
        <section className="panel">
          <h2>{t("Estratégias de rotação")}</h2>
          <div className="strategy">
            <strong>{t("Estratégias cadastradas")}</strong>
            <p>{t("Consulte e gerencie as sequências na página Rotação de Culturas.")}</p>
          </div>
        </section>
      </div>
    </>
  );
}

function obterCoordenadasTalhao(talhao) {
  if (!talhao) return null;

  // Coordenadas diretas
  const lat = Number(talhao.lat);
  const lon = Number(talhao.lon);

  if (
    Number.isFinite(lat) &&
    Number.isFinite(lon) &&
    lat >= -90 && lat <= 90 &&
    lon >= -180 && lon <= 180
  ) {
    return { lat, lon };
  }

  // Coordenadas de um polígono GeoJSON
  const geometry =
    talhao.geometry ||
    talhao.geometria ||
    talhao.geojson?.geometry;

  if (!geometry) return null;

  let anel;

  if (geometry.type === "Polygon") {
    anel = geometry.coordinates?.[0];
  } else if (geometry.type === "MultiPolygon") {
    anel = geometry.coordinates?.[0]?.[0];
  }

  if (!Array.isArray(anel) || anel.length < 3) {
    return null;
  }

  // Calcula o centro da caixa envolvente do polígono
  const pontos = anel.filter(
    (p) =>
      Array.isArray(p) &&
      Number.isFinite(p[0]) &&
      Number.isFinite(p[1])
  );

  if (pontos.length < 3) return null;

  const longitudes = pontos.map((p) => p[0]);
  const latitudes = pontos.map((p) => p[1]);

  return {
    lat: (Math.min(...latitudes) + Math.max(...latitudes)) / 2,
    lon: (Math.min(...longitudes) + Math.max(...longitudes)) / 2,
  };
}

function SoilPage() {
  const { t, tn } = useI18n();
  const [talhoes] = useState(carregarTalhoes);

  const [talhaoId, setTalhaoId] = useState(
    () => carregarTalhoes()[0]?.id || ""
  );

  const talhao = talhoes.find(
    (item) => String(item.id) === String(talhaoId)
  );
  const coordenadas = obterCoordenadasTalhao(talhao);

  return (
    <>
      <div className="page-heading">
        <h1>{t("Diagnóstico do Solo")}</h1>
        <p>
          {t("Analise as características físicas e químicas do solo da sua propriedade.")}
        </p>
      </div>

      {talhoes.length > 0 ? (
        <>
          <div className="dashboard-field-select">
            <label htmlFor="soil-talhao">
              {t("Talhão analisado")}
            </label>

            <select
              id="soil-talhao"
              value={talhaoId}
              onChange={(e) => setTalhaoId(e.target.value)}
            >
              {talhoes.map((item) => (
                <option key={item.id} value={item.id}>
                  {tn(item.nome)}
                </option>
              ))}
            </select>
          </div>

          {talhao && coordenadas ? (
            <SoilDiagnostic
              key={talhao.id}
              lat={coordenadas.lat}
              lon={coordenadas.lon}
            />
          ) : (
            <section className="panel">
              <h3>{t("Coordenadas indisponíveis")}</h3>
              <p>
                {t("Não foi possível identificar a localização geográfica deste talhão.")}
              </p>
            </section>
          )}
        </>
      ) : (
        <section className="panel">
          <h2>{t("Nenhum talhão cadastrado")}</h2>
          <p>
            {t("Cadastre um talhão no Mapa da Propriedade para gerar o diagnóstico do solo.")}
          </p>
        </section>
      )}
    </>
  );
}


export default function App() {
  const { t } = useI18n();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const page = menu.find(item => item.path === location.pathname);

  return (
    <div className="app-layout">
      {menuOpen && (
        <div
          className="overlay"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-icon"><Leaf size={26} /></div>
          <div>
            <h2>Cerrado<span>Shift</span></h2>
            <small>NASA Space Apps Challenge</small>
          </div>
        </div>

        <nav className="sidebar-nav">
          {menu.map(({ name, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              <Icon size={19} />
              <span>{t(name)}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <Satellite size={22} />
          <div>
            <strong>{t("Dados da NASA")}</strong>
            <small>{t("Integração em desenvolvimento")}</small>
          </div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu"
              aria-label={menuOpen ? t("Fechar menu") : t("Abrir menu")}
              onClick={() => setMenuOpen(!menuOpen)}
            >
              {menuOpen ? <X /> : <Menu />}
            </button>
            <div className="breadcrumb">
              CerradoShift <span>/</span> {page ? t(page.name) : t("Página")}
            </div>
          </div>
          <div className="topbar-right">
            <LanguageSwitch />
            <div className="farm-selector">
              <Map size={16} />
              {t("Fazenda demonstrativa")}
            </div>
          </div>
        </header>

        <main className="main-content">
          
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route
              path="/calculadora"
              element={<CalculatorPage />}
            />
            <Route
              path="/mapa"
              element={
                <>
                  <div className="page-heading">
                    <h1>{t("Mapa da Propriedade")}</h1>
                    <p>{t("Selecione e delimite os talhões agrícolas.")}</p>
                  </div>

                  <FarmMap />
                </>
              }
            />
            <Route path="/rotacao" element={<RotationPage />} />
            <Route
              path="/analises"
              element={<AnalysisPage />}
            />
            <Route
              path="/relatorios"
              element={<ReportsPage />}
            />
            <Route
              path="/solo"
              element={<SoilPage />}
            />
            <Route path="/configuracoes" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
