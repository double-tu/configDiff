import re
from typing import Any, Dict, List, Set, Optional

class ServiceNameNotFoundError(Exception):
    """Raised when the specified service name is not found in config data"""
    pass

class PlaceholderContextNotFoundError(Exception):
    """Raised when the placeholder context (records) is not found"""
    pass

class PlaceholderNotFoundError(Exception):
    """Raised when a placeholder key is not found in the context"""
    pass

class CircularPlaceholderDependencyError(Exception):
    """Raised when circular dependency is detected in placeholder values"""
    pass

def substitute_placeholders(config_data: Any, service_name: str) -> Any:
    """
    Substitute all {{placeholder}} patterns in the config data with values from the service's records context.
    
    Args:
        config_data: Fully expanded config structure (after env merge, $ref resolution and <<: merge)
        service_name: Name of the service to process
        
    Returns:
        Config structure with all placeholders substituted
        
    Raises:
        ServiceNameNotFoundError: If service_name is not found in config_data
        PlaceholderContextNotFoundError: If records context is not found
        PlaceholderNotFoundError: If a placeholder key is not found in context
        CircularPlaceholderDependencyError: If circular dependency is detected
    """
    # Step 1: Locate the service config block and extract records context
    service_block = _find_service_block(config_data, service_name)
    records = _extract_records_context(service_block)
    
    # Step 2: Perform iterative substitution until no more substitutions can be made
    max_iterations = 100  # Prevent infinite loops
    iteration = 0
    changed = True
    
    while changed and iteration < max_iterations:
        iteration += 1
        changed, service_block = _substitute_in_block(service_block, records)
    
    if iteration >= max_iterations:
        raise CircularPlaceholderDependencyError(
            f"Max iterations ({max_iterations}) reached. Possible circular dependency in placeholders."
        )
    
    return service_block

def _find_service_block(config_data: Any, service_name: str) -> Dict:
    """Find the service block matching the service_name in config_data"""
    def clean_name(name):
        if isinstance(name, str):
            return name.strip('"\' ')
        return str(name)
        
    target_name = clean_name(service_name)
    
    def find_in_dict(data: dict) -> Optional[Dict]:
        # 检查常规name键
        if 'name' in data and clean_name(data['name']) == target_name:
            return data
        # 检查带"- "前缀的键
        for key in data:
            if key.startswith('- name') and clean_name(data[key]) == target_name:
                return data
        return None
    
    # 处理包含services键的情况
    if isinstance(config_data, dict) and 'services' in config_data:
        services = config_data['services']
        if isinstance(services, list):
            for service in services:
                if isinstance(service, dict):
                    found = find_in_dict(service)
                    if found:
                        return found
        elif isinstance(services, dict):
            found = find_in_dict(services)
            if found:
                return found
    
    # 处理直接是服务列表的情况
    if isinstance(config_data, list):
        for item in config_data:
            if isinstance(item, dict):
                found = find_in_dict(item)
                if found:
                    return found
    
    # 处理直接是服务块的情况
    if isinstance(config_data, dict):
        found = find_in_dict(config_data)
        if found:
            return found
    
    # 调试输出
    print(f"Searching for service: '{target_name}'")
    print("Available services:")
    if isinstance(config_data, dict) and 'services' in config_data:
        services = config_data['services']
        if isinstance(services, list):
            for i, s in enumerate(services):
                if isinstance(s, dict):
                    name = s.get('name') or next((s[k] for k in s if k.startswith('- name')), None)
                    print(f"  [{i}]: {name}")
        elif isinstance(services, dict):
            name = services.get('name') or next((services[k] for k in services if k.startswith('- name')), None)
            print(f"  {name}")
    
    raise ServiceNameNotFoundError(
        f"Service '{target_name}' not found in config data. Available services: {config_data.get('services', []) if isinstance(config_data, dict) else []}"
    )

def _extract_records_context(service_block: Dict) -> Dict:
    """Extract the records context from the service block"""
    # 简化查找逻辑，直接使用合并后的properties.configs.private
    try:
        private_config = service_block['properties']['configs']['private']
        if 'records' in private_config:
            return private_config['records']
        # 如果没有records键，返回整个private配置作为上下文
        return private_config
    except KeyError:
        # 如果路径不存在，返回空字典避免报错
        return {}

def _substitute_in_block(data: Any, records: Dict) -> (bool, Any):
    """
    Perform one pass of substitution in the data block.
    Returns tuple of (changed_flag, new_data)
    """
    if isinstance(data, str):
        return _substitute_in_string(data, records)
    elif isinstance(data, dict):
        changed = False
        new_dict = {}
        for k, v in data.items():
            item_changed, new_v = _substitute_in_block(v, records)
            new_dict[k] = new_v
            changed = changed or item_changed
        return changed, new_dict
    elif isinstance(data, list):
        changed = False
        new_list = []
        for item in data:
            item_changed, new_item = _substitute_in_block(item, records)
            new_list.append(new_item)
            changed = changed or item_changed
        return changed, new_list
    else:
        return False, data

def _substitute_in_string(s: str, records: Dict) -> (bool, str):
    """Perform substitution in a single string value"""
    changed = False
    new_s = s
    
    for match in re.finditer(r'\{\{([^}]+)\}\}', s):
        placeholder_key = match.group(1)
        if placeholder_key in records:
            replacement = str(records[placeholder_key])
            new_s = new_s.replace(match.group(0), replacement)
            changed = True
        else:
            raise PlaceholderNotFoundError(
                f"Placeholder key '{placeholder_key}' not found in records context"
            )
    
    return changed, new_s