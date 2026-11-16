
import { useState } from "react";
import "./RotationPage.css";
import { useI18n } from "../i18n";

const STORAGE_TALHOES = "cerradoshift_talhoes";

function carregarTalhoes() {
  try {
    const dados = JSON.parse(localStorage.getItem(STORAGE_TALHOES));
    return Array.isArray(dados) ? dados : [];
  } catch {
    return [];
  }
}

const culturas = [
  "Soja",
  "Milho",
  "Feijão",
  "Braquiária",
  "Milheto",
  "Sorgo",
  "Trigo",
  "Algodão",
];

const STORAGE_KEY = "cerradoshift_rotacoes";

function carregarRotacoes() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

export default function RotationPage() {
  const { t, tn } = useI18n();
  const [talhoesDisponiveis] = useState(carregarTalhoes);
  const [talhao, setTalhao] = useState("");
  const [ciclos, setCiclos] = useState(["Soja", "Milho", "Braquiária"]);
  const [rotacoes, setRotacoes] = useState(carregarRotacoes);

  function alterarCiclo(index, cultura) {
    setCiclos(anteriores =>
      anteriores.map((item, i) => i === index ? cultura : item)
    );
  }

  function salvarRotacao() {
    if (!talhao.trim()) {
      alert(t("Informe o nome do talhão."));
      return;
    }

    const nova = {
      id: crypto.randomUUID(),
      talhao: talhao.trim(),
      ciclos: [...ciclos],
    };

    const atualizadas = [...rotacoes, nova];

    setRotacoes(atualizadas);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(atualizadas));
  }

  function excluirRotacao(id) {
    const atualizadas = rotacoes.filter(item => item.id !== id);

    setRotacoes(atualizadas);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(atualizadas));
  }

  return (
    <div className="rotation-page">
      <div className="page-heading">
        <h1>{t("Planejamento de Rotação de Culturas")}</h1>
        <p>
          {t("Organize e compare sequências de cultivo para os talhões da propriedade.")}
        </p>
      </div>

      <section className="rotation-card">
        <h2>{t("Nova estratégia")}</h2>

        <label htmlFor="talhao">{t("Nome do talhão")}</label>
        
        <select
        id="talhao"
        value={talhao}
        onChange={(e) => setTalhao(e.target.value)}
        >
        <option value="">{t("Selecione um talhão")}</option>

        {talhoesDisponiveis.map((item) => (
            <option key={item.id} value={item.id}>
            {tn(item.nome)} — {item.area.toFixed(2)} ha
            </option>
        ))}
        </select>


        <div className="cycle-grid">
          {ciclos.map((cultura, index) => (
            <div className="cycle" key={index}>
              <span>{t("Ciclo {n}", { n: index + 1 })}</span>

              <select
                value={cultura}
                onChange={e =>
                  alterarCiclo(index, e.target.value)
                }
              >
                {culturas.map(item => (
                  <option key={item} value={item}>
                    {t(item)}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>

        <h3>{t("Sequência planejada")}</h3>

        <div className="rotation-timeline">
          {ciclos.map((cultura, index) => (
            <div className="timeline-step" key={index}>
              <div className="timeline-crop">{t(cultura)}</div>
              {index < ciclos.length - 1 && (
                <span className="timeline-arrow">→</span>
              )}
            </div>
          ))}
        </div>

        <button className="rotation-save" onClick={salvarRotacao}>
          {t("Salvar estratégia")}
        </button>
      </section>

      <section className="rotation-card">
        <h2>{t("Estratégias cadastradas")}</h2>

        {rotacoes.length === 0 ? (
          <p>{t("Nenhuma estratégia cadastrada ainda.")}</p>
        ) : (
          <div className="saved-rotations">
            {rotacoes.map(rotacao => (
              <div className="saved-rotation" key={rotacao.id}>
                <div>
                  <strong>{rotacao.talhao}</strong>
                  <p>{rotacao.ciclos.map(c => t(c)).join(" → ")}</p>
                </div>

                <button onClick={() => excluirRotacao(rotacao.id)}>
                  {t("Excluir")}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
