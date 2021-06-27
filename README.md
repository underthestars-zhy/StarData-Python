# StarData-Python
> 一个现代化便捷的数据管理系统

## Start
1. 首先你需要有一个**StarData**数据库。<br>
什么你还没有，[立即搭建](https://github.com/underthestars-zhy/StarData/tree/master)
2. 请确保设置了`is_primary`并保证只有**一个参数**设置
3. 引入基类`from StarData import BaseData`
4. 创建一个子类
```python
from StarData import BaseData
class Table(BaseData):
    api = "你的api"
    key = "你的密钥"
    salt = "你的密钥加盐"
    url = "你的网址，最后不要有/"
    db_name = "数据库名称"
    table_name = "表名称"
```

## 获取所有实例
1. 首先确保你已经创建了的子类
2. 引入查询器`from StarData import get_all_items`
3. 开始查询`items = get_all_items(Table)`
4. `get_all_items`需要一个`BaseData`的子类

## 获取值
1. 首先确保你已经创建了的子类
2. 定义相关函数
```python
from StarData import BaseData
class Table(BaseData):
    @property
    def name(self):
        return super().get_value("name")
```
3. 通过`Table`的一个**实例**调用`name`，如`get_all_items(Table)[0].name`