# kubernetes-csi

An experimental assembly of the Kubernetes CSI attacher, provisioner, resizer, and snapshotter sidecars, with standalone snapshot controller and conversion webhook images.

## What this repository builds

The current assembly produces three release binaries and container images:

- `csi-sidecars` runs the selected attacher, provisioner, resizer, and
  snapshotter controllers in one process.
- `snapshot-controller` runs the cluster-wide snapshot controller separately.
- `snapshot-conversion-webhook` runs the VolumeSnapshot API conversion webhook.

## Project status

This project is under active development. The current assembly syncs four CSI
sidecars and validates builds, command-line behavior, image packaging, and a
limited hostpath end-to-end configuration. This coverage does not establish
production readiness for the combined process.

Coordinated lifecycle management, shared diagnostics endpoints, complete
multi-controller in-cluster coverage, and the final release pipeline remain in
progress. Generated assembly sources are not yet committed; the user story below
describes the intended build experience once that work is ready.

## User story

> As a user, I want a fresh checkout to contain the generated source and pinned
> dependencies required by the build, so that I can build the project directly
> without running the repository assembly process or fetching the individual CSI
> component repositories.

Once the sync tooling is ready, its generated assembly will be committed to this
repository. This includes generated command and package sources, staging
content, Go module and workspace metadata, and vendored dependencies required
for an offline, reproducible build.

The intended workflow is:

- Users clone the repository and build it directly; running the sync tooling is
  not part of the user build path.
- Maintainers update the hand-maintained sources and source locks, run the sync
  tooling, and commit the resulting generated changes separately for review.
- Generated files are not edited by hand and retain enough source provenance to
  identify the upstream component revisions from which they were assembled.
- CI regenerates the assembly from the committed sources and locks, then fails
  if the working tree differs from the committed generated output.

This model reduces the setup and network requirements for users while keeping
source updates reviewable and reproducible for maintainers.

## Documentation

- [Code layout](CODE_LAYOUT.md) explains the hand-maintained and generated
  source layers.
- [Assembly tools](tools/README.md) documents source locks, synchronization,
  builds, and artifact verification.
- [Hostpath deployment](deploy/README.md) describes the Kubernetes deployment
  used by the Prow end-to-end tests.
- [Contributing](CONTRIBUTING.md) covers contribution guidelines and community
  resources.
- [Security policy](SECURITY.md) explains how to report vulnerabilities.

## Community, discussion, contribution, and support

Learn how to engage with the Kubernetes community on the [community page](http://kubernetes.io/community/).

You can reach the maintainers of this project at:

- [Slack channel](https://kubernetes.slack.com/messages/sig-storage)
- [Mailing List](https://groups.google.com/a/kubernetes.io/g/sig-storage)

### Code of conduct

Participation in the Kubernetes community is governed by the [Kubernetes Code of Conduct](code-of-conduct.md).
