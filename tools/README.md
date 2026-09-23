# tools/ — hand-maintained tool code

This directory is the **source of truth** maintained by developers. See the
repository-root [CODE_LAYOUT.md](../CODE_LAYOUT.md) for how this layer relates
to the generated assembly area.

The assembly area (`cmd/`, `pkg/`, `go.mod`, `vendor/`)
is produced by `scripts/sync.sh` from the locked upstream revisions and is
**not committed** — `.gitignore` excludes it as build output. A fresh checkout
runs sync once inside the locked builder, then builds with a plain `go build`;
sync is not a step of every build.

## Contents

| Path | Purpose |
|------|---------|
| `cmd/csi-sidecars/main.go` | AIO unified entry point; dispatches to each sidecar's `<sidecar>_main`. |
| `cmd/csi-sidecars/main_test.go` | Tests for `parseControllers` and the config→global-var mapping. |
| `cmd/csi-sidecars/config/flags.go` | AIO + snapshotter flag registration. |
| `cmd/csi-sidecars/config/flags_test.go` | Flag-registration regression tests. |
| `pkg/attacher/cmd/csi-attacher/main.go` | Individual attacher entrypoint retained to verify AIO/standalone compatibility against the assembled packages. |
| `pkg/attacher/cmd/csi-attacher/config/flags.go` | Attacher flag registration (prefixed + unprefixed). |
| `pkg/attacher/cmd/csi-attacher/config/flags_test.go` | Equivalent defaults and field mappings for prefixed AIO and unprefixed individual flags. |
| `scripts/sync.sh` | Clones upstream `external-*`, rewrites imports, generates the root `go.mod`, and runs module-mode tidy/vendor. |
| `scripts/cleanup.sh` | Removes generated artifacts and `.assembly-env` (leaves `tools/` untouched). |
| `scripts/assembly_lifecycle_test.py` | Offline regression tests for preflight ordering, repeated runs, environment cleanup, and failure recovery. |
| `scripts/isolated_sync.py` | Runs `sync.sh` (or tooling checks) inside the locked Linux builder with the checkout mounted, regenerating the assembly area in place. |
| `scripts/retry-go-dependencies.sh` | Bounded retries for transient Go dependency transport failures; preserves checksum verification. |
| `scripts/retry_go_dependencies_test.py` | Regression tests for retry limits, exit status, and integrity failures. |
| `scripts/verify_artifacts.py` | Checks AIO/individual entrypoint CLIs and packaged image executables/entrypoints/help. |
| `scripts/verify_artifacts_test.py` | Regression tests for the artifact verifier; no assembly or container engine required. |
| `scripts/makefile_test.py` | Formatting-gate coverage for maintained and assembled code, excluding retained upstream originals. |
| `scripts/deploy_test.py` | Shared user/e2e RBAC and ServiceAccount, image override independence, and rollout regression tests with stubbed commands. |
| `scripts/assembly_sources.py` | Source-lock validation and exact single-commit checkout of each upstream input. |
| `scripts/assembly_sources_test.py` | Malformed-lock, stale-output, exact-history import, and provenance fixtures. |
| `scripts/assembly_dependencies.py` | Generates the root `go.mod`, aligns the Kubernetes family, and resolves csi-lib-utils to its locked module revision. |
| `scripts/assembly_dependencies_test.py` | Module generation, source-identity checks, version pinning despite transitive upgrades, vendoring, and workspace isolation. |
| `scripts/build_environment.py` | Locked builder-image selection, tool preflight, and fresh hash-verified Python bootstrap. |
| `scripts/build_environment_test.py` | Builder/version, wheel tampering, partial-install, and generator-integrity fixtures. |
| `scripts/image_inputs.py` | Image-lock/Dockerfile checks, standalone Dockerfile generation, test-image selection, and explicit registry verification. |
| `scripts/image_inputs_test.py` | Image/schema drift, filesystem safety, registry checksums/platforms, and harmless Prow-wrapper fixtures. |
| `assembly/sources.lock.json` | Exact original revisions and repository identities for all five source inputs. |
| `assembly/build-environment.lock.json` | Per-architecture builder digests, exact tool versions, and Python wheel URLs/hashes. |
| `assembly/images.lock.json` | Shared runtime index/platform digests and explicitly selected legacy Kubernetes test images. |

## Usage

Build directly from a populated tree (no sync required):

```bash
make build            # plain go build of the three release commands
```

Populate or regenerate the assembly area inside the locked Linux builder:

```bash
podman pull "$(python3 -B tools/scripts/build_environment.py image)"
python3 -B tools/scripts/isolated_sync.py --update-dependencies 1.MINOR.PATCH
```

The helper defaults to Podman; use `--engine docker` with a Docker preload
instead. The container mounts the checkout, so the tree is regenerated in
place: preflight verifies any existing outputs are disposable and `sync.sh`
removes them before assembling. `--tooling-only`
runs the tooling tests, gofmt, and license checks without assembling.
`make sync KUBERNETES=1.MINOR.PATCH` and `make clean` wrap the root scripts.
Both `sync.sh` and `cleanup.sh` can be started from any directory: they resolve
the repository root from their own location and always operate on it.

`sync.sh` symlinks the hand-maintained entrypoints from `tools/` into the
assembly area and generates the rest from upstream. It generates the root
`go.mod` from the original source requirements (via `assembly_dependencies.py
seed`), aligning Kubernetes staging modules on the release passed via
`--update-dependencies`, then runs `go mod tidy` and `go mod vendor` with
`GOWORK=off`.

The four sidecars belong to the root module. csi-lib-utils is an ordinary Go
module dependency: the generator resolves its full locked commit through Go,
checks the returned repository and commit identity, and reads its `go.mod` from
Go's module cache. A version-based `replace` pins the resolved version even if a
transitive dependency requests a newer one. There is no local library checkout,
source patch, or `staging/` output. Go's normal proxy and checksum verification
remain enabled; `go mod vendor` copies the required packages into `vendor/` for
builds. No workspace file is generated or needed. Makefile, Prow, and Cloud Build
use module mode even when the caller has selected an unrelated workspace.
Cleanup still removes legacy `staging/` and workspace files from older assemblies.

## Assembly lifecycle

These are single-task development tools; run only one assembly, tooling check,
or cleanup at a time in a checkout. They do not implement concurrency control.

Sync validates its arguments, source/image inputs, and the actual builder before
removing existing assembly outputs. An invalid invocation or failed preflight
leaves those outputs intact.

`.assembly-env` is disposable and is never reused. Each validated session removes
any old environment, creates a fresh one, and cleans it on success, ordinary
failure, or a handled termination signal. If an uncatchable termination leaves a
partial environment, the next session removes it before trying again.
`make clean` also removes it. Repeating tooling checks, or running sync after
tooling checks, does not require manual environment deletion.

## Updating source revisions

All four independent upstream controllers remain present. Update each source's
`ref` and exact `commit` in `assembly/sources.lock.json`; normal sync consumes
that lock directly and never resolves moving branches.

When updating upstream controllers, manually review and update
[`deploy/rbac.yaml`](../deploy/rbac.yaml), the single RBAC manifest shared by
users and hostpath e2e. See the [deployment guide](../deploy/README.md).
RBAC is not generated by sync or fetched during deployment.

The source lock targets Kubernetes 1.36.3, with staging modules aligned at
0.36.3. `assembly_dependencies.py seed` reads the original component
requirements (including the snapshot client) and aligns every Kubernetes staging
module on the selected release while generating `go.mod`. The resolved
tree is then pinned by the source lock and `go.sum`; there is no separate consistency
re-check, so a build is a plain `go build` against the generated vendor tree.

## Runtime and legacy test image inputs

`images.lock.json` pins one `gcr.io/distroless/static` index for the root AIO
image and both standalone snapshot images, plus the Linux amd64/arm64 child
manifests. Root and generated Dockerfiles use the same checked template and
preserve command-specific entrypoints and the `binary` build argument.

```bash
# Offline maintained-input check; does not create generated files:
python3 -B tools/scripts/image_inputs.py preflight
# After sync, verify all three Dockerfiles:
python3 -B tools/scripts/image_inputs.py verify --root <ASSEMBLY_SOURCE_DIR>
# Explicit online verification of index, child manifest, and config checksums/platforms:
python3 -B tools/scripts/image_inputs.py registry
```

Normal sync does not resolve tags or contact image registries. It checks the root
Dockerfile before tool bootstrap, then generates only fresh standalone
Dockerfiles. `CMDS_DIR` must stay `cmd` in the inherited container path.

The existing Kubernetes **1.31.9 legacy regression** selection is pinned to the
index published in the [kind v0.28.0 release](https://github.com/kubernetes-sigs/kind/releases/tag/v0.28.0).
The maintained `.prow.sh` selects that exact patch image and matching kind
version before sourcing inherited defaults. An unknown version or malformed lock
fails before Prow is sourced. Tests execute the wrapper only against a harmless
stub; no real cluster is created or changed.

## Build

The root `Makefile` inherits the plain `go build` target from
`release-tools/build.make`; it stamps `main.version` from the git revision and
uses the `vendor/` directory automatically when present. No separate controlled
build step is required.

## Dual-entrypoint compatibility checks

```bash
make verify-entrypoints
```

After sync, this target runs the AIO and individual attacher package tests,
then builds native `csi-sidecars` and `csi-attacher` binaries in a temporary
directory. It checks all eight attacher flags through both CLIs, `--help`, and
version stamping. `sync.sh` runs this target automatically; individual attacher
is a compatibility entrypoint, not an additional release image.

The entrypoints share attacher configuration registration and assembled library
packages, but retain separate startup implementations. AIO uses
`--attacher-*` flags; individual attacher preserves the original unprefixed
flags. In AIO, `--attacher-retry-interval-start/max` configure attacher only,
independently of the common `--retry-interval-start/max` flags. Both entrypoints
support `--version` without Kubernetes configuration or a CSI socket; AIO does
not require `--controllers` for this operation.

These are build, configuration, and CLI checks, not proof of controller startup
against a live cluster/driver. Full individual-controller lifecycle coverage
still requires integration tests. Worker-thread and timeout sharing between
AIO controllers is unchanged by these checks.

## Image smoke checks

Build local images from the assembled tree using its root AIO Dockerfile and
generated standalone Dockerfiles, with a unique tag. `.dockerignore` limits the
build context to those Dockerfiles and `bin/` (including architecture-suffixed
binaries); custom `binary` build arguments must therefore also point under
`bin/`. Sources, caches, and local settings are not image inputs. Then verify them:

```bash
python3 -B tools/scripts/verify_artifacts.py images --engine podman --tag YOUR_UNIQUE_TAG
```
