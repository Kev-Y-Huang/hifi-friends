# **LOG**

## **5/6**

Tasks done

* Combining in Paxos for our replication and fault tolerance
    * Combined Paxos protocol with existing server code
    * Combined replication for file upload
    * Combined fault tolerance for server failure
    
TODOs

Problems/Questions:

* 

Resources:

## **5/5**

* Synchonized fo playback across clients
    * Playback gets unsynchronized when clients call play/pause/skip
    * Added queue to keep track of song frames on the server
        * When the songs are paused, the queues of each of the clients sync up if they are not at the same place
* Work on Paxos implementation
TODOs
* Combine Paxos implementation with existing server code
## **5/2**

How do we implement synchronization across multiple clients using a centralized server?


* Every certain amount of time (maybe every half second or second in internal clock time), have all clients share their current timestamps and get back current agreed upon time

* Connect to UI
    * Use flask routes to connect to UI and call on existing client code

## **4/27**

Tasks done

* Client/System communication
    * Finished audio file upload from client to server
    * Finished audio streaming directly from server to client
    * Combined both into centralized client and server files
    * Tested concurrent upload and streaming
* Front end
    * Implemented flask app
* Paxos/replication

TODOs

Problems/Questions:

* 

Resources:


* [Audio livestreaming with flask and pyaudio](https://stackoverflow.com/questions/51079338/audio-livestreaming-with-python-flask)
* 


## **4/26**

Distributed Streaming Service

* Clients connecting to server
    * Able to Upload Music - Ashley
        * TCP protocol
    * Able to Stream Music - Kevin
        * UDP protocol
    * Each client should be able to queue a song and view current queue
    * Clients should be synchronized on the playback of the current song
        * Leader server broadcasts a stream to all clients
    * Heartbeat process
        * Every &lt;X> ms, the client sends the timestamp it is currently at to the server
        * The server has keeps track of the current timestamp (whichever client is furthest ahead)
* Server replication
    * Leader election through Paxos - Patrick
    * Save audio files to directory (either as mp4 or bytes)
* Frontend
    * [https://stackoverflow.com/questions/47106364/stream-audio-from-pyaudio-with-flask-to-html5](https://stackoverflow.com/questions/47106364/stream-audio-from-pyaudio-with-flask-to-html5)
    * Every client runs the flask app
    * It has upload button, playback interface
        * Clients are not able to skip to the middle of song/delete songs (for now)

Tasks done



* Brainstorming
    * Distributed audio file storage
    * Replication
    * Paxos consensus protocol
    * Streaming audio from the server
    * Shared audio listening (everyone can control stream)
    * Frontend

TODOs
1. Commenting
2. Documentation
3. Diagramming
4. Coding
5. The Project

Problems/Questions:
* 

Resources:
* [Paxos Overview](https://martinfowler.com/articles/patterns-of-distributed-systems/paxos.html)
* [Distributed Music Player](https://www.scs.stanford.edu/14au-cs244b/labs/projects/fun_with_chords.pdf), [https://github.com/markulrich/musicbeacon/](https://github.com/markulrich/musicbeacon/) 
* [https://www.scs.stanford.edu/14au-cs244b/labs/projects/clintr-cs244b-final-proj.pdf](https://www.scs.stanford.edu/14au-cs244b/labs/projects/clintr-cs244b-final-proj.pdf) `
* File upload/download
    * [Grpc Implementation](https://betterprogramming.pub/grpc-file-upload-and-download-in-python-910cc645bcf0)
* Audio Streaming
    * [Socket Implementation using UDP](https://pyshine.com/How-to-send-audio-from-PyAudio-over-socket/)

# **TODOs**
## Bugs

- [x] Client dropping crashes server
- [x] Upload existing file bug
## Need Before Paper

- [x] Implement Paxos Protocol
- [x] Unit tests
- [x] Experiments/analysis?
- [x] The paper
- [x] Clean up eng notebook
- [x] README
    - [x] sudo sysctl -w net.inet.udp.maxdgram=65535

## Need Before Demo

- [x] Can’t queue files that haven’t been fully uploaded (in progress)
- [x] Implement Audio File Transfer
- [x] Error handling for incorrect file name
- [x] Basic replication - Patrick
    - [x] Change server_files/ to be server_files_{port}/
- [x] Frontend without progress bar - Alex
    - [x] Listing songs from actual server
    - [x] Listing songs in queue from actual server
    - [x] Indicator for when something is playing
    - [x] Current song that is playing
    - [x] Drop down for adding a song to queue
    - [x] Make sure that the songs can actually play through flask
    - [x] Make upload actually work
- [x] Determine if song has finished - Kevin
* Interesting details:
    * Now, instead of sending audio all at once, even if a different song is still playing, we wait to start sending chunks once the last song has finished playing
    * We check if the last song has finished playing by checking if there are no more chunks in the queue
- [x] List available songs - Ashley
- [x] Fix upload wire protocol - Ashley
- [x] Presentation 
- [x] Record Demo


## Wow!

- [x] Sync up between clients
    - [x] Consensus protocol for synchronization
    - [x] Sharing timestamps with server
- [x] Implement features
    - [x] Play
    - [x] Pause
    - [x] Skip (will be in conjunction with client sync up
- [x] Fix pyaudio on Ashley's laptop >:(

## Nice to Have

- [x] Frame rate
- [ ] Rejoining client(?)
- [ ] Progress bar for uploading
- [ ] Frontend with progress bar
- [ ] Remove .wav from queue input / list
