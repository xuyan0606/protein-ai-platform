"""Protect secret injection and source integrity before a production cutover."""
import importlib.util
import copy
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "release_prepare", Path(__file__).parents[1] / "scripts/prepare_thermostability_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def mounted_runtime():
    return {
        'Id': 'active-id', 'Image': 'sha256:' + 'a' * 64,
        'State': {'Health': {'Status': 'healthy'}},
        'Config': {'Env': ['KEEP=unchanged'], 'Cmd': ['start']},
        'HostConfig': {'Binds': ['/releases/old/backend/app:/app/app:ro',
                                 '/data:/data:rw']},
        'Mounts': [{'Source': '/releases/old/backend/app', 'Destination': '/app/app', 'RW': False},
                   {'Source': '/data', 'Destination': '/data', 'RW': True}],
        'NetworkSettings': {'Networks': {'production': {'Aliases': ['backend', 'active-id']}}},
    }


def test_second_release_replaces_only_verified_readonly_source_mount():
    info = mounted_runtime()
    original = copy.deepcopy(info)
    frozen = {'container_id': info['Id'], 'checkpoint_image_id': info['Image']}
    payload = release.runtime_create_payload(
        info, frozen, [(Path('/releases/new/backend/app'), '/app/app')], {},
        prior_mounts={'/app/app': '/releases/old/backend/app'},
    )
    assert payload['HostConfig']['Binds'] == ['/data:/data:rw', '/releases/new/backend/app:/app/app:ro']
    assert payload['Env'] == ['KEEP=unchanged'] and payload['Cmd'] == ['start']
    assert info == original


@pytest.mark.parametrize('change', ['id', 'image', 'writable', 'source', 'unrecorded'])
def test_second_release_rejects_runtime_drift(change):
    info = mounted_runtime()
    frozen = {'container_id': info['Id'], 'checkpoint_image_id': info['Image']}
    prior = {'/app/app': '/releases/old/backend/app'}
    if change == 'id':
        info['Id'] = 'unexpected'
    elif change == 'image':
        info['Image'] = 'sha256:' + 'b' * 64
    elif change == 'writable':
        info['Mounts'][0]['RW'] = True
    elif change == 'source':
        info['Mounts'][0]['Source'] = '/unreviewed'
    else:
        prior = {}
    with pytest.raises(RuntimeError):
        release.runtime_create_payload(info, frozen, [(Path('/releases/new/backend/app'), '/app/app')], {}, prior_mounts=prior)


def test_original_snapshot_flow_still_refuses_existing_source_mount():
    info = mounted_runtime()
    with pytest.raises(RuntimeError, match='source mount'):
        release.runtime_create_payload(info, {'container_id': info['Id'], 'checkpoint_image_id': info['Image']},
                                       [(Path('/new'), '/app/app')], {})


def test_model_settings_do_not_copy_scientific_overrides(tmp_path):
    path = tmp_path / "service.env"
    path.write_text("MODEL_SERVICE_TOKEN=" + "x" * 48 + "\nDDGUN_ALLOW_VALIDATION_DATABASE=1\nDATABASE_URL=private\n")
    path.chmod(0o600)
    settings = release.model_service_environment(path)
    assert len(settings) == 9
    assert settings["DDGUN_SERVICE_URL"] == "http://172.18.0.1:4270/ddgun"
    assert settings["EVCOUPLINGS_SERVICE_TIMEOUT_SECONDS"] == "7260"
    assert "DATABASE_URL" not in settings
    assert "DDGUN_ALLOW_VALIDATION_DATABASE" not in settings


def test_nonprivate_token_file_rejected(tmp_path):
    path = tmp_path / "service.env"
    path.write_text("MODEL_SERVICE_TOKEN=" + "x" * 48)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="private"):
        release.model_service_environment(path)


def test_modified_release_rejected_before_docker_operation(tmp_path, monkeypatch):
    source = tmp_path / "source/backend/app"
    source.mkdir(parents=True)
    code = source / "main.py"
    code.write_text("original")
    root = tmp_path / "source"
    (tmp_path / "RUNTIME-PREPARED.json").write_text(json.dumps({
        "release_path": str(root), "source_sha256": release.release_inventory(root)}))
    code.write_text("changed after preparation")
    monkeypatch.setattr(release, "docker", lambda *args, **kwargs: pytest.fail("Docker must not run"))
    with pytest.raises(ValueError, match="source changed"):
        release.switch_runtime(tmp_path, tmp_path / "unused-backup.json")
