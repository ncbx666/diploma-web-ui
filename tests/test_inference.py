from __future__ import annotations

from io import BytesIO

import pandas as pd

from app.inference import model_feature_columns, predict_workbook, result_to_excel_bytes


def make_krasnodar_workbook() -> BytesIO:
    data = pd.DataFrame(
        {
            "year": [2022, 2022, 2022],
            "day": [153, 154, 155],
            "T_min": [15.9, 14.8, 18.1],
            "T_max": [24.9, 24.5, 27.0],
            "Is_rain": [0, 0, 1],
            "Precipitation": [0.0, 0.0, 6.5],
            "T_avg": [20.0, 19.7, 22.5],
            "Cloudines": [50, 60, 80],
            "T>7": [20.0, 19.7, 22.5],
        }
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="Лист1")
    output.seek(0)
    return output


def make_gatchina_workbook() -> BytesIO:
    data = pd.DataFrame(
        {
            "Unnamed: 0": [2022, 2022, 2022],
            "day": [152, 153, 154],
            "T_min": [9.5, 7.8, 10.1],
            "T_max": [20.3, 20.5, 21.0],
            "Is_rain": [1, 1, 0],
            "Precipitation": [0.8, 0.1, 0.0],
            "T_avg": [15.7, 18.7, 16.2],
            "Cloudiness": [8, 8, 4],
            "Precipitation_T_gt_10": [0.8, 0.1, 0.0],
            "T>10": [15.7, 18.7, 16.2],
        }
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="G2022")
    output.seek(0)
    return output


def test_krasnodar_feature_columns_match_artifact() -> None:
    assert model_feature_columns("krasnodar_rice_blast") == [
        "year",
        "day",
        "t_min",
        "t_max",
        "is_rain",
        "precipitation",
        "t_avg",
        "cloudiness",
        "t_gt_7",
    ]


def test_gatchina_feature_columns_match_artifact() -> None:
    assert model_feature_columns("gatchina_potato_late_blight") == [
        "year",
        "day",
        "t_min",
        "t_max",
        "is_rain",
        "precipitation",
        "t_avg",
        "cloudiness",
        "precipitation_t_gt_10",
        "t_gt_10",
    ]


def test_predict_krasnodar_workbook_adds_markup_columns() -> None:
    result = predict_workbook(make_krasnodar_workbook(), "krasnodar_rice_blast")

    assert result.rows == 3
    assert "прогноз_пирикуляриоз" in result.frame.columns
    assert "вероятность_пирикуляриоз" in result.frame.columns
    assert set(result.frame["прогноз_пирикуляриоз"].unique()).issubset({0, 1})


def test_predict_gatchina_workbook_adds_markup_columns() -> None:
    result = predict_workbook(make_gatchina_workbook(), "gatchina_potato_late_blight")

    assert result.rows == 3
    assert "прогноз_фитофтороз" in result.frame.columns
    assert "вероятность_фитофтороз" in result.frame.columns
    assert set(result.frame["прогноз_фитофтороз"].unique()).issubset({0, 1})


def test_result_to_excel_bytes_returns_xlsx() -> None:
    result = predict_workbook(make_krasnodar_workbook(), "krasnodar_rice_blast")
    payload = result_to_excel_bytes(result)

    assert payload.startswith(b"PK")
    parsed = pd.read_excel(BytesIO(payload), sheet_name="marked_data")
    assert len(parsed) == 3
