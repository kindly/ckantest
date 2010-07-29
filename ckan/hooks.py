from blinker import signal

INIT_MODEL = signal('init_model')
MAKE_APP = signal('make_app')


def subscribe(signal, callback):
    _callback = lambda sender, *a, **kw: callback(*a, **kw)
    signal.connect(callback)
    
def unsubscribe(signal, callback):
    raise ValueError()
    
def trigger(signal, *a, **kw):
    return signal.send(*a, **kw)
