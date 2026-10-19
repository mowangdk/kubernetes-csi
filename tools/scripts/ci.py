#!/usr/bin/env python3
# Copyright 2026 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Check committed controller sources before CI builds or tests them."""

import argparse
from pathlib import Path
import subprocess

import build_environment
import image_inputs

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATHS = ("cmd", "pkg", "vendor", "go.mod", "go.sum")
REQUIRED_FILES = ("go.mod", "go.sum", "vendor/modules.txt", "pkg/.GENERATED",
                  "cmd/csi-sidecars/main.go", "cmd/snapshot-controller/main.go",
                  "cmd/snapshot-conversion-webhook/main.go")
GO_VERSION_FILE = "tmp/ci-go-version"


def go_version(root=ROOT):
    return build_environment.load(root)["versions"]["go"].removeprefix("go")


def check(root=ROOT):
    """Require the committed assembly instead of regenerating it in CI."""
    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            raise ValueError(f"missing committed {name}; sync locally and commit generated sources")
    image_inputs.dockerfiles(root)
    if (root / ".git").exists():
        changes = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", *SNAPSHOT_PATHS],
            cwd=root, text=True)
        if changes:
            raise ValueError("generated sources differ from the committed snapshot; "
                             "sync locally and commit cmd/, pkg/, vendor/, go.mod, and go.sum")


def prepare_cloud(root=ROOT):
    """Validate Cloud Build's locked builder and pass its Go version to publishing."""
    build_environment.preflight(build_environment.load(root))
    check(root)
    output = root / GO_VERSION_FILE
    if output.parent.is_symlink():
        raise ValueError("refusing symlinked Cloud Build handoff directory")
    output.parent.mkdir(exist_ok=True)
    output.write_text(go_version(root) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "go-version", "prepare-cloud"))
    args = parser.parse_args()
    if args.command == "check":
        check()
    elif args.command == "prepare-cloud":
        prepare_cloud()
    else:
        print(go_version())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(f"CI source check failed: {error}") from error
