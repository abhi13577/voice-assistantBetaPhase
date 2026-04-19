import json
import redis

class ConversationMemory:

    def __init__(self):
        self.client = redis.Redis(host="redis", port=6379, decode_responses=True)

    def save(self, conversation_id, data):
        self.client.setex(
            f"conv:{conversation_id}",
            600,
            json.dumps(data)
        )

    def get(self, conversation_id):
        data = self.client.get(f"conv:{conversation_id}")
        if data:
            return json.loads(data)
        return None


conversation_memory = ConversationMemory()