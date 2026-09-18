# Kubernetes 1.31 hostpath test deployment

This directory contains the local hostpath deployment selected by `.prow.sh` for
the configured Kubernetes regression suite. `release-tools/prow.sh` discovers
the matching versioned `deploy.sh`, loads the commands declared by the root
`Makefile`, and invokes the script before running the storage tests.

The deployment script applies RBAC tied to the locked AIO source revisions,
rewrites configurable upstream image references, deploys the hostpath manifests,
and waits for the StatefulSets to become ready. When `CSI_PROW_TEST_DRIVER` is
set, it writes the external-storage test configuration there and pins
`ClientNodeName` to the node hosting the driver.

These manifests are a legacy E2E fixture, not a production deployment.
