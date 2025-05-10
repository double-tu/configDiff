import re

def simple_yaml_parse(content):
    """简化版YAML解析器，避免处理占位符"""
    def create_data_structure(lines):
        result = {}
        stack = [(0, result)]
        
        for line in lines:
            # 跳过空行和注释
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue
            
            # 获取缩进和内容
            indent = len(line) - len(line.lstrip())
            line = line.strip()
            
            # 确保栈不为空
            if not stack:
                raise ValueError("Invalid YAML structure: missing root level")
                
            current_level, current_dict = stack[-1]
            
            # 处理键值对
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if value.startswith('[') and value.endswith(']'):
                    # 简单列表处理
                    current_dict[key] = [item.strip() for item in value[1:-1].split(',')]
                elif value.startswith('{') and value.endswith('}'):
                    # 简单字典处理
                    current_dict[key] = {}
                    stack.append((indent, current_dict[key]))
                else:
                    current_dict[key] = value
            
            # 处理嵌套结构
            if line.endswith(':'):
                key = line.split(':')[0].strip()
                current_dict[key] = {}
                stack.append((indent, current_dict[key]))
        
        return result
    
    # 预处理内容：确保所有占位符保持原样
    lines = []
    for line in content.split('\n'):
        if '{{' in line and '}}' in line:
            # 保持占位符原样
            line = re.sub(r'(\{\{[^}]+\}\})', r'"\1"', line)
        lines.append(line)
    
    return create_data_structure(lines)