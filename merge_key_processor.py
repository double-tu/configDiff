import copy
from typing import Any, Dict, List, Callable

def merge_yaml_with_merge_keys(
    data: Any,
    merged_config_map: Dict[str, str], # Map of relative_path_posix -> absolute_path
    current_file_relative_path: str, # Relative path of the file currently being processed
    ref_resolver_func: Callable[[str, Dict[str, str], str], Any] # ref_value, merged_map, current_file_rel_path -> resolved_content
) -> Any:
    """
    处理YAML Merge Key `<<:` 并合并配置的递归函数。
    $ref 应该在此步骤之前被解析，或者 ref_resolver_func 能够处理它们。
    根据需求 2.3, `<<:` 列表中的项，列表靠前的项具有更高的优先级。
    
    Args:
        data: 输入的数据结构(字典或列表), 假设 $ref 已经被解析，或者 ref_resolver_func 能处理。
        merged_config_map: 子任务1的输出，键是相对路径(posix)，值是绝对路径。
        current_file_relative_path: 包含当前 'data' 的文件的相对路径 (posix 格式)。
                                   用于解析 `<<:` 中 `$ref` 的相对路径。
        ref_resolver_func: 一个函数，签名如 (ref_string, merged_config_map, current_file_path_for_ref) -> resolved_data
                           注意：这里的 ref_resolver_func 期望的是我们之前修改过的 ref_resolver.resolve_refs
                           的内部 _resolve_ref 或者一个类似的包装器，它能返回解析后的内容。
                           **修正**：根据 `config_processor.py` 的调用方式，`ref_resolver_func`
                           实际上是 `resolve_refs` 本身，或者一个包装器，它需要能够处理单个 `$ref` 字符串。
                           我们将假设 `ref_resolver_func` 是一个可以解析单个 `$ref` 字符串的函数，
                           它需要 `current_file_relative_path` 作为上下文。

    Returns:
        处理后的数据结构，所有`<<:`已被合并。
    """
    if isinstance(data, dict):
        data_copy = copy.deepcopy(data) # Work on a copy
        
        if '<<:' in data_copy:
            merge_sources = data_copy.pop('<<:') # Get and remove '<<:' key
            if not isinstance(merge_sources, list):
                raise ValueError(f"`<<:`的值必须是一个列表, 但在文件 '{current_file_relative_path}' 中得到: {type(merge_sources)}")
            
            # 初始化合并结果的字典
            # 最终结果将是 merge_sources 中的内容（按优先级）和 data_copy 中剩余的内容合并
            final_merged_dict = {}

            # 1. 合并 `<<:` 列表中的源。根据需求，列表靠前的项具有更高的优先级。
            #    我们将从列表的最后一个元素（最低优先级）开始，逐个合并到 final_merged_dict。
            #    然后，列表中的下一个（更高优先级的）元素将合并进来，并可能覆盖之前合并的内容。
            
            # 首先，将所有 merge_sources 合并到一个临时的基底字典中。
            # _deep_merge_dicts(target, source) -> source (较高优先级) 的值覆盖 target (较低优先级) 的值。
            # 我们需要从后往前迭代 merge_sources，这样列表前面的（高优先级）会覆盖后面的（低优先级）。
            
            base_for_merge = {}
            for item_in_list in reversed(merge_sources): # 从列表末尾（最低优先级）开始
                resolved_item = None
                # 假设当 merge_yaml_with_merge_keys 被调用时，
                # data 内部（包括 <<: 列表中的 $ref）已经被 resolve_refs 完全解析了。
                # 这是基于 config_processor.py 的处理流程。
                if isinstance(item_in_list, dict):
                    resolved_item = item_in_list # 已经是解析后的字典
                else:
                    # 如果 $ref 没有被完全解析，这里会出问题。
                    # 但根据流程，它们应该是解析过的。
                    raise ValueError(
                        f"`<<:`列表中的项必须是字典 (因为$ref应已被解析), "
                        f"但在 '{current_file_relative_path}' 中得到: {type(item_in_list)} for item {item_in_list}"
                    )

                if not isinstance(resolved_item, dict): # 双重检查
                    raise ValueError(
                        f"解析 `<<:` 列表中的项后，期望得到字典, "
                        f"但在 '{current_file_relative_path}' 得到: {type(resolved_item)} for item {item_in_list}"
                    )
                
                # 合并 resolved_item (当前列表项，作为 source) 到 base_for_merge (作为 target)
                # 因为我们从 reversed(merge_sources) 迭代，所以 resolved_item 的优先级会逐渐增高。
                # _deep_merge_dicts(target, source) -> source 覆盖 target
                _deep_merge_dicts(base_for_merge, resolved_item)

            # 2. 现在，将原始 data_copy 中的其他键（非 '<<:' 的）合并到 base_for_merge 之上。
            #    这些原始键具有最高优先级，应覆盖来自 `<<:` 的所有内容。
            _deep_merge_dicts(base_for_merge, data_copy) # data_copy (原始键) 覆盖 base_for_merge (来自 <<:)
            data_copy = base_for_merge # 这是此级别的完全合并结果

        # 递归处理字典中的其他值
        # Pass current_file_relative_path as it's the context for any nested structures in this file
        processed_dict = {}
        for key, value in data_copy.items():
            processed_dict[key] = merge_yaml_with_merge_keys(
                value,
                merged_config_map,
                current_file_relative_path, 
                ref_resolver_func # Pass along the resolver
            )
        return processed_dict
            
    elif isinstance(data, list):
        # Process list type
        # Pass current_file_relative_path as it's the context for items in this list from this file
        processed_list = []
        for i, item in enumerate(data):
            processed_list.append(merge_yaml_with_merge_keys(
                item,
                merged_config_map,
                current_file_relative_path,
                ref_resolver_func # Pass along the resolver
            ))
        return processed_list
            
    return data # Return basic types as is

def _deep_merge_dicts(target: Dict, source: Dict) -> Dict:
    """
    深度合并两个字典，`source` 中的值会覆盖 `target` 中的值。
    函数会修改 `target` 字典。
    
    Args:
        target: 目标字典 (较低优先级，会被覆盖)
        source: 源字典 (较高优先级，会覆盖 target)
        
    Returns:
        合并后的字典 (即修改后的 `target`)
    """
    for key, value_from_source in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value_from_source, dict):
            # If both are dicts, recurse
            _deep_merge_dicts(target[key], value_from_source)
        else:
            # Otherwise, value from source overrides value in target (or adds if key not in target)
            target[key] = copy.deepcopy(value_from_source)
    return target