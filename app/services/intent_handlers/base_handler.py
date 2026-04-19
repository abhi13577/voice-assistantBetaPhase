"""
Base class for all intent handlers with error handling infrastructure.
Production-grade error handling and logging.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseIntentHandler(ABC):
    """
    Base class for all intent handlers.
    
    Each handler must define an intent_name and implement the handle() method.
    The base class provides error handling, logging, and metrics collection.
    """

    intent_name: str = None

    @abstractmethod
    async def handle(self, user_id, project_id, transcript, llm_slots):
        """
        Process intent and return a response.
        
        Args:
            user_id: The user ID
            project_id: The project ID
            transcript: The user's transcript
            llm_slots: Extracted slots from LLM fallback
            
        Returns:
            Tuple of (reply, intents, suggestions)
            - reply (str): The response to the user
            - intents (list): List of intents handled
            - suggestions (list): Suggested follow-up actions
            
        Raises:
            Any exception will be caught by intent_router and handled gracefully
        """
        raise NotImplementedError("Handler must implement handle()")
    
    async def handle_safe(self, user_id, project_id, transcript, llm_slots):
        """
        Safely execute handle() with error catching and logging.
        
        Args:
            user_id: The user ID
            project_id: The project ID  
            transcript: The user's transcript
            llm_slots: Extracted slots from LLM fallback
            
        Returns:
            Tuple of (reply, intents, suggestions)
        """
        try:
            logger.debug(
                f"Handler {self.intent_name} processing: "
                f"user_id={user_id}, project_id={project_id}, "
                f"transcript={transcript[:100]}"
            )
            
            result = await self.handle(user_id, project_id, transcript, llm_slots)
            
            if not isinstance(result, tuple) or len(result) != 3:
                logger.error(
                    f"Handler {self.intent_name} returned invalid result format: {result}"
                )
                return (
                    "I encountered an error processing that request.",
                    [self.intent_name],
                    []
                )
            
            logger.debug(f"Handler {self.intent_name} succeeded")
            return result
            
        except ValueError as e:
            logger.warning(f"Handler {self.intent_name} validation error: {e}")
            return (
                "I didn't understand that properly. Could you please rephrase?",
                [self.intent_name],
                []
            )
        except KeyError as e:
            logger.error(f"Handler {self.intent_name} missing required data: {e}")
            return (
                "I couldn't find the information I need to answer that.",
                [self.intent_name],
                []
            )
        except Exception as e:
            logger.error(
                f"Unexpected error in handler {self.intent_name}: "
                f"{type(e).__name__}: {e}",
                exc_info=True
            )
            return (
                "Something went wrong. Please try again.",
                [self.intent_name],
                []
            )