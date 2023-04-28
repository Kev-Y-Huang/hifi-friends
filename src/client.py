import queue
import socket
import threading
import time
import sys

import pyaudio

host_name = socket.gethostname()
host_ip = socket.gethostbyname(host_name)
print(host_ip)
port = 1539


def audio_stream_UDP():
	try:
		BUFF_SIZE = 65536
		client_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
		client_socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,BUFF_SIZE)
		p = pyaudio.PyAudio()
		CHUNK = 10*1024
		stream = p.open(format=p.get_format_from_width(2),
						channels=2,
						rate=48000,
						output=True,
						frames_per_buffer=CHUNK)
						
		# create socket
		message = b'Hello'
		client_socket.sendto(message,(host_ip,port))
		DATA_SIZE,_= client_socket.recvfrom(BUFF_SIZE)
		DATA_SIZE = int(DATA_SIZE.decode())
		q = queue.Queue(maxsize=DATA_SIZE)
		cnt=0
		def getAudioData():
			while True:
				frame,_= client_socket.recvfrom(BUFF_SIZE)
				q.put(frame)
				print('[Queue size while loading]...',q.qsize())
					
		t1 = threading.Thread(target=getAudioData, args=())
		t1.start()
		time.sleep(5)
		DURATION = DATA_SIZE*CHUNK/48000
		print('[Now Playing]... Data',DATA_SIZE,'[Audio Time]:',DURATION ,'seconds')
		while True:
			frame = q.get()
			stream.write(frame)
			print('[Queue size while playing]...',q.qsize(),'[Time remaining...]',round(DURATION),'seconds')
			DURATION-=CHUNK/48000
			if q.empty():
				break
	except:
		client_socket.close()
		print('Audio closed')
		sys.exit(1)



t1 = threading.Thread(target=audio_stream_UDP, args=())
t1.start()


