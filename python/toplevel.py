# this would be defined in the TOPLEVEL module
import remap

def __init__(self):
    # add any one-time initialization here
    if self.task:
        # this is the milltask instance of interp
        remap.init(self)
    else:
        # this is a non-milltask instance of interp
        pass

def __delete__(self):
    # add any cleanup/state saving actions here
    if self.task: # as above
        remap.delete(self)
    else:
        pass

