
import io





def comprese_audio(audio, target_bitrate: str, duration: int) -> dict: 
    """
    Decrease track bitrate

    audio = track get by pydub
    target_bitrate = to what bitrate wanna compose audio 

    return track's chunks
    """
    buffer = io.BytesIO()

    audio.export(buffer, format="mp3", bitrate=target_bitrate)
    compresed_audio = buffer.getvalue()
    buffer.close()
    track_size = len(compresed_audio) / (1024 * 1024)
    

    # bitrate = (track_size / 8) / duration)

    track_data = {
        "audio_file": compresed_audio, 
        "audio_size": track_size
    }

    return track_data


