# HiFi-Friends: A Distributed Music Sharing System

## Description

This is our implementation of a distributed music sharing system as a final project for
CS 262: Introduction to Distributed Computing.

## Video Demo

Replication and persistence using Paxos demo

https://user-images.githubusercontent.com/54912191/236712655-9f608eac-464d-4808-b2f6-f59ff9fab368.mp4


Synced Audio Play/Pause/Skip demo

https://user-images.githubusercontent.com/54912191/236711952-52220a72-6ea2-48ef-bb17-1e99e187dfe3.mp4


## Built on

We built a server and client using the `socket` and `threading` native Python libraries for our wire protocol implementation. 

## How to run the app

HiFi Friends can be run cross-platform on multiple machines. However, on MacOS, before attempting to start the service, run

```bash
sudo sysctl -w net.inet.udp.maxdgram=65535
``` 

in order to change the size of the messages that can be transmitted through UDP ports. To start the service, ensure you are in the root directory, and have created the following subdirectories:

```bash
server_0_files
server_1_files
server_2_files
```

Then, run the servers

```bash
python3 src/server_paxos.py -s 0 
python3 src/server_paxos.py -s 1
python3 src/server_paxos.py -s 2 
```

Connect the clients to the server. Modify the `HOST` variable of line 15 of `client-paxos.py` to be the IP address of the server, and update the ports to correspond with the respective machine in `machines.py`.

```bash
python3 src/client_paxos.py
```

After starting the client and connecting to the server successfully, you will be prompted to input an operation code. The client can used these operations to queue, play, pause, and skip songs as specified below:

```
Enter Operation Code:
1 -> Upload a song to the server. You will be prompted the file name
2 -> Queue a song to the server. You will be prompted the file name. The song will automatically start playing after the current song finishes (if no song is playing, it will start playing immediately)
3 -> List the songs available in the server. These are the songs that can be queued
4 -> List the current queue
5 -> Pause the current song
6 -> Play the current song
7 -> Skip the current song
```
Note that when a song is queued, paused, played, or skipped, this affects all clients; i.e., all clients are listening to a synchronized/shared audio stream.


## How to run the tests

Navigate into the `src` directory and run the following command

```bash
python3 -m unittest tests
```

All tests should pass.

## Folder Structure
```
├── src                         # All of the source code is here
|   ├── __init__.py             # Initializes application from config file
|   ├── deprecated              # Deprecated Files
|   |   ├── static     
|   |   │   ├── script.js       # Supporting JavaScript for the client (deprecated)
|   |   │   ├── sound.gif       
|   |   |   └── styles.css      # Supporting style file for the client (deprecated)
|   |   ├── templates           # Supporting templates for Flask app (deprecated)
|   |   |   └── index.html      # HTML files
|   |   ├── music_service.py    # Code for the music service (deprecated)          
|   |   ├── app.py              # Code for Flask client (deprecated)
|   |   ├── client.py           # Code to support the client (deprecated)
|   |   └── server.py           # Code for server (deprecated)
|   ├── client_paxos.py         # Code for the client
|   ├── server_paxos.py         # Code for the server
│   ├── paxos.py                # Code supporting the Paxos algorithm
│   ├── tests.py                # Contains unit tests
│   ├── wire_protocol.py        # Code for defining the wire protocol
│   ├── machines.py             # Code defining the machines and their IPs and ports
|   └── utils.py                # Defines common functions used by the application
├── .gitignore	
├── NOTEBOOK.md                 # Engineering notebook	
└── README.md                   # README
``` 
