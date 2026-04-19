import json
from pathlib import Path

"""
Future feature: Suggestion engine / context tracking.

Currently not integrated in the demo vertical.
Will be used when conversation memory is implemented.
"""
class ContextService:
    def __init__(self):
        path = Path(__file__).parent.parent / "data" / "mock_context.json"
        with open(path, "r") as f:
            self.context = json.load(f)

    def get_context(self):
        return self.context


context_service = ContextService()