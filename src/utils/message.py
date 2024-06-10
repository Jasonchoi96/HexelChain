# Helper classes that make it easier to return messages and responses from 
# from the LLMs
# This is used by all the LLMs in the src/llm_kernel/llm_classes/ directory

class Message:
    def __init__(self,
            prompt,
            context = None,
            tools = None
        ) -> None:
        self.prompt = prompt
        self.context = context
        self.tools = tools

class Response:
    def __init__(
            self,
            response_message,
            tool_calls = None
        ) -> None:
        self.response_message = response_message
        self.tool_calls = tool_calls
