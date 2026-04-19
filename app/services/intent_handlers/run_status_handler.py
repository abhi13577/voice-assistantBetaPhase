"""
Handler for checking test run status with production-grade error handling.
"""

import logging
from app.services.intent_handlers.base_handler import BaseIntentHandler
from app.services.product_api_client import product_api_client
from app.services.slot_resolver import SlotResolver

logger = logging.getLogger(__name__)


class RunStatusHandler(BaseIntentHandler):

    intent_name = "check_run_status"

    async def handle(self, user_id, project_id, transcript, llm_slots):
        """
        Handle run status query with comprehensive error handling.
        """
        try:
            projects = product_api_client.get_projects(user_id)
            
            if not projects:
                logger.warning(f"No projects found for user_id={user_id}")
                return (
                    "You don't have any projects yet. Please create a project first.",
                    ["run_status"],
                    []
                )

            slot_resolver = SlotResolver(projects)
            slots = slot_resolver.resolve(transcript)

            if llm_slots:
                slots.update(llm_slots)

            if slots.get("project"):
                run = product_api_client.get_last_run_by_project(
                    user_id,
                    slots["project"]
                )
            else:
                run = product_api_client.get_last_run(user_id)

            if not run:
                return (
                    "I couldn't find a run for that project. Say 'list my projects' to hear your projects.",
                    ["run_status"],
                    []
                )

            # Safely find project name with fallback
            project_name = None
            for p in projects:
                if p.get("id") == run.get("project_id"):
                    project_name = p.get("name", "Unknown Project")
                    break
            
            if not project_name:
                logger.error(
                    f"Project not found for run. project_id={run.get('project_id')}, "
                    f"user_id={user_id}"
                )
                return (
                    "I found a run but couldn't identify its project. Please try again.",
                    ["run_status"],
                    []
                )

            # Build status response safely
            failed_tests = run.get("failed_tests", 0)
            total_tests = run.get("total_tests", 0)
            
            if failed_tests == 0:
                reply = f"Your run for {project_name} passed. All {total_tests} tests passed."
            else:
                reply = f"Your run for {project_name} completed with {failed_tests} failures out of {total_tests} tests."

            logger.info(f"Successfully retrieved run status for user_id={user_id}, project={project_name}")
            return reply, ["run_status"], []
            
        except KeyError as e:
            logger.error(f"Missing required field in run data: {e}", exc_info=True)
            return (
                "I encountered an error retrieving your run status. Please try again.",
                ["run_status"],
                []
            )
        except Exception as e:
            logger.error(f"Unexpected error in RunStatusHandler: {type(e).__name__}: {e}", exc_info=True)
            return (
                "Something went wrong while checking your run status. Please try again.",
                ["run_status"],
                []
            )