import sys 
import math
import numpy as np
import pyaudio
import aubio
import time
import copy

from multiprocessing import Process, Manager, Queue

import note_helper


def list_audio_devices():
    pA = pyaudio.PyAudio()

    result = []

    info = pA.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (pA.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            result.append((pA.get_device_info_by_host_api_device_index(0, i).get('name'), i))

    return result


def tracking_process(sample_rate,
                     hop_size,
                     buffer_size,
                     device_index,
                     pitch_detection_method,
                     onset_detection_method,
                     silence_threshold,
                     analysis_results,
                     analysis_window_len,
                     stop):

    pA = pyaudio.PyAudio()

    # Open microphone stream
    mic = pA.open(format=pyaudio.paFloat32, 
                  channels=1,
                  rate=sample_rate, 
                  input=True,
                  frames_per_buffer=hop_size,
                  input_device_index=device_index)

    # Initialize pitch detection
    pDetection = aubio.pitch(method=pitch_detection_method, 
                                buf_size=buffer_size,
                                hop_size=hop_size, 
                                samplerate=sample_rate)

    if onset_detection_method is not None:
        oDetection = aubio.onset(method=onset_detection_method, 
                                buf_size=buffer_size,
                                hop_size=hop_size, 
                                samplerate=sample_rate)    

    # Set to Hz
    pDetection.set_unit("Hz")
    
    # Amplitudes lower than that will be considered silence (in dB)
    pDetection.set_silence(silence_threshold)

    while not stop.is_set():
        data = mic.read(hop_size, exception_on_overflow=False)

        samples = np.fromstring(data, dtype=aubio.float_type)

        pitch = pDetection(samples)[0]
        if onset_detection_method is not None:
            onset = oDetection(samples)
        else:
            onset = 0.0
        confidence = pDetection.get_confidence()

        # Compute volume
        volume = 10 * np.log10(np.sum(samples**2)/len(samples))

        analysis_results.append((time.time(), pitch, volume, confidence, onset))

        if (len(analysis_results) > analysis_window_len):
            analysis_results.pop(0)


class PitchTracker():

    def __init__(self, device_index, 
                       buffer_size=4096, 
                       sample_rate=44100,        
                       analysis_window=30,        # in seconds
                       filter_window=0.2,          # in seconds
                       silence_threshold=-50,     # in dB
                       lowest_frequency=65.4064): # in Hz

        self.device_index = device_index
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.silence_threshold = silence_threshold

        # Pitch detection parameters
        self.pitch_detection_method = "default"
        self.onset_detection_method = None
        self.hop_size = int(math.ceil((1 / lowest_frequency) * sample_rate))

        if (self.hop_size > self.buffer_size):
            raise ValueError("Hop size must be smaller than buffer size!")

        # Analysis and filter windows
        denom = (self.hop_size / self.sample_rate)
        self.analysis_window_len = int(math.ceil(analysis_window / denom))
        self.filter_window_len = int(math.ceil(filter_window / denom))

        if (self.filter_window_len > self.analysis_window_len):
            raise ValueError("Filter window length must be smaller than analysis length!")        

        self.manager = Manager()     


    def start_tracking(self):
        self.analysis_results = self.manager.list()    
        self.stop = self.manager.Event()   
        
        self.background_process = Process(target=tracking_process, args=(self.sample_rate,
                                                                         self.hop_size,
                                                                         self.buffer_size,
                                                                         self.device_index,
                                                                         self.pitch_detection_method,
                                                                         self.onset_detection_method,
                                                                         self.silence_threshold,
                                                                         self.analysis_results, 
                                                                         self.analysis_window_len,
                                                                         self.stop))             
        self.background_process.start()       


    def stop_tracking(self):
        self.stop.set()
        self.background_process.join()

    
    def get_analysis_results(self):
        # Perform filtering on the signal
        if (self.filter_window_len > 0) and (len(self.analysis_results) >= self.filter_window_len):
            timestamps, pitches, volumes, confidences, onsets = list(map(list, zip(*self.analysis_results)))

            filtered_pitches = copy.copy(pitches)

            MAX_FACTOR = 1.5
            for i in range((self.filter_window_len), (len(pitches) - self.filter_window_len)):
                reference = pitches[(i - self.filter_window_len):(i + self.filter_window_len)]

                median = np.median(reference)

                if pitches[i] < median/MAX_FACTOR or pitches[i] > median * MAX_FACTOR:
                    filtered_pitches[i] = median

            filtered_analysis_results = list(zip(timestamps, filtered_pitches, volumes, confidences, onsets))
            
            return filtered_analysis_results
        else:
            return self.analysis_results


    def change_device(self, device_index):
        self.stop_tracking()
        self.device_index = device_index
        self.start_tracking()


    def set_silence(self, silence_threshold):
        self.stop_tracking()
        self.silence_threshold = silence_threshold
        self.start_tracking()