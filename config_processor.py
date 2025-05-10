import os
import logging
import yaml
from typing import Any
from config_merger import merge_env_configs
from ref_resolver import resolve_refs
from merge_key_processor import merge_yaml_with_merge_keys
from placeholder_substitutor import substitute_placeholders

class PlaceholderSafeLoader(yaml.SafeLoader):
    """自定义YAML加载器，保持{{...}}占位符为字符串"""
    def construct_scalar(self, node):
        value = super().construct_scalar(node)
        if isinstance(value, str) and value.startswith('{{') and value.endswith('}}'):
            return value  # 保持原样
        return value

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_config_package(
    config_package_path: str,
    environment_name: str,
    service_name: str,
    main_config_file: str = "resources.yaml"
) -> Any:
    """
    主处理函数，集成配置生成与解析流程
    
    参数:
        config_package_path: 配置包根目录路径
        environment_name: 环境名称 (如 'perf')
        service_name: 服务名称
        main_config_file: 主配置文件名 (默认为 'resources.yaml')
    
    返回:
        处理后的最终配置数据
    
    异常:
        可能抛出各子模块的异常
    """
    try:
        logger.info(f"开始处理配置包: {config_package_path} (环境: {environment_name})")
        
        # 1. 构建路径
        global_config_dir = os.path.join(config_package_path, "value", "global")
        env_specific_config_dir = os.path.join(
            config_package_path, "value", "specs", environment_name
        )
        logger.info(f"全局配置目录: {global_config_dir}")
        logger.info(f"环境特定配置目录: {env_specific_config_dir}")
        
        # 2. 环境配置融合
        logger.info("开始环境配置融合...")
        merged_config_map = merge_env_configs(
            global_config_dir,
            env_specific_config_dir,
            environment_name
        )
        logger.info("环境配置融合完成")
        
        # 3. 加载主文件(不解析$ref)
        logger.info(f"加载主文件: {main_config_file}...")
        if main_config_file not in merged_config_map:
            raise ValueError(f"主文件不存在: {main_config_file}")
            
        main_file_abs = merged_config_map[main_config_file]
        with open(main_file_abs, 'r', encoding='utf-8') as f:
            content = f.read()
            # 预处理：只包裹值部分的占位符，保持YAML结构
            from yaml_simple_parser import simple_yaml_parse
            
            if main_file_abs.endswith(('.yaml', '.yml')):
                base_data = simple_yaml_parse(content)
            elif main_file_abs.endswith('.properties'):
                base_data = convert_properties_to_dict(f)
            else:
                raise ValueError(f"不支持的文件类型: {main_file_abs}")
        
        # 4. $ref 解析 (先解析所有引用)
        logger.info(f"开始解析 $ref (主文件: {main_config_file})...")
        resolved_data = resolve_refs(
            main_config_file,
            merged_config_map,
            config_package_path
        )
        logger.info("$ref 解析完成")
        
        # 5. <<: 优先级合并(处理已解析的$ref)
        logger.info("开始 <<: 优先级合并...")
        merged_data = merge_yaml_with_merge_keys(
            resolved_data,
            merged_config_map,
            config_package_path,
            lambda ref, _, __: {'$ref': ref}  # 返回未解析的$ref结构
        )
        logger.info("<<: 优先级合并完成")
        
        # 6. 占位符替换
        logger.info("开始占位符替换...")
        final_config = substitute_placeholders(
            resolved_data,  # 使用解析后的数据而不是合并后的数据
            service_name
        )
        logger.info("占位符替换完成")
        
        logger.info("配置处理流程完成")
        return final_config
        
    except Exception as e:
        logger.error(f"处理配置时发生错误: {str(e)}")
        raise

if __name__ == '__main__':
    # 测试调用
    import sys
    if len(sys.argv) < 4:
        print("Usage: python config_processor.py <config_package_path> <environment_name> <service_name>")
        sys.exit(1)
        
    try:
        result = process_config_package(sys.argv[1], sys.argv[2], sys.argv[3])
        print("处理成功，结果:")
        print(yaml.dump(result, allow_unicode=True, sort_keys=False))
    except Exception as e:
        logger.error(f"处理失败: {str(e)}")
        raise