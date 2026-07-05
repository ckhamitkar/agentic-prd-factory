"""
Artifact Manager for Sprint Development.

Handles saving and organizing sprint artifacts including code,
tests, configuration, and documentation.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List

PROJECTS_DIR = "projects"


def get_sprint_dir(project_name: str, sprint_id: int) -> str:
    """Get the directory path for a specific sprint."""
    return os.path.join(PROJECTS_DIR, project_name, "sprints", f"sprint_{sprint_id}")


def get_codebase_dir(project_name: str) -> str:
    """Get the directory path for the final merged codebase."""
    return os.path.join(PROJECTS_DIR, project_name, "codebase")


class ArtifactManager:
    """Manages sprint artifacts and codebase files."""

    SPRINT_SUBDIRS = ["planning", "backend", "frontend", "devops", "tests", "docs", "review"]
    CODEBASE_SUBDIRS = ["backend", "frontend", "infrastructure", "docs", "tests"]

    def ensure_sprint_dirs(self, project_name: str, sprint_id: int) -> str:
        """
        Create all necessary directories for a sprint.

        Returns:
            Path to the sprint directory.
        """
        sprint_dir = get_sprint_dir(project_name, sprint_id)

        for subdir in self.SPRINT_SUBDIRS:
            os.makedirs(os.path.join(sprint_dir, subdir), exist_ok=True)

        return sprint_dir

    def ensure_codebase_dirs(self, project_name: str) -> str:
        """
        Create all necessary directories for the codebase.

        Returns:
            Path to the codebase directory.
        """
        codebase_dir = get_codebase_dir(project_name)

        for subdir in self.CODEBASE_SUBDIRS:
            os.makedirs(os.path.join(codebase_dir, subdir), exist_ok=True)

        return codebase_dir

    def save_sprint_artifacts(
        self,
        project_name: str,
        sprint_id: int,
        artifacts: Dict[str, Any]
    ) -> List[str]:
        """
        Save all artifacts from a sprint.

        Args:
            project_name: Name of the project
            sprint_id: Sprint identifier
            artifacts: Dictionary of artifact_id -> SprintArtifact

        Returns:
            List of saved file paths
        """
        sprint_dir = self.ensure_sprint_dirs(project_name, sprint_id)
        saved_files = []

        # Mapping of artifact types to subdirectories
        type_mapping = {
            "code": self._get_code_subdir,
            "test": lambda _: "tests",
            "config": lambda _: "devops",
            "docs": lambda _: "docs"
        }

        for artifact_id, artifact in artifacts.items():
            artifact_type = artifact.get("artifact_type", "code")
            file_path = artifact.get("file_path", f"{artifact_id}.txt")
            content = artifact.get("content", "")

            # Determine subdirectory
            if artifact_type in type_mapping:
                if callable(type_mapping[artifact_type]):
                    subdir = type_mapping[artifact_type](artifact_id)
                else:
                    subdir = type_mapping[artifact_type]
            else:
                subdir = "other"

            # Build full path
            target_dir = os.path.join(sprint_dir, subdir)
            os.makedirs(target_dir, exist_ok=True)

            # Use just the filename from file_path
            filename = os.path.basename(file_path)
            full_path = os.path.join(target_dir, filename)

            # Save the artifact
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            saved_files.append(full_path)

        # Save manifest
        self._save_manifest(sprint_dir, sprint_id, list(artifacts.keys()))

        return saved_files

    def _get_code_subdir(self, artifact_id: str) -> str:
        """Determine code subdirectory based on artifact ID."""
        if "backend" in artifact_id.lower():
            return "backend"
        elif "frontend" in artifact_id.lower():
            return "frontend"
        elif "devops" in artifact_id.lower() or "infra" in artifact_id.lower():
            return "devops"
        else:
            return "backend"  # Default to backend

    def _save_manifest(
        self,
        sprint_dir: str,
        sprint_id: int,
        artifact_ids: List[str]
    ) -> None:
        """Save a manifest file for the sprint."""
        manifest = {
            "sprint_id": sprint_id,
            "artifacts": artifact_ids,
            "timestamp": datetime.now().isoformat(),
            "version": 1
        }

        manifest_path = os.path.join(sprint_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def save_to_codebase(
        self,
        project_name: str,
        codebase: Dict[str, str]
    ) -> List[str]:
        """
        Save the final merged codebase.

        Args:
            project_name: Name of the project
            codebase: Dictionary of file_path -> content

        Returns:
            List of saved file paths
        """
        codebase_dir = self.ensure_codebase_dirs(project_name)
        saved_files = []

        for file_path, content in codebase.items():
            # Build full path
            full_path = os.path.join(codebase_dir, file_path)

            # Ensure directory exists
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Save the file
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            saved_files.append(full_path)

        return saved_files

    def save_sprint_review(
        self,
        project_name: str,
        sprint_id: int,
        review_data: Dict[str, Any]
    ) -> str:
        """
        Save sprint review feedback.

        Returns:
            Path to saved review file.
        """
        sprint_dir = self.ensure_sprint_dirs(project_name, sprint_id)
        review_dir = os.path.join(sprint_dir, "review")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        iteration = review_data.get("iteration", 0)
        filename = f"{timestamp}_review_iteration_{iteration}.json"

        review_path = os.path.join(review_dir, filename)
        with open(review_path, "w", encoding="utf-8") as f:
            json.dump(review_data, f, indent=2)

        return review_path

    def load_sprint_manifest(
        self,
        project_name: str,
        sprint_id: int
    ) -> Dict[str, Any]:
        """Load the manifest for a sprint."""
        sprint_dir = get_sprint_dir(project_name, sprint_id)
        manifest_path = os.path.join(sprint_dir, "manifest.json")

        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return {"sprint_id": sprint_id, "artifacts": [], "timestamp": None}

    def get_sprint_artifact_paths(
        self,
        project_name: str,
        sprint_id: int
    ) -> Dict[str, List[str]]:
        """
        Get all artifact paths organized by subdirectory.

        Returns:
            Dictionary of subdir -> list of file paths
        """
        sprint_dir = get_sprint_dir(project_name, sprint_id)
        result = {}

        for subdir in self.SPRINT_SUBDIRS:
            subdir_path = os.path.join(sprint_dir, subdir)
            if os.path.exists(subdir_path):
                files = [
                    os.path.join(subdir_path, f)
                    for f in os.listdir(subdir_path)
                    if os.path.isfile(os.path.join(subdir_path, f))
                ]
                result[subdir] = files
            else:
                result[subdir] = []

        return result
