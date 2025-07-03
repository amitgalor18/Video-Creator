import numpy as np
from scipy.signal import lfilter

class Downsampler:
    @staticmethod
    def _design_lowpass_filter(cutoff_hz: float, fs: float, numtaps: int = 101, window='hamming') -> np.ndarray:
        nyquist = fs / 2.0
        cutoff = cutoff_hz / nyquist
        n = np.arange(numtaps)
        center = (numtaps - 1) / 2.0
        h = np.sinc(cutoff * (n - center))
        
        if window == 'hamming':
            w = np.hamming(numtaps)
        elif window == 'hann':
            w = np.hanning(numtaps)
        elif window == 'blackman':
            w = np.blackman(numtaps)
        else:
            raise ValueError("Unsupported window type.")
        h *= w
        h /= np.sum(h)
        # (For debugging; you can remove it in production)
        print("INIT")
        return h

    def __init__(self, orig_sr: int, target_sr: int, numtaps: int = 101, window='hamming'):
        self.orig_sr = orig_sr
        self.target_sr = target_sr
        self.decimation_factor = orig_sr / target_sr  # may be non-integer
        self.numtaps = numtaps

        # Design the FIR filter once.
        self.fir = self._design_lowpass_filter(cutoff_hz=target_sr/2, fs=orig_sr, numtaps=numtaps, window=window)
        # For a FIR filter, the “state” is just the last numtaps-1 samples.
        self.zi = np.zeros(len(self.fir) - 1)
        
    def encode(self, audio_chunk: np.ndarray) -> np.ndarray:
        """
        Process one audio_chunk (or a padded chunk for flushing) using a stateful FIR filter.
        For integer decimation factors the code simply takes every Nth filtered sample;
        for non-integer factors it uses linear interpolation.
        """
        # Ensure audio_chunk is 1D
        if audio_chunk is None:
            self.zi = np.zeros(len(self.fir) - 1)
            return np.array([])
        if audio_chunk.ndim != 1:
            raise ValueError("audio must be 1D")
        
        # Process the chunk with lfilter (which uses the previous state).
        # Note that since our filter is FIR, we can “stream” it easily.
        filtered, self.zi = lfilter(self.fir, 1, audio_chunk, zi=self.zi)
        
        # If the decimation factor is integer, just take every Nth sample.
        if np.isclose(self.decimation_factor, int(self.decimation_factor)):
            decim = int(self.decimation_factor)
            # For many applications your chunks are long enough so that:
            return filtered[::decim]
        else:
            # For non-integer decimation factors, compute the indices where output is desired.
            N = len(filtered)
            # Create the (non-integer) sample positions.
            indices = np.arange(0, N, self.decimation_factor)
            indices_int = indices.astype(np.int32)
            frac = indices - indices_int
            # Avoid indexing past the end:
            indices_int = np.minimum(indices_int, N - 2)
            output = filtered[indices_int] * (1 - frac) + filtered[indices_int + 1] * frac
            return output
