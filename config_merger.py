import os
from pathlib import Path
from typing import Dict

def merge_env_configs(
    global_config_dir_path: str,
    env_specific_config_dir_path: str,
    selected_env: str  # selected_env 暂时未使用，但根据需求文档保留
) -> Dict[str, str]:
    """
    融合全局配置和特定环境的配置。

    文件级覆盖原则：如果在 env_specific_config_dir_path 目录中存在与
    global_config_dir_path 目录中相对路径和文件名均相同的文件，
    则特定环境 (spec) 的文件将完全覆盖全局 (global) 的文件。

    Args:
        global_config_dir_path: 指向全局配置目录的路径 (例如 "value/global/").
        env_specific_config_dir_path: 指向特定环境配置目录的路径 (例如 "value/specs/perf/").
        selected_env: 选定的环境名称 (例如 "perf").

    Returns:
        一个字典 (merged_config_map)，键是文件在逻辑 "current-config/" 目录下的
        相对路径 (例如, "resources.yaml", "config/xxx4.yaml")，
        值是该文件最终选定的源文件的绝对路径。

    Raises:
        FileNotFoundError: 如果 global_config_dir_path 或 env_specific_config_dir_path 不存在。
    """
    global_path = Path(global_config_dir_path).resolve()
    env_specific_path = Path(env_specific_config_dir_path).resolve()

    if not global_path.is_dir():
        raise FileNotFoundError(
            f"全局配置目录不存在: {global_config_dir_path} (解析为: {global_path})"
        )
    if not env_specific_path.is_dir():
        raise FileNotFoundError(
            f"特定环境配置目录不存在: {env_specific_config_dir_path} (解析为: {env_specific_path})"
        )

    merged_config_map: Dict[str, str] = {}

    # 1. 扫描全局配置目录
    for item in global_path.rglob('*'):
        if item.is_file():
            relative_path = item.relative_to(global_path)
            # 使用 POSIX 风格的路径作为键，以保证跨平台一致性
            merged_config_map[relative_path.as_posix()] = str(item.resolve())

    # 2. 扫描特定环境配置目录，并应用覆盖原则
    for item in env_specific_path.rglob('*'):
        if item.is_file():
            relative_path = item.relative_to(env_specific_path)
            # 使用 POSIX 风格的路径作为键
            merged_config_map[relative_path.as_posix()] = str(item.resolve())
            # 如果键已存在，新值会自动覆盖旧值，实现了覆盖逻辑

    return merged_config_map

if __name__ == '__main__':
    # 创建示例目录和文件结构 (用于测试)
    # 请确保在运行此脚本之前，当前工作目录下有 value/global 和 value/specs/perf 目录结构
    # 或者修改下面的 base_dir 来指向你的项目根目录

    # 获取当前脚本所在的目录作为基础目录
    script_dir = Path(__file__).parent.resolve()
    
    # 定义基础目录，相对于脚本位置
    # 如果你的 value 目录与 config_merger.py 在同一级，则 base_dir = script_dir
    # 如果 value 目录在 config_merger.py 的父目录的 value 子目录中，
    # 则 base_dir = script_dir.parent
    # 这里假设 value 目录与 config_merger.py 在同一级
    base_dir = script_dir 

    # 全局配置路径
    global_dir = base_dir / "value" / "global"
    # 特定环境配置路径 (perf)
    perf_dir = base_dir / "value" / "specs" / "perf"

    # 创建目录
    global_config_files_structure = {
        "resources.yaml": "global resources content",
        "config/xxx4.yaml": "global xxx4 content",
        "config/xxx7.yaml": "global xxx7 content",
        "config/xxx8.yaml": "global xxx8 content",
        "config/common.yaml": "global common content" # 新增一个 common.yaml 用于测试覆盖
    }
    
    perf_config_files_structure = {
        "values.yaml": "perf values content",
        "config/xxx3.yaml": "perf xxx3 content",
        "config/common.yaml": "perf common content specific to perf" # 覆盖全局的 common.yaml
    }

    def create_files(base_path: Path, structure: Dict[str, str]):
        for rel_path_str, content in structure.items():
            file_path = base_path / rel_path_str
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"创建文件: {file_path}")

    print(f"基础目录: {base_dir}")
    print(f"创建全局配置文件于: {global_dir}")
    create_files(global_dir, global_config_files_structure)
    
    print(f"创建 'perf' 环境配置文件于: {perf_dir}")
    create_files(perf_dir, perf_config_files_structure)

    print("\n示例目录和文件创建完毕。\n")

    try:
        print(f"调用 merge_env_configs:")
        print(f"  global_config_dir_path = '{global_dir}'")
        print(f"  env_specific_config_dir_path = '{perf_dir}'")
        print(f"  selected_env = 'perf'")
        
        merged_configs = merge_env_configs(
            str(global_dir),
            str(perf_dir),
            "perf"
        )
        
        print("\n融合后的配置 (merged_config_map):")
        for rel_path, abs_path in merged_configs.items():
            print(f'  "{rel_path}": "{abs_path}"')

        # 验证示例
        # 预期结果 (绝对路径会因环境而异)
        # {
        #     "resources.yaml": ".../value/global/resources.yaml",
        #     "config/xxx4.yaml": ".../value/global/config/xxx4.yaml",
        #     "config/xxx7.yaml": ".../value/global/config/xxx7.yaml",
        #     "config/xxx8.yaml": ".../value/global/config/xxx8.yaml",
        #     "config/common.yaml": ".../value/specs/perf/config/common.yaml", (被 perf 覆盖)
        #     "values.yaml": ".../value/specs/perf/values.yaml",
        #     "config/xxx3.yaml": ".../value/specs/perf/config/xxx3.yaml"
        # }

        # 检查 common.yaml 是否被正确覆盖
        expected_common_path_suffix = Path("value") / "specs" / "perf" / "config" / "common.yaml"
        if "config/common.yaml" in merged_configs:
            actual_common_path = Path(merged_configs["config/common.yaml"])
            if actual_common_path.name == expected_common_path_suffix.name and \
               actual_common_path.parent.name == expected_common_path_suffix.parent.name and \
               actual_common_path.parent.parent.name == expected_common_path_suffix.parent.parent.name and \
               actual_common_path.parent.parent.parent.name == expected_common_path_suffix.parent.parent.parent.name:
                print("\n[验证通过] config/common.yaml 正确地从 'perf' 环境加载。")
            else:
                print(f"\n[验证失败] config/common.yaml 未被正确覆盖。实际路径: {actual_common_path}, 期望后缀: .../{expected_common_path_suffix}")
        else:
            print("\n[验证失败] merged_configs 中未找到 config/common.yaml。")


    except FileNotFoundError as e:
        print(f"\n错误: {e}")
    except Exception as e:
        print(f"\n发生意外错误: {e}")

    # 测试目录不存在的情况
    print("\n测试目录不存在的情况:")
    try:
        merge_env_configs(
            str(base_dir / "non_existent_global"),
            str(perf_dir),
            "perf"
        )
    except FileNotFoundError as e:
        print(f"  成功捕获错误: {e}")

    try:
        merge_env_configs(
            str(global_dir),
            str(base_dir / "value" / "specs" / "non_existent_env"),
            "non_existent_env"
        )
    except FileNotFoundError as e:
        print(f"  成功捕获错误: {e}")