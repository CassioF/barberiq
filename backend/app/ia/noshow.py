"""
Módulo de IA — previsão de no-show (falta ao agendamento).

Algoritmo: Regressão Logística (scikit-learn) treinada com histórico SIMULADO.
Variáveis (conforme o escopo do projeto):
  1. taxa_faltas       — proporção de faltas do cliente nos atendimentos anteriores (0 a 1)
  2. dia_semana        — 0 = segunda ... 6 = domingo (codificado em one-hot)
  3. antecedencia_horas — quanto tempo antes o horário foi marcado

Saída: probabilidade (0 a 1) de o cliente faltar.
Treino: `python -m app.ia.noshow` (também roda sozinho na 1ª previsão se não houver modelo salvo).
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

PASTA = Path(__file__).parent
ARQ_MODELO = PASTA / "modelo_noshow.joblib"
ARQ_METRICAS = PASTA / "modelo_noshow_metricas.json"
VERSAO = "logreg-v1"
FEATURES = ["taxa_faltas", "dia_semana", "antecedencia_horas"]
TAXA_CLIENTE_NOVO = 0.10  # sem histórico, assume a taxa média da população

_modelo = None


def gerar_dados_simulados(n: int = 6000, seed: int = 42) -> pd.DataFrame:
    """Gera histórico sintético com uma regra plausível + ruído."""
    rng = np.random.default_rng(seed)
    taxa = np.clip(rng.beta(0.8, 5.0, n), 0, 1)
    dia = rng.integers(0, 7, n)
    antecedencia = np.clip(rng.exponential(60, n) + 1, 1, 720)

    z = (
        -2.9
        + 4.5 * taxa                                   # quem já faltou, falta mais
        + np.where(np.isin(dia, [0, 4, 5]), 0.5, 0.0)  # segunda, sexta e sábado
        + np.where(antecedencia > 120, 0.9, 0.0)       # marcado com muita antecedência
        + np.where(antecedencia < 6, -0.6, 0.0)        # marcado em cima da hora
    )
    prob = 1 / (1 + np.exp(-z))
    faltou = (rng.random(n) < prob).astype(int)
    return pd.DataFrame(
        {"taxa_faltas": taxa, "dia_semana": dia, "antecedencia_horas": antecedencia, "faltou": faltou}
    )


def _construir_pipeline() -> Pipeline:
    prep = ColumnTransformer(
        [
            ("dia", OneHotEncoder(categories=[list(range(7))], handle_unknown="ignore"), ["dia_semana"]),
            ("taxa", "passthrough", ["taxa_faltas"]),
            ("antec", FunctionTransformer(np.log1p), ["antecedencia_horas"]),
        ]
    )
    return Pipeline([("prep", prep), ("clf", LogisticRegression(max_iter=1000))])


def treinar(df: pd.DataFrame | None = None) -> dict:
    """Treina, salva modelo + métricas e devolve as métricas."""
    global _modelo
    df = gerar_dados_simulados() if df is None else df
    X_tr, X_te, y_tr, y_te = train_test_split(
        df[FEATURES], df["faltou"], test_size=0.25, random_state=7, stratify=df["faltou"]
    )
    pipe = _construir_pipeline().fit(X_tr, y_tr)
    prob = pipe.predict_proba(X_te)[:, 1]
    metricas = {
        "algoritmo": "Regressão Logística (scikit-learn)",
        "versao": VERSAO,
        "amostras_treino": int(len(X_tr)),
        "amostras_teste": int(len(X_te)),
        "taxa_noshow_base": round(float(df["faltou"].mean()), 4),
        "acuracia": round(float(accuracy_score(y_te, prob >= 0.5)), 4),
        "auc_roc": round(float(roc_auc_score(y_te, prob)), 4),
        "dados": "histórico simulado",
    }
    joblib.dump(pipe, ARQ_MODELO)
    ARQ_METRICAS.write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")
    _modelo = pipe
    return metricas


def _carregar() -> Pipeline:
    global _modelo
    if _modelo is None:
        if ARQ_MODELO.exists():
            try:
                _modelo = joblib.load(ARQ_MODELO)
            except Exception:  # arquivo incompatível com a versão do sklearn
                treinar()
        else:
            treinar()
    return _modelo


def metricas() -> dict:
    _carregar()
    return json.loads(ARQ_METRICAS.read_text(encoding="utf-8"))


def prever(taxa_faltas: float, dia_semana: int, antecedencia_horas: float) -> float:
    """Probabilidade (0-1) de no-show para as variáveis informadas."""
    X = pd.DataFrame(
        [{"taxa_faltas": taxa_faltas, "dia_semana": dia_semana, "antecedencia_horas": max(antecedencia_horas, 0.0)}]
    )
    return float(_carregar().predict_proba(X)[0, 1])


def nivel(risco: float, limite_alto: float = 0.5) -> str:
    if risco >= limite_alto:
        return "alto"
    if risco >= limite_alto * 0.5:
        return "medio"
    return "baixo"


if __name__ == "__main__":
    print(json.dumps(treinar(), ensure_ascii=False, indent=2))
