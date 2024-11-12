from preprocessors.PNGCollater import PNGCollater
from models.AzureImageTranscriber import AzureImageTranscriber
from memory.MemoryManagement import MemoryManager

from datetime import datetime
import logging
import os
import time
import argparse
from dotenv import load_dotenv

import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

MAX_CONVERT_WORKERS = 2
MAX_TRANSCRIBE_WORKERS = os.cpu_count() * 2
RETRY_DELAY = 60  # Delay in seconds before retrying transcription after rate limit error

job_counter = threading.Lock()
job_id = 0

class CustomFilter(logging.Filter):
    def filter(self, record):
        return "rate limit" not in record.getMessage()

def setup_logging(log_directory):
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(log_directory, f"transcribe_image_{current_time}.log")
    error_log_file_path = os.path.join(log_directory, f"transcribe_image_errors_{current_time}.log")

    os.makedirs(log_directory, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        ]
    )

    error_logger = logging.getLogger('error_logger')
    error_handler = logging.FileHandler(error_log_file_path, mode='a', encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] - %(message)s"))
    error_handler.addFilter(CustomFilter())
    error_logger.addHandler(error_handler)

    return error_logger

def generate_job_id():
    global job_id
    with job_counter:
        job_id += 1
        return job_id

def copy_png_image_task(png_path, collater, transcription_queue, job_id, transcript_directory):
    global error_logger  # Ensure error_logger is accessible within this function
    try:
        output_image_path = collater.copy_png_image(png_path, transcript_directory)
        if output_image_path:  # Only add to the queue if the image was copied
            logging.info(f"[JOB_ID_{job_id}]: [COPY SUCCESS] Copied {png_path} to {output_image_path}")
            transcription_queue.put((job_id, output_image_path))  # Put the result into the transcription queue
            return output_image_path
        else:
            logging.info(f"[JOB_ID_{job_id}]: [COPY SKIPPED] Skipped copying for {png_path} as it already has a transcript/it is not a slide")
            return "Skipped"
    except Exception as e:
        logging.error(f"[JOB_ID_{job_id}]: [COPY FAILED] Failed to copy {png_path}: {e}")
        error_logger.error(f"[JOB_ID_{job_id}]: Failed to copy {png_path}: {e}")
        return f"Failed: {e}"

def transcribe_image_task(transcription_queue, azure_image_transcriber, memory_manager):
    global error_logger
    while True:
        job = transcription_queue.get()
        if job is None:
            logging.info("[TRANSCRIBE END] Received termination signal, exiting transcription worker.")
            break

        job_id, image_file_path = job
        try:
            azure_image_transcriber.transcribe_image(image_file_path, job_id)
            logging.info(f"[JOB_ID_{job_id}]: [TRANSCRIBE SUCCESS] Transcribed and saved result for {image_file_path}")
            memory_manager.del_temp_audio(image_file_path)
            logging.info(f"[JOB_ID_{job_id}]: [MEMORY MANAGEMENT] Deleted temporary file {image_file_path}")
        except Exception as e:
            if hasattr(e, 'response') and e.response.status_code == 429:
                logging.error(f"[JOB_ID_{job_id}]: [RATE LIMIT EXCEEDED] Rate limit error for {image_file_path}. Re-adding to queue after delay.")
                time.sleep(RETRY_DELAY)
                transcription_queue.put(job)
                logging.info(f"[JOB_ID_{job_id}]: [RETRY] Re-added task to queue after rate limit error for {image_file_path}")
            else:
                logging.error(f"[JOB_ID_{job_id}]: [TRANSCRIBE FAILED] Failed to transcribe {image_file_path} : {e}")
                error_logger.error(f"[JOB_ID_{job_id}]: [TRANSCRIBE FAILED] Error during transcription : {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="Process PNG files and transcribe images using Azure.")
    parser.add_argument('--base_dir', help='Base directory containing PNG files', required=True)
    parser.add_argument('--output_image_dir', help='Directory to save copied PNG images', required=True)
    parser.add_argument('--output_txt_dir', help='Directory to save transcribed text', required=True)
    parser.add_argument('--logs_dir', help='Directory to save logging', required=True)
    return parser.parse_args()

def file_generator(base_dir):
    """Lazy generator to yield PNG files."""
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.png'):
                yield os.path.join(root, file)

def conversion_worker(args):
    file_queue, output_image_dir, output_txt_dir, transcription_queue, logs_dir = args
    global error_logger
    error_logger = setup_logging(logs_dir)
    
    collater = PNGCollater(output_directory=output_image_dir)
    logging.info("[CONVERTER INITIALISATION] Initialised PNG Collater")

    with ThreadPoolExecutor(max_workers=MAX_CONVERT_WORKERS) as executor:
        futures = []

        while True:
            png_path = file_queue.get()
            if png_path is None:
                logging.info("[CONVERSION END] Received termination signal in conversion worker, exiting.")
                break

            job_id = generate_job_id()
            future = executor.submit(copy_png_image_task, png_path, collater, transcription_queue, job_id, output_txt_dir)
            futures.append(future)

        # Wait for all futures to complete
        for future in as_completed(futures):
            result = future.result()
            if result == "Skipped" or result.startswith("Failed:"):
                logging.info(f"Conversion result: {result}")
            else:
                logging.info(f"Successfully copied file to: {result}")

    logging.info("[CONVERSION COMPLETE] All conversion tasks are complete.")
    transcription_queue.put(None)  # Signal to terminate transcription workers

def transcription_worker(args):
    transcription_queue, output_txt_dir, logs_dir = args
    global error_logger
    error_logger = setup_logging(logs_dir)
    
    azure_image_transcriber = AzureImageTranscriber(output_txt_dir=output_txt_dir)
    logging.info("[TRANSCRIBER INITIALISATION] Initialised Azure Image Transcriber")
    memory_manager = MemoryManager()

    transcribe_threads = []
    for _ in range(MAX_TRANSCRIBE_WORKERS):
        thread = threading.Thread(target=transcribe_image_task, args=(transcription_queue, azure_image_transcriber, memory_manager))
        thread.start()
        transcribe_threads.append(thread)

    for thread in transcribe_threads:
        thread.join()

    logging.info("[TRANSCRIPTION COMPLETE] All transcription tasks are complete.")

def main():
    args = parse_args()

    base_dir = args.base_dir
    output_image_dir = args.output_image_dir
    output_txt_dir = args.output_txt_dir
    logs_dir = args.logs_dir

    os.makedirs(output_txt_dir, exist_ok=True)

    setup_logging(logs_dir)  # Initial logging setup
    logging.info("Collecting PNG files to process.")

    transcription_queue = multiprocessing.Queue()
    file_queue = multiprocessing.Queue()

    # Start the workers
    transcription_args = (transcription_queue, output_txt_dir, logs_dir)
    conversion_args = (file_queue, output_image_dir, output_txt_dir, transcription_queue, logs_dir)
    
    transcription_process = multiprocessing.Process(target=transcription_worker, args=(transcription_args,))
    conversion_process = multiprocessing.Process(target=conversion_worker, args=(conversion_args,))

    
    transcription_process.start()
    conversion_process.start()

    # Add files to the file queue using the generator
    for png_file in file_generator(base_dir):
        file_queue.put(png_file)

    # Add termination signals to close the conversion worker
    file_queue.put(None)

    # Wait for the conversion process to finish
    conversion_process.join()

    # Add termination signals to close the transcription workers
    for _ in range(MAX_TRANSCRIBE_WORKERS):
        transcription_queue.put(None)

    # Wait for the transcription process to finish
    transcription_process.join()

    logging.info("[PROGRAM COMPLETE] All tasks are complete. Terminating the program.")

if __name__ == '__main__':
    main()