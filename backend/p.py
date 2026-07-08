from functools import wraps, update_wrapper

class desc:
    def __init__( self, fget=None, fset=None):
        self.fget = fget
        self.fset = fset
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("dolbaeb")
        return self.fget(obj)
    
    def __set__(self, obj, value):
        if self.fset is None:
            raise AttributeError("DAUN")
        self.fset(obj, value)

    def setter(self, fset):
        self.fset = fset
        return self
    
class cmth:
    def __init__(self, name):
        self.name = name
    
   
    def name(self):
        return self.name
    

    def set_name(self, value):
        if not value:
            raise ValueError("Name cannot be empty")
        self.name = value
    

p =cmth("Gay")
print(p.name)
p.name = "kmfk"
print(p.name)