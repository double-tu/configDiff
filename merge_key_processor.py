import copy
from typing import Any, Dict, List, Callable

def merge_yaml_with_merge_keys(
    data: Any,
    merged_config_map: Dict[str, str],
    current_config_base_path: str,
    ref_resolver_func: Callable
) -> Any:
    """
    处理YAML Merge Key `<<:` 并合并配置的递归函数
    
    Args:
        data: 输入的数据结构(字典或列表)
        merged_config_map: 子任务1的输出，键是相对路径，值是绝对路径
        current_config_base_path: 逻辑current-config/目录的根路径
        ref_resolver_func: 解析$ref引用的函数
        
    Returns:
        处理后的数据结构，所有`<<:`已被合并
    """
    if isinstance(data, dict):
        # 处理字典类型
        data = copy.deepcopy(data)
        
        if '<<:' in data:
            # 处理<<:合并键
            merge_list = data.pop('<<:')
            if not isinstance(merge_list, list):
                raise ValueError("`<<:`的值必须是一个列表")
                
            # 解析并合并所有引用
            merged = {}
            for item in merge_list:
                # 解析引用项(可能是$ref或已解析的字典)
                if isinstance(item, dict) and '$ref' in item:
                    resolved = ref_resolver_func(
                        item['$ref'],
                        merged_config_map,
                        current_config_base_path
                    )
                elif isinstance(item, dict):
                    resolved = item
                else:
                    raise ValueError("`<<:`列表中的项必须是字典")
                    
                # 深度合并到结果中
                print(f"Merging resolved content: {resolved.keys() if isinstance(resolved, dict) else resolved}")
                _deep_merge_dicts(merged, resolved)
                
            # 将合并结果与原始数据合并(原始数据优先级更高)
            print(f"Merging with original data: {data.keys() if isinstance(data, dict) else data}")
            _deep_merge_dicts(merged, data)
            data = merged
            print(f"Merged result: {data.keys() if isinstance(data, dict) else data}")
            
        # 递归处理字典中的其他值
        for key, value in data.items():
            data[key] = merge_yaml_with_merge_keys(
                value,
                merged_config_map,
                current_config_base_path,
                ref_resolver_func
            )
            
    elif isinstance(data, list):
        # 处理列表类型
        data = copy.deepcopy(data)
        for i, item in enumerate(data):
            data[i] = merge_yaml_with_merge_keys(
                item,
                merged_config_map,
                current_config_base_path,
                ref_resolver_func
            )
            
    return data

def _deep_merge_dicts(high_priority: Dict, low_priority: Dict) -> Dict:
    """
    深度合并两个字典，high_priority中的值会覆盖low_priority中的值
    
    Args:
        high_priority: 高优先级字典
        low_priority: 低优先级字典
        
    Returns:
        合并后的字典(修改high_priority本身)
    """
    for key, value in low_priority.items():
        if key not in high_priority:
            high_priority[key] = copy.deepcopy(value)
        else:
            # 键存在，需要检查是否需要递归合并
            if isinstance(high_priority[key], dict) and isinstance(value, dict):
                _deep_merge_dicts(high_priority[key], value)
            else:
                # 类型不同或不是字典，直接使用高优先级的值
                pass
    return high_priority