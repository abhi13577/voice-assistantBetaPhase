import json
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProductAPIClient:
    """Mock API client for test data. Replace with real API in production."""
    def __init__(self):
        path = Path(__file__).parent.parent / "data" / "testneo_vertical.json"
        with open(path, "r") as f:
            self.data = json.load(f)

    # ---------- USERS ----------
    def get_user(self, user_id: int):
        """Get user by ID or return None if not found."""
        user = next((u for u in self.data["users"] if u["id"] == user_id), None)
        if not user:
            logger.debug(f"User not found: user_id={user_id}")
        return user

    # ---------- PROJECTS ----------
    def get_projects(self, user_id: int):
        """Get all projects for a user."""
        projects = [p for p in self.data["projects"] if p["user_id"] == user_id]
        if not projects:
            logger.debug(f"No projects found for user_id={user_id}")
        return projects

    # ---------- RUNS ----------
    def get_runs(self, user_id: int) -> list:
        """Get all test runs for a user."""
        runs = [r for r in self.data["test_runs"] if r["user_id"] == user_id]
        if not runs:
            logger.debug(f"No runs found for user_id={user_id}")
        return runs

    def get_last_run(self, user_id: int):
        runs = self.get_runs(user_id)
        runs_sorted = sorted(
            runs,
            key=lambda x: datetime.fromisoformat(x["started_at"].replace("Z", "")),
            reverse=True
        )
        return runs_sorted[0] if runs_sorted else None

    def get_last_run_by_project(self, user_id: int, project_name: str):
        projects = self.get_projects(user_id)
        project = next((p for p in projects if p["name"].lower() == project_name.lower()), None)
        if not project:
            return None

        runs = [
            r for r in self.get_runs(user_id)
            if r["project_id"] == project["id"]
        ]

        runs_sorted = sorted(
            runs,
            key=lambda x: datetime.fromisoformat(x["started_at"].replace("Z", "")),
            reverse=True
        )

        return runs_sorted[0] if runs_sorted else None
    def get_last_error(self, user_id: int):
        runs = self.get_runs(user_id)

        failed_runs = [r for r in runs if r["failed_tests"] > 0]

        if not failed_runs:
            return None

        failed_runs_sorted = sorted(
           failed_runs,
           key=lambda x: datetime.fromisoformat(x["started_at"].replace("Z", "")),
           reverse=True
    )

        return failed_runs_sorted[0]
    
    def get_tts_templates(self):
        return self.data["tts_templates"]


product_api_client = ProductAPIClient()