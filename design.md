
构造新的一个class，在里面定义原子级别的读写操作，是new core的实例化，其原子级别的操作是由db和git里的协同完成的，可一定程度上借鉴老版本的core中的设计

```python
class GitDB
    def write()
    def read()
```