## Extracting the filepath after the base_dir

def create_audio_filename_cfa(ogg_file_path):
    relative_path = ogg_file_path.split('podcast/', 1)[-1]
    relative_path = relative_path.split('.')[0]
    cleaned_filename_without_extension = relative_path.replace('/', '_').replace(':', '_').replace('\\', '_')
    return cleaned_filename_without_extension

def create_audio_filename_duphonics(mp4_file_path):
    relative_path = mp4_file_path.split('presentation/', 1)[-1]
    relative_path = relative_path.split('.')[0]
    cleaned_filename_without_extension = relative_path.replace('/', '_').replace(':', '_').replace('\\', '_')
    return cleaned_filename_without_extension

def create_image_filename(svg_file_path):
    relative_path = svg_file_path.split('presentation/', 1)[-1]
    relative_path = relative_path.split('.')[0]
    cleaned_filename_without_extension = relative_path.replace('/', '_').replace(':', '_').replace('\\', '_')
    return cleaned_filename_without_extension