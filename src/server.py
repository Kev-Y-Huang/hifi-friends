import math
import socket
import threading
import time
import wave

import pyaudio

host_name = socket.gethostname()
host_ip = 'localhost'#  socket.gethostbyname(host_name)
print(host_ip)
port = 9633

def audio_stream_UDP():

	BUFF_SIZE = 65536
	server_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
	server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)

	server_socket.bind((host_ip, (port)))
	CHUNK = 10*1024
	wf = wave.open("temp.wav")
	p = pyaudio.PyAudio()
	print('server listening at',(host_ip, (port)),wf.getframerate())
	stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
					channels=wf.getnchannels(),
					rate=wf.getframerate(),
					input=True,
					frames_per_buffer=CHUNK)

	data = None
	sample_rate = wf.getframerate()
	while True:
		msg,client_addr = server_socket.recvfrom(BUFF_SIZE)
		print('[GOT connection from]... ',client_addr,msg)
		DATA_SIZE = math.ceil(wf.getnframes()/CHUNK)
		DATA_SIZE = str(DATA_SIZE).encode()
		print('[Sending data size]...',wf.getnframes()/sample_rate)
		server_socket.sendto(DATA_SIZE,client_addr)
		cnt=0
		while True:
			
			data = wf.readframes(CHUNK)
			server_socket.sendto(data,client_addr)
			time.sleep(0.001) # Here you can adjust it according to how fast you want to send data keep it > 0
			print(cnt)
			if cnt >(wf.getnframes()/CHUNK):
				break
			cnt+=1

		break
	print('SENT...')            

t1 = threading.Thread(target=audio_stream_UDP, args=())
t1.start()