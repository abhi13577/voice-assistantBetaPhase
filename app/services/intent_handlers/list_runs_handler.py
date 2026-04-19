from app.services.intent_handlers.base_handler import BaseIntentHandler
from app.services.product_api_client import product_api_client


class ListRunsHandler(BaseIntentHandler):
    intent_name = "list_runs"

    async def handle(self, user_id, project_id, transcript, llm_slots):

        runs = product_api_client.get_runs(user_id)

        reply = f"You have {len(runs)} test runs."

        return reply, ["runs"], []
    