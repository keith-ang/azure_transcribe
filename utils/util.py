## Extracting the filepath after the base_dir

# specific util functions to remove certains parts of the filepath 

def create_audio_filename_cfa(ogg_file_path):
    """
    Creates a cleaned filename for CFA audio files by extracting part of the path and removing problematic characters.

    :param ogg_file_path: The original path of the OGG file.
    :return: The cleaned filename without extension.
    """
    relative_path = ogg_file_path.split('podcast/', 1)[-1]
    relative_path = relative_path.split('.')[0]
    cleaned_filename_without_extension = relative_path.replace('/', '_').replace(':', '_').replace('\\', '_')
    return cleaned_filename_without_extension

def create_audio_filename_duphonics(mp4_file_path):
    """
    Creates a cleaned filename for Duphonics audio files by extracting part of the path and removing problematic characters.

    :param mp4_file_path: The original path of the MP4 file.
    :return: The cleaned filename without extension.
    """
    relative_path = mp4_file_path.split('presentation/', 1)[-1]
    relative_path = relative_path.split('.')[0]
    cleaned_filename_without_extension = relative_path.replace('/', '_').replace(':', '_').replace('\\', '_')
    return cleaned_filename_without_extension

def create_image_filename(svg_file_path):
    """
    Creates a cleaned filename for image files by extracting part of the path and removing problematic characters.

    :param svg_file_path: The original path of the SVG file.
    :return: The cleaned filename without extension.
    """
    relative_path = svg_file_path.split('presentation/', 1)[-1]
    relative_path = relative_path.split('.')[0]
    cleaned_filename_without_extension = relative_path.replace('/', '_').replace(':', '_').replace('\\', '_')
    return cleaned_filename_without_extension