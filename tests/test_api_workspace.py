"""Workspace reads must preserve provider truth and keep credentials private."""
from dataclasses import replace

from fastapi.testclient import TestClient

from AniRec.api import create_app
from AniRec.infrastructure.json_storage import JsonStore


def test_sample_reports_are_explicit_and_do_not_replace_missing_live_data(tmp_path):
    with TestClient(create_app(root_override=str(tmp_path))) as client:
        live = client.get("/api/workspace/profile").json()
        assert live["profile"] is None
        assert live["reason"] == "not-connected"
        sample = client.get("/api/workspace/profile?sample=true").json()["profile"]
        assert sample["is_sample"] is True
        assert sample["identity"]["username"] == "anirec_sample"
        assert sample["identity"]["completed"] == 312
        assert client.get("/api/workspace/profile").json() == live
        assert not list(tmp_path.rglob("*.csv"))


def test_compare_preserves_counts_scores_and_refuses_unknown_sample_names(tmp_path):
    with TestClient(create_app(root_override=str(tmp_path))) as client:
        assert client.get("/api/workspace/compare").json()["reason"] == "username-required"
        sample = client.get("/api/workspace/compare?sample=true").json()["report"]
        assert sample["is_sample"] is True
        assert sample["friend"]["total_anime"] == 412
        assert sample["friend"]["match_score"] == 78
        assert sample["friend"]["shared_anime"] == 96
        assert sample["friend"]["both_rated"] == 74
        assert client.get("/api/workspace/compare?sample=true&username=unknown").json()["report"] is None


def test_settings_response_is_an_allowlist_not_a_serialized_settings_object(tmp_path):
    app = create_app(root_override=str(tmp_path))
    service = app.state.container.settings
    service.save_preferences(replace(service.load(), client_id="test-client", client_secret="not-a-real-secret"))
    with TestClient(app) as client:
        response = client.get("/api/workspace/settings")
        assert response.status_code == 200
        assert response.json()["client_id_present"] is True
        assert "test-client" not in response.text
        assert "not-a-real-secret" not in response.text
        assert "client_secret" not in response.text


def test_workspace_reads_use_existing_token_boundary(tmp_path):
    with TestClient(create_app(root_override=str(tmp_path), token="test-token")) as client:
        for route in ("profile", "compare", "settings"):
            assert client.get(f"/api/workspace/{route}").status_code == 401
            assert client.get(f"/api/workspace/{route}", headers={"X-AniRec-Token": "test-token"}).status_code == 200


def test_local_profile_reads_the_active_synced_snapshot(tmp_path):
    app = create_app(root_override=str(tmp_path))
    profiles = app.state.container.profiles
    profile = profiles.create_profile("local_reader")
    directory = profiles.directory(profile.profile_id, create=True)
    JsonStore().write(profile.to_dict(), directory / "profile.json")
    profiles.set_active(profile.profile_id)
    (directory / "completed_anime.csv").write_text(
        "Anime ID,Title,User Score,Mean Score,Episodes\n19,Monster,9,8.87,74\n",
        encoding="utf-8",
    )
    with TestClient(app) as client:
        result = client.get("/api/workspace/profile").json()
        assert result["reason"] is None
        assert result["profile"]["is_sample"] is False
        assert result["profile"]["identity"]["username"] == "local_reader"
        assert result["profile"]["identity"]["completed"] == 1
        assert result["profile"]["identity"]["mean_score"] == 9


def _active_snapshot(app):
    profiles = app.state.container.profiles
    profile = profiles.create_profile('local_reader')
    directory = profiles.directory(profile.profile_id, create=True)
    JsonStore().write(profile.to_dict(), directory / 'profile.json')
    profiles.set_active(profile.profile_id)
    (directory / 'completed_anime.csv').write_text('Anime ID,Title,User Score,Mean Score\n19,Monster,9,8.87\n20,Naruto,0,8.0\n', encoding='utf-8')
    return profile, directory


def test_preferences_save_preserves_secrets_and_unexposed_settings(tmp_path):
    app = create_app(root_override=str(tmp_path), token='test-token')
    service = app.state.container.settings
    original = replace(service.load(), client_id='private-id', client_secret='private-secret', debug_logging=True)
    service.save_preferences(original)
    with TestClient(app) as client:
        headers = {'X-AniRec-Token': 'test-token'}
        payload = client.get('/api/workspace/settings', headers=headers).json()
        for key in ('username', 'client_id_present', 'using_defaults'):
            payload.pop(key)
        payload.update(adventurousness=8, theme='oled', minimum_mal_score=None)
        assert client.post('/api/workspace/settings', json=payload).status_code == 401
        response = client.post('/api/workspace/settings', json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()['adventurousness'] == 8
        assert 'private-' not in response.text
        saved = service.load()
        assert saved.client_secret == original.client_secret
        assert saved.client_id == original.client_id
        assert saved.debug_logging is True
        assert saved.pipeline.candidate_pool_size == original.pipeline.candidate_pool_size
        assert saved.theme == 'oled'
        assert client.post('/api/workspace/settings', json={**payload, 'client_id': 'overwrite'}, headers=headers).status_code == 422
        assert client.post('/api/workspace/settings', json={**payload, 'font_scale': 4}, headers=headers).status_code == 422
        assert service.load() == saved


def test_unreadable_settings_cannot_be_overwritten_with_defaults(tmp_path):
    app = create_app(root_override=str(tmp_path))
    service = app.state.container.settings
    service.path.parent.mkdir(parents=True, exist_ok=True)
    service.path.write_text('broken', encoding='utf-8')
    with TestClient(app) as client:
        payload = client.get('/api/workspace/settings').json()
        for key in ('username', 'client_id_present', 'using_defaults'):
            payload.pop(key)
        assert client.post('/api/workspace/settings', json=payload).status_code == 409
        assert service.path.read_text() == 'broken'


def test_library_reads_saved_metadata_outside_latest_feed(tmp_path):
    app = create_app(root_override=str(tmp_path))
    profile, directory = _active_snapshot(app)
    service = app.state.container.recommendation_state
    service.set_watch_later(profile.profile_id, 19, True)
    with TestClient(app) as client:
        response = client.get('/api/workspace/library', params={'profile_id': profile.profile_id})
        assert response.status_code == 200
        models = response.json()['recommendations']
        assert [model['display_title'] for model in models] == ['Monster']
        assert models[0]['personal_match_available'] is False
        assert models[0]['mal_score'] == 8.87
        assert client.get('/api/workspace/library', params={'profile_id': 'other'}).status_code == 409
        assert client.post('/api/workspace/library/resolve', json={'profile_id': profile.profile_id, 'mal_id': 99}).status_code == 400


def test_live_comparison_joins_ids_and_keeps_unrated_distinct(tmp_path, monkeypatch):
    import pandas as pd
    from AniRec.services.anime_data_service import AnimeDataService
    app = create_app(root_override=str(tmp_path))
    _active_snapshot(app)
    service = app.state.container.settings
    service.save_preferences(replace(service.load(), client_id='test-id'))
    monkeypatch.setattr(AnimeDataService, 'fetch_completed_anime', lambda *args, **kwargs: pd.DataFrame([
        {'Anime ID': 19, 'Title': 'Monster', 'User Score': 6},
        {'Anime ID': 20, 'Title': 'Naruto', 'User Score': 8},
        {'Anime ID': 21, 'Title': 'One Piece', 'User Score': 10},
    ]))
    with TestClient(app) as client:
        result = client.get('/api/workspace/compare?username=other_reader').json()['report']
        assert result['is_sample'] is False
        assert result['friend']['match_score'] is None
        assert result['friend']['total_anime'] == 3
        assert result['friend']['shared_anime'] == 2
        assert result['friend']['both_rated'] == 1
        rated, unrated = result['sections']
        assert rated['entries'][0]['scores']['difference'] == 3
        assert unrated['entries'][0]['scores']['your_score'] is None
        assert unrated['entries'][0]['scores']['difference'] is None


def test_failed_live_comparison_does_not_become_empty_or_sample(tmp_path, monkeypatch):
    from AniRec.errors import AccessDeniedError
    from AniRec.services.anime_data_service import AnimeDataService
    app = create_app(root_override=str(tmp_path))
    _active_snapshot(app)
    service = app.state.container.settings
    service.save_preferences(replace(service.load(), client_id='test-id'))
    def fail(*args, **kwargs):
        raise AccessDeniedError('private')
    monkeypatch.setattr(AnimeDataService, 'fetch_completed_anime', fail)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/api/workspace/compare?username=private_reader')
        assert response.status_code == 500
        assert response.json()['error']['code'] == 'access_denied'
        assert 'report' not in response.json()


def test_comparison_client_refuses_invalid_payload_and_foreign_pagination():
    import pytest
    from AniRec.errors import InvalidResponseError
    from AniRec.services.workspace_service import ComparisonClient
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {'unexpected': []}
    calls = []
    def get(*args, **kwargs):
        calls.append(args[0])
        return Response()
    client = ComparisonClient(http_get=get)
    with pytest.raises(InvalidResponseError):
        client.get_json('https://foreign.test/v2/users/name/animelist', client_id='secret')
    assert not calls
    with pytest.raises(InvalidResponseError):
        client.get_json('https://api.myanimelist.net/v2/users/name/animelist')
