class HumanInLoopAgent:
    def request_info(self, event, extracted):
        """
        Notes:
        - Requests missing info from a human (this is a dummy
        implementation for demonstration).
        - In a real scenario, this could send an email, Slack
        message, or open a web form.
        - Here, it simulates a user providing the missing
        information.
        """
        print(
            f"Please provide missing info for event "
            f"{event.get('id', '<unknown>')}: {extracted['info']}"
        )
        # Simulate human response for demo purposes:
        extracted["info"]["company_name"] = (
            extracted["info"].get("company_name") or "Example Corp"
        )
        extracted["info"]["web_domain"] = (
            extracted["info"].get("web_domain") or "example.com"
        )
        extracted["is_complete"] = True
        return extracted
