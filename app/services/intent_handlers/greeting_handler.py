from app.services.intent_handlers.base_handler import BaseIntentHandler


class GreetingHandler(BaseIntentHandler):
     intent_name = "greeting"

     async def handle(self, user_id, project_id, transcript, llm_slots):

        reply = "Hello. I can help you check your run status or list your projects."

        return reply, [], []
    