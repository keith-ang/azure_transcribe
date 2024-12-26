import json
import logging

class JSONPostprocessor:
    def __init__(self, system_content: str):
        """
        Initializes the JSONPostprocessor with the system content.

        :param system_content: The content for the system role message.
        """
        self.system_content = system_content

    def convert_response(self, response_content: str) -> list:
        """
        Converts the response content into the desired JSON format.

        :param response_content: The original response content from the model.
        :return: A list of JSON objects in the new format.
        """
        try:
            qa_pairs = json.loads(response_content)
            processed_responses = []

            for qa_pair in qa_pairs:
                json_object = {"messages": [{"role": "system", "content": self.system_content}, {"role": "user", "content": qa_pair["question"]}, {"role": "assistant", "content": qa_pair["answer"]}]}
                processed_responses.append(json_object)

            return processed_responses
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from response content: {e}")
            return []
        except KeyError as e:
            logging.error(f"Missing expected key in the response content: {e}")
            return []

