import json

def parse_llm_response(text: str):

    try:
        start = text.find("{")
        end = text.rfind("}") + 1

        clean_json = text[start:end]

        data = json.loads(clean_json)

        intent = data.get("intent", "unknown")
        slots = data.get("slots", {})

        confidence = data.get("confidence", 0.6)

        return intent, slots, confidence

    except Exception:
        return "unknown", {}, 0.3