import interpreter
import threading
import serial
import Queue
import time
import traceback
throw_exceptions = 1

# const
DNC_STAT_DEAD = -2
DNC_STAT_ERROR = -1
DNC_STAT_IDLE = 0
DNC_STAT_RUN = 1
DNC_STAT_RUNNING = 2
DNC_STAT_FINISH = 3

DNC_CMD_ABORT = -1
DNC_CMD_RUN = 1

class Dnc(threading.Thread):
    # const
    DNC_SERIAL_XON = 0x11
    DNC_SERIAL_XOFF = 0x13
    DNC_RETRY_TIME = 3
    DNC_RETRY_NUMBER = 3
    
    def __init__(self):
        # initialize
        self._lock = threading.Lock()
        self._stat = DNC_STAT_DEAD
        self._serial = None
        self._blocks = None
        self._loop = True
        
        threading.Thread.__init__(self)
        
    def settings(self, port, baudrate, stopbits, readahead):
        if (self._stat is DNC_STAT_DEAD) or (self._stat is DNC_STAT_IDLE):
            try:
                with self._lock:
                    # port
                    st_port = port
                    
                    # baudrate
                    st_baudrate = baudrate
                    
                    # bytesize, parity, stopbits
                    if stopbits == 1:
                        st_bytesize = serial.EIGHTBITS
                        st_parity = serial.PARITY_NONE
                        st_stopbits = serial.STOPBITS_ONE
                    elif stopbits == 2:
                        st_bytesize = serial.SEVENBITS
                        st_parity = serial.PARITY_EVEN
                        st_stopbits = serial.STOPBITS_TWO
                    else:
                        st_stopbits = None
                        
                    # serial close
                    if self._serial is not None:
                        if self._serial.isOpen():
                            self._serial.setDTR(False)
                            self._serial.setRTS(False)
                            self._serial.close()
                        self._serial = None
                        
                    # settings
                    self._serial = serial.Serial(
                        port = st_port,
                        baudrate = st_baudrate,
                        bytesize = st_bytesize,
                        parity = st_parity,
                        stopbits = st_stopbits,
                        timeout = 0,
                        xonxoff = False,
                        rtscts = False,
                        dsrdtr = False,
                        writeTimeout = 0,
                        interCharTimeout = None
                    )
                    
                    # clear blocks
                    if self._blocks is not None:
                        with self._blocks.mutex:
                            self._blocks.queue.clear()
                        self._blocks = None
                    self._blocks = Queue.Queue(maxsize = readahead)
                    
            except BaseException,e:
                print e
                
    def run(self):
        try:
            with self._lock:
                # thread initialize value
                lineno = -1
                
                # state set idle
                self._stat = DNC_STAT_IDLE
                
        except BaseException,e:
            print e
            self._loop = False
            
        while self._loop:
            try:
                with self._lock:
                    # state idle
                    if self._stat is DNC_STAT_IDLE:
                        pass
                            
                    # state run
                    elif self._stat is DNC_STAT_RUN:
                        # state set running
                        self._stat = DNC_STAT_RUNNING
                        
                        # flush serial
                        self._serial.flushInput()
                        self._serial.flushOutput()
                        
                        # serial DTR RTS on
                        self._serial.setDTR(True)
                        self._serial.setRTS(True)
                        
                        # blocks clear
                        self._blocks.queue.clear()
                            
                        # read line empty
                        readline = ""
                        
                        # xonxoff reset
                        xonxoff = None
                        xonxoff_last = None
                        
                        # retry
                        retry_time = 0
                        retry_num = self.DNC_RETRY_NUMBER
                        
                        # line number 0
                        lineno = 0
                        
                    # state running
                    elif self._stat is DNC_STAT_RUNNING:
                        # serial recv
                        if self._serial.getDSR():
                            # set DC1
                            xonxoff = self.DNC_SERIAL_XON
                            
                            # serial read
                            if (self._serial.inWaiting() > 0) and (xonxoff_last is self.DNC_SERIAL_XON):
                                # serial recv program
                                read = self._serial.read()
                                
                                # add read code
                                if read:
                                    readline += read
                                    
                                # reset retry
                                retry_time = time.time() + self.DNC_RETRY_TIME
                                retry_num = self.DNC_RETRY_NUMBER
                                
                                # check LF
                                if read == '\n':
                                    # tv parity check
                                    if (len(readline) % 2) == 0:
                                        readline = readline.strip()
                                        lreadline = readline.lower()
                                        ltreadline = lreadline.translate(None, ' ')
                                        
                                        # finish
                                        if (ltreadline == "m2") or (ltreadline == "m30"):
                                            # state set finish
                                            self._stat = DNC_STAT_FINISH
                                            
                                            self._blocks.put((self._stat, lreadline, lineno, None))
                                            
                                        # macro alarm
                                        elif ltreadline.startswith("#3000="):
                                            # state set error
                                            self._stat = DNC_STAT_ERROR
                                            
                                            # error message
                                            self._blocks.put((self._stat, None, lineno, "DNC Macro Alarm: {0}".format(readline)))
                                            
                                        # macro stop
                                        elif ltreadline.startswith("#3006="):
                                            self._blocks.put((self._stat, "m0", lineno, "DNC Macro Stop: {0}".format(readline)))
                                            
                                        # execute
                                        else:
                                            self._blocks.put((self._stat, lreadline, lineno, None))
                                            
                                        # increment line number
                                        lineno += 1
                                        
                                        # read line empty
                                        readline = ""
                                        
                                    # tv parity error
                                    else:
                                        # state set error
                                        self._stat = DNC_STAT_ERROR
                                        
                                        # error message
                                        self._blocks.put((self._stat, None, lineno, "DNC Error: TV parity\nline: {0}\n{1}".format(lineno, readline)))
                                        
                                    # set DC3
                                    xonxoff = self.DNC_SERIAL_XOFF
                                    
                            # check blocks queue
                            if self._blocks.full():
                                # set DC3
                                xonxoff = self.DNC_SERIAL_XOFF
                                
                            # serial send
                            if self._serial.getCTS():
                                # send DC once
                                if xonxoff is not xonxoff_last:
                                    self._serial.write(chr(xonxoff))
                                    xonxoff_last = xonxoff
                                    
                            # serial retry
                            if xonxoff == self.DNC_SERIAL_XON:
                                if retry_num > 0:
                                    if retry_time < time.time():
                                        retry_num = retry_num - 1
                                        retry_time = time.time() + self.DNC_RETRY_TIME
                                        xonxoff_last = None
                                else:
                                    # state set error
                                    self._stat = DNC_STAT_ERROR
                                    
                                    # error message
                                    self._blocks.put((self._stat, None, lineno, "DNC Error: retry failed"))
                                    
                        # serial disconnect
                        else:
                            # state set error
                            self._stat = DNC_STAT_ERROR
                            
                            # error message
                            self._blocks.put((self._stat, None, lineno, "DNC Error: disconnection"))
                            
                    # state finish
                    elif self._stat is DNC_STAT_FINISH:
                        # state set idle
                        self._stat = DNC_STAT_IDLE
                        
                        # serial DTR RTS off
                        if self._serial is not None:
                            if self._serial.isOpen():
                                self._serial.setDTR(False)
                                self._serial.setRTS(False)
                                
                        # xonxoff reset
                        xonxoff = None
                        xonxoff_prev = None
                        
                    # state error
                    elif self._stat is DNC_STAT_ERROR:
                        # state set idle
                        self._stat = DNC_STAT_IDLE
                        
                        # serial DTR RTS off
                        if self._serial is not None:
                            if self._serial.isOpen():
                                self._serial.setDTR(False)
                                self._serial.setRTS(False)
                                
                        # xonxoff reset
                        xonxoff = None
                        xonxoff_prev = None
                        
                    # abnormal
                    else:
                        # state set error
                        self._stat = DNC_STAT_ERROR
                        
                        # error message
                        self._blocks.put((self._stat, None, lineno, "DNC Error: dnc stat"))
                        
            except BaseException,e:
                # state set error
                self._stat = DNC_STAT_ERROR
                
                # error message
                self._blocks.put((self._stat, None, lineno, "DNC Error: {0}".format(e)))
                
                # stack trace
                print traceback.format_exc()
                
        # lock delete
        self._lock = None
        
        # state delete
        self._stat = None
        
        # serial delete
        if self._serial is not None:
            if self._serial.isOpen():
                self._serial.setDTR(False)
                self._serial.setRTS(False)
                self._serial.close()
            self._serial = None
            
        # blocks delete
        if self._blocks is not None:
            self._blocks.queue.clear()
            self._blocks = None
            
        # loop delete
        self._loop = None
        
    def stop(self):
        self._loop = False
        
    def command(self, cmd):
        with self._lock:
            # abort
            if cmd is DNC_CMD_ABORT:
                if self._stat is DNC_STAT_RUNNING:
                    # state set run
                    self._stat = DNC_STAT_IDLE
                    
                    # serial send DC3, DTR RTS off
                    if self._serial is not None:
                        if self._serial.isOpen():
                            self._serial.write(chr(self.DNC_SERIAL_XOFF))
                            self._serial.setDTR(False)
                            self._serial.setRTS(False)
                            
                    # wait
                    time.sleep(3)
                    
            # run
            elif cmd is DNC_CMD_RUN:
                if self._stat is DNC_STAT_IDLE:
                    self._stat = DNC_STAT_RUN
            
    def stat(self):
        return self._stat
        
    def blocks_size(self):
        with self._lock:
            if self._blocks is not None:
                ret = self._blocks.qsize()
            else:
                ret = 0
        return ret
        
    def blocks_get(self):
        with self._lock:
            if self._blocks is not None:
                try:
                    ret = self._blocks.get(block = False)
                except Queue.Empty:
                    ret = None
            else:
                ret = None
        return ret
        
