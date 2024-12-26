import os
import json
import re
import logging
from openai import AzureOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from models.JSONPostprocessor import JSONPostprocessor

class AzureChat:
    def __init__(self, output_txt_dir, transcribe_content_type: str = "create_json_file"):
        """
        Initializes the AzureChat with necessary configurations and system prompt.

        :param output_txt_dir: The directory where the transcribed output text files will be saved.
        :param transcribe_content_type: The type of content to be transcribed, default is 'create_json_file'.
        """
        self.output_txt_dir = self._replace_backslashes(output_txt_dir)
        os.makedirs(self.output_txt_dir, exist_ok=True)

        self.max_tokens = int(os.getenv("MAX_TOKENS", "2048"))
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
        self.postprocessor = JSONPostprocessor(system_content="You are an expert in CFA finance.")

    @staticmethod
    def _replace_backslashes(path: str) -> str:
        """
        Replaces backslashes with forward slashes in the given path.
        
        :param path: The file path to be modified.
        :return: The path with backslashes replaced by forward slashes.
        """
        return path.replace('\\\\', '/').replace('\\', '/')

    @staticmethod
    def read_system_prompt(file_path: str) -> str:
        """
        Reads and returns the system prompt from the specified file path.

        :param file_path: Path to the system prompt text file.
        :return: Content of the system prompt file as a string.
        """
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()

    @staticmethod
    def read_data_to_convert(file_path: str) -> str:
        """
        Reads the file to be converted and processes its content.

        :param file_path: Path to the file to be read and processed.
        :return: Cleaned content of the file as a string.
        """
        file_path = AzureChat._replace_backslashes(file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                content = file.read()
                content = re.sub(r'[^\x00-\x7F]+', ' ', content)
                content = re.sub(r'\s+', ' ', content)
                logging.debug(f"Read and cleaned file content: {content[:100]}...")
                return content.strip()
        except Exception as e:
            logging.error(f"Error reading and cleaning file {file_path}: {e}")
            raise

    def split_text(self, text: str, chunk_size: int = 2048, chunk_overlap: int = 100) -> list:
        """
        Splits the text into smaller chunks for processing.

        :param text: The text to be split.
        :param chunk_size: The size of each chunk.
        :param chunk_overlap: The overlap between consecutive chunks.
        :return: A list of text chunks.
        """
        if chunk_size <= chunk_overlap:
            raise ValueError("Chunk size should be larger than chunk overlap")
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        return text_splitter.split_text(text)

    def send_message(self, data_file_path: str):
        """
        Sends the data in the file as messages to the Azure OpenAI model and writes the responses to an output file.

        :param data_file_path: Path to the file containing data to be sent.
        :return: A boolean indicating whether the process was successful.
        """
        data_file_path = self._replace_backslashes(data_file_path)
        try:
            logging.info(f"Reading data from file: {data_file_path}")
            data_to_convert = self.read_data_to_convert(data_file_path)
            logging.info(f"Data read and cleaned from file: {data_file_path}")

            total_max_length = self.max_tokens - len(self.system_prompt)
            chunk_size = max(total_max_length - 200, 200)
            chunk_overlap = 100
            
            data_chunks = self.split_text(data_to_convert, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

            output_jsonl_path = self._replace_backslashes(
                os.path.join(self.output_txt_dir, os.path.splitext(os.path.basename(data_file_path.split('.')[0]))[0] + ".jsonl")
            )
            
            logging.info(f"Output JSONL path: {output_jsonl_path}")

            with open(output_jsonl_path, "a", encoding="utf-8") as file:
                for i, chunk in enumerate(data_chunks):
                    messages = [
                        {
                            "role": "system",
                            "content": self.system_prompt
                        },
                        {
                            "role": "user",
                            "content": f"""
Curriculum Context: {chunk}
-----------------------------------------------------------
Generate possible questions and answers from this segment of curriculum.
"""
                        }
                    ]
                    logging.debug(f"Sending message for chunk {i+1}: {chunk[:100]}...")

                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=self.max_tokens
                    )

                    try:
                        response_content = response.choices[0].message.content.strip()
                        logging.debug(f"Response content for chunk {i+1}: {response_content[:500]}...")
                        
                        processed_responses = self.postprocessor.convert_response(response_content)
                        
                        for processed_response in processed_responses:
                            file.write(json.dumps(processed_response) + "\n")
                            file.flush()

                    except (AttributeError, KeyError) as e:
                        logging.error(f"Error extracting response content for file {data_file_path} chunk {i+1}: {e}")
                        continue

                    logging.info(f"Finished chunk {i + 1}/{len(data_chunks)}")

            return True

        except Exception as e:
            if hasattr(e, 'response') and e.response.status_code == 429:
                logging.error(f"[RATE LIMIT EXCEEDED] for {data_file_path}. Re-adding to queue after delay.")
                return False
            elif hasattr(e, 'response') and e.response.status_code == 400:
                logging.error(f"[CONTENT FILTERING] Error for {data_file_path}. Skipping this file.")
            else:
                logging.error(f"Error processing file {data_file_path}: {e}")

        return True  # Return True to indicate the task should not be re-added to the queue