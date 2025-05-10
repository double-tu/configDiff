#!/usr/bin/env python3
import argparse
import json
import logging
import sys
import os # 新增
import yaml # 新增
from config_processor import process_config_package
from properties_parser import convert_properties_to_dict # 新增
from placeholder_substitutor import substitute_placeholders, PlaceholderContextNotFoundError, PlaceholderNotFoundError # 新增
from ref_resolver import preprocess_yaml_content # 新增 (用于加载 tmpl/*.yaml)

def configure_logging(log_level):
    """Configure logging based on command line argument"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def write_output(result, output_file=None, indent=None):
    """Write result to file or stdout with optional indentation"""
    if output_file:
        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=indent)
        logging.info(f"Output written to {output_file}")
    else:
        json.dump(result, sys.stdout, indent=indent)
        print()  # Add newline after JSON output

# 新增函数：处理模板文件
def process_template_files(tmpl_input_dir, tmpl_output_dir, records_context, service_name):
    """
    Processes template files from tmpl_input_dir, substitutes placeholders using records_context,
    and writes them to tmpl_output_dir.
    """
    if not os.path.isdir(tmpl_input_dir):
        logging.warning(f"Template input directory not found: {tmpl_input_dir}")
        return

    if not os.path.exists(tmpl_output_dir):
        os.makedirs(tmpl_output_dir)
        logging.info(f"Created template output directory: {tmpl_output_dir}")

    logging.info(f"Processing template files from '{tmpl_input_dir}' for service '{service_name}'")

    for root, _, files in os.walk(tmpl_input_dir):
        for filename in files:
            input_filepath = os.path.join(root, filename)
            # Construct relative path from tmpl_input_dir to maintain structure in output
            relative_path = os.path.relpath(input_filepath, tmpl_input_dir)
            output_filepath = os.path.join(tmpl_output_dir, relative_path)
            
            # Ensure subdirectory structure exists in output
            output_file_dir = os.path.dirname(output_filepath)
            if not os.path.exists(output_file_dir):
                os.makedirs(output_file_dir)

            try:
                with open(input_filepath, 'r', encoding='utf-8') as f_in:
                    content = f_in.read()
                
                logging.debug(f"Processing template file: {input_filepath}")

                # Updated file type detection logic
                if '.properties' in filename:
                    # Convert .properties to dict
                    data_to_substitute = convert_properties_to_dict(content)
                    # Substitute placeholders
                    substituted_data = substitute_placeholders(data_to_substitute, records_context)
                    # Output filename: original_filename.yaml
                    # Example: tmpl.xxx1.properties -> output_tmpl/tmpl.xxx1.properties.yaml
                    # Example: xxx3.properties.tmpl -> output_tmpl/xxx3.properties.tmpl.yaml
                    # The relative_path already includes the original filename.
                    # We just need to ensure the output_filepath in the tmpl_output_dir has .yaml appended.
                    # If output_filepath already ends with .yaml (e.g. if original was .properties.yaml), this is fine.
                    # However, the instruction is to *append* .yaml to the *original* filename.
                    # The current output_filepath is os.path.join(tmpl_output_dir, relative_path)
                    # So, if relative_path is "tmpl.xxx1.properties", output_filepath becomes "output_tmpl/tmpl.xxx1.properties"
                    # We need to append ".yaml" to this.
                    
                    # Construct the correct output filename by appending .yaml to the original filename (which is `relative_path`)
                    # and placing it in the tmpl_output_dir.
                    # The `output_filepath` is already `os.path.join(tmpl_output_dir, relative_path)`.
                    # So we just append `.yaml` to `output_filepath`.
                    final_output_filepath = output_filepath + '.yaml'
                    
                    # Ensure subdirectory structure exists for the new final_output_filepath
                    final_output_file_dir = os.path.dirname(final_output_filepath)
                    if not os.path.exists(final_output_file_dir):
                        os.makedirs(final_output_file_dir)

                    with open(final_output_filepath, 'w', encoding='utf-8') as f_out:
                        yaml.dump(substituted_data, f_out, allow_unicode=True, sort_keys=False)
                    logging.info(f"Processed properties file {filename} and wrote to {final_output_filepath}")

                elif '.yaml' in filename and '.properties' not in filename: # Process as YAML if not already handled as properties
                    # Preprocess for {{placeholders}} that are not quoted
                    preprocessed_content = preprocess_yaml_content(content)
                    # Load YAML
                    data_to_substitute = yaml.load(preprocessed_content, Loader=yaml.SafeLoader)
                    # Substitute placeholders
                    substituted_data = substitute_placeholders(data_to_substitute, records_context)
                    # Output filename remains the same (including .tmpl if present)
                    # The `output_filepath` is already correctly set as os.path.join(tmpl_output_dir, relative_path)
                    with open(output_filepath, 'w', encoding='utf-8') as f_out:
                        yaml.dump(substituted_data, f_out, allow_unicode=True, sort_keys=False)
                    logging.info(f"Processed YAML file {filename} and wrote to {output_filepath}")
                
                else:
                    logging.debug(f"Skipping file (does not contain .properties or .yaml, or was already handled): {filename}")

            except PlaceholderNotFoundError as e:
                logging.error(f"Error processing template file {input_filepath}: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred while processing template file {input_filepath}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Configuration Package Processor'
    )
    
    # Required arguments
    parser.add_argument(
        'package_path1',
        help='Path to first configuration package'
    )
    parser.add_argument(
        'package_path2',
        nargs='?',
        help='Path to second configuration package (optional)'
    )
    parser.add_argument(
        '-e', '--environment',
        required=True,
        help='Environment name (e.g. "perf")'
    )
    parser.add_argument(
        '-s', '--service',
        required=True,
        help='Service name (e.g. "MyApplication")'
    )
    
    # Optional arguments
    parser.add_argument(
        '--main-config',
        default='resources.yaml',
        help='Main configuration filename (default: resources.yaml)'
    )
    parser.add_argument(
        '--output-file1',
        help='Output file path for first package result'
    )
    parser.add_argument(
        '--output-file2',
        help='Output file path for second package result'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    # 新增参数 for tmpl processing
    parser.add_argument(
        '--tmpl-input-dir',
        help='Input directory for template files (e.g., data/sample_config_package/tmpl/)'
    )
    parser.add_argument(
        '--tmpl-output-dir',
        default='output_tmpl',
        help='Output directory for processed template files (default: output_tmpl/)'
    )
    
    args = parser.parse_args()
    
    try:
        # Configure logging
        configure_logging(args.log_level)
        
        # Process first package
        logging.info(f"Processing first package: {args.package_path1}")
        result1 = process_config_package(
            args.package_path1,
            args.environment,
            args.service,
            args.main_config
        )
        
        # Output first result
        if args.package_path2:
            write_output(result1, args.output_file1, indent=None)
        else:
            # If only one package, output with indent=2 by default if output_file1 is specified
            # or to stdout if output_file1 is not specified.
            # The task implies result_perf_myapplication.json is generated, so output_file1 will be used.
            write_output(result1, args.output_file1, indent=2)
        
        # Process second package if provided
        if args.package_path2:
            logging.info(f"Processing second package: {args.package_path2}")
            result2 = process_config_package(
                args.package_path2,
                args.environment,
                args.service,
                args.main_config
            )
            write_output(result2, args.output_file2, indent=2)

        # --- 新增: 处理模板文件 ---
        if args.tmpl_input_dir:
            records_context = None
            # 提取 records_context
            # 假设 result1 包含我们需要的服务配置
            if result1 and args.service in result1:
                service_config = result1[args.service]
                # 根据 result_perf_myapplication.json 的结构
                # MyApplication.properties.configs.private.records
                try:
                    records_context = service_config['properties']['configs']['private']['records']
                except KeyError:
                    logging.warning(
                        f"Could not find 'properties.configs.private.records' for service '{args.service}' in the processed config. Skipping template processing."
                    )
                
                if records_context is not None:
                    process_template_files(
                        args.tmpl_input_dir,
                        args.tmpl_output_dir,
                        records_context,
                        args.service
                    )
            else:
                logging.warning(
                    f"Service '{args.service}' not found in the first package result. Skipping template processing."
                )
        else:
            logging.info("No template input directory provided (--tmpl-input-dir). Skipping template processing.")
            
    except PlaceholderContextNotFoundError as e: # Specific exception from placeholder_substitutor
        logging.error(f"Placeholder context error: {str(e)}")
        sys.exit(1)
    except PlaceholderNotFoundError as e: # Specific exception from placeholder_substitutor
        logging.error(f"Placeholder not found error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error processing configuration packages or templates: {str(e)}", exc_info=True) # Add exc_info for more details
        sys.exit(1)

if __name__ == '__main__':
    main()