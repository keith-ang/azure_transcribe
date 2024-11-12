from models.AzureSpeechTranscriber import AzureSpeechTranscriber
from preprocessors.VideoPreprocessor import VideoPreprocessor
from memory.MemoryManagement import MemoryManager
from utils.languages import LANGUAGE_MAP

from datetime import datetime
import argparse
import os
import time
import logging
from dotenv import load_dotenv

import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

MAX_CONVERT_WORKERS = 2  # Set an appropriate number based on your CPU capabilities
MAX_TRANSCRIBE_WORKERS = os.cpu_count() * 3  # Adjust for I/O-bound nature of transcription tasks
RETRY_DELAY = 60  # Delay in seconds before retrying transcription after rate limit error

job_counter = threading.Lock()
job_id = 0

class CustomFilter(logging.Filter):
    def filter(self, record):
        return "rate limit" not in record.getMessage()

def setup_logging(log_directory):        
    os.makedirs(log_directory, exist_ok=True)

    current_time =  datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(log_directory, f"transcribe_video_{current_time}.log")
    error_log_file_path = os.path.join(log_directory, f"transcribe_video_errors_{current_time}.log")

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

def convert_video_to_wav_task(mp4_path, video_preprocessor, transcription_queue, job_id, transcription_directory):
    global error_logger  # Ensure error_logger is accessible within this function
    try:
        logging.info(f"[JOB_ID_{job_id}]: Starting conversion for {mp4_path}...")
        output_wav_path = video_preprocessor.convert_mp4_or_webm_to_wav(mp4_path, transcription_directory)
        if output_wav_path:  # Only add to the queue if conversion is successful
            logging.info(f"[JOB_ID_{job_id}]: [CONVERT SUCCESS] Converted {mp4_path} to {output_wav_path}")
            transcription_queue.put((job_id, output_wav_path))  # Put the result into the transcription queue
            return output_wav_path
        else:
            logging.info(f"[JOB_ID_{job_id}]: [CONVERT SKIPPED] Skipped conversion for {mp4_path} as it already has a transcript")
            return "Skipped"
    except Exception as e:
        logging.error(f"[JOB_ID_{job_id}]: [CONVERT FAILED] Failed to convert {mp4_path}: {e}")
        error_logger.error(f"[JOB_ID_{job_id}]: [CONVERT FAILED] Failed to convert {mp4_path}: {e}")
        return f"Failed: {e}"

def transcribe_wav_task(transcription_queue, azure_speech_transcriber, memory_manager):
    global error_logger  # Ensure error_logger is accessible within this function
    while True:
        job = transcription_queue.get()
        if job is None:
            logging.info("[TRANSCRIBE WORKER END] Received termination signal in transcription worker, exiting.")
            break
        
        job_id, wav_file_path = job
        try:
            logging.info(f"[JOB_ID_{job_id}]: Starting transcription for {wav_file_path}")
            transcript_file_path = azure_speech_transcriber.transcribe(wav_file_path)
            logging.info(f"[JOB_ID_{job_id}]: [TRANSCRIBE SUCCESS] Transcribed and saved transcript to: {transcript_file_path}")
            memory_manager.del_temp_audio(wav_file_path)
            logging.info(f"[JOB_ID_{job_id}]: [MEMORY_MANAGEMENT] Deleted {wav_file_path} for memory management")
        except Exception as e:
            if hasattr(e, 'response') and e.response.status_code == 429:
                logging.info(f"[JOB_ID_{job_id}]: [RE-ADD_TO_QUEUE] Rate limit exceeded for {wav_file_path}. Re-adding to queue after delay.")
                time.sleep(RETRY_DELAY)
                transcription_queue.put(job)  # Re-add the task to the queue
                logging.info(f"[JOB_ID_{job_id}]: [TRANSCRIBE RETRY] Task re-added to the queue after rate limit error.")
            else:
                logging.error(f"[JOB_ID_{job_id}]: [TRANSCRIBE FAILED] Failed to transcribe {wav_file_path}: {e}")
                error_logger.error(f"[JOB_ID_{job_id}]: [TRANSCRIBE FAILED] Failed to transcribe {wav_file_path}: {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="Process MP4 files and transcribe audio using Azure.")
    parser.add_argument('--base_dir', help='Base directory containing MP4 files', required=True)
    parser.add_argument('--output_wav_dir', help='Directory to save converted WAV files', required=True)
    parser.add_argument('--output_txt_dir', help='Directory to save transcribed text', required=True)
    parser.add_argument('--logs_dir', help='Directory to save logging', required=True)
    parser.add_argument('--language', help='Language of the audio to transcribe ("english" or "thai")', required=True)
    
    return parser.parse_args()

def file_generator(base_dir):
    """ Lazy generator to yield MP4 files. """
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.mp4') or file.endswith('.webm'):
                yield os.path.join(root, file)

def conversion_worker(args):
    file_queue, output_wav_dir, transcription_directory, transcription_queue, logs_dir = args
    global error_logger
    error_logger = setup_logging(logs_dir)
    
    video_preprocessor = VideoPreprocessor(temp_audio_path=output_wav_dir)
    logging.info("[CONVERSION INITIALISATION] Initialised MP4 Converter")

    with ThreadPoolExecutor(max_workers=MAX_CONVERT_WORKERS) as executor:
        futures = []

        while True:
            mp4_path = file_queue.get()
            if mp4_path is None:
                logging.info("[CONVERSION END] Received termination signal in conversion worker, exiting.")
                break
            
            job_id = generate_job_id()
            future = executor.submit(convert_video_to_wav_task, mp4_path, video_preprocessor, transcription_queue, job_id, transcription_directory)
            futures.append(future)

        # Wait for all futures to complete
        for future in as_completed(futures):
            result = future.result()
            if result == "Skipped" or result.startswith("Failed:"):
                logging.info(f"Conversion result: {result}")
            else:
                logging.info(f"Successfully converted file to: {result}")

    logging.info("[CONVERSION COMPLETE] All conversion tasks are complete.")
    transcription_queue.put(None)  # Signal to terminate transcription workers

def transcription_worker(args):
    transcription_queue, output_txt_dir, language, logs_dir = args
    global error_logger
    error_logger = setup_logging(logs_dir)
    
    azure_speech_transcriber = AzureSpeechTranscriber(language_to_transcribe=LANGUAGE_MAP[language], output_folder=output_txt_dir)
    logging.info(f"[TRANSCRIPTION INITIALISATION] Initialised Azure Speech Service to transcribe {azure_speech_transcriber.language_to_transcribe} language")
    memory_manager = MemoryManager()
        
    transcribe_threads = []
    for _ in range(MAX_TRANSCRIBE_WORKERS):
        thread = threading.Thread(target=transcribe_wav_task, args=(transcription_queue, azure_speech_transcriber, memory_manager))
        thread.start()
        transcribe_threads.append(thread)
        
    for thread in transcribe_threads:
        thread.join()
        
    logging.info("[TRANSCRIPTION COMPLETE] All transcription tasks are complete.")

def main():
    args = parse_args()
    
    base_dir = args.base_dir
    output_wav_dir = args.output_wav_dir
    output_txt_dir = args.output_txt_dir
    logs_dir = args.logs_dir
    language = args.language.upper()
    if language not in LANGUAGE_MAP:
        raise ValueError(f"Invalid language. Available options are: {', '.join(LANGUAGE_MAP.keys())}")
        
    os.makedirs(output_txt_dir, exist_ok=True)
    
    setup_logging(logs_dir)
    logging.info("Collecting MP4/WEBM files to process.")
    
    file_queue = multiprocessing.Queue()
    transcription_queue = multiprocessing.Queue()
    
    # Start the workers
    conversion_args = (file_queue, output_wav_dir, output_txt_dir, transcription_queue, logs_dir)
    transcription_args = (transcription_queue, output_txt_dir, language, logs_dir)
    
    conversion_process = multiprocessing.Process(target=conversion_worker, args=(conversion_args,))
    transcription_process = multiprocessing.Process(target=transcription_worker, args=(transcription_args,))
    
    transcription_process.start()
    conversion_process.start()
    
    for mp4_file in file_generator(base_dir):
        file_queue.put(mp4_file)
    
    file_queue.put(None)  # Send termination signal to the conversion worker
    
    # Wait for all processes to finish
    conversion_process.join()

    # Add termination signals to close the transcription workers
    for _ in range(MAX_TRANSCRIBE_WORKERS):
        transcription_queue.put(None)
        
    transcription_process.join()
    
    logging.info("[PROGRAM COMPLETE] All tasks are complete. Terminating the program.")

if __name__ == "__main__":
    main()