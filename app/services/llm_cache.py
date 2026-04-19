class LLMCache:

    def __init__(self):
        self.cache = {}

    def get(self, transcript):

        return self.cache.get(transcript.lower())

    def set(self, transcript, result):

        self.cache[transcript.lower()] = result


llm_cache = LLMCache()