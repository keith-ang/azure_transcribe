from models.AzureChat import AzureChat
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import os
import logging
import time
from datetime import datetime

# Constants
INPUT_DIR = "data_coding_txt"  # Directory containing input text files
OUTPUT_TXT_DIR = "./coding_jsonl"  # Directory to save transcribed text
MAX_WORKERS = os.cpu_count()  # Maximum number of worker threads
RETRY_DELAY = 60  # Delay in seconds before retrying after a rate limit error

# Initialize logging
log_dir = './logs'
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'create_training_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all logs
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # If you also want to see logs on the console
    ]
)

# Initialize a queue
job_queue = Queue()

def worker(chat):
    """
    Worker function to process jobs from the queue.

    :param chat: Instance of AzureChat.
    """
    while True:
        job = job_queue.get()
        if job is None:
            break
        process_file(chat, job)
        job_queue.task_done()

def process_file(chat, file_path):
    """
    Processes a single file using AzureChat.

    :param chat: Instance of AzureChat.
    :param file_path: Path to the file to be processed.
    """
    try:
        logging.info(f"Processing file: {AzureChat._replace_backslashes(file_path)}")
        chat.send_message(file_path)
        logging.info(f"Successfully processed file: {AzureChat._replace_backslashes(file_path)}")
    except Exception as e:
        if hasattr(e, 'response') and e.response.status_code == 429:
            logging.error(f"[RATE LIMIT EXCEEDED] Rate limit error for {AzureChat._replace_backslashes(file_path)}. Re-adding to queue after delay.")
            time.sleep(RETRY_DELAY)
            job_queue.put(file_path)
            logging.info(f"[RETRY] Re-added task to queue after rate limit error for {AzureChat._replace_backslashes(file_path)}")
        else:
            logging.error(f"Error processing file {AzureChat._replace_backslashes(file_path)}: {e}")

def main(input_dir, output_txt_dir, max_workers=4):
    """
    Main function to initialize processing and manage worker threads.

    :param input_dir: Directory containing input text files.
    :param output_txt_dir: Directory to save transcribed text.
    :param max_workers: Maximum number of workers to use.
    """
    chat = AzureChat(AzureChat._replace_backslashes(output_txt_dir), transcribe_content_type="create_coding_data")
    
    # Enqueue all .txt files to the job queue
    for root, _, files in os.walk(AzureChat._replace_backslashes(input_dir)):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                job_queue.put(AzureChat._replace_backslashes(file_path))
    
    # Start worker threads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for _ in range(max_workers):
            futures.append(executor.submit(worker, chat))
        
        # Wait for the queue to be empty
        job_queue.join()
    
    # Signal termination to workers
    for _ in range(max_workers):
        job_queue.put(None)

    # Wait for all workers to finish
    for future in as_completed(futures):
        future.result()

if __name__ == '__main__':
    main(INPUT_DIR, OUTPUT_TXT_DIR, MAX_WORKERS)