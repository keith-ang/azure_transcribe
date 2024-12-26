from models.AzureChat import AzureChat
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
import os
import logging
import time
from datetime import datetime

# Constants
INPUT_DIR = "data_cfa"
OUTPUT_TXT_DIR = "./cfa_jsonl"
MAX_WORKERS = os.cpu_count() * 2
RETRY_DELAY = 60

# Initialize logging
log_dir = './logs'
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'create_training_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

# Initialize a queue
job_queue = Queue()

def process_file(chat, file_path):
    """
    Processes a single file using AzureChat.

    :param chat: Instance of AzureChat.
    :param file_path: Path to the file to be processed.
    """
    try:
        logging.info(f"Processing file: {file_path}")
        success = chat.send_message(file_path)
        if success:
            logging.info(f"Successfully processed file: {file_path}")
        else:
            logging.info(f"Re-added file for retry due to rate limit: {file_path}")
            time.sleep(RETRY_DELAY)
            job_queue.put(file_path)
    except Exception as e:
        logging.error(f"Unhandled error processing file {file_path}: {e}")
    finally:
        job_queue.task_done()

def worker(chat):
    """
    Worker function to process jobs from the queue.

    :param chat: Instance of AzureChat.
    """
    while True:
        try:
            job = job_queue.get(timeout=1)
        except Empty:
            continue
        
        if job is None:
            break
        
        process_file(chat, job)

def main(input_dir, output_txt_dir, max_workers=4):
    """
    Main function to initialize processing and manage worker threads.

    :param input_dir: Directory containing input text files.
    :param output_txt_dir: Directory to save transcribed text.
    :param max_workers: Maximum number of workers to use.
    """
    chat = AzureChat(output_txt_dir, transcribe_content_type="create_cfa_data")
    
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                job_queue.put(file_path)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for _ in range(max_workers):
            futures.append(executor.submit(worker, chat))
        
        job_queue.join()
    
    for _ in range(max_workers):
        job_queue.put(None)

    for future in as_completed(futures):
        future.result()

if __name__ == '__main__':
    main(INPUT_DIR, OUTPUT_TXT_DIR, MAX_WORKERS)