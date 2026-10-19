# Release provenance manifest

`schemas/release-manifest.v1.schema.json` defines the release record. Generate it only after the source checkout is clean and all production images have immutable registry digests. The manifest records the full Git commit/tree, Compose source hashes, a hash of non-secret environment settings, immutable image references, and the previous release manifest hash for rollback. Environment values and credentials are never copied into the record.

## Create and verify

Run from a clean release checkout after pushing images:

```sh
python3 scripts/release_provenance.py create \
  --release-id 20261016-report-evidence-001 \
  --output RELEASE-MANIFEST.json \
  --image backend=registry.example/protein-ai-backend@sha256:<64-hex-digest> \
  --image frontend=registry.example/protein-ai-frontend@sha256:<64-hex-digest> \
  --image worker=registry.example/protein-ai-backend@sha256:<64-hex-digest> \
  --image md-worker=registry.example/protein-ai-backend@sha256:<64-hex-digest> \
  --image ligand-worker=registry.example/protein-ai-ligand-worker@sha256:<64-hex-digest> \
  --compose-file docker/docker-compose.aliyun-app.yml \
  --env-file docker/.env.aliyun.app \
  --rollback-release-id <previous-release-id> \
  --rollback-manifest <path-to-previous-RELEASE-MANIFEST.json>

python3 scripts/release_provenance.py verify \
  --manifest RELEASE-MANIFEST.json \
  --image backend=registry.example/protein-ai-backend@sha256:<64-hex-digest> \
  --image frontend=registry.example/protein-ai-frontend@sha256:<64-hex-digest> \
  --image worker=registry.example/protein-ai-backend@sha256:<64-hex-digest> \
  --image md-worker=registry.example/protein-ai-backend@sha256:<64-hex-digest> \
  --image ligand-worker=registry.example/protein-ai-ligand-worker@sha256:<64-hex-digest> \
  --env-file docker/.env.aliyun.app
```

Replace each placeholder with a real digest; the example is not directly executable. First release may omit the rollback arguments, in which case rollback readiness remains an operator decision. `--allow-dirty` is for recording a non-deployable diagnostic snapshot only; the verifier will reject it. Do not deploy by `:aliyun` or other mutable tag after adopting this manifest. The deployment runner should resolve Compose services to the manifest's immutable references and verify the running container image IDs before marking a release current.

## Current integration boundary

`package_deploy_bundle.py` now includes root `VERSION` and `RELEASE-MANIFEST.json` when present. The ECS installer remains backward-compatible by default, but a controlled deployment can fail closed before switching `current`:

```sh
REQUIRE_RELEASE_MANIFEST=1 \
  /opt/protein-ai-platform/current/scripts/install_release_bundle.sh \
  /opt/protein-ai-platform/incoming/protein-ai-platform-<release>.tar.gz
```

Existing releases without `RELEASE-MANIFEST.json` are legacy/unverified. The manifest verifier is still a separate read-only gate; the deployment path must use digest-pinned image references and verify running container image IDs before marking a release current.

`deploy-aliyun.sh app|gpu config` and `up` now verify the manifest and bind it to the selected Compose file. A manifest release cannot run `build`; `up` pulls the pinned images and checks each running service image and repository digest. Set `ALLOW_LEGACY_RELEASE=1` only for an explicitly unverified legacy operation.
