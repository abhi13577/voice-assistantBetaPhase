from app.services.intent_handlers.base_handler import BaseIntentHandler
from app.services.product_api_client import product_api_client


class ListProjectsHandler(BaseIntentHandler):
    intent_name = "list_projects"

    async def handle(self, user_id, project_id, transcript, llm_slots):

        projects = product_api_client.get_projects(user_id)

        names = [p["name"] for p in projects]

        reply = f"You have {len(names)} projects: {', '.join(names)}."

        return reply, ["projects"], []
    