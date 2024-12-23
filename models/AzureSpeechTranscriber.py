import azure.cognitiveservices.speech as speechsdk
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class AzureSpeechTranscriber:
    def __init__(self, language_to_transcribe, output_folder="E:/thai_transcripts", max_retries=3, strings_to_remove_file="./txt_files/strings_to_remove.txt"):
        """
        Initializes the AzureSpeechTranscriber with the necessary configurations.

        :param language_to_transcribe: The language to transcribe.
        :param output_folder: The folder where the transcriptions will be saved.
        :param max_retries: The maximum number of retries for the transcription process.
        :param strings_to_remove_file: File containing a list of strings to be removed from the transcriptions.
        """
        self.subscription_key = os.getenv('AZURE_SPEECH_API_KEY')
        self.region = os.getenv('AZURE_SPEECH_REGION')
        self.language_to_transcribe = language_to_transcribe
        print(f"Azure Speech Service Initialised to transcribe {self.language_to_transcribe} language")
        self.output_folder = output_folder
        self.max_retries = max_retries

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)
        
        # Initialize strings to remove by reading from the provided file
        self.strings_to_remove = self.read_strings_to_remove(strings_to_remove_file)

    def read_strings_to_remove(self, strings_to_remove_file):
        """
        Reads strings to remove from a file, where each line in the file contains one string.

        :param strings_to_remove_file: The file containing strings to be removed.
        :return: A list of strings to be removed.
        """
        if not os.path.isfile(strings_to_remove_file):
            print(f"Warning: {strings_to_remove_file} does not exist. No strings will be removed.")
            return []
        
        with open(strings_to_remove_file, 'r', encoding='utf-8') as file:
            strings = [line.strip() for line in file.readlines() if line.strip()]
        
        return strings

    def create_transcript_filepath(self, wav_file_path):
        """
        Creates a file path for the transcript based on the WAV file path.

        :param wav_file_path: The path to the WAV file.
        :return: The output file path for the transcript.
        """
        # Extract the portion of the file path after "temp_audio_files/"
        relative_path = wav_file_path.split('temp_wav_files/', 1)[-1]
        # Generate a new filename with .txt extension
        cleaned_filename = relative_path.replace('/', '_').replace(':', '_').replace('.', '_').replace('\\', '_').replace('.wav', '.txt')
        
        return os.path.join(self.output_folder, cleaned_filename).replace('\\', '/')

    def remove_strings(self, text):
        """
        Removes pre-specified strings from the text.

        :param text: The text from which to remove strings.
        :return: The text with the specified strings removed.
        """
        for string in self.strings_to_remove:
            text = text.replace(string, '')
        return text

    def transcribe(self, wav_file_path):
        """
        Transcribes the content of a WAV file into text using Azure's speech service.

        :param wav_file_path: The path to the WAV file to be transcribed.
        :return: The path to the file where the transcription is saved.
        """
        speech_config = speechsdk.SpeechConfig(subscription=self.subscription_key, region=self.region)
        speech_config.speech_recognition_language = self.language_to_transcribe
        audio_config = speechsdk.audio.AudioConfig(filename=wav_file_path)
        recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        transcript_file_path = self.create_transcript_filepath(wav_file_path)
        print(f"Transcribing to: {transcript_file_path}")

        recognized_segments = 0
        eos_reached = False

        def recognized(evt):
            """
            Callback function for handling recognized speech segments.
            
            :param evt: Event containing the recognized speech result.
            """
            nonlocal recognized_segments
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                text = evt.result.text
                # print(f"Recognized: {text}")
                with open(transcript_file_path, 'a', encoding='utf-8') as file:
                    file.write(text + '\n')
                recognized_segments += 1
                # print(f"Segments recognized: {recognized_segments}")
            # elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            #     print("No speech could be recognized")

        def canceled(evt):
            """
            Callback function for handling recognition cancellation events.
            
            :param evt: Event containing the cancellation details.
            """
            nonlocal eos_reached
            # print(f"Recognition canceled: {evt.cancellation_details}")
            if evt.cancellation_details.reason == speechsdk.CancellationReason.EndOfStream:
                print("Reached end of stream with no errors.")
                eos_reached = True
            elif evt.cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {evt.cancellation_details.error_details}")

        recognizer.recognized.connect(recognized)
        recognizer.canceled.connect(canceled)

        retries = 0
        while retries < self.max_retries:
            try:
                recognizer.start_continuous_recognition_async().get()
                while not eos_reached:
                    time.sleep(0.5)  # Small sleep to yield control and prevent tight loop
                recognizer.stop_continuous_recognition_async().get()
                break
            except Exception as e:
                print(f"Error encountered: {e}")
                retries += 1
                print(f"Retrying... ({retries}/{self.max_retries})")
                time.sleep(2)  # Wait for a few seconds before retrying

        if recognized_segments == 0:
            raise RuntimeError("No segments recognized, but EndOfStream reached.")

        # Remove strings from the transcript file
        self.clean_transcript_file(transcript_file_path)

        return transcript_file_path

    def clean_transcript_file(self, transcript_file_path):
        """
        Reads the transcript file, removes specified strings, and writes the cleaned content back to the file.

        :param transcript_file_path: The path to the transcript file to be cleaned.
        """
        try:
            with open(transcript_file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            cleaned_content = self.remove_strings(content)

            with open(transcript_file_path, 'w', encoding='utf-8') as file:
                file.write(cleaned_content)

            # print(f"Cleaned transcript file: {transcript_file_path}")

        except Exception as e:
            print(f"Error cleaning transcript file {transcript_file_path}: {e}")