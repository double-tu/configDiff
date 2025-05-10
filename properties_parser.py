import re
from typing import Dict

def convert_properties_to_dict(properties_content: str) -> Dict:
    """
    将 Java .properties 文件内容转换为多层 Python 字典结构
    
    参数:
        properties_content: .properties 文件的完整文本内容
        
    返回:
        多层嵌套的字典结构，其中:
        - 键名按 '.' 分割成路径片段
        - 值作为字符串保留原样
        - 保留 {{placeholder}} 格式的占位符
        - 忽略以 '#' 或 '!' 开头的注释行和空行
        
    示例:
        >>> convert_properties_to_dict("a.b.c=val")
        {'a': {'b': {'c': 'val'}}}
        >>> convert_properties_to_dict("db.user={{user}}")
        {'db': {'user': '{{user}}'}}
    """
    result = {}
    if not properties_content.strip():
        return result
        
    # 正则匹配键值对 (key=value)
    key_value_pattern = re.compile(r'^\s*([^=]+?)\s*=\s*(.*?)\s*$')
    # 匹配注释行 (以 # 或 ! 开头) 和空行
    comment_or_empty_pattern = re.compile(r'^\s*([#!].*)?$')
    
    for line in properties_content.split('\n'):
        # 跳过注释行和空行
        if comment_or_empty_pattern.match(line):
            continue
            
        match = key_value_pattern.match(line)
        if not match:
            continue  # 跳过格式错误的行
            
        key, value = match.groups()
        current = result
        keys = key.split('.')
        
        # 构建嵌套字典结构
        for k in keys[:-1]:
            current = current.setdefault(k, {})
            
        # 设置最终键的值
        current[keys[-1]] = value
        
    return result