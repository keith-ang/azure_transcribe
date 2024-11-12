# Transcription Tools

This repository contains two scripts designed to automate the process of transcribing images and videos using Azure Services.

## Table of Contents
- [Overview](#overview)
- [Requirements](#requirements)
- [Setup](#setup)
- [Usage](#usage)
  - [Image Transcription](#image-transcription)
  - [Video Transcription](#video-transcription)
- [Error Handling](#error-handling)
- [Logging](#logging)
- [Contributors](#contributors)

## Overview
- **transcribe_image.py**: This script copies PNG images from a source directory to a target directory and uses Azure OCR to transcribe the text in these images.
- **transcribe_video.py**: This script converts videos (MP4/WEBM) into audio files (WAV) and uses Azure's Speech-to-Text service to transcribe the audio.

Both scripts handle tasks using multiprocessing and multithreading to improve performance and manage resource usage effectively.

## Requirements
- Python 3.8+
- Azure Services (Computer Vision for OCR, Speech Service for audio transcription)
- `dotenv` for environment variables
- `argparse` for command-line argument parsing
- `logging` for logging
- `concurrent.futures` for threading
- `multiprocessing` for parallel processing

## Setup
1. **Install Required Packages:**
    ```sh
    pip install -r requirements.txt
    ```

2. **Environment Variables:** Create a `.env` file in the root of the repository and populate it with your Azure service credentials.

    ```plaintext
    AZURE_OPENAI_API_KEY=<your Azure OpenAI API key>
    AZURE_OPENAI_ENDPOINT=<your Azure OpenAI API endpoint>
    API_VERSION=<your Azure OpenAI API version>
    DEPLOYMENT_NAME=<your Azure OpenAI deployment name>
    MAX_TOKENS=<your Azure OpenAI token limit>

    AZURE_SPEECH_API_KEY=<your Azure Speech Services API key>
    AZURE_SPEECH_REGION=<your Azure Speech Services region>
    ```

## Usage 

### Image Transcription

#### Command-Line Arguments
- `--base_dir`: Base directory containing PNG files.
- `--output_image_dir`: Directory to save copied PNG images.
- `--output_txt_dir`: Directory to save transcribed text.
- `--logs_dir`: Directory to save logging.

#### Example Command:
```sh
python3 transcribe_image.py --base_dir ./input_images --output_image_dir ./output_images --output_txt_dir ./output_texts --logs_dir ./logs
```

### Video Transcription 

#### Command-Line Arguments
- `--base_dir`: Base directory containing MP4 or WEBM files.
- `--output_wav_dir`: Directory to save converted WAV files.
- `--output_txt_dir`: Directory to save transcribed text.
- `--logs_dir`: Directory to save logging.
- `--language`: Language of the videos (e.g., `en-US` for English/`th-TH` for Thai).

#### Example Command:
```sh
python3 transcribe_video.py --base_dir ./input_videos --output_wav_dir ./output_wavs --output_txt_dir ./output_texts --logs_dir ./logs --language en-US
```

## Error Handling
Both programs handle errors gracefully:
- Logs errors and continues processing other files.
- For rate limiting errors (HTTP 429), the script retries after a delay.

## Logging
The programs log activity to both a console and log files. There are separate logs for general information and errors to help with debugging and auditing.

## Contributors
If you would like to contribute to this project, feel free to fork the repository and create a pull request.
