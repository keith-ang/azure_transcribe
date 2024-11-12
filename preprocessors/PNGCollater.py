import os
import shutil
from utils.util import create_image_filename

class PNGCollater:
    def __init__(self, output_directory="F:/duphonics_presentation_images"):
        self.output_directory = output_directory
        os.makedirs(self.output_directory, exist_ok=True)



    def create_image_filepath(self, png_file_path):
        cleaned_filename_without_extension = create_image_filename(png_file_path)
        cleaned_filename_full = cleaned_filename_without_extension + '.png'
        
        return os.path.join(self.output_directory, cleaned_filename_full).replace('\\', '/')
    
    def copy_png_image(self, png_file_path, transcript_directory):
        # Ensure the SVG file exists
        if not os.path.exists(png_file_path):
            raise FileNotFoundError(f"The SVG file {png_file_path} does not exist.")
        
        # Create the path for the output image file
        cleaned_filename_without_extension = create_image_filename(png_file_path)
        
        # Check if corresponding transcript already exists
        if f"{cleaned_filename_without_extension}.txt" in os.listdir(transcript_directory) or "slide" not in cleaned_filename_without_extension:
            return None  # Skip this file as it already has a transcript or it is not a slide

        output_path = self.create_image_filepath(png_file_path)

        # Copy image to image directory
        shutil.copy2(png_file_path, output_path)
        
        return output_path