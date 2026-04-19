from app.schemas.response import SuggestedAction
"""
Future feature: Suggestion engine / context tracking.

Currently not integrated in the demo vertical.
Will be used when conversation memory is implemented.
"""

class SuggestionEngine:

    def generate(self, intent: str, context: dict, user_permissions=None):

        suggestions = []

        if intent == "explain_failure":
            error_message = context.get("error_message", "").lower()

            # Timeout case
            if "timeout" in error_message:
                suggestions.append(
                    SuggestedAction(
                        label="Increase timeout for this step",
                        action_type="update_timeout",
                        params={}
                    )
                )

                suggestions.append(
                    SuggestedAction(
                        label="Rerun this test",
                        action_type="rerun_test",
                        params={"test_case_id": 201}
                    )
                )

            # Selector issue
            elif "selector" in error_message or "not found" in error_message:
                suggestions.append(
                    SuggestedAction(
                        label="Open test editor to update selector",
                        action_type="open_test_editor",
                        params={}
                    )
                )

                suggestions.append(
                    SuggestedAction(
                        label="Rerun this test",
                        action_type="rerun_test",
                        params={"test_case_id": 201}
                    )
                )

            # Unknown error
            else:
                suggestions.append(
                    SuggestedAction(
                        label="View execution logs",
                        action_type="view_logs",
                        params={}
                    )
                )

                suggestions.append(
                    SuggestedAction(
                        label="Escalate to L2 support",
                        action_type="escalate_case",
                        params={}
                    )
                )

        return suggestions


suggestion_engine = SuggestionEngine()