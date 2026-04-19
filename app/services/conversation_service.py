import redis
import json
import os


class ConversationService:

    def __init__(self):
        self.client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True
        )

        self.TTL = 3600

    def _key(self, conversation_id):
        return f"conv:{conversation_id}"

    def get_state(self, conversation_id):

        data = self.client.get(self._key(conversation_id))

        if data:
            return json.loads(data)

        return {
            "last_intent": None,
            "last_project": None,
            "last_run": None,
            "history": []
        }

    def save_state(self, conversation_id, state):

        self.client.setex(
            self._key(conversation_id),
            self.TTL,
            json.dumps(state)
        )

    def update_state(self, conversation_id, user_text, bot_reply):

        state = self.get_state(conversation_id)

        # safe init if state is missing or empty
        if not state:
            state = {
                "history": [],
                "context": {}
            }

        # schema migration guard — ensure history key always exists
        if "history" not in state:
            state["history"] = []

        state["history"].append({
            "user": user_text,
            "bot": bot_reply
        })

        # keep last 5 only
        state["history"] = state["history"][-5:]

        self.save_state(conversation_id, state)

        return state


conversation_service = ConversationService()