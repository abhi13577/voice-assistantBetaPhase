import pkgutil
import importlib
import inspect
import logging

from app.services.intent_handlers.base_handler import BaseIntentHandler

logger = logging.getLogger(__name__)


class IntentRouter:

    def __init__(self):

        self.handlers = {}

        package = "app.services.intent_handlers"

        for _, module_name, _ in pkgutil.iter_modules(
            importlib.import_module(package).__path__
        ):

            module = importlib.import_module(f"{package}.{module_name}")

            for name, obj in inspect.getmembers(module):

                if (
                    inspect.isclass(obj)
                    and issubclass(obj, BaseIntentHandler)
                    and obj is not BaseIntentHandler
                ):

                    handler_instance = obj()

                    intent_name = getattr(handler_instance, "intent_name", None)

                    if intent_name:
                        self.handlers[intent_name] = handler_instance

        logger.info("Loaded intent handlers: %s", list(self.handlers.keys()))

    async def route(self, intent, user_id, project_id, transcript, llm_slots):

        handler = self.handlers.get(intent)

        if not handler:
            return (
                "I didn’t understand that. You can ask about your last run or list your projects.",
                [],
                []
            )

        return await handler.handle(
            user_id,
            project_id,
            transcript,
            llm_slots
        )


intent_router = IntentRouter()