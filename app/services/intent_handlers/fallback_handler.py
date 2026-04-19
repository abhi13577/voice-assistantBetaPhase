from app.services.intent_handlers.base_handler import BaseIntentHandler


class FallbackHandler(BaseIntentHandler):

    intent_name = "fallback"

    async def handle(self, user_id, project_id, transcript, llm_slots):

        return (
            "I didn’t understand that.\n"
            "Try one of these:\n"
            "- show my runs\n"
            "- list projects\n"
            "- check last run status",
            [],
            ["list_runs", "list_projects", "check_run_status"]
        )