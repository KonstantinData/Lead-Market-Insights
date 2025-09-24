# Notes: Agent responsible for detecting if an event matches one of the trigger words.
class TriggerDetectionAgent:
    def __init__(self, trigger_words=None):
        # Notes: List of trigger words, can be set via config or directly.
        self.trigger_words = trigger_words or ["trigger word", "demo"]

    def check(self, event):
        """
        Notes:
        - Checks if the event contains any of the trigger words.
        - Returns True if a trigger is detected, otherwise False.
        """
        summary = event.get("summary", "").lower()
        return any(word.lower() in summary for word in self.trigger_words)
