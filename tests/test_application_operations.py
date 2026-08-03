from __future__ import annotations

import ast
import inspect

import pandas as pd

from application import operations


def test_application_operations_do_not_call_terminal_io():
    tree = ast.parse(inspect.getsource(operations))
    terminal_calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"input", "print"}
    ]
    assert terminal_calls == []


def test_fetch_operations_are_parameter_driven_and_silent(
    system_temp_dir,
    completed_anime_df,
    top_anime_df,
    capsys,
):
    top_result = operations.fetch_top_anime_to_file(
        system_temp_dir,
        limit=3,
        access_token="fake-access-token",
        fetcher=lambda **_kwargs: top_anime_df,
    )
    completed_result = operations.fetch_completed_anime_to_file(
        "fixture-user",
        system_temp_dir,
        access_token="fake-access-token",
        fetcher=lambda *_args: completed_anime_df,
    )

    assert top_result.row_count == 3
    assert completed_result.row_count == 3
    assert top_result.path.is_file()
    assert completed_result.path.is_file()
    assert capsys.readouterr() == ("", "")


def test_local_file_operations_preserve_csv_pipeline_and_return_results(
    csv_fixture_dir,
    capsys,
):
    imputed = operations.impute_missing_scores_file(csv_fixture_dir)
    genre = operations.calculate_genre_importance_file(csv_fixture_dir)
    candidates = operations.create_recommendation_candidates_file(csv_fixture_dir)
    recommendations = operations.generate_recommendations_file(
        "fixture_user",
        csv_fixture_dir,
        num_recommendations=2,
        top_anime_count=2,
        randomness_factor=1,
    )

    assert imputed.path.name == "completed_anime_imputed.csv"
    assert genre.path.name == "genre_importance.csv"
    assert candidates.path.name == "recommendation_candidates.csv"
    assert recommendations.path.name == "fixture_user_recommendations.csv"
    assert recommendations.row_count == 2
    assert len(recommendations.titles) == 2
    assert pd.read_csv(recommendations.path)["Title"].tolist() == list(
        recommendations.titles
    )
    assert capsys.readouterr() == ("", "")
