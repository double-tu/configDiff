import os
import yaml
import jsonpointer
import re # 新增导入 re 模块
from properties_parser import convert_properties_to_dict

# 新增 YAML 内容预处理函数
def preprocess_yaml_content(content: str) -> str:
    # 正则表达式解释:
    # (^\s*[\w.-]+:\s*)             # 捕获组1: 行首、可选空格、键名、冒号、可选空格
    # ({{.*?}})                     # 捕获组2: {{placeholder}} 本身
    # (\s*(?:#.*)?$)                # 捕获组3: 可选空格，可选的行尾注释，然后是行尾
    #
    # 这个表达式旨在匹配类似 'key: {{placeholder}}' 或 'key: {{placeholder}} # comment' 的行
    # 并且只对这些行中的占位符加引号。
    # 它避免了对已经是字符串一部分的占位符进行操作，
    # 例如 'key: "prefix_{{placeholder}}_suffix"' 或 'key: ''prefix_{{placeholder}}_suffix'''
    
    # 方案A：针对简单键值对的占位符
    # pattern = r'(?m)(^\s*[\w.-]+:\s*)({{.*?}})(\s*(?:#.*)?$)'
    # replacement = r'\1"\2"\3'
    # preprocessed_content = re.sub(pattern, replacement, content)
    
    # 方案B：一个更通用的方法，查找未被引号包围的 {{...}}
    # 这需要更复杂的 lookbehind/lookahead，或者分步处理。
    #
    # 让我们尝试一个更安全的版本，它查找那些明显是值的、未加引号的占位符。
    # 它查找前面是 ": " 后面是换行或行尾的 {{...}}
    # (?<=[ \t]) 是一个正向后行断言，确保 {{ 前面是空格或制表符
    # (?![^:\n]*['"]) 是一个负向前行断言，确保占位符后面直到行尾或下一个冒号之前没有引号
    # 这仍然很复杂且容易出错。

    # 简化并聚焦于最常见的情况： value: {{placeholder}}
    # 我们需要确保 {{placeholder}} 不是已经是字符串的一部分。
    # 一个更简单的方法是逐行处理，如果一行匹配 `key: {{value}}` 模式，则替换。

    lines = content.splitlines()
    processed_lines = []
    # 匹配 `key:` 部分，然后是可选空格，然后是 `{{...}}`，然后是可选空格和可选注释
    pattern = re.compile(r'^(\s*[^#\s][^:]*:\s*)({{.*?}})(\s*(?:#.*)?)$')
    for line in lines:
        match = pattern.match(line)
        if match:
            # 如果匹配，则对占位符部分加引号
            processed_lines.append(f'{match.group(1)}"{match.group(2)}"{match.group(3)}')
        else:
            processed_lines.append(line)
    preprocessed_content = "\n".join(processed_lines)
    return preprocessed_content

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
    
    def _resolve_refs_recursive(data, current_file_path_for_ref_resolution):
        """
        递归解析$ref引用的内部函数
        
        Args:
            data: 当前要处理的数据结构
            current_file_path_for_ref_resolution: 当前文件用于解析相对引用的路径 (POSIX 格式的相对路径)
        """
        nonlocal visited_refs
        
        if isinstance(data, dict):
            if '$ref' in data:
                ref_value = data['$ref']
                # 使用传入的 current_file_path_for_ref_resolution 来构建 ref_key
                ref_key = f"{current_file_path_for_ref_resolution}->{ref_value}"
                
                # 检查循环引用
                if ref_key in visited_refs:
                    raise RefResolutionError(f"检测到循环引用: {ref_key}")
                visited_refs.add(ref_key)
                
                # 解析$ref
                # _resolve_ref 需要 current_file_path_for_ref_resolution 来解析相对文件路径
                resolved_content, referenced_file_relative_path = _resolve_ref(ref_value, current_file_path_for_ref_resolution)
                
                # 移除循环引用标记，因为我们即将深入解析 resolved_content
                # 如果 resolved_content 内部有指向相同 ref_key 的 $ref，那才是真正的循环
                # visited_refs.remove(ref_key) # 暂时注释，观察行为
                                
                # 递归解析解析后的内容，使用被引用文件的路径作为新的上下文
                # referenced_file_relative_path 是解析 $ref 后得到的文件的路径
                fully_resolved_value = _resolve_refs_recursive(resolved_content, referenced_file_relative_path)
                
                # visited_refs.add(ref_key) # 重新添加，以防其他地方引用它

                # 对于 $ref 节点，总是返回完全解析后的值
                return fully_resolved_value
                
            else:
                # 处理普通字典
                # 使用 current_file_path_for_ref_resolution 作为子元素的上下文路径
                # 因为这些子元素是定义在 current_file_path_for_ref_resolution 文件中的
                new_dict = {}
                for key, value in data.items(): # Iterate over items for potentially new structure
                    new_dict[key] = _resolve_refs_recursive(value, current_file_path_for_ref_resolution)
                return new_dict # Return new dict to handle cases where value might change type
                    
        elif isinstance(data, list):
            # 处理列表
            # 使用 current_file_path_for_ref_resolution 作为列表元素的上下文路径
            new_list = []
            for item in data: # Iterate over items for potentially new structure
                new_list.append(_resolve_refs_recursive(item, current_file_path_for_ref_resolution))
            return new_list # Return new list
                
        return data # 基本类型直接返回
    
    def _resolve_ref(ref_value: str, current_file_path_for_ref_resolution: str):
        """
        解析单个$ref引用
        
        Args:
            ref_value: $ref的值，格式为'<filename>#<json_pointer_path>'
            current_file_path_for_ref_resolution: 当前文件用于解析相对引用的路径 (POSIX 格式的相对路径)
            
        Returns:
            一个元组 (解析后的内容, 被引用文件的相对路径 (POSIX 格式))
        """
        # 分离文件名和JSON Pointer路径
        if '#' not in ref_value:
            # 假设是引用整个文件，追加 '#'
            ref_file_part = ref_value
            pointer_part = ""
        else:
            ref_file_part, pointer_part = ref_value.split('#', 1)

        # 去除可能的引号
        ref_file_part = ref_file_part.strip('"\'')
        pointer_part = pointer_part.strip('"\'')
        
        # 获取被引用文件的相对路径 (相对于 config_package_path/value/global 或 config_package_path/value/specs/<env>)
        # current_file_path_for_ref_resolution 是类似 "resources.yaml" 或 "config/common_settings.yaml"
        # ref_file_part 是类似 "config/common_settings.yaml" 或 "../global/config/global_records.yaml"
        if not ref_file_part: # 处理 "#/pointer" 的情况，引用当前文件
            referenced_file_relative_posix = current_file_path_for_ref_resolution
        else:
            # os.path.dirname("resources.yaml") -> ""
            # os.path.dirname("config/resources.yaml") -> "config"
            dir_of_current_file = os.path.dirname(current_file_path_for_ref_resolution)
            # os.path.join("", "config/file.yaml") -> "config/file.yaml"
            # os.path.join("config", "../other_config/file.yaml") -> "other_config/file.yaml"
            referenced_file_relative = os.path.normpath(os.path.join(dir_of_current_file, ref_file_part))
            referenced_file_relative_posix = referenced_file_relative.replace(os.sep, '/')
            if referenced_file_relative_posix == ".": # 处理引用当前目录的情况，通常意味着引用文件本身但无文件名
                 referenced_file_relative_posix = current_file_path_for_ref_resolution


        # 检查路径是否存在于 merged_config_map (键是 POSIX 格式的相对路径)
        ref_file_abs = merged_config_map.get(referenced_file_relative_posix)
        
        if not ref_file_abs:
            # 尝试另一种可能性：ref_file_part 本身就是一个完整的相对路径 (从 merged_config_map 的根开始)
            # 这种情况通常是 $ref: "config/common_settings.yaml#"
            # 而 current_file_path_for_ref_resolution 可能是 "resources.yaml"
            # 此时 os.path.join(os.path.dirname("resources.yaml"), "config/common_settings.yaml") -> "config/common_settings.yaml"
            # 这个逻辑应该已经覆盖了。
            # 如果 ref_file_part 是绝对路径（虽然不标准），这里不会处理。
            raise RefResolutionError(
                f"引用的文件无法在 merged_config_map 中找到: '{referenced_file_relative_posix}'. "
                f"原始引用: '{ref_value}' in file '{current_file_path_for_ref_resolution}'. "
                f"可用文件键: {list(merged_config_map.keys())}"
            )
            
        # 加载被引用文件
        try:
            with open(ref_file_abs, 'r', encoding='utf-8') as f:
                content = f.read()
                if ref_file_abs.endswith(('.yaml', '.yml')):
                    preprocessed_content = preprocess_yaml_content(content)
                    ref_data = yaml.load(preprocessed_content, Loader=yaml.SafeLoader) # 使用预处理内容和 SafeLoader
                elif ref_file_abs.endswith('.properties'):
                    # .properties 文件通常是键值对，转换为字典
                    # seek(0) is not needed as we pass the content string
                    # f.seek(0) # This line is removed
                    ref_data = convert_properties_to_dict(content)
                else:
                    raise RefResolutionError(f"不支持的文件类型: {ref_file_abs}")
                
                # 处理JSON Pointer路径
                if pointer_part:
                    try:
                        # import jsonpointer # 已经在模块顶部导入
                        resolved_pointer_data = jsonpointer.resolve_pointer(ref_data, pointer_part)
                    except jsonpointer.JsonPointerException as e:
                        raise RefResolutionError(f"JSON Pointer '{pointer_part}' 解析失败 in file '{referenced_file_relative_posix}'. 错误: {str(e)}")
                    return resolved_pointer_data, referenced_file_relative_posix
                else:
                    # 如果 pointer_part 为空，表示引用整个文件内容
                    return ref_data, referenced_file_relative_posix
        except Exception as e:
            # 包装原始异常以提供更多上下文
            raise RefResolutionError(f"加载或解析文件 '{ref_file_abs}' (来自引用 '{ref_value}' in '{current_file_path_for_ref_resolution}') 失败. 错误: {str(e)}") from e

    # 获取主文件的绝对路径
    if base_file_relative_path not in merged_config_map:
        raise RefResolutionError(f"基础文件不存在: {base_file_relative_path}")
        
    base_file_abs = merged_config_map[base_file_relative_path]
    
    # 加载主文件
    try:
        with open(base_file_abs, 'r', encoding='utf-8') as f:
            content = f.read()
            if base_file_abs.endswith(('.yaml', '.yml')):
                preprocessed_content = preprocess_yaml_content(content)
                base_data = yaml.load(preprocessed_content, Loader=yaml.SafeLoader) # 使用预处理内容和 SafeLoader
            elif base_file_abs.endswith('.properties'):
                base_data = convert_properties_to_dict(content)
            else:
                raise RefResolutionError(f"不支持的文件类型: {base_file_abs}")
    except Exception as e:
        raise RefResolutionError(f"加载基础文件失败: {base_file_abs}. 错误: {str(e)}")
        
    # 递归解析$ref
    return _resolve_refs_recursive(base_data, base_file_relative_path)