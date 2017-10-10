# LinuxCNC-DNC
Serial based DNC
## 1.install python serial
    $pip install pyserial
## 2.add/replace ini configuretion file
    [DISPLAY]
    OPEN_FILE = dnc.ngc
    [PYTHON]
    TOPLEVEL = python/toplevel.py
    PATH_APPEND = python
    [RS274NGC]
    FEATURES = 12
    REMAP = M999 modalgroup=10 argspec=eprsh python=remapdnc
    [DNC]
    PORT = 0
    BAUDRATE = 9600
    STOPBITS = 2
    READAHEAD = 10
## 3.copy python folder
python/
* dnc.py  
* remap.py  
* toplevel.py  
## 4.run LinuxCNC
