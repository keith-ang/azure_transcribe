import os

class MemoryManager:
    def __init__(self):
        pass

    def del_temp_audio(self, temp_audio_filepath):
        removed = False
        try:
            if os.path.exists(temp_audio_filepath):
                os.remove(temp_audio_filepath)
                removed = True
        except OSError as e:
            print(f"Error: {e.strerror}. Could not delete file {temp_audio_filepath}.")

        return removed