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

def substitute_placeholders(
    data_to_process: Any,
    records_context: Dict,
    max_iterations: int = 10, # Max depth for iterative substitution
    current_iteration: int = 0, # For tracking recursion depth, not used in the loop here
    visited_placeholders: Optional[Set[str]] = None # For circular dependency detection in string values
) -> Any:
    """
    Substitute all {{placeholder}} patterns in the data_to_process with values from the records_context.
    This function is called by config_processor.py with the specific service block and its records.
    
    Args:
        data_to_process: The data structure (dict, list, str) to perform substitutions on.
        records_context: A dictionary containing placeholder keys and their values.
        max_iterations: Maximum number of passes for iterative substitution.
        current_iteration: (Not directly used by the loop, more for conceptual depth)
        visited_placeholders: Set to track placeholders during the substitution of a single string value to detect cycles.

    Returns:
        Data structure with placeholders substituted.
        
    Raises:
        PlaceholderNotFoundError: If a placeholder key is not found in context (and not self-referential in a resolvable way).
        CircularPlaceholderDependencyError: If circular dependency is detected after max_iterations or within a string.
    """
    
    # Iterative substitution for the entire data_to_process block
    # This handles cases where a placeholder's value might itself be or contain another placeholder.
    
    processed_data = data_to_process
    
    for i in range(max_iterations):
        # `_substitute_pass` will return (changed_flag, substituted_data_segment)
        # We need to apply this recursively to the structure.
        # The `_substitute_in_block_iterative` will handle the recursive traversal and iterative substitution.
        
        # Let's simplify: the main loop for iterations should be here.
        # `_substitute_in_block_one_pass` will do one pass over the structure.
        
        changed_in_pass, temp_data = _substitute_in_block_one_pass(processed_data, records_context, set()) # Pass fresh visited set for each top-level pass
        processed_data = temp_data
        if not changed_in_pass:
            # No changes in this pass, substitution is complete or stuck.
            # Check for any remaining placeholders to ensure completion or identify issues.
            if _contains_placeholders(processed_data):
                 # This could happen if a placeholder was not in records_context or due to a complex cycle not caught by string-level check.
                 # The PlaceholderNotFoundError should ideally be raised during _substitute_in_string_one_pass if a key is missing.
                 # If we reach here with remaining placeholders, it implies a more complex scenario or a bug.
                 # For now, assume _substitute_in_string_one_pass handles missing keys.
                 # A remaining placeholder might indicate a cycle that wasn't resolved.
                 # However, the string-level cycle detection should catch direct {{a}} -> {{b}} -> {{a}} in values.
                 # This check is more of a safeguard.
                 # Consider if an error should be raised here if _contains_placeholders is true.
                 # For now, we rely on max_iterations to break very complex cycles.
                 pass # Substitution converged or stuck
            return processed_data # Return the result

    # If loop finishes due to max_iterations, check if there are still placeholders
    if _contains_placeholders(processed_data):
        # Find an example of an unresolved placeholder
        unresolved_example = _find_first_placeholder(processed_data)
        raise CircularPlaceholderDependencyError(
            f"最大迭代次数 ({max_iterations}) 已达到，但仍有未解析的占位符。 "
            f"可能存在循环依赖或占位符在上下文中缺失。示例: '{unresolved_example}'"
        )
        
    return processed_data


def _contains_placeholders(data: Any) -> bool:
    """Recursively checks if the data structure contains any {{placeholder}}."""
    if isinstance(data, str):
        return bool(re.search(r'\{\{([^}]+)\}\}', data))
    elif isinstance(data, dict):
        return any(_contains_placeholders(v) for v in data.values())
    elif isinstance(data, list):
        return any(_contains_placeholders(item) for item in data)
    return False

def _find_first_placeholder(data: Any) -> Optional[str]:
    """Finds the first {{placeholder}} encountered in the data structure."""
    if isinstance(data, str):
        match = re.search(r'(\{\{[^}]+\}\})', data)
        return match.group(1) if match else None
    elif isinstance(data, dict):
        for v in data.values():
            found = _find_first_placeholder(v)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_first_placeholder(item)
            if found:
                return found
    return None


def _substitute_in_block_one_pass(
    data: Any,
    records: Dict,
    visited_in_string_substitution: Set[str] # Used for cycle detection within a single string's resolution path
) -> (bool, Any):
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
            item_changed, new_v = _substitute_in_block_one_pass(v, records, visited_in_string_substitution)
            new_dict[k] = new_v
            changed = changed or item_changed
        return changed, new_dict
    elif isinstance(data, list):
        changed = False
        new_list = []
        for item in data:
            item_changed, new_item = _substitute_in_block_one_pass(item, records, visited_in_string_substitution)
            new_list.append(new_item)
            changed = changed or item_changed
        return changed, new_list
    else:
        return False, data

# Sentinel object to indicate that a key was not found by _get_value_by_path
_NOT_FOUND_SENTINEL = object()

def _get_value_by_path(data_dict: Dict, path_string: str) -> Any:
    """
    Retrieves a value from a nested dictionary using a dot-separated path string.
    Returns _NOT_FOUND_SENTINEL if the path is invalid or key not found.
    """
    keys = path_string.split('.')
    current_level = data_dict
    for key in keys:
        if isinstance(current_level, dict) and key in current_level:
            current_level = current_level[key]
        else:
            return _NOT_FOUND_SENTINEL # Key not found at this level or current_level is not a dict
    return current_level

def _substitute_in_string(s: str, records: Dict) -> (bool, str):
    """Perform substitution in a single string value, supporting dot-notation for nested keys."""
    changed = False
    new_s = s
    
    for match in re.finditer(r'\{\{([^}]+)\}\}', s):
        placeholder_key = match.group(1).strip() # Remove leading/trailing whitespace from key
        
        value = _get_value_by_path(records, placeholder_key)
        
        if value is not _NOT_FOUND_SENTINEL:
            replacement = str(value)
            # Ensure that the original placeholder (match.group(0)) is replaced,
            # not just a potentially modified key if strip() was effective.
            new_s = new_s.replace(match.group(0), replacement)
            changed = True
        else:
            raise PlaceholderNotFoundError(
                f"Placeholder key '{placeholder_key}' not found in records context"
            )
            
    return changed, new_s