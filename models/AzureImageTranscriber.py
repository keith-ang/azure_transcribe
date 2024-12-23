import os
import base64
import logging
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

class AzureImageTranscriber:
    def __init__(self, output_txt_dir, transcribe_content_type: str = "default"):
        """
        Initializes the AzureImageTranscriber with necessary configurations and system prompt.

        :param output_txt_dir: The directory where the transcribed output text files will be saved.
        :param transcribe_content_type: The type of content to be transcribed, default is 'default'.
        """
        self.output_txt_dir = output_txt_dir
        self.max_tokens = os.getenv("MAX_TOKENS")
        self.model = os.getenv("DEPLOYMENT_NAME")
        try:
            self.system_prompt = self.read_system_prompt(f"./txt_files/system_prompt_{transcribe_content_type}.txt")
        except FileNotFoundError:
            raise FileNotFoundError(f"System prompt file for '{transcribe_content_type}' not found at './txt_files/system_prompt_{transcribe_content_type}.txt'")
        except Exception as e:
            raise RuntimeError(f"An error occurred while reading the system prompt for '{transcribe_content_type}': {e}")

        self.client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
            api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
            api_version=os.getenv("API_VERSION")
        )

    @staticmethod
    def read_system_prompt(file_path: str) -> str:
        """
        Reads and returns the system prompt from the specified file path.

        :param file_path: Path to the system prompt text file.
        :return: Content of the system prompt file as a string.
        """
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()
        
    def transcribe_image(self, image_file_path: str, job_id):
        """
        Transcribes the content of an image file into text using Azure's OpenAI service.

        :param image_file_path: The path to the image file to be transcribed.
        :param job_id: An identifier for the job, useful for logging and debugging purposes.
        :return: The transcribed text content.
        """
        # Convert image to base64
        with open(image_file_path, "rb") as image_file:
            image_base64_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": f"{self.system_prompt}"
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": image_base64_string,
                    }
                ]
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            content = response.choices[0].message.content
            
            # Generate output .txt file path from image file path
            os.makedirs(self.output_txt_dir, exist_ok=True)
            output_txt_path = os.path.join(self.output_txt_dir, os.path.splitext(os.path.basename(image_file_path))[0] + ".txt")
            with open(output_txt_path, "w", encoding="utf-8") as file:
                file.write(content)
            return content

        except Exception as e:
            logging.error(f"Job {job_id}: Failed to make the request. Error: {e}")
            raise