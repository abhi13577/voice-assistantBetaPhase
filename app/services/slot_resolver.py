class SlotResolver:

    def __init__(self, projects):
        self.projects = projects

    def resolve(self, transcript: str):
        transcript_lower = transcript.lower()
        slots = {}

        # Detect "last"
        if "last" in transcript_lower or "recent" in transcript_lower:
            slots["which"] = "last"

        # Detect project name
        for project in self.projects:
            if project["name"].lower() in transcript_lower:
                slots["project"] = project["name"]

        # Detect failed count
        if "failed" in transcript_lower:
            slots["detail"] = "failed_count"
        if "nightly" in transcript.lower():
            slots["run_name"] = "nightly"

        if "regression" in transcript.lower():
            slots["run_name"] = "regression"

        return slots