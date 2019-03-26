
import logging
import subprocess
import threading
from threading import Timer
from pydub import AudioSegment

from multiprocessing.connection import Client
from pydub.silence import split_on_silence
from timeit import default_timer as timer
from pathlib import Path
import os
import time 
import signal

SPLIT_INTERVAL = 10
BUFFER = 3

logger = logging.getLogger("SpeechToText")


class ExtractAudio(threading.Thread):

    def __init__(self, audio_path,audio_length,start_point,buffer=3):
        threading.Thread.__init__(self)
        Path("/tmp/stt/").mkdir(exist_ok=True)
       
        self.start_point  = start_point
        self.audio_path = audio_path
        self.audio_length = audio_length
        self.buffer = buffer

        # self.audio_length = int(float(subprocess.run(["ffprobe" ,"-i" , self.audio_path ,
        #                                 "-show_entries","format=duration", "-v" ,"quiet" ,"-of" ,'csv=p=0'],
        #                                 stdout=subprocess.PIPE).stdout.decode('utf-8').strip()))

    
    def extract_audio (self):
        logger.debug("Starting Extarct")
        start_time  = ts = timer()
        
        intermediate_name = self.start_point

        end_point = min(self.start_point + SPLIT_INTERVAL * self.buffer ,self.audio_length-SPLIT_INTERVAL)

        for i in range(self.start_point, end_point, SPLIT_INTERVAL):
            subprocess.run(["ffmpeg","-nostats", "-loglevel", "0" 
                            ,"-ss",str(i), "-i" , self.audio_path 
                            ,"-t", str(SPLIT_INTERVAL) 
                            ,"-acodec", "pcm_s16le", "-ar" , "16000"
                            , "-ac" ,"1" ,#'-af', 'highpass=f=200, lowpass=f=800',
                            "-vn" ,"/tmp/stt/" + str(i)+".wav", "-y"])
            now = timer()
            logger.debug("Chunk " +  str(intermediate_name)+" in {}s ".format(  now -ts))
            ts = now
            
            intermediate_name+=1
        
        logger.debug("Finished Extarcting  in {:.3}s ".format(timer() - start_time))
    

    def run(self):
        
        self.extract_audio()





class SyncDaemon(object):
    def __init__(self, interval,audio_path ,media_player , sub_box, *args, **kwargs):
        self._timer     = None
        self.media_player = media_player
        self.interval   = interval
        self.audio_path = audio_path
        self.audio_length = int(float(subprocess.run(["ffprobe" ,"-i" , self.audio_path ,
                                        "-show_entries","format=duration", "-v" ,"quiet" ,"-of" ,'csv=p=0'],
                                        stdout=subprocess.PIPE).stdout.decode('utf-8').strip()))
        self.subs_box = sub_box
        self.extracted_chunks = set({})
        self.subs_text  = {}
        
        signal.signal(signal.SIGXFSZ, self.receive_text)
        address = ('localhost', 6001)     # family is deduced to be 'AF_INET'
        self.conn   = Client(address)

        
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()


    def receive_text(self, *args):
        msg = self.conn.recv()
        print(msg)

    def fill_buffers(self, start):
        buffer_length = BUFFER*SPLIT_INTERVAL + start
        buff = 3
        for i in range(start, buffer_length, SPLIT_INTERVAL):
            if i not in self.extracted_chunks:
                ExtractAudio(self.audio_path,self.audio_length, i, buff).start()
                break            
            buff -=1

    def set_subtitles(self,rounded):
        
        if rounded not in self.subs_text:
            self.subs_box.setText("<NA>")
            return
        
            self.subs_box.setText(self.subs_text[rounded])


    def monitor(self):
        timestamp = int(self.media_player.get_position())
        rounded = timestamp - (timestamp % SPLIT_INTERVAL)

        if rounded not in self.extracted_chunks:
            ExtractAudio(self.audio_path,self.audio_length, rounded).start()

        self.set_subtitles(rounded)

        self.fill_buffers(rounded) 
    



    def _run(self):
        self.is_running = False
        self.start()
        self.monitor(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False
    
    def interrupt(self):
        self.stop()




if __name__ == "__main__":
    ExtractAudio(["/home/aditya/Downloads/indian.mp4"]).start()