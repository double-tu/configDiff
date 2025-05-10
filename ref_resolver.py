import os
import yaml
import jsonpointer
from properties_parser import convert_properties_to_dict
from yaml_simple_parser import simple_yaml_parse

class RefResolutionError(Exception):
    """自定义异常，用于$ref解析过程中的错误"""
    pass

def resolve_refs(base_file_relative_path: str, merged_config_map: dict, current_config_base_path: str):
    """
    解析配置文件中的$ref引用
    
    Args:
        base_file_relative_path: 作为解析起点的文件的相对路径
        merged_config_map: 子任务1的输出，键是相对路径，值是绝对路径
        current_config_base_path: 逻辑current-config/目录的根路径
        
    Returns:
        解析后的Python数据结构(字典或列表)
        
    Raises:
        RefResolutionError: 当解析过程中出现错误时抛出
    """
    # 跟踪已解析的引用路径，用于检测循环引用
    visited_refs = set()
    
    def _resolve_refs_recursive(data, current_file_path):
        """
        递归解析$ref引用的内部函数
        
        Args:
            data: 当前要处理的数据结构
            current_file_path: 当前文件的路径(用于解析相对路径)
        """
        nonlocal visited_refs
        
        if isinstance(data, dict):
            if '$ref' in data:
                ref_value = data['$ref']
                ref_key = f"{current_file_path}->{ref_value}"
                
                # 检查循环引用
                if ref_key in visited_refs:
                    raise RefResolutionError(f"检测到循环引用: {ref_key}")
                visited_refs.add(ref_key)
                
                # 解析$ref
                resolved = _resolve_ref(ref_value, current_file_path)
                
                # 递归解析解析后的内容
                _resolve_refs_recursive(resolved, current_file_path)
                
                # 替换$ref结构
                data.clear()
                if isinstance(resolved, dict):
                    data.update(resolved)
                else:
                    # 对于非字典类型，直接替换整个结构
                    return resolved
                
            else:
                # 处理普通字典
                for key, value in list(data.items()):
                    data[key] = _resolve_refs_recursive(value, current_file_path)
                    
        elif isinstance(data, list):
            # 处理列表
            for i, item in enumerate(data):
                data[i] = _resolve_refs_recursive(item, current_file_path)
                
        return data
    
    def _resolve_ref(ref_value: str, current_file_path: str):
        """
        解析单个$ref引用
        
        Args:
            ref_value: $ref的值，格式为'<filename>#<json_pointer_path>'
            current_file_path: 当前文件的路径(用于解析相对路径)
            
        Returns:
            解析后的内容
        """
        # 分离文件名和JSON Pointer路径
        if '#' not in ref_value:
            raise RefResolutionError(f"无效的$ref格式: {ref_value}")
            
        ref_file_part, pointer_part = ref_value.split('#', 1)
        
        # 去除可能的引号
        ref_file_part = ref_file_part.strip('"\'')
        pointer_part = pointer_part.strip('"\'')
        
        # 获取被引用文件的绝对路径并统一使用正斜杠
        ref_file_relative = os.path.normpath(os.path.join(os.path.dirname(current_file_path), ref_file_part))
        ref_file_relative_posix = ref_file_relative.replace(os.sep, '/')
        
        # 检查路径是否存在(统一使用POSIX格式比较)
        ref_file_abs = None
        for config_path in merged_config_map:
            if ref_file_relative_posix == config_path:
                ref_file_abs = merged_config_map[config_path]
                break
        
        if not ref_file_abs:
            raise RefResolutionError(f"引用的文件不存在: {ref_file_relative} (搜索路径: {ref_file_relative_posix}, 可用文件: {list(merged_config_map.keys())})")
            
        # 加载被引用文件
        try:
            with open(ref_file_abs, 'r', encoding='utf-8') as f:
                content = f.read()
                if ref_file_abs.endswith(('.yaml', '.yml')):
                    ref_data = simple_yaml_parse(content)
                elif ref_file_abs.endswith('.properties'):
                    ref_data = convert_properties_to_dict(f)
                else:
                    raise RefResolutionError(f"不支持的文件类型: {ref_file_abs}")
                
                # 处理JSON Pointer路径
                if pointer_part:
                    try:
                        import jsonpointer
                        ref_data = jsonpointer.resolve_pointer(ref_data, pointer_part)
                    except jsonpointer.JsonPointerException as e:
                        raise RefResolutionError(f"JSON Pointer解析失败: {pointer_part}. 错误: {str(e)}")
                
                return ref_data
        except Exception as e:
            raise RefResolutionError(f"加载文件失败: {ref_file_abs}. 错误: {str(e)}")
            
        # 处理JSON Pointer路径
        if pointer_part:
            try:
                ref_data = jsonpointer.resolve_pointer(ref_data, pointer_part)
            except jsonpointer.JsonPointerException as e:
                raise RefResolutionError(f"JSON Pointer解析失败: {pointer_part}. 错误: {str(e)}")
                
        return ref_data
    
    # 获取主文件的绝对路径
    if base_file_relative_path not in merged_config_map:
        raise RefResolutionError(f"基础文件不存在: {base_file_relative_path}")
        
    base_file_abs = merged_config_map[base_file_relative_path]
    
    # 加载主文件
    try:
        with open(base_file_abs, 'r', encoding='utf-8') as f:
            content = f.read()
            if base_file_abs.endswith(('.yaml', '.yml')):
                base_data = simple_yaml_parse(content)
            elif base_file_abs.endswith('.properties'):
                base_data = convert_properties_to_dict(f)
            else:
                raise RefResolutionError(f"不支持的文件类型: {base_file_abs}")
    except Exception as e:
        raise RefResolutionError(f"加载基础文件失败: {base_file_abs}. 错误: {str(e)}")
        
    # 递归解析$ref
    return _resolve_refs_recursive(base_data, base_file_relative_path)