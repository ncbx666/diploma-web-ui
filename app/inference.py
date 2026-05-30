from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import joblib
import numpy as np
import pandas as pd


APP_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = APP_ROOT / "models"

COLUMN_ALIASES = {
    "unnamed_0": "year",
    "год": "year",
    "target_fav": "target_favorable",
    "target_favourable": "target_favorable",
    "cloudines": "cloudiness",
    "cloudines_": "cloudiness",
    "t_7": "t_gt_7",
    "t_gt_7": "t_gt_7",
    "t_10": "t_gt_10",
    "t_gt_10": "t_gt_10",
}

REQUIRED_ID_COLUMNS = ["year", "day"]


@dataclass(frozen=True)
class ModelProfile:
    key: str
    title: str
    disease: str
    location: str
    model_label: str
    model_path: Path
    config_path: Path
    prediction_column: str
    probability_column: str
    positive_label: str
    negative_label: str
    feature_descriptions: dict[str, str]


COMMON_FEATURES = {
    "year": "Год наблюдения. Колонка должна называться `year` или `год`; если год указан в названии листа, сервис добавит его сам.",
    "day": "День года. Колонка должна называться `day`.",
    "t_min": "Минимальная температура за день. В Excel можно писать `T_min`.",
    "t_max": "Максимальная температура за день. В Excel можно писать `T_max`.",
    "is_rain": "Флаг дождя: 1 - дождь был, 0 - дождя не было. В Excel можно писать `Is_rain`.",
    "precipitation": "Количество осадков. В Excel можно писать `Precipitation`.",
    "t_avg": "Средняя температура. В Excel можно писать `T_avg`; если колонки нет, считается как `(t_min + t_max) / 2`.",
    "cloudiness": "Облачность. В Excel можно писать `Cloudiness` или `Cloudines`.",
}

MODEL_PROFILES = {
    "krasnodar_rice_blast": ModelProfile(
        key="krasnodar_rice_blast",
        title="Пирикуляриоз риса в Краснодаре",
        disease="пирикуляриоз риса",
        location="Краснодар",
        model_label="krasnodar_model_results_optuna_10/random_forest_f1_0.741",
        model_path=MODEL_DIR / "krasnodar_rice_blast_random_forest.joblib",
        config_path=MODEL_DIR / "krasnodar_rice_blast_config.json",
        prediction_column="прогноз_пирикуляриоз",
        probability_column="вероятность_пирикуляриоз",
        positive_label="ожидается пирикуляриоз риса",
        negative_label="признаков события нет",
        feature_descriptions={
            **COMMON_FEATURES,
            "t_gt_7": "Температурный признак `T>7`. В Excel можно писать `T>7`; если колонки нет, используется `t_avg`.",
        },
    ),
    "gatchina_potato_late_blight": ModelProfile(
        key="gatchina_potato_late_blight",
        title="Фитофтороз картофеля в Гатчине",
        disease="фитофтороз картофеля",
        location="Гатчина",
        model_label="golitcino_model_results_optuna_50/random_forest_f1_0.691",
        model_path=MODEL_DIR / "gatchina_potato_late_blight_random_forest.joblib",
        config_path=MODEL_DIR / "gatchina_potato_late_blight_config.json",
        prediction_column="прогноз_фитофтороз",
        probability_column="вероятность_фитофтороз",
        positive_label="ожидается фитофтороз картофеля",
        negative_label="признаков события нет",
        feature_descriptions={
            **COMMON_FEATURES,
            "precipitation_t_gt_10": "Осадки при температуре выше 10 градусов. В Excel можно писать `Precipitation_T_gt_10`; если колонки нет, считается из `precipitation` и `t_avg`.",
            "t_gt_10": "Температурный признак `T>10`. В Excel можно писать `T>10`; если колонки нет, используется `t_avg`.",
        },
    ),
}


@dataclass(frozen=True)
class PredictionResult:
    frame: pd.DataFrame
    rows: int
    event_count: int
    feature_columns: list[str]
    source_sheets: list[str]
    profile: ModelProfile


def normalize_column(name: object) -> str:
    text = str(name).strip().lower().replace(">", "_gt_").replace("-", "_")
    cleaned = "".join(char if char.isalnum() or char == "_" else "_" for char in text)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def clean_numeric(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.replace("\xa0", " ", regex=False).str.strip()
    text = text.replace({"": np.nan, " ": np.nan, "nan": np.nan, "None": np.nan, "<NA>": np.nan, "-": np.nan})
    text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def get_profile(profile_key: str) -> ModelProfile:
    try:
        return MODEL_PROFILES[profile_key]
    except KeyError as exc:
        allowed = ", ".join(MODEL_PROFILES)
        raise ValueError(f"Неизвестный сценарий прогноза: {profile_key}. Доступно: {allowed}.") from exc


def load_config(profile: ModelProfile) -> dict:
    with profile.config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_model(profile: ModelProfile):
    if not profile.model_path.exists():
        raise FileNotFoundError(f"Model file not found: {profile.model_path}")
    return joblib.load(profile.model_path)


def model_feature_columns(profile_key: str = "krasnodar_rice_blast", model=None) -> list[str]:
    profile = get_profile(profile_key)
    if model is None:
        model = load_model(profile)
    names = getattr(model, "feature_names_in_", None)
    if names is not None:
        return [str(name) for name in names]
    config = load_config(profile)
    return [str(name) for name in config["feature_columns"]]


def load_excel_workbook(file_obj: str | Path | BinaryIO | BytesIO) -> tuple[pd.DataFrame, list[str]]:
    workbook = pd.ExcelFile(file_obj, engine="openpyxl")
    frames: list[pd.DataFrame] = []
    used_sheets: list[str] = []

    for sheet_name in workbook.sheet_names:
        raw = pd.read_excel(workbook, sheet_name=sheet_name, engine="openpyxl")
        if raw.empty:
            continue

        raw.columns = [COLUMN_ALIASES.get(normalize_column(column), normalize_column(column)) for column in raw.columns]
        if "year" not in raw.columns:
            match = re.search(r"\d{4}", str(sheet_name))
            if match is not None:
                raw.insert(0, "year", int(match.group(0)))

        if not set(REQUIRED_ID_COLUMNS).issubset(raw.columns):
            continue

        for column in raw.columns:
            raw[column] = clean_numeric(raw[column])

        raw = raw.dropna(subset=REQUIRED_ID_COLUMNS).copy()
        if raw.empty:
            continue

        raw["year"] = raw["year"].astype(int)
        raw["day"] = raw["day"].astype(int)
        raw["source_sheet"] = str(sheet_name)
        frames.append(raw)
        used_sheets.append(str(sheet_name))

    if not frames:
        raise ValueError("В Excel-файле не найдены листы с колонками year/day.")

    data = pd.concat(frames, ignore_index=True).sort_values(["year", "day"]).reset_index(drop=True)
    return data, used_sheets


def prepare_features(data: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    prepared = data.copy()

    if "t_avg" not in prepared.columns and {"t_min", "t_max"}.issubset(prepared.columns):
        prepared["t_avg"] = (prepared["t_min"] + prepared["t_max"]) / 2
    if "t_gt_7" not in prepared.columns and "t_avg" in prepared.columns:
        prepared["t_gt_7"] = prepared["t_avg"]
    if "t_gt_10" not in prepared.columns and "t_avg" in prepared.columns:
        prepared["t_gt_10"] = prepared["t_avg"]
    if "precipitation_t_gt_10" not in prepared.columns and {"precipitation", "t_avg"}.issubset(prepared.columns):
        prepared["precipitation_t_gt_10"] = prepared["precipitation"].where(prepared["t_avg"] > 10, 0)
    if "is_rain" not in prepared.columns and "precipitation" in prepared.columns:
        prepared["is_rain"] = (prepared["precipitation"].fillna(0) > 0).astype(int)

    missing = [column for column in feature_columns if column not in prepared.columns]
    for column in missing:
        prepared[column] = np.nan

    features = prepared[feature_columns].replace([np.inf, -np.inf], np.nan)
    return features


def predict_workbook(
    file_obj: str | Path | BinaryIO | BytesIO,
    profile_key: str = "krasnodar_rice_blast",
) -> PredictionResult:
    profile = get_profile(profile_key)
    model = load_model(profile)
    feature_columns = model_feature_columns(profile.key, model)
    data, source_sheets = load_excel_workbook(file_obj)
    features = prepare_features(data, feature_columns)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Skipping features without any observed values.*")
        predictions = model.predict(features).astype(int)
        probabilities = _positive_probabilities(model, features, predictions)

    result = data.copy()
    result[profile.prediction_column] = predictions
    result[profile.probability_column] = np.round(probabilities, 4)
    result["метка_прогноза"] = np.where(
        predictions == 1,
        profile.positive_label,
        profile.negative_label,
    )

    return PredictionResult(
        frame=result,
        rows=len(result),
        event_count=int(predictions.sum()),
        feature_columns=feature_columns,
        source_sheets=source_sheets,
        profile=profile,
    )


def _positive_probabilities(model, features: pd.DataFrame, predictions: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(features)
        classes = list(getattr(model, "classes_", [0, 1]))
        positive_index = classes.index(1) if 1 in classes else -1
        return probabilities[:, positive_index].astype(float)
    return predictions.astype(float)


def result_to_excel_bytes(result: PredictionResult) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        result.frame.to_excel(writer, index=False, sheet_name="marked_data")
        summary = pd.DataFrame(
            [
                {"metric": "rows", "value": result.rows},
                {"metric": "predicted_events", "value": result.event_count},
                {"metric": "scenario", "value": result.profile.title},
                {"metric": "model", "value": result.profile.model_label},
                {"metric": "features", "value": ", ".join(result.feature_columns)},
                {"metric": "source_sheets", "value": ", ".join(result.source_sheets)},
            ]
        )
        summary.to_excel(writer, index=False, sheet_name="summary")
    return output.getvalue()
