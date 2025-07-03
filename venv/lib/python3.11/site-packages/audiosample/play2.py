import io
from contextlib import redirect_stderr
from audiosample import AudioSample
import ctypes
import time
import ctypes
from ctypes import c_int, c_double, c_char_p, c_void_p, c_uint, c_ulong, POINTER, byref
import math
import struct

def play2(self):
    # Load the PortAudio library (path may vary)
    # On Linux/macOS typically:
    portaudio = ctypes.cdll.LoadLibrary("libportaudio.so")  
    # On macOS (Homebrew):
    # portaudio = ctypes.cdll.LoadLibrary("/usr/local/lib/libportaudio.dylib")
    # On Windows:
    # portaudio = ctypes.cdll.LoadLibrary("portaudio_x64.dll")

    # Define return and argument types for functions we will use
    portaudio.Pa_Initialize.argtypes = []
    portaudio.Pa_Initialize.restype = c_int

    portaudio.Pa_Terminate.argtypes = []
    portaudio.Pa_Terminate.restype = c_int

    # Define a PaStream as a void pointer
    PaStream = c_void_p

    # We'll need to describe the PaStreamParameters struct
    class PaStreamParameters(ctypes.Structure):
        _fields_ = [
            ("device", c_int),
            ("channelCount", c_int),
            ("sampleFormat", c_ulong),
            ("suggestedLatency", c_double),
            ("hostApiSpecificStreamInfo", c_void_p),
        ]

    # Constants from portaudio.h
    paFloat32 = 0x00000001
    paNoDevice = -1
    paNoFlag = 0

    portaudio.Pa_GetDefaultOutputDevice.argtypes = []
    portaudio.Pa_GetDefaultOutputDevice.restype = c_int

    portaudio.Pa_OpenStream.argtypes = [
        POINTER(PaStream),            # stream
        c_void_p,                     # inputParameters
        POINTER(PaStreamParameters),  # outputParameters
        c_double,                     # sampleRate
        c_uint,                       # framesPerBuffer
        c_ulong,                      # streamFlags
        c_void_p,                     # streamCallback
        c_void_p                      # userData
    ]
    portaudio.Pa_OpenStream.restype = c_int

    portaudio.Pa_StartStream.argtypes = [PaStream]
    portaudio.Pa_StartStream.restype = c_int

    portaudio.Pa_WriteStream.argtypes = [PaStream, c_void_p, c_ulong]
    portaudio.Pa_WriteStream.restype = c_int

    portaudio.Pa_StopStream.argtypes = [PaStream]
    portaudio.Pa_StopStream.restype = c_int

    portaudio.Pa_CloseStream.argtypes = [PaStream]
    portaudio.Pa_CloseStream.restype = c_int

    # Initialize PortAudio
    err = portaudio.Pa_Initialize()
    if err != 0:
        raise OSError("Pa_Initialize failed")

    # Get default output device
    device_index = portaudio.Pa_GetDefaultOutputDevice()
    if device_index == paNoDevice:
        raise OSError("No default output device found")

    # Set up output parameters
    output_params = PaStreamParameters()
    output_params.device = device_index
    output_params.channelCount = 2  # stereo
    output_params.sampleFormat = paFloat32  # 32-bit float
    output_params.suggestedLatency = 0.1  # a guess; query device info for a better value
    output_params.hostApiSpecificStreamInfo = None

    sample_rate = 48000
    frames_per_buffer = 256 

    stream = PaStream()

    # Open the stream in blocking mode (no callback)
    err = portaudio.Pa_OpenStream(
        byref(stream),
        None,  # no input
        byref(output_params),
        c_double(sample_rate),
        frames_per_buffer,
        paNoFlag,
        None,  # no callback
        None
    )
    if err != 0:
        raise OSError("Pa_OpenStream failed")


    # Generate a simple tone (sine wave) for demonstration

    duration = 2.0
    frequency = 440.0
    num_samples = int(sample_rate * duration)

    buffer = []
    for i in range(num_samples):
        sample_value = math.sin(2.0 * math.pi * frequency * (i / sample_rate))
        # Stereo: same sample on both channels
        buffer.append(sample_value)
        buffer.append(sample_value)

    # Pack the buffer into bytes
    byte_data = struct.pack('f'*len(buffer), *buffer)

    # Write data in chunks
    chunk_size = frames_per_buffer * 2  # frames_per_buffer * 2 channels

    # Start the stream
    err = portaudio.Pa_StartStream(stream)
    if err != 0:
        raise OSError("Pa_StartStream failed")
    # cdata = ctypes.create_string_buffer(b'\x00'*8192)
    # err = portaudio.Pa_WriteStream(stream, cdata, frames_per_buffer)
    # if err != 0:
    #     raise OSError("Pa_WriteStream failed")
    # for i in range(0, len(buffer), chunk_size):
    #     chunk = byte_data[i*4:(i+chunk_size)*4]  # *4 because 4 bytes per float
    #     cdata = ctypes.create_string_buffer(chunk)
    #     err = portaudio.Pa_WriteStream(stream, cdata, frames_per_buffer)
    #     if err != 0:
    #         raise OSError("Pa_WriteStream failed")
    #     # time.sleep(chunk_size / (sample_rate) / 100)
    # return
    if self.f and not self._data and not self.iterable_input_buffer:
        self.read()
    try:
        if self.iterable_input_buffer:
            sub_chunk_size = chunk_size*4
            for chunk in self.as_data_stream(force_out_format='f32le'):
                data_bytes = chunk[i:(i + sub_chunk_size)]
                cdata = ctypes.create_string_buffer(data_bytes)
                current_buffer_frames = len(data_bytes) // 4
                err = portaudio.Pa_WriteStream(stream, cdata, current_buffer_frames)
                if err != 0:
                    raise OSError("Pa_WriteStream failed")
        else:
            data = self.as_data(force_out_format='f32le')
            open("test.f32le", "wb").write(data)
            for i in range(0, len(data)//4, chunk_size):
                data_bytes = data[i*4:(i + chunk_size)*4]
                print(f"{len(data_bytes)=}")
                cdata = ctypes.create_string_buffer(data_bytes)
                current_buffer_frames = len(data_bytes) // 4
                err = portaudio.Pa_WriteStream(stream, cdata, current_buffer_frames)
                print(f"{err=}")
                if err != 0:
                    raise OSError("Pa_WriteStream failed")
                time.sleep(0.005)
    except StopIteration:
        pass
    finally:        
        # Stop and close the stream
        portaudio.Pa_StopStream(stream)
        portaudio.Pa_CloseStream(stream)

        # Terminate PortAudio
        portaudio.Pa_Terminate()

AudioSample.register_plugin('play2', play2)