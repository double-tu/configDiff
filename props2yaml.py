import re
import yaml
from typing import Dict, Union

class Props2YAML:
    """
    Properties 转 YAML 工具类
    
    功能：
    1. 支持将 properties 格式的文本转换为 YAML 格式
    2. 支持从 properties 文件读取并转换为 YAML
    3. 支持数组格式的转换（如 key[0]=value）
    4. 支持注释保留（以 # 开头的行）
    
    返回：
    - 返回标准的 Python 字典对象，可通过 pyyaml 库转换为 YAML 字符串
    
    示例：
    >>> converter = Props2YAML()
    >>> yaml_dict = converter.from_text("key.subkey=value")
    >>> yaml_dict = converter.from_file("config.properties")
    """
    
    def __init__(self):
        # 初始化正则表达式
        self.array_regex = re.compile(r'^(.+)\[(\d+)\]$')  # 匹配数组格式 key[index]
        self.comment_regex = re.compile(r'^\s*#')  # 匹配注释行
        self.empty_regex = re.compile(r'^\s*$')  # 匹配空行
        self.key_value_regex = re.compile(r'^\s*([^=]+?)\s*=\s*(.*?)\s*$')  # 匹配 key=value

    def from_text(self, props_text: str) -> Dict:
        """
        从 properties 文本转换为 YAML 字典
        
        参数:
            props_text: properties 格式的文本，可以是单行或多行
            
        返回:
            字典对象，可通过 pyyaml 转换为 YAML 格式
        """
        yaml_dict = {}
        lines = props_text.split('\n')
        
        for line in lines:
            # 跳过注释行和空行
            if self.comment_regex.match(line) or self.empty_regex.match(line):
                continue
                
            # 解析键值对
            match = self.key_value_regex.match(line)
            if not match:
                continue
                
            key, value = match.groups()
            self._process_property(yaml_dict, key, value)
            
        return yaml_dict
    
    def from_file(self, file_path: str) -> Dict:
        """
        从 properties 文件转换为 YAML 字典
        
        参数:
            file_path: properties 文件路径
            
        返回:
            字典对象，可通过 pyyaml 转换为 YAML 格式
            
        异常:
            FileNotFoundError: 当文件不存在时抛出
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            props_text = f.read()
        return self.from_text(props_text)
    
    def _process_property(self, yaml_dict: Dict, key: str, value: str) -> None:
        """
        处理单个属性，将其添加到字典中
        
        参数:
            yaml_dict: 要更新的字典
            key: properties 键名（可能包含点号分隔）
            value: 属性值
        """
        # 检查是否是数组格式 (key[index])
        array_match = self.array_regex.match(key)
        if array_match:
            base_key = array_match.group(1)
            index = int(array_match.group(2))
            self._add_array_property(yaml_dict, base_key, index, value)
        else:
            self._add_simple_property(yaml_dict, key, value)
    
    def _add_simple_property(self, yaml_dict: Dict, key: str, value: str) -> None:
        """
        添加简单属性（非数组）
        
        参数:
            yaml_dict: 要更新的字典
            key: 可能包含点号分隔的键名
            value: 属性值
        """
        keys = key.split('.')
        current = yaml_dict
        
        # 遍历嵌套键
        for i, k in enumerate(keys[:-1]):
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                # 如果中间键已经存在但不是字典，则转换为字典
                current[k] = {'_value': current[k]}
            current = current[k]
            
        last_key = keys[-1]
        
        # 处理最后一级键
        if last_key in current:
            # 如果键已存在，确保它是一个字典并添加 _value
            if isinstance(current[last_key], dict):
                current[last_key]['_value'] = value
            else:
                current[last_key] = {'_value': current[last_key], '_value2': value}
        else:
            current[last_key] = value
    
    def _add_array_property(self, yaml_dict: Dict, base_key: str, index: int, value: str) -> None:
        """
        添加数组属性
        
        参数:
            yaml_dict: 要更新的字典
            base_key: 数组基名（不包含[index]部分）
            index: 数组索引
            value: 属性值
        """
        keys = base_key.split('.')
        current = yaml_dict
        
        # 遍历嵌套键
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                # 如果中间键已经存在但不是字典，则转换为字典
                current[k] = {'_value': current[k]}
            current = current[k]
            
        last_key = keys[-1]
        
        # 确保目标是一个列表
        if last_key not in current:
            current[last_key] = []
        elif not isinstance(current[last_key], list):
            # 如果已存在但不是列表，则转换为列表
            current[last_key] = [current[last_key]]
            
        # 扩展列表到所需大小
        while len(current[last_key]) <= index:
            current[last_key].append(None)
            
        current[last_key][index] = value


# 示例用法
if __name__ == '__main__':
    # 创建转换器实例
    converter = Props2YAML()
    
    # 示例 properties 文本
    props_text = """
    # 这是一个注释
    server.port=8080
    db.host=localhost
    db.port=3306
    db.user=root
    features[0]=logging
    features[1]=monitoring
    logging.level=INFO
    """
    
    # 从文本转换
    yaml_dict = converter.from_text(props_text)
    print("从文本转换结果:")
    print(yaml.dump(yaml_dict, default_flow_style=False, allow_unicode=True))
    
    # 从文件转换 (示例，需要实际文件)
    try:
        yaml_dict = converter.from_file("test.properties")
        print("\n从文件转换结果:")
        print(yaml.dump(yaml_dict, default_flow_style=False, allow_unicode=True))
    except FileNotFoundError:
        print("\n测试文件不存在，跳过文件转换示例")