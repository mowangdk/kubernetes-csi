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

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import build_environment
import ci
import image_inputs


class CommittedSourceCITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(ci.ROOT / "tools/assembly", self.root / "tools/assembly")
        shutil.copy2(ci.ROOT / "Dockerfile", self.root / "Dockerfile")

    def assembled(self):
        for name in ci.REQUIRED_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n")
        image_inputs.dockerfiles(self.root, generate=True)

    def test_fresh_checkout_requires_committed_generated_sources(self):
        with self.assertRaisesRegex(ValueError, "sync locally and commit"):
            ci.check(self.root)

    def test_complete_committed_sources_are_accepted_without_sync_outputs(self):
        self.assembled()
        ci.check(self.root)
        for name in ("vendor/modules.txt", "cmd/snapshot-controller/main.go"):
            path = self.root / name
            content = path.read_bytes()
            path.unlink()
            with self.assertRaisesRegex(ValueError, "missing committed"):
                ci.check(self.root)
            path.write_bytes(content)

    def test_dirty_or_new_generated_source_is_rejected(self):
        self.assembled()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.org",
                        "commit", "-qm", "snapshot"], cwd=self.root, check=True)
        ci.check(self.root)
        source = self.root / "cmd/csi-sidecars/main.go"
        source.write_text("changed generated source\n")
        with self.assertRaisesRegex(ValueError, "differ from the committed snapshot"):
            ci.check(self.root)
        source.write_text("fixture\n")
        (self.root / "cmd/csi-sidecars/new.go").write_text("new generated source\n")
        with self.assertRaisesRegex(ValueError, "differ from the committed snapshot"):
            ci.check(self.root)

    def test_cloud_prepare_checks_builder_before_writing_handoff(self):
        self.assembled()
        with patch.object(ci.build_environment, "preflight", side_effect=ValueError("wrong builder")):
            with self.assertRaisesRegex(ValueError, "wrong builder"):
                ci.prepare_cloud(self.root)
        self.assertFalse((self.root / ci.GO_VERSION_FILE).exists())
        with patch.object(ci.build_environment, "preflight"):
            ci.prepare_cloud(self.root)
        self.assertEqual((self.root / ci.GO_VERSION_FILE).read_text(), ci.go_version(self.root) + "\n")

    def test_cloud_prepare_refuses_symlinked_handoff_directory(self):
        self.assembled()
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "tmp").symlink_to(outside, target_is_directory=True)
        with patch.object(ci.build_environment, "preflight"):
            with self.assertRaisesRegex(ValueError, "symlinked"):
                ci.prepare_cloud(self.root)
        self.assertEqual(list(outside.iterdir()), [])

    def test_cloud_publish_requires_prepared_committed_sources(self):
        shutil.copy2(ci.ROOT / ".cloudbuild.sh", self.root / ".cloudbuild.sh")
        result = subprocess.run(["bash", ".cloudbuild.sh"], cwd=self.root,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source check first", result.stderr)

    def test_cloud_publish_uses_locked_version_and_release_inputs(self):
        self.assembled()
        shutil.copy2(ci.ROOT / ".cloudbuild.sh", self.root / ".cloudbuild.sh")
        (self.root / "release-tools").mkdir()
        (self.root / "release-tools/prow.sh").write_text(
            'gcr_cloud_build() { printf "%s\\n" "$CSI_PROW_GO_VERSION_BUILD" '
            '"$CSI_PROW_BUILD_PLATFORMS" "$GIT_TAG" "$PULL_BASE_REF" "$REGISTRY_NAME" "$GOWORK"; }\n')
        with patch.object(ci.build_environment, "preflight"):
            ci.prepare_cloud(self.root)
        for version in (ci.go_version(self.root), "1.2.3;exit 0"):
            (self.root / ci.GO_VERSION_FILE).write_text(version + "\n")
            result = subprocess.run(["bash", ".cloudbuild.sh"], cwd=self.root,
                                    env={**os.environ, "GIT_TAG": "v20261018-test", "PULL_BASE_REF": "main",
                                         "REGISTRY_NAME": "registry.example/staging", "GOWORK": "/unrelated"},
                                    capture_output=True, text=True, timeout=10)
            if ";" in version:
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("registry.example", result.stdout)
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), [version,
                    "linux amd64 amd64 -amd64; linux arm64 arm64 -arm64",
                    "v20261018-test", "main", "registry.example/staging", "off"])

    def test_cloud_config_uses_locked_builder_without_sync(self):
        image = build_environment.select_image(build_environment.load(), arch="amd64")
        config = (ci.ROOT / "cloudbuild.yaml").read_text()
        self.assertIn("name: " + image + "\n", config)
        self.assertIn("CSI_AIO_BUILDER_IMAGE=" + image + "\n", config)
        self.assertIn("'prepare-cloud'", config)
        self.assertNotIn("'sync'", config)

    def test_direct_prow_stops_if_committed_sources_are_missing(self):
        scripts = self.root / "tools/scripts"
        scripts.mkdir()
        for name in ("ci.py", "image_inputs.py", "build_environment.py", "assembly_sources.py"):
            shutil.copy2(ci.ROOT / "tools/scripts" / name, scripts / name)
        shutil.copy2(ci.ROOT / ".prow.sh", self.root / ".prow.sh")
        result = subprocess.run(["bash", ".prow.sh"], cwd=self.root,
                                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing committed", result.stderr)
        self.assertNotIn("release-tools/prow.sh", result.stderr)


if __name__ == "__main__":
    unittest.main()
