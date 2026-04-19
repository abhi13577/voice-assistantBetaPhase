class ConversationContext:

    def __init__(self):
        self.context = {}

    def get(self, conversation_id):

        return self.context.get(conversation_id, {})

    def update(self, conversation_id, data):

        if conversation_id not in self.context:
            self.context[conversation_id] = {}

        self.context[conversation_id].update(data)


conversation_context = ConversationContext()