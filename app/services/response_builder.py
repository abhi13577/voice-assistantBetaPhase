from app.services.product_api_client import product_api_client
from app.services.slot_resolver import SlotResolver
import logging

logger = logging.getLogger(__name__)


class ResponseBuilder:
    """Build responses based on classified intent and user context."""

    async def build(
        self,
        intent: str,
        user_id: int,
        project_id: int,
        transcript: str,
        llm_slots: dict = None
    ) -> tuple:
        """Build response with full validation.
        
        Returns:
            Tuple of (reply_text, context_used, suggestions)
        """
        
        # ✅ VALIDATION: Ensure user exists
        user = product_api_client.get_user(user_id)
        if not user:
            logger.warning(f"ResponseBuilder: User not found user_id={user_id}")
            return (
                "I couldn't find your account. Please contact support.",
                [],
                []
            )
        
        # ✅ VALIDATION: Ensure project exists for user
        if project_id:
            projects = product_api_client.get_projects(user_id)
            project_exists = any(p["id"] == project_id for p in projects)
            if not project_exists and project_id != 0:
                logger.warning(f"ResponseBuilder: Project not found project_id={project_id} for user_id={user_id}")
                return (
                    "You don't have access to that project.",
                    [],
                    []
                )

        # Get projects (already have user validation above)
        projects = product_api_client.get_projects(user_id)
        templates = product_api_client.get_tts_templates()

        # -------- SLOT RESOLUTION --------
        if llm_slots:
            slots = llm_slots
        else:
            slot_resolver = SlotResolver(projects)
            slots = slot_resolver.resolve(transcript)

        # -------- SYSTEM INTENT --------
        if intent == "greeting":
            return (
                "Hello. I can help you check your run status or list your projects.",
                [],
                []
            )

        # -------- CHECK RUN STATUS --------
        if intent == "check_run_status":

            if slots.get("project"):
                run = product_api_client.get_last_run_by_project(
                    user_id,
                    slots["project"]
                )
            else:
                run = product_api_client.get_last_run(user_id)

            if not run:
                reply = templates["run_not_found"]
                return reply, ["run_status"], []

            # ✅ FIX: Use safe pattern to avoid StopIteration crash
            project_match = next(
                (p for p in projects if p["id"] == run["project_id"]),
                None
            )
            
            if not project_match:
                # Project not found - shouldn't happen but handle gracefully
                logger.warning(f"Project not found: project_id={run['project_id']}")
                reply = "Could not find project information for your run."
                return reply, ["run_status"], []
            
            project_name = project_match["name"]

            # All tests passed
            if run["failed_tests"] == 0:
                reply = templates["check_run_status_all_passed"].format(
                    project_name=project_name,
                    total_tests=run["total_tests"]
                )
            else:
                reply = templates["check_run_status_success"].format(
                    project_name=project_name,
                    passed_tests=run["passed_tests"],
                    failed_tests=run["failed_tests"],
                    status=run["status"]
                )

            return reply, ["run_status"], []

        # -------- LIST PROJECTS --------
        if intent == "list_projects":
            names = [p["name"] for p in projects]

            reply = templates["list_projects"].format(
                count=len(names),
                project_names=", ".join(names)
            )

            return reply, ["projects"], []

        # -------- LIST RUNS --------
        if intent == "list_runs":
            runs = product_api_client.get_runs(user_id)

            reply = f"You have {len(runs)} test runs."
            return reply, ["runs"], []

        # -------- FALLBACK --------
        return (
            "I didn’t understand that. You can ask about your last run or list your projects.",
            [],
            []
        )


response_builder = ResponseBuilder()