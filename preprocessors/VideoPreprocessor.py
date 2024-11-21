import subprocess
import os
from utils.util import create_audio_filename_cfa, create_audio_filename_duphonics
from moviepy.editor import VideoFileClip


class VideoPreprocessor:
    def __init__(self, temp_audio_path="E:/temp_audio_files"):
        self.temp_audio_path = temp_audio_path
        os.makedirs(self.temp_audio_path, exist_ok=True)

        
    def create_audio_filepath_cfa(self, ogg_file_path):
        cleaned_filename_without_extension = create_audio_filename_cfa(ogg_file_path)
        cleaned_filename_full = cleaned_filename_without_extension + '.wav'
        return os.path.join(self.temp_audio_path, cleaned_filename_full).replace('\\', '/')
    
    def create_audio_filepath_duphonics(self, mp4_file_path):
        cleaned_filename_without_extension = create_audio_filename_duphonics(mp4_file_path)
        cleaned_filename_full = cleaned_filename_without_extension + '.wav'
        return os.path.join(self.temp_audio_path, cleaned_filename_full).replace('\\', '/')
    
    def convert_mp4_or_webm_to_wav(self, input_path, transcript_directory):
        # Ensure the MP4/WEBM file exists
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"The MP4/webm file {input_path} does not exist.")
        
        # Ensure the input file has the correct extension
        if not input_path.lower().endswith('.mp4') and not input_path.lower().endswith('.webm'):
            raise ValueError("Currently, only .mp4/.webm format is supported for conversion to .wav")
        
        # Create the path for the output WAV file
        cleaned_filename_without_extension = create_audio_filename_duphonics(input_path)
        
        # Skip this file as it already has a transcript
        if f"{cleaned_filename_without_extension}.txt" in os.listdir(transcript_directory):
            return None
        
        if "deskshare" in input_path:
            return None
        
        wav_file_path = self.create_audio_filepath_duphonics(input_path)

        if wav_file_path in self.temp_audio_path: 
            return wav_file_path

        try:
            # Load the video file
            video_clip = VideoFileClip(input_path)

            # Extract audio from the video and write it to a .wav file
            audio_clip = video_clip.audio
            audio_clip.write_audiofile(wav_file_path, codec='pcm_s16le')
            

            # Close the video and audio clip to release resources
            video_clip.close()
            audio_clip.close()
        except Exception as e:
            print(f"Failed to convert .mp4/.webm to .wav with error: {e}")

        return wav_file_path

    def convert_ogg_to_wav(self, input_path, transcript_directory):
        # Ensure the OGG file exists
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"The OGG file {input_path} does not exist.")
        
        # Ensure the input file has the correct extension
        if not input_path.lower().endswith('.ogg'):
            raise ValueError("Currently, only .ogg format is supported for conversion to .wav")
        
        # Create the path for the output WAV file
        cleaned_filename_without_extension = create_audio_filename_cfa(input_path)
        
        # Check if corresponding transcript already exists
        if f"{cleaned_filename_without_extension}.txt" in os.listdir(transcript_directory):
            return None  # Skip this file as it already has a transcript

        wav_file_path = self.create_audio_filepath_cfa(input_path)
        
        try:
            # Run the ffmpeg command to convert OGG to WAV
            result = subprocess.run(
                ["ffmpeg", "-i", input_path, wav_file_path],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error occurred while converting {input_path} to WAV: {e.stderr.decode('utf-8')}")


        return wav_file_path