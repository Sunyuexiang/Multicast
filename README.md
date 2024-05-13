# Multicast
The main task of this project is to design, develop, and demonstrate an SDN control-plane application upon the OpenFlow-based SDN controller platform RYU, to allow network operators or users to control the routes of their multicast traffic in an easy way. 

## Stap 1 DownLoad 
Download document "Ryu+Mininet", "Json" and "Front-end.zip" and unzip"Front-end.zip", "index.html", "app.py"
1. "Ryu-Mininet": Used to creat Topo and control Multicst
2. "Json":Examples of Json
3. "Front-end": Front-end Part
Replace the "index.html" and "app.py" in the "Front-end" folder with the two downloaded files

## Stap 2 Environment
```
Linux: Ubuntu 22.04
Python: Python3.9/Python3.10
Pycharm Pro
Ryu:4.24
Mininet
```

## Step 3 Test
1. Open "Front-end Project" in Pycharm Pro
2. Run and click[Example Link](http://127.0.0.1:5000)
3. Open a Terminal with Python 3.9 and go to the "Ryu+mininet" directory
4. Use
   ```
   ryu-manager controller
   ```
   to start Ryu controller and
   ```
   sudo python gen_topo
   ```
   to create topo
   Note:it is best to run Ryu after topo is created
5. Return Front-end Page and log in with user"root"and password "123"
6. click button "Topo" and uplode a example json "netconf.json"-->the photo will be shown on the screen
7. click button "Multicast" and upload a example json "file.json"-->the json will be show on the screen
8. click button "View" can see the detail of the json
9. click button "Delete Groups" can not see the group anymore
10. After upload Multicast Json zhe Ryu controller will have response information that the Groups and flows are added
11. Use Mininet Enter "links" to check links and "nodes" to check nodes and "xterm + hosts" to open hosts terminals
12. Source host termianl enter "python sender.py" and targets hosts terminals enter "python receiver.py"-->targets hosts will receive text
13. In front-end page delete groups and try again--> do not receive anymore
