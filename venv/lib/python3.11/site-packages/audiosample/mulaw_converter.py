import numpy as np
from audiosample import AudioSample

def design_lowpass_filter(cutoff_hz: float, fs: float, numtaps: int=101, window='hamming') -> np.ndarray:
    """
    Create a windowed-sinc FIR filter for low-pass.
    
    cutoff_hz: cutoff frequency in Hz
    fs: sampling rate in Hz
    numtaps: number of FIR filter taps
    window: 'hamming' or 'hann' or 'blackman' etc. 
    """
    # Normalized cutoff (relative to Nyquist = fs/2)
    nyquist = fs / 2.0
    cutoff = cutoff_hz / nyquist  # between 0 and 1
    
    # Ideal sinc filter in time domain
    # We'll center it so "middle" is at (numtaps-1)/2
    n = np.arange(numtaps)
    center = (numtaps - 1) / 2.0

    # Avoid divide-by-zero with np.where or a small offset
    # sinc(x) = sin(pi*x)/(pi*x). In discrete-time, x = (n - center)*cutoff
    h = np.sinc(cutoff * (n - center))
    
    # Apply a window (e.g. Hamming)
    if window == 'hamming':
        w = np.hamming(numtaps)
    elif window == 'hann':
        w = np.hanning(numtaps)
    elif window == 'blackman':
        w = np.blackman(numtaps)
    else:
        raise ValueError("Unsupported window type.")
    
    h *= w
    
    # Normalize filter so its sum = 1.0 (unity gain at DC)
    h /= np.sum(h)
    
    return h

def downsample_using_fir(audio: np.ndarray, orig_sr: int, target_sr: int, numtaps: int=101, 
                        state: np.ndarray=None, flush: bool=False) -> tuple[np.ndarray, np.ndarray]:
    """
    Downsample from 48 kHz to 8 kHz using a basic FIR low-pass filter + decimation.
    Handles streaming input by maintaining filter state between calls.
    
    Args:
        audio: Input audio chunk
        orig_sr: Original sampling rate
        target_sr: Target sampling rate
        numtaps: Number of FIR filter taps
        state: Previous filter state (numtaps-1 samples)
        flush: If True, process remaining samples in state
        
    Returns:
        tuple of (downsampled_audio, new_state)
    """
    # 1) Design a low-pass filter for cutoff ~ 4 kHz
    fir = design_lowpass_filter(cutoff_hz=target_sr/2, fs=orig_sr, numtaps=numtaps, window='hamming')
    
    if state is None:
        # Pad with zeros to get remaining samples
        state = np.zeros(numtaps - 1)
    
    if flush:
        # Pad with zeros to get remaining samples
        audio = np.zeros(numtaps - 1)
    
    # 2) Convolve (filter) the input using filter state
    filtered = np.convolve(np.concatenate([state, audio]), fir, mode='valid')
    new_state = audio[-numtaps+1:]
    
    # 3) Decimate by picking samples at fractional intervals
    decimation_factor = orig_sr / target_sr
    output_length = int(len(filtered) / decimation_factor)
    sample_positions = np.arange(output_length) * decimation_factor
    sample_positions_int = sample_positions.astype(np.int32)
    
    # Linear interpolation between samples
    frac = sample_positions - sample_positions_int
    audio_target_sr = filtered[sample_positions_int] * (1 - frac) + \
                     filtered[np.minimum(sample_positions_int + 1, len(filtered)-1)] * frac

    return audio_target_sr, new_state


def mu_law_encode(audio: np.ndarray, mu: int = 255) -> np.ndarray:
    """
    Encode a float32/float64 signal in [-1,1] to 8-bit mu-law.
    Returns np.uint8 array in [0..255].
    """
    # 1) Ensure the signal is within -1..1. Clip if needed
    audio = np.clip(audio, -1.0, 1.0)

    # 2) Apply mu-law
    magnitude = np.log1p(mu * np.abs(audio)) / np.log1p(mu)
    signal = np.sign(audio) * magnitude  # in [-1,1]

    # 3) Convert to 0..255
    mu_law_8bit = ((signal + 1) * 127.5).astype(np.uint8)
    # or equivalently: np.floor((signal + 1) / 2 * 255) 
    # but 127.5 is exact half of 255, so either approach works
    
    return mu_law_8bit


if __name__ == "__main__":
    # 1) Create or load your 48 kHz signal -> audio_48k
    au = AudioSample("../tests/beep.wav")
    audio_48k = au.as_numpy()

    #repeat audio_48k 10 times
    audio_48k_10 = np.tile(audio_48k, (10, 1))
    audio_48k_10 = np.reshape(audio_48k_10, (1, -1)).squeeze()
    #write to file
    au = AudioSample.from_numpy(audio_48k_10, rate=48000)
    TARGET_SR = 22050
    audio_48k_10_to_8k,_ = downsample_using_fir(audio_48k_10, orig_sr=48000, target_sr=TARGET_SR, numtaps=101)

    # 2) Downsample from 48 kHz to 8 kHz
    audios = []
    state = None
    for i in range(0, 10):
        audio_8k, state = downsample_using_fir(audio_48k, orig_sr=48000, target_sr=TARGET_SR, numtaps=101, state=state)
        audios.append(audio_8k)

    tttt, _ = downsample_using_fir(None, orig_sr=48000, target_sr=TARGET_SR, numtaps=101, state=state, flush=True)
    print(tttt.shape)
    #concat
    audio_8k = np.concatenate(audios, axis=-1)
    print(audio_8k.shape, audio_48k_10_to_8k.shape)
    #compare
    assert np.all(audio_8k == audio_48k_10_to_8k)
    audio_8k_mulaw = mu_law_encode(audio_8k, mu=255)

    print("8 kHz shape:", audio_8k.shape)
    print("Mu-Law shape:", audio_8k_mulaw.shape)
    print("First 10 samples (mu-law 8-bit):", audio_8k_mulaw[:10])
    f = open("audio_8k_mulaw.wav", "wb")
    #write header
    #WAVE_HEADER_STRUCT = RIFF_HEADER_STRUCT + (JUST_WAVE_HEADER_STRUCT + CHUNK_HEADER_STRUCT + FORMAT_HEADER_CONTENT_STRUCT + FORMAT_HEADER_EX_STRUCT + DATA_HEADER_STRUCT).replace("<","")
    #FORMAT_HEADER_CONTENT_STRUCT = "HHIIHH"
    f.write(b'RIFF')
    total_length = 44 + audio_8k_mulaw.shape[-1]
    f.write(total_length.to_bytes(4, 'little'))
    f.write(b'WAVE')
    f.write(b'fmt ')
    f.write(b'\x10\x00\x00\x00')
    f.write(b'\x01\x00') # PCM
    f.write(b'\x01\x00') # 1 channel
    # 8000 Hz
    f.write(b'\x40\x1f\x00\x00') # 8000 Hz
    f.write(b'\x01\x00') # 16-bit
    f.write(b'\x00\x00\x00\x00') # block align
    f.write(b'\x08\x00') # 8-bit
    f.write(b'data')
    f.write(audio_8k_mulaw.tobytes())