import linuxcnc
import emccanon
from interpreter import *

import dnc
import re
throw_exceptions = 1

def prepare_prolog(self,**words):
    try:
        cblock = self.blocks[self.remap_level]
        if not cblock.t_flag:
            self.set_errormsg("T requires a tool number")
            return INTERP_ERROR
        tool = cblock.t_number
        if tool:
            (status, pocket) = self.find_tool_pocket(tool)
            if status != INTERP_OK:
                self.set_errormsg("T{0}: pocket not found".format(tool))
                return status
        else:
            pocket = -1 # this is a T0 - tool unload
        self.params["tool"] = tool
        self.params["pocket"] = pocket
        return INTERP_OK
    except Exception, e:
        self.set_errormsg("T{0}/prepare_prolog: {1}".format(int(words['t']), e))
        return INTERP_ERROR
        
def prepare_epilog(self, **words):
    try:
        if not self.value_returned:
            r = self.blocks[self.remap_level].executing_remap
            self.set_errormsg("the {0} remap procedure {1} did not return a value".format(r.name,r.remap_ngc if r.remap_ngc else r.remap_py))
            return INTERP_ERROR
        if self.blocks[self.remap_level].builtin_used:
            #print "---------- T builtin recursion, nothing to do"
            return INTERP_OK
        else:
            if self.return_value > 0:
                self.selected_tool = int(self.params["tool"])
                self.selected_pocket = int(self.params["pocket"])
                emccanon.SELECT_POCKET(self.selected_pocket, self.selected_tool)
                return INTERP_OK
            else:
                self.set_errormsg("T{0}: aborted (return code {1:.1f})".format(int(self.params["tool"]),self.return_value))
                return INTERP_ERROR
    except Exception, e:
        self.set_errormsg("T{0}/prepare_epilog: {1}".format(tool,e))
        return INTERP_ERROR   
        
def change_prolog(self, **words):
    try:
        # this is relevant only when using iocontrol-v2.
        if self.params[5600] > 0.0:
            if self.params[5601] < 0.0:
                self.set_errormsg("Toolchanger hard fault {0}".format(int(self.params[5601])))
                return INTERP_ERROR
            print "change_prolog: Toolchanger soft fault {0}".format(int(self.params[5601]))
            
        if self.selected_pocket < 0:
                self.set_errormsg("M6: no tool prepared")
                return INTERP_ERROR
        if self.cutter_comp_side:
            self.set_errormsg("Cannot change tools with cutter radius compensation on")
            return INTERP_ERROR
        self.params["tool_in_spindle"] = self.current_tool
        self.params["selected_tool"] = self.selected_tool
        self.params["current_pocket"] = self.current_pocket
        self.params["selected_pocket"] = self.selected_pocket
        return INTERP_OK
    except Exception, e:
        self.set_errormsg("M6/change_prolog: {0}".format(e))
        return INTERP_ERROR
        
def change_epilog(self, **words):
    try:
        if not self.value_returned:
            r = self.blocks[self.remap_level].executing_remap
            self.set_errormsg("the {0} remap procedure {1} did not return a value".format(r.name,r.remap_ngc if r.remap_ngc else r.remap_py))
            return INTERP_ERROR
        # this is relevant only when using iocontrol-v2.
        if self.params[5600] > 0.0:
            if self.params[5601] < 0.0:
                self.set_errormsg("Toolchanger hard fault {0}".format(int(self.params[5601])))
                return INTERP_ERROR
            print "change_epilog: Toolchanger soft fault {0}".format(int(self.params[5601]))
            
        if self.blocks[self.remap_level].builtin_used:
            #print "---------- M6 builtin recursion, nothing to do"
            return INTERP_OK
        else:
            if self.return_value > 0.0:
                # commit change
                self.selected_pocket =  int(self.params["selected_pocket"])
                emccanon.CHANGE_TOOL(self.selected_pocket)
                self.current_pocket = self.selected_pocket
                self.selected_pocket = -1
                self.selected_tool = -1
                # cause a sync()
                self.set_tool_parameters()
                self.toolchange_flag = True
                return INTERP_EXECUTE_FINISH
            else:
                self.set_errormsg("M6 aborted (return code {0:.1f})".format(self.return_value))
                return INTERP_ERROR
    except Exception, e:
        self.set_errormsg("M6/change_epilog: {0}".format(e))
        return INTERP_ERROR
        
def remapdnc(self, **words):
    # initial return value
    ret = INTERP_OK
    retval = 1.0
    
    # initial global value
    self.params["_dnc_func"] = 0
    self.params["_dnc_a"] = 0
    self.params["_dnc_b"] = 0
    self.params["_dnc_c"] = 0
    self.params["_dnc_d"] = 0
    self.params["_dnc_e"] = 0
    self.params["_dnc_f"] = 0
    self.params["_dnc_g"] = 0
    self.params["_dnc_h"] = 0
    self.params["_dnc_i"] = 0
    self.params["_dnc_j"] = 0
    self.params["_dnc_k"] = 0
    self.params["_dnc_l"] = 0
    self.params["_dnc_m"] = 0
    self.params["_dnc_n"] = 0
    self.params["_dnc_o"] = 0
    self.params["_dnc_p"] = 0
    self.params["_dnc_q"] = 0
    self.params["_dnc_r"] = 0
    self.params["_dnc_s"] = 0
    self.params["_dnc_t"] = 0
    self.params["_dnc_u"] = 0
    self.params["_dnc_v"] = 0
    self.params["_dnc_w"] = 0
    self.params["_dnc_x"] = 0
    self.params["_dnc_y"] = 0
    self.params["_dnc_z"] = 0
    
    # milltask
    if self.task:
        # words length
        wordc = len(words)
        
        # run
        if wordc == 0:
            # is dead
            if self.dnc.stat() is dnc.DNC_STAT_DEAD:
                self.set_errormsg("DNC Error: thread is dead")
                retval = 0.0
                
            # is alive
            else:
                # blocks size
                blocks_size = self.dnc.blocks_size()
                
                # stat idle
                if blocks_size == 0:
                    if self.dnc.stat() is dnc.DNC_STAT_IDLE:
                        self.dnc.command(dnc.DNC_CMD_RUN)
                        
                # get block
                elif blocks_size > 0:
                    block = self.dnc.blocks_get()
                    print block
                    if block is not None:
                        (stat, code, lineno, msg) = block
                        
                        # stat running
                        if stat is dnc.DNC_STAT_RUNNING:
                            if msg is not None:
                                emccanon.MESSAGE(msg)
                                
                            # set function parameter
                            for func in re.finditer("([a-z])([+-]?\d*\.\d+|[+-]?\d+\.?\d*)", code):
                                self.params["_dnc_{0}".format(func.group(1))] = float(func.group(2))
                                
                            # replace #0 => 0
                            code = code.replace("#0", "0")
                            
                            # m98 sub call
                            if self.params["_dnc_m"] == 98:
                                self.params["_dnc_func"] = self.params["_dnc_p"]
                                
                            # g65 macro call
                            elif self.params["_dnc_g"] == 65:
                                self.params["_dnc_func"] = self.params["_dnc_p"]
                                
                            # g66 macro call
                            elif self.params["_dnc_g"] == 66:
                                self.params["_dnc_func"] = self.params["_dnc_p"]
                                
                            # execute
                            else:
                                self.execute(code, lineno)
                                
                        # stat finish
                        elif stat is dnc.DNC_STAT_FINISH:
                            #if msg is not None:
                            #    emccanon.MESSAGE(msg)
                            retval = 0.0
                            
                        # stat error
                        elif stat is dnc.DNC_STAT_ERROR:
                            if msg is not None:
                                self.set_errormsg(msg)
                            ret = INTERP_ERROR
                            retval = 0.0
                            
        # key words
        elif wordc == 1:
            # abort
            if words.has_key('e'):
                # abort dnc thread
                self.dnc.command(dnc.DNC_CMD_ABORT)
                if self.dnc.stat() is dnc.DNC_STAT_RUNNING:
                    self.set_errormsg("DNC Error: abort")
                    ret = INTERP_ERROR
                    
        # settings
        elif wordc == 4:
            # serial port
            if words.has_key('p'):
                port = "/dev/ttyS" + str(int(words['p']))
            else:
                self.set_errormsg("DNC Error: setting port 'p' not found")
                ret = INTERP_ERROR
                
            # serial baudrate
            if words.has_key('r'):
                baudrate = words['r']
            else:
                self.set_errormsg("DNC Error: setting baudrate 'r' not found")
                ret = INTERP_ERROR
                
            # serial stopbits
            if words.has_key('s'):
                stopbits = words['s']
            else:
                self.set_errormsg("DNC Error: setting stopbits 's' not found")
                ret = INTERP_ERROR
                
            # dnc read-ahead
            if words.has_key('h'):
                readahead = words['h']
            else:
                self.set_errormsg("DNC Error: setting read-ahead 'h' not found")
                ret = INTERP_ERROR
                
            # dnc settings
            if ret is INTERP_OK:
                self.dnc.settings(port, baudrate, stopbits, readahead)
                
        # ???
        else:
            self.set_errormsg("DNC Error: ???")
            ret = INTERP_ERROR
            
    # non-milltask
    else:
        retval = 0.0
    
    # return
    self.return_value = retval
    return ret
    
def init(self):
    # milltask
    if self.task:
        # create dnc thread
        self.dnc = dnc.Dnc()
        self.dnc.start()

def delete(self):
    # milltask
    if self.task:
        # stop dnc thread
        self.dnc.stop()
        
