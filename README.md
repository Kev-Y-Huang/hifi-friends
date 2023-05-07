# HiFi-Friends: A Distributed Music Sharing System

## Description

This is our implementation of a distributed music sharing system as a final project for
CS 262: Introduction to Distributed Computing.

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
cd python3 src/server-paxos.py -s 0 
cd python3 src/server-paxos.py -s 1
cd python3 src/server-paxos.py -s 2 
```

Connect the clients to the server. Modify the `HOST' variable of line 15 of `client-paxos.py` to be the IP address of the server.

```bash
cd python3 src/client-paxos.py
```

After starting the client and connecting to the server successfully, you will be prompted to input an operation code. Operation in the client can then be used to queue, play, pause, and skips songs as the following:

```
Enter Operation Code:
1 -> Upload a song to the server. You will be prompted the file name
2 -> Queue a song to the server. You will be prompted the file name. The song will automatically start playing after the current song finishes (if no song is playing, it will start playing immediately)
3 -> List the songs in the server
4 -> List the current queue
5 -> Pause the current song
6 -> Play the current song
7 -> Skip the current song
```


## How to run the tests

Navigate into the `src` directory and run the following command

```bash
python3 -m unittest tests
```

All tests should pass.

## Folder Structure
```
├── src        # All of the source code is here
|   ├── __init__.py	            # Initializes application from config file
│   ├── client.py               # Code to support the client (deprecated)
│   ├── server.py               # Code for server (deprecated)
│   ├── app.py                  # Code for Flask client (deprecated)
│   ├── client-paxos.py         # Code to support the client (deprecated)
│   ├── server-paxos.py         # Code for server (deprecated)
│   ├── paxos.py                # Code supporting the Paxos algorithm
│   ├── tests.py                # Contains unit tests
│   ├── wire_protocol.py        # Code for defining the wire protocol
│   ├── machines.py             # Code defining the machines and their IPs and ports
|   └── utils.py                # Defines common functions used by the application
├── static     # Supporting assets for the client
│   ├── script.js               # Supporting JavaScript for the client
│   ├── sound.gif               
|   └── styles.css              # Supporting style file for the client
├── templates  # Supporting templates for Flask app (deprecated)
|   └── index.html              # HTML files
├── .gitignore	
├── NOTEBOOK.md                 # Engineering notebook	
└── README.md                   # README
``` 
