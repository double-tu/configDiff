import os
import logging
import yaml
from typing import Any, Dict # Added Dict for type hinting
from config_merger import merge_env_configs
from ref_resolver import resolve_refs
from merge_key_processor import merge_yaml_with_merge_keys
from placeholder_substitutor import substitute_placeholders
# from yaml_simple_parser import simple_yaml_parse # 已被移除，因为 ref_resolver 使用了 SafeStringLoader
from properties_parser import convert_properties_to_dict # For loading .properties

# PlaceholderSafeLoader 已被移除，因为 ref_resolver 中的 SafeStringLoader 提供了更通用的解决方案

# 设置日志
logging.basicConfig(
    level=logging.INFO, # Default level, can be overridden by main.py
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' # Added %(name)s
)
logger = logging.getLogger(__name__)

def process_config_package(
    config_package_path: str,
    environment_name: str,
    service_name_to_extract: str, # Renamed for clarity
    main_config_file: str = "resources.yaml"
) -> Any:
    """
    主处理函数，集成配置生成与解析流程
    
    参数:
        config_package_path: 配置包根目录路径
        environment_name: 环境名称 (如 'perf')
        service_name_to_extract: 要提取和处理的服务名称
        main_config_file: 主配置文件名 (默认为 'resources.yaml')
    
    返回:
        一个字典，键是服务名称，值是该服务处理后的最终配置数据。
        例如: {"MyApplication": {...config...}}
    
    异常:
        可能抛出各子模块的异常
    """
    try:
        logger.info(f"开始处理配置包: {config_package_path} (环境: {environment_name}, 服务: {service_name_to_extract})")
        
        # 1. 构建路径
        global_config_dir = os.path.join(config_package_path, "value", "global")
        env_specific_config_dir = os.path.join(
            config_package_path, "value", "specs", environment_name
        )
        logger.debug(f"全局配置目录: {global_config_dir}")
        logger.debug(f"环境特定配置目录: {env_specific_config_dir}")
        
        # 2. 环境配置融合
        logger.info("开始环境配置融合...")
        merged_config_map = merge_env_configs(
            global_config_dir,
            env_specific_config_dir,
            environment_name 
        )
        logger.debug(f"融合后的文件映射: {merged_config_map}")
        logger.info("环境配置融合完成.")
        
        # 3. $ref 解析 (在整个已融合的配置结构上进行)
        logger.info(f"开始解析 $ref (主文件: {main_config_file})...")
        if main_config_file not in merged_config_map:
            raise ValueError(f"主文件 '{main_config_file}' 在融合后的配置映射中不存在。可用: {list(merged_config_map.keys())}")

        # `resolve_refs` loads `main_config_file` (using its relative path from merged_config_map)
        # and recursively resolves all $refs.
        # `current_config_base_path` is passed but its usage inside resolve_refs might need review
        # if merged_config_map keys (which are relative) are the primary source for path resolution.
        # The modified resolve_refs uses the `base_file_relative_path` (main_config_file here)
        # as the context for the first level of refs, and then the path of the referenced file for deeper refs.
        resolved_data_from_main_file = resolve_refs(
            base_file_relative_path=main_config_file, # e.g., "resources.yaml"
            merged_config_map=merged_config_map,
            current_config_base_path=config_package_path # Root path of the config package
        )
        logger.info("$ref 解析完成.")
        logger.debug(f"完整 $ref 解析后的数据 (来自 {main_config_file}): {resolved_data_from_main_file}")

        # 4. <<: 优先级合并 (在 $ref 解析后的数据上进行)
        logger.info("开始 <<: 优先级合并...")
        # `merge_yaml_with_merge_keys` expects `current_file_relative_path` to be the
        # relative path of the file whose content is being processed. For the initial call,
        # this is `main_config_file`.
        # The `ref_resolver_func` is set to None because $refs should have been fully resolved
        # in the previous step. The modified `merge_key_processor` assumes this.
        data_after_merge_keys = merge_yaml_with_merge_keys(
            data=resolved_data_from_main_file,
            merged_config_map=merged_config_map, # Still passed in case needed by a complex resolver
            current_file_relative_path=main_config_file, # Context for the data being processed
            ref_resolver_func=None # $refs should be resolved by now.
        )
        logger.info("<<: 优先级合并完成.")
        logger.debug(f"完整 <<: 合并后的数据: {data_after_merge_keys}")

        # 5. 提取特定服务
        if not isinstance(data_after_merge_keys, dict) or "services" not in data_after_merge_keys:
            raise ValueError(f"预期 '{main_config_file}' 解析后包含 'services' 列表，但未找到。数据: {data_after_merge_keys}")

        services_list = data_after_merge_keys.get("services")

        # Tentative fix: If services_list is a dict (like a single service) instead of a list of services, wrap it in a list.
        # This handles cases where the 'services' key might point to a single service definition (as a dict)
        # instead of a list of them, possibly due to how refs or merges resolved.
        if not isinstance(services_list, list) and isinstance(services_list, dict):
            logger.warning(
                f"警告: 'services' 键的值是一个字典，而不是预期的列表。 "
                f"假设它是一个单一服务条目，并将其包装在列表中。原始数据: {services_list}"
            )
            services_list = [services_list]
            
        if not isinstance(services_list, list):
            # If, after the potential fix, it's still not a list, then raise the original error.
            raise ValueError(f"'services' 键的值不是列表。实际类型: {type(services_list)}. 数据: {services_list}")

        target_service_config = None
        actual_service_name_key = None

        for service_entry in services_list:
            if isinstance(service_entry, dict) and "name" in service_entry:
                if service_entry["name"] == service_name_to_extract:
                    target_service_config = service_entry
                    actual_service_name_key = service_entry["name"] 
                    break
        
        if target_service_config is None:
            # The previous attempt to find by "- name:" has been removed as the YAML parsing
            # should now correctly produce a "name" key.
            raise ValueError(f"服务 '{service_name_to_extract}' 在 '{main_config_file}' 的 'services' 列表中未找到。可用服务名称: {[s.get('name') for s in services_list if isinstance(s, dict) and 'name' in s]}")


        logger.info(f"已找到服务 '{actual_service_name_key}' 的配置。准备占位符替换。")
        logger.debug(f"服务 '{actual_service_name_key}' 合并后配置 (替换前): {target_service_config}")
        
        # 6. 占位符替换 (仅在选定的服务配置块内，使用其 records 作为上下文)
        records_context = {}
        try:
            # Path to records: properties -> configs -> private -> records
            properties = target_service_config.get("properties", {})
            configs = properties.get("configs", {}) if isinstance(properties, dict) else {}
            private_config = configs.get("private", {}) if isinstance(configs, dict) else {}
            records_context = private_config.get("records", {}) if isinstance(private_config, dict) else {}
            
            if not isinstance(records_context, dict):
                logger.warning(f"服务 '{actual_service_name_key}' 的 records 部分不是字典或不存在，将使用空上下文进行占位符替换。 Records: {records_context}")
                records_context = {}
        except AttributeError: 
            logger.warning(f"服务 '{actual_service_name_key}' 的 records 路径不完整，将使用空上下文。")
            records_context = {}

        logger.debug(f"用于占位符替换的 Records 上下文: {records_context}")

        final_service_config = substitute_placeholders(
            data_to_process=target_service_config, 
            records_context=records_context
        )
        logger.info("占位符替换完成.")
        logger.debug(f"服务 '{actual_service_name_key}' 配置 (替换后): {final_service_config}")
        
        # 7. 构建最终输出: {"ServiceName": {config}}
        # This ensures the output JSON has the service name as the root key.
        output_result = {actual_service_name_key: final_service_config}
        
        logger.info("配置处理流程完成.")
        return output_result
        
    except Exception as e:
        logger.error(f"处理配置时发生错误: {str(e)}", exc_info=True) 
        raise

if __name__ == '__main__':
    # 测试调用
    import sys
    if len(sys.argv) < 4:
        print("Usage: python config_processor.py <config_package_path> <environment_name> <service_name>")
        sys.exit(1)
        
    # Example: python config_processor.py data/sample_config_package perf MyApplication
    try:
        # Ensure logger level is set for standalone testing if needed
        if len(sys.argv) > 4 and sys.argv[4].upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            logging.getLogger().setLevel(sys.argv[4].upper())
        
        result = process_config_package(sys.argv[1], sys.argv[2], sys.argv[3])
        print("\n处理成功，最终输出的Python字典:")
        # Using yaml.dump for better readability of complex structures, mimics JSON structure
        print(yaml.dump(result, allow_unicode=True, sort_keys=False, indent=2))
    except Exception as e:
        logger.error(f"处理失败: {str(e)}", exc_info=True)
        # No need to raise again, already logged.
        sys.exit(1) # Exit with error for script runners