# import logging


# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# logger.info("Hello, world!")


# class SomeClass:
#     @property
#     def some_prop(self):
#         return 10

# obj = SomeClass()
# print(obj.some_prop)

# from testy import logger

# logger.info("Hello, world!")

# def myfunc(*args, **kwargs):
#     print(type(args))
#     print(type(kwargs))
#     print(args)
#     print(kwargs)

# myfunc(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, name="John", age=30)


# def the_decorator(func):
#     def wrapper(*args, **kwargs):
#         print("Before the function is called")
#         print(type(args))
#         print(type(kwargs))
#         print(args)
#         print(kwargs)
#         kwargs["input"] = [1, 2, 3]
#         new_args = tuple()
#         new_kwargs = {
#             "input": [1, 2, 3]
#         }
#         func(*new_args, **new_kwargs)
#         # or func(**new_kwargs)
#         print("After the function is called")
#     return wrapper


# @the_decorator
# def the_func(input):
#     for i in input:
#         print(i)


# the_func(1,2,3,4,name="John",age=30)


from functools import wraps


def third_decorator(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        print("Third decorator before the function is called")
        return f(*args, **kwargs)
    return wrapper

def second_decorator(f):
    @third_decorator
    def wrapper(*args, **kwargs):
        print("Second decorator before the function is called")
        return f(*args, **kwargs)
    return wrapper

def decorator(f):
    def wrapper(*args, **kwargs):
        print("First decorator before the function is called")
        return f(*args, **kwargs)
    return wrapper

def call_decorator():
    return (decorator)

@third_decorator
@second_decorator
@call_decorator()
def the_func(input):
    for i in input:
        print(i)

the_func([1,2,3,4])


from pydantic import BaseModel, Field, ConfigDict
from typing import Optional 

class ProductCreateRequest(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str = Field(..., min_length=1, max_length=200)
    price: float = Field(..., gt=0)
    description: Optional[str] = None

p1 = ProductCreateRequest(name="Product 1", price=100)
print(p1, type(p1))
print("--------------------------------")
print(p1.model_dump(), type(p1.model_dump()))
print("--------------------------------")
print(p1.model_dump_json(exclude_none=True), type(p1.model_dump_json(exclude_none=True)))



def the_func(*args, **kwargs):
    kwargs["input"] = 1
    return kwargs

def the_func2(a,b):
    return a + b

def the_func3(*args, **kwargs):
    args = [1, 2]
    return the_func2(*args, **kwargs)
    
a = the_func()
a = the_func3()

print(a, type(a))

a, *args = [1, 2, 3, 4, 5]
print(a, *args)