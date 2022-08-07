# from tasks import add
from ambuda.tasks import add


r = add.delay(4, 4)
print(r.status)
print(r.result)
print(r.get(timeout=1))
print(r.status)
print(r.result)
