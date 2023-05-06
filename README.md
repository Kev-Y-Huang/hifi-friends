# HiFi-Friends: A Distributed Music Sharing System

## Description

This is our implementation of a distributed music sharing system as a final project for
CS 262: Introduction to Distributed Computing.

## Built on

We built a server and client using the `socket` and `threading` native Python libraries for our wire protocol implementation. 

## How to run the app

To run the server

```bash
cd src/ && python3 server.py
```

To run the client

```bash
cd src/ && python3 app.py
```

## How to run the tests

## Folder Structure
```
├── src                         # All of the source code is here
|   ├── __init__.py	            # Initializes application from config file
│   ├── client.py               # Contains the code to support the client
│   ├── app.py                  # Contains the code for Flask client
│   ├── server.py               # Contains the code for server
│   ├── wire_protocol.py        # Contains the code for defining the wire protocol
│   ├── machines.py             # Contains the code defining the machines and their IPs and ports
|   └── utils.py                # Defines common functions used by the application
├── static                      # Supporting assets for the client
│   ├── script.js               # Supporting JavaScript for the client
│   ├── sound.gif               # Gif
|   └── styles.css              # Supporting style file for the client
├── templates                   # Supporting templates for Flask app
|   └── index.html              # HTML files
├── .gitignore	
├── NOTEBOOK.md                 # Engineering notebook	
└── README.md                   # README
``` 
