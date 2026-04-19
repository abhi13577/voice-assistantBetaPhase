"""
Production-grade response builder with error handling and validation.
"""

from typing import Tuple, List, Dict, Optional
from app.core.base_service import Service
from app.core.exceptions import ValidationError
from app.services.product_api_client import product_api_client
from app.services.slot_resolver import SlotResolver


class ResponseBuilder(Service):
    """
    Builds natural language responses based on intent and context.
    """
    
    # Response templates by intent
    TEMPLATES = {
        "greeting": "Hello! I can help you check your run status or list your projects.",
        "run_not_found": "I couldn't find any runs. Try creating a test run first.",
        "project_not_found": "I couldn't find that project. Would you like me to list your projects?",
        "error": "Sorry, I encountered an error. Please try again.",
        "unauthorized": "You don't have permission to perform this action.",
    }
    
    async def build(
        self,
        intent: str,
        user_id: int,
        transcript: str,
        project_id: Optional[int] = None,
        llm_slots: Optional[dict] = None,
    ) -> Tuple[str, List[str], List[str]]:
        """
        Build response for user intent.
        
        Returns: (response_text, suggested_actions, followup_questions)
        """
        try:
            # Validate input
            if not intent:
                raise ValidationError("Intent is required")
            if user_id <= 0:
                raise ValidationError("Invalid user ID")
            
            self.logger.info(f"Building response for intent: {intent}, user: {user_id}")
            
            # Get user context
            projects = await self._safe_get_projects(user_id)
            
            # Resolve slots
            if llm_slots:
                slots = llm_slots
            else:
                slot_resolver = SlotResolver(projects)
                slots = slot_resolver.resolve(transcript)
            
            # Route by intent
            if intent == "greeting":
                return self._handle_greeting()
            
            elif intent == "check_run_status":
                return await self._handle_check_run_status(user_id, slots, projects)
            
            elif intent == "list_projects":
                return await self._handle_list_projects(user_id, projects)
            
            elif intent == "list_runs":
                return await self._handle_list_runs(user_id, project_id, slots)
            
            elif intent == "help":
                return self._handle_help()
            
            else:
                # Fallback
                self.logger.warning(f"Unknown intent: {intent}")
                return self.TEMPLATES["error"], [], []
        
        except Exception as e:
            self.logger.exception(f"Error building response: {e}")
            return self.TEMPLATES["error"], [], []
    
    def _handle_greeting(self) -> Tuple[str, List[str], List[str]]:
        """Handle greeting intent."""
        return (
            self.TEMPLATES["greeting"],
            ["status", "projects"],
            ["What would you like to do?"]
        )
    
    def _handle_help(self) -> Tuple[str, List[str], List[str]]:
        """Handle help intent."""
        help_text = """I can help you with:
- Checking test run status
- Listing your projects
- Listing test runs
- Rerunning tests
        """
        return help_text, [], []
    
    async def _handle_check_run_status(
        self,
        user_id: int,
        slots: Dict,
        projects: List[Dict]
    ) -> Tuple[str, List[str], List[str]]:
        """Handle check run status intent."""
        try:
            # Get last run (or for specific project)
            if slots.get("project"):
                project_id = self._resolve_project_id(slots["project"], projects)
                if not project_id:
                    return self.TEMPLATES["project_not_found"], [], []
                
                run = await self._safe_get_last_run_by_project(user_id, project_id)
            else:
                run = await self._safe_get_last_run(user_id)
            
            if not run:
                return self.TEMPLATES["run_not_found"], ["create_run"], []
            
            # Format response
            response = f"Last run: {run.get('status', 'unknown')} - {run.get('name', 'N/A')}"
            return response, ["view_details", "rerun"], []
        
        except Exception as e:
            self.logger.error(f"Error checking run status: {e}")
            return self.TEMPLATES["error"], [], []
    
    async def _handle_list_projects(
        self,
        user_id: int,
        projects: List[Dict]
    ) -> Tuple[str, List[str], List[str]]:
        """Handle list projects intent."""
        if not projects:
            return "You don't have any projects yet.", [], []
        
        project_names = ", ".join([p.get("name", "Unknown") for p in projects[:5]])
        response = f"Your projects: {project_names}"
        
        return response, ["select_project"], []
    
    async def _handle_list_runs(
        self,
        user_id: int,
        project_id: Optional[int],
        slots: Dict
    ) -> Tuple[str, List[str], List[str]]:
        """Handle list runs intent."""
        try:
            runs = await self._safe_get_runs(user_id, project_id)
            
            if not runs:
                return "No runs found.", [], []
            
            run_names = ", ".join([r.get("name", "Unknown") for r in runs[:5]])
            response = f"Recent runs: {run_names}"
            
            return response, ["view_run"], []
        
        except Exception as e:
            self.logger.error(f"Error listing runs: {e}")
            return self.TEMPLATES["error"], [], []
    
    async def _safe_get_projects(self, user_id: int) -> List[Dict]:
        """Safely get projects with error handling."""
        try:
            return product_api_client.get_projects(user_id) or []
        except Exception as e:
            self.logger.warning(f"Failed to get projects: {e}")
            return []
    
    async def _safe_get_last_run(self, user_id: int) -> Optional[Dict]:
        """Safely get last run with error handling."""
        try:
            return product_api_client.get_last_run(user_id)
        except Exception as e:
            self.logger.warning(f"Failed to get last run: {e}")
            return None
    
    async def _safe_get_last_run_by_project(
        self,
        user_id: int,
        project_id: int
    ) -> Optional[Dict]:
        """Safely get last run for project."""
        try:
            return product_api_client.get_last_run_by_project(user_id, project_id)
        except Exception as e:
            self.logger.warning(f"Failed to get run by project: {e}")
            return None
    
    async def _safe_get_runs(
        self,
        user_id: int,
        project_id: Optional[int]
    ) -> List[Dict]:
        """Safely get runs list."""
        try:
            return product_api_client.get_runs(user_id, project_id) or []
        except Exception as e:
            self.logger.warning(f"Failed to get runs: {e}")
            return []
    
    def _resolve_project_id(self, project_name: str, projects: List[Dict]) -> Optional[int]:
        """Resolve project name to ID."""
        for project in projects:
            if project.get("name", "").lower() == project_name.lower():
                return project.get("id")
        return None


# Singleton instance
_response_builder: Optional[ResponseBuilder] = None


def get_response_builder() -> ResponseBuilder:
    """Get or create response builder singleton."""
    global _response_builder
    if _response_builder is None:
        _response_builder = ResponseBuilder()
    return _response_builder
